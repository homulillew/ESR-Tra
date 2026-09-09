"""Thin Anthropic adapter with durable global reservations and raw provider receipts."""
from dataclasses import dataclass, asdict
import json
import sqlite3
import time
import uuid

from .protocol import HarnessError, canonical


class GlobalBudget:
    """One writer, all remote purposes. Outstanding requests remain conservatively charged."""
    def __init__(self, path, *, input_limit=30000000, output_limit=6000000, episode_limit=240, probe_limit=12):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS limits (singleton INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, purpose TEXT, input_reserved INTEGER,
              output_reserved INTEGER, input_charged INTEGER, output_charged INTEGER, settled INTEGER, usage TEXT);
            CREATE TABLE IF NOT EXISTS episodes (id TEXT PRIMARY KEY, category TEXT NOT NULL, status TEXT NOT NULL);
        """)
        self.limits = dict(input_limit=input_limit, output_limit=output_limit, episode_limit=episode_limit, probe_limit=probe_limit)
        current = self.db.execute("SELECT payload FROM limits").fetchone()
        if current and json.loads(current[0]) != self.limits:
            raise ValueError("Global limits cannot change on resume")
        if not current:
            self.db.execute("INSERT INTO limits VALUES(1,?)", (canonical(self.limits),))
            self.db.commit()

    def episode(self, episode_id, category):
        with self.db:
            n = self.db.execute("SELECT count(*) FROM episodes").fetchone()[0]
            cap = self.limits["episode_limit"] - (54 if category != "confirmation" else 0)
            if n >= cap:
                raise HarnessError("generation_budget_exhausted", "Global episode cap / confirmation reservation reached")
            self.db.execute("INSERT INTO episodes VALUES(?,?,?)", (episode_id, category, "started"))

    def reserve(self, purpose, input_tokens, output_tokens):
        with self.db:
            used_in, used_out = self.db.execute("SELECT coalesce(sum(input_charged),0), coalesce(sum(output_charged),0) FROM requests").fetchone()
            if used_in + input_tokens > self.limits["input_limit"] or used_out + output_tokens > self.limits["output_limit"]:
                raise HarnessError("generation_budget_exhausted", "Global input/output reservation limit reached")
            if purpose == "probe" and self.db.execute("SELECT count(*) FROM requests WHERE purpose='probe'").fetchone()[0] >= self.limits["probe_limit"]:
                raise HarnessError("generation_budget_exhausted", "Connectivity request limit reached")
            rid = uuid.uuid4().hex
            self.db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,0,NULL)", (rid, purpose, input_tokens, output_tokens, input_tokens, output_tokens))
        return rid

    def settle(self, rid, usage):
        if usage is None:
            return
        with self.db:
            changed = self.db.execute("UPDATE requests SET input_charged=?,output_charged=?,settled=1,usage=? WHERE id=? AND settled=0",
                                     (usage["prompt_tokens"], usage["completion_tokens"], canonical(usage), rid)).rowcount
            if changed != 1:
                raise ValueError("Unknown or already settled request")

    def summary(self):
        rows = self.db.execute("SELECT purpose,count(*),sum(input_charged),sum(output_charged),sum(1-settled) FROM requests GROUP BY purpose").fetchall()
        return {"limits": self.limits, "purposes": [{"purpose": p, "requests": n, "charged_input_tokens": i,
                 "charged_output_tokens": o, "unknown_or_outstanding_requests": u} for p,n,i,o,u in rows]}


def measured_usage(response):
    raw = response.get("usage", {})
    if not isinstance(raw, dict):
        return None
    fields = [raw.get("input_tokens"), raw.get("output_tokens")]
    if not all(type(x) is int and x >= 0 for x in fields):
        return None
    cache = {k: raw.get(k, 0) for k in ("cache_read_input_tokens", "cache_creation_input_tokens")}
    if not all(type(v) is int and v >= 0 for v in cache.values()):
        return None
    detail = ((raw.get("billing_usage") or {}).get("openai_usage") or {}).get("completion_tokens_details") or {}
    return {"prompt_tokens": fields[0] + sum(cache.values()), "completion_tokens": fields[1],
            "uncached_input_tokens": fields[0], **cache, "reasoning_tokens": detail.get("reasoning_tokens"), "provider_usage": raw}


@dataclass(frozen=True)
class RemoteConfig:
    model: str = "EB-GLM-5.2"
    max_output_tokens: int = 4096
    context_operating_cap: int = 65536
    temperature: float = 0.6
    timeout: float = 60
    transport_attempts: int = 2


class AnthropicClient:
    def __init__(self, transport, budget, ledger, global_budget, *, config=None, deadline=None):
        self.transport, self.budget, self.ledger, self.global_budget = transport, budget, ledger, global_budget
        self.config = config or RemoteConfig()
        self.deadline = deadline
        self.identity = {"protocol": "anthropic_messages", "config": asdict(self.config),
                         "context_estimate": "UTF-8 bytes of mapped JSON + 1024 overhead; conservative, not verified tokenizer",
                         "thinking": "omitted; provider default unverified", "model_revision": "gateway_alias_unpinned",
                         "url": transport.base_url + "/v1/messages", "parser": "one_final_text_json_v1"}

    def body(self, messages, max_tokens):
        systems, turns = [], []
        for message in messages:
            if message["role"] == "system":
                systems.append(message["content"])
            elif message["role"] in {"user", "assistant"}:
                # Merge adjacent roles explicitly. Exact mapped body is recorded before network I/O.
                if turns and turns[-1]["role"] == message["role"]:
                    turns[-1]["content"] += "\n\n" + message["content"]
                else:
                    turns.append(dict(message))
            else:
                raise HarnessError("protocol_error", "Unsupported message role")
        result = {"model": self.config.model, "max_tokens": max_tokens, "temperature": self.config.temperature, "messages": turns}
        if systems:
            result["system"] = "\n\n".join(systems)
        return result

    @staticmethod
    def input_reservation(body):
        return len(canonical(body).encode("utf-8")) + 1024

    def fits(self, messages):
        maximum = min(self.config.max_output_tokens, self.budget.remaining)
        return self.input_reservation(self.body(messages, maximum)) + maximum <= self.config.context_operating_cap

    def complete(self, messages, purpose="policy"):
        reserve_finish = 512 if purpose == "audit" else 0
        maximum = min(self.config.max_output_tokens, self.budget.remaining - reserve_finish)
        if maximum <= 0:
            raise HarnessError("generation_budget_exhausted", "Combined output budget exhausted or reserved for final policy")
        if not self.fits(messages):
            raise HarnessError("context_overflow", "Conservative provider capacity exceeded")
        body = self.body(messages, maximum)
        input_reserved = self.input_reservation(body)
        for attempt in range(self.config.transport_attempts):
            left = self.deadline - time.monotonic() if self.deadline else self.config.timeout
            if left <= 0:
                raise HarnessError("service_error", "episode_wall_timeout")
            if self.budget.remaining < maximum + reserve_finish:
                raise HarnessError("generation_budget_exhausted", "Unknown-cost retry cannot fit remaining budget")
            rid = self.global_budget.reserve(purpose, input_reserved, maximum)
            self.ledger.append({"type": "generation_request", "request_id": rid, "purpose": purpose,
                                "request": body, "reserved_completion_tokens": maximum,
                                "reserved_input_tokens": input_reserved, "transport_attempt": attempt + 1,
                                "url": self.identity["url"]})
            self.budget.charged_tokens += maximum
            started = time.monotonic()
            try:
                response, receipt = self.transport.request(body, timeout=min(self.config.timeout, left))
            except Exception as exc:
                # Only safe classification, never stringify an exception containing authentication.
                http_status = getattr(getattr(exc, "response", None), "status_code", None)
                kind = "authentication_error" if http_status in {401,403} else "rate_limit" if http_status == 429 else "transport_error"
                self.ledger.append({"type": "generation", "request_id": rid, "purpose": purpose,
                                    "error_code": kind, "http_status": http_status, "exception_type": type(exc).__name__,
                                    "usage": None, "reserved_completion_tokens": maximum,
                                    "elapsed_seconds": time.monotonic()-started})
                self.budget.unknown_usage_requests += 1
                retryable = http_status in {429,500,502,503,504} or type(exc).__name__ in {"ConnectTimeout","ReadTimeout","ConnectError"}
                if retryable and attempt + 1 < self.config.transport_attempts:
                    time.sleep(0.25)
                    continue
                raise HarnessError("service_error", f"{kind}; HTTP {http_status}; {type(exc).__name__}") from None
            usage = measured_usage(response) if isinstance(response, dict) else None
            # Durable global settlement first; the episode receipt keeps the complete raw response.
            self.global_budget.settle(rid, usage)
            self.ledger.append({"type": "generation", "request_id": rid, "purpose": purpose,
                                "response": response, "receipt": receipt, "usage": usage,
                                "reserved_completion_tokens": maximum, "elapsed_seconds": time.monotonic()-started})
            self.budget.charged_tokens -= maximum
            self.budget.add(usage, maximum)
            if usage is None:
                raise HarnessError("service_error", "Unknown provider usage; full reservation retained")
            if usage["completion_tokens"] > maximum or usage["prompt_tokens"] > input_reserved:
                raise HarnessError("generation_budget_exhausted", "Provider exceeded reservation; stop to revise capacity assumptions")
            if response.get("stop_reason") == "max_tokens":
                raise HarnessError("output_truncated", "Provider stop_reason=max_tokens; no partial action executed")
            if response.get("stop_reason") != "end_turn":
                raise HarnessError("protocol_error", "Unexpected provider stop_reason=" + str(response.get("stop_reason")))
            blocks = response.get("content", [])
            texts = [b["text"] for b in blocks if b.get("type") == "text" and isinstance(b.get("text"), str)]
            if len(texts) != 1 or any(b.get("type") not in {"text","thinking","redacted_thinking"} for b in blocks):
                raise HarnessError("protocol_error", "Expected exactly one final text block; raw content retained")
            return texts[0]
        raise AssertionError("unreachable")
