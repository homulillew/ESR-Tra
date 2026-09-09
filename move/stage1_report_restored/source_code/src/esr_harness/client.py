"""OpenAI-compatible inference client with explicit context/usage accounting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import time
from typing import Callable

from .ledger import Ledger
from .protocol import HarnessError
from .views import post_json


class HFTokenCounter:
    """Use the exact served chat template/tokenizer; never estimate via char ratios."""
    def __init__(self, path: str, revision: str | None = None):
        try:
            import transformers
        except ImportError as exc:
            raise RuntimeError("Live inference needs transformers: pip install -e '.[model]'") from exc
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(path, revision=revision, trust_remote_code=False)
        self.identity = {"path": path, "revision": revision, "transformers": transformers.__version__}

    def __call__(self, messages: list[dict], thinking: bool) -> int:
        tokens = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                    enable_thinking=thinking)
        return len(tokens)


@dataclass(frozen=True)
class ChatConfig:
    base_url: str
    model: str
    model_revision: str = "unspecified"
    max_context_tokens: int = 32768
    max_output_tokens: int = 2048
    temperature: float = 0.6
    thinking: bool = True
    timeout: float = 120.0
    api_key_env: str = "ESR_API_KEY"
    transport_attempts: int = 2

    def __post_init__(self):
        if not self.model or self.max_output_tokens < 1 or self.max_context_tokens <= self.max_output_tokens:
            raise ValueError("Invalid model/context/output limits")
        if self.transport_attempts not in {1, 2, 3} or self.timeout <= 0:
            raise ValueError("Invalid transport retry/timeout configuration")
        if not 0 <= self.temperature <= 2:
            raise ValueError("Invalid temperature")


class UsageBudget:
    """Measured usage plus conservative reservations for requests with unknown cost."""
    def __init__(self, max_completion_tokens=24000, events=None):
        if type(max_completion_tokens) is not int or max_completion_tokens < 1:
            raise ValueError("Generation budget must be positive")
        self.limit = max_completion_tokens
        self.prompt_tokens = self.completion_tokens = self.charged_tokens = 0
        self.unknown_usage_requests = 0
        outstanding = {}
        for event in events or []:
            if event.get("type") == "generation_request":
                outstanding[event["request_id"]] = event["reserved_completion_tokens"]
            elif event.get("type") == "generation":
                amount = outstanding.pop(event.get("request_id"), event.get("reserved_completion_tokens", 0))
                self.add(event.get("usage"), amount)
        for amount in outstanding.values():
            self.add(None, amount)  # Crash/timeout is not a free unrecorded request.

    @property
    def remaining(self):
        return max(0, self.limit - self.charged_tokens)

    def add(self, usage, reserved=0):
        if usage is None:
            self.unknown_usage_requests += 1
            self.charged_tokens += reserved
        else:
            self.prompt_tokens += usage["prompt_tokens"]
            self.completion_tokens += usage["completion_tokens"]
            self.charged_tokens += usage["completion_tokens"]

    def summary(self):
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "completion_budget": self.limit, "charged_completion_tokens": self.charged_tokens,
                "remaining_completion_tokens": self.remaining,
                "unknown_usage_requests": self.unknown_usage_requests,
                "usage_complete": self.unknown_usage_requests == 0}


class ChatClient:
    def __init__(self, config, counter, budget, ledger, transport=post_json, finalization_reserve=128):
        if finalization_reserve < 0:
            raise ValueError("Negative finalization reserve")
        self.config, self.counter, self.budget, self.ledger, self.transport = config, counter, budget, ledger, transport
        self.finalization_reserve = finalization_reserve
        self.identity = {"chat": asdict(config), "tokenizer": getattr(counter, "identity", {"type": type(counter).__name__}),
                         "finalization_reserve": finalization_reserve}

    def fits(self, messages):
        reserve = min(self.config.max_output_tokens, self.budget.remaining)
        return self.counter(messages, self.config.thinking) + reserve <= self.config.max_context_tokens

    def complete(self, messages, purpose="policy"):
        from .protocol import digest
        if self.budget.remaining <= 0:
            raise HarnessError("generation_budget_exhausted", "Combined policy+audit budget exhausted")
        available = self.budget.remaining - (self.finalization_reserve if purpose == "audit" else 0)
        if available <= 0:
            raise HarnessError("audit_budget_reserved", "Remaining tokens reserved for policy finalization; no audit was called")
        if not self.fits(messages):
            raise HarnessError("context_overflow", "Required context does not fit; no evidence was silently truncated")
        body = {"model": self.config.model, "messages": messages,
                "max_tokens": min(self.config.max_output_tokens, available), "temperature": self.config.temperature,
                "chat_template_kwargs": {"enable_thinking": self.config.thinking}}
        headers = {}
        if os.getenv(self.config.api_key_env):
            headers["Authorization"] = "Bearer " + os.environ[self.config.api_key_env]
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        for attempt in range(self.config.transport_attempts):
            if self.budget.remaining < body["max_tokens"] + (self.finalization_reserve if purpose == "audit" else 0):
                code = "audit_budget_reserved" if purpose == "audit" else "generation_budget_exhausted"
                raise HarnessError(code, "Cannot safely retry an unknown-cost request with identical parameters")
            started = time.monotonic()
            rid = digest([self.ledger.header, len(self.ledger.events()), purpose, body])
            reserved = body["max_tokens"]
            self.ledger.append({"type": "generation_request", "request_id": rid, "purpose": purpose,
                                "request": body, "reserved_completion_tokens": reserved})
            # Reserve before transport. If a later disk write fails, the reservation remains.
            self.budget.charged_tokens += reserved
            try:
                response = self.transport(url, body, timeout=self.config.timeout, headers=headers)
            except HarnessError as exc:
                self.ledger.append({"type": "generation", "request_id": rid, "purpose": purpose,
                                    "error_code": exc.code, "error": str(exc), "usage": None,
                                    "reserved_completion_tokens": reserved,
                                    "elapsed_seconds": time.monotonic() - started})
                self.budget.unknown_usage_requests += 1
                retryable = str(exc).startswith(("HTTP 5", "Request failed:"))
                if not retryable or attempt + 1 == self.config.transport_attempts:
                    raise
                time.sleep(0.25 * (attempt + 1))
                continue
            usage = response.get("usage") if isinstance(response, dict) else None
            valid = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                                    for k in ("prompt_tokens", "completion_tokens"))
            measured = {k: usage[k] for k in ("prompt_tokens", "completion_tokens")} if valid else None
            self.ledger.append({"type": "generation", "request_id": rid, "purpose": purpose,
                                "response": response, "usage": measured, "reserved_completion_tokens": reserved,
                                "elapsed_seconds": time.monotonic() - started})
            self.budget.charged_tokens -= reserved
            self.budget.add(measured, reserved)
            if measured is None:
                raise HarnessError("service_error", "Token usage unknown; requested maximum charged conservatively")
            if measured["completion_tokens"] > body["max_tokens"]:
                raise HarnessError("generation_budget_exhausted", "Provider exceeded requested output limit")
            try:
                choice = response["choices"][0]
                text = choice["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise HarnessError("service_error", "Malformed chat completion response") from exc
            if choice.get("finish_reason") not in {None, "stop"}:
                raise HarnessError("protocol_error", "Incomplete JSON response: finish_reason=" + str(choice.get("finish_reason")))
            if not isinstance(text, str):
                raise HarnessError("protocol_error", "Expected textual JSON, not a missing content field")
            return text
        raise AssertionError("unreachable")
