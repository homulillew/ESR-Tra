"""Explicit-network providers. Native IDs, raw responses, no retries or text extraction.

Adapters implement prepare -> send -> parse. The engine persists the exact prepared
wire request before send. HTTP errors never echo response bodies/authentication.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any, Protocol
import urllib.error
import urllib.parse
import urllib.request

from .contract import ContractError, canonical, digest, loads


@dataclass(frozen=True)
class Reply:
    message: dict
    usage: dict
    response_model: str | None


class Model(Protocol):
    identity: dict
    def prepare(self, messages: list[dict], tools: list[dict], output_limit: int) -> dict: ...
    def send(self, wire: dict) -> dict: ...
    def parse(self, raw: dict) -> Reply: ...


class Retriever(Protocol):
    identity: dict
    def search(self, query: str, top_k: int) -> list[dict]: ...
    def get_document(self, docid: str) -> dict: ...


def endpoint(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid endpoint") from exc
    if (p.scheme not in ("http", "https") or not p.hostname or p.username or p.password
            or p.query or p.fragment or any(ord(c) < 33 for c in url)):
        raise ValueError("Endpoint must be http(s), with a hostname and no credentials/query/fragment")
    if port is not None and not 0 < port <= 65535:
        raise ValueError("Invalid endpoint port")
    return url.rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ContractError("redirect_refused", "HTTP redirects are not followed", fatal=True)


class HTTP:
    def __init__(self, *, allow_network: bool = False, timeout: int = 45, opener=None):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.allow_network, self.timeout = allow_network, timeout
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def post(self, url: str, body: dict, headers: dict | None = None) -> dict:
        if not self.allow_network:
            raise ContractError("network_not_authorized", "Explicit --allow-network is required", fatal=True)
        endpoint(url)
        request = urllib.request.Request(url, data=canonical(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ContractError("response_size", "HTTP response exceeds 8 MB", fatal=True)
            value = loads(data.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ContractError("http_error", f"HTTP {exc.code}; no automatic retry", fatal=True) from exc
        except (urllib.error.URLError, OSError, TimeoutError, UnicodeError) as exc:
            raise ContractError("transport_error", f"Transport failed: {type(exc).__name__}", fatal=True) from exc
        if not isinstance(value, dict):
            raise ContractError("response_envelope", "Expected a JSON object", fatal=True)
        return value


def usage_of(raw: Any, provider: str) -> dict:
    u = raw.get("usage", {}) if isinstance(raw, dict) else {}
    if not isinstance(u, dict):
        u = {}
    result = {}
    mapping = ({"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"}
               if provider == "openai" else {"input_tokens": "input_tokens", "output_tokens": "output_tokens",
               "cache_read_tokens": "cache_read_input_tokens", "cache_write_tokens": "cache_creation_input_tokens"})
    for target, source in mapping.items():
        if type(u.get(source)) is int and u[source] >= 0:
            result[target] = u[source]
    if provider == "openai":
        details = u.get("prompt_tokens_details", {})
        if isinstance(details, dict) and type(details.get("cached_tokens")) is int and details["cached_tokens"] >= 0:
            result["cache_read_tokens"] = details["cached_tokens"]
    # Anthropic input_tokens excludes cache read/write; reports keep these components separate.
    return result


def check_calls(message: dict) -> dict:
    calls = message.get("tool_calls", [])
    if not isinstance(calls, list):
        raise ContractError("policy_protocol", "tool_calls must be an array")
    ids = set()
    for call in calls:
        if not isinstance(call, dict):
            raise ContractError("policy_protocol", "Tool call must be an object")
        cid, f = call.get("id"), call.get("function")
        if (not isinstance(cid, str) or not cid or len(cid) > 200 or cid in ids or call.get("type") != "function"
                or not isinstance(f, dict) or not isinstance(f.get("name"), str) or len(f["name"]) > 100 or not isinstance(f.get("arguments"), str)):
            raise ContractError("policy_protocol", "Native tool calls require unique IDs and string JSON arguments")
        ids.add(cid)
    return deepcopy(message)


class OpenAIModel:
    provider = "openai"
    def __init__(self, base_url: str, model: str, *, revision: str, http: HTTP, api_key: str | None = None,
                 temperature: float = 0.2, expected_response_model: str | None = None,
                 output_parameter: str = "max_tokens"):
        if not model or not revision or output_parameter not in ("max_tokens", "max_completion_tokens"):
            raise ValueError("A model, revision label and supported output parameter are required")
        if self.provider == "anthropic" and output_parameter != "max_tokens":
            raise ValueError("Anthropic Messages uses max_tokens")
        self.base_url, self.model, self.http, self.key = endpoint(base_url), model, http, api_key
        self.temperature, self.expected = temperature, expected_response_model
        self.output_parameter = output_parameter
        self.identity = {"kind": self.provider, "endpoint": self.base_url, "model": model, "revision_label": revision,
                         "temperature": temperature, "expected_response_model": self.expected,
                         "output_parameter": output_parameter}

    def prepare(self, messages, tools, output_limit):
        clean = [{k: deepcopy(v) for k, v in m.items() if not k.startswith("_")} for m in messages]
        return {"model": self.model, "messages": clean, "tools": deepcopy(tools), "tool_choice": "auto",
                self.output_parameter: output_limit, "temperature": self.temperature}

    def send(self, wire):
        return self.http.post(self.base_url + "/chat/completions", wire,
                              {"Authorization": "Bearer " + self.key} if self.key else {})

    def parse(self, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("choices"), list) or len(raw["choices"]) != 1:
            raise ContractError("response_envelope", "Expected exactly one completion choice", fatal=True)
        choice = raw["choices"][0]
        if not isinstance(choice, dict) or choice.get("finish_reason") not in ("tool_calls", "stop"):
            raise ContractError("incomplete_response", "Truncated/filtered/incomplete output is not executed", fatal=True)
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ContractError("response_envelope", "Expected assistant message", fatal=True)
        if message.get("content") is not None and not isinstance(message["content"], str):
            raise ContractError("response_envelope", "This adapter supports text-only assistant content", fatal=True)
        if self.expected is not None and raw.get("model") != self.expected:
            raise ContractError("model_identity_changed", "Unexpected returned model; stop the run", fatal=True)
        out = {k: deepcopy(message[k]) for k in ("role", "content", "tool_calls", "reasoning_content") if k in message}
        return Reply(check_calls(out), usage_of(raw, "openai"), raw.get("model"))


class AnthropicModel(OpenAIModel):
    provider = "anthropic"
    def prepare(self, messages, tools, output_limit):
        system, out = [], []
        for m in messages:
            if m["role"] == "system":
                system.append(m["content"])
                continue
            if m["role"] == "assistant":
                if "_anthropic_blocks" in m:
                    blocks = deepcopy(m["_anthropic_blocks"])
                else:
                    blocks = ([{"type": "text", "text": m["content"]}] if m.get("content") else [])
                    blocks += [{"type": "tool_use", "id": c["id"], "name": c["function"]["name"],
                                "input": loads(c["function"]["arguments"])} for c in m.get("tool_calls", [])]
                role = "assistant"
            elif m["role"] == "tool":
                role, blocks = "user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"],
                                        "content": m["content"], "is_error": bool(m.get("_error", False))}]
            else:
                role, blocks = "user", [{"type": "text", "text": m["content"]}]
            if out and out[-1]["role"] == role:
                out[-1]["content"].extend(blocks)
            else:
                out.append({"role": role, "content": blocks})
        return {"model": self.model, "system": "\n".join(system), "messages": out,
                "tools": [{"name": t["function"]["name"], "description": t["function"]["description"],
                           "input_schema": deepcopy(t["function"]["parameters"])} for t in tools],
                "max_tokens": output_limit, "temperature": self.temperature}

    def send(self, wire):
        headers = {"anthropic-version": "2023-06-01"}
        if self.key:
            headers["x-api-key"] = self.key
        return self.http.post(self.base_url + "/messages", wire, headers)

    def parse(self, raw):
        if (not isinstance(raw, dict) or raw.get("role") != "assistant"
                or not isinstance(raw.get("content"), list)):
            raise ContractError("response_envelope", "Expected native Messages envelope", fatal=True)
        if raw.get("stop_reason") not in ("tool_use", "end_turn"):
            raise ContractError("incomplete_response", "Incomplete Messages response is not executed", fatal=True)
        if self.expected is not None and raw.get("model") != self.expected:
            raise ContractError("model_identity_changed", "Unexpected returned model", fatal=True)
        calls, texts = [], []
        for b in raw["content"]:
            if not isinstance(b, dict):
                raise ContractError("response_envelope", "Invalid content block", fatal=True)
            if b.get("type") == "tool_use":
                if not isinstance(b.get("input"), dict):
                    raise ContractError("policy_protocol", "tool_use input must be an object")
                calls.append({"id": b.get("id"), "type": "function", "function": {
                    "name": b.get("name"), "arguments": canonical(b["input"])}})
            elif b.get("type") == "text" and isinstance(b.get("text"), str):
                texts.append(b["text"])
            elif b.get("type") not in ("thinking", "redacted_thinking"):
                raise ContractError("response_envelope", "Unsupported content block", fatal=True)
        out = {"role": "assistant", "content": "\n".join(texts) or None, "tool_calls": calls,
               "_anthropic_blocks": deepcopy(raw["content"])}
        return Reply(check_calls(out), usage_of(raw, "anthropic"), raw.get("model"))


class EchoRetriever:
    def __init__(self, base_url: str, *, index_id: str, http: HTTP):
        if not index_id.strip():
            raise ValueError("Frozen corpus/index identity is required")
        self.base_url, self.http = endpoint(base_url), http
        self.identity = {"kind": "echo-http", "endpoint": self.base_url, "index_id": index_id}

    def search(self, query, top_k):
        self.last_wire_request = {"path": "/retrieve", "body": {"queries": [query], "topk": top_k}}
        raw = self.http.post(self.base_url + "/retrieve", self.last_wire_request["body"])
        self.last_wire_response = deepcopy(raw)
        rows = raw.get("result", raw.get("results"))
        if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], list):
            rows = rows[0]
        if not isinstance(rows, list):
            raise ContractError("retrieval_protocol", "Search results must be a list", fatal=True)
        out = []
        for row in rows[:top_k]:
            if not isinstance(row, dict):
                raise ContractError("retrieval_protocol", "Search hit must be an object", fatal=True)
            nested = row.get("document", {})
            if not isinstance(nested, dict):
                raise ContractError("retrieval_protocol", "Nested document must be an object", fatal=True)
            key = row.get("docid", row.get("id", nested.get("docid")))
            if not isinstance(key, (str, int)) or isinstance(key, bool) or not str(key):
                raise ContractError("retrieval_protocol", "Missing document identity", fatal=True)
            title = row.get("title", nested.get("title", ""))
            snippet = row.get("snippet", row.get("content", nested.get("contents", "")))
            if not isinstance(title, str) or not isinstance(snippet, str):
                raise ContractError("retrieval_protocol", "Title/snippet must be text", fatal=True)
            out.append({"docid": str(key), "title": title, "snippet": snippet})
        return out

    def get_document(self, docid):
        self.last_wire_request = {"path": "/get_doc", "body": {"docid": docid}}
        raw = self.http.post(self.base_url + "/get_doc", self.last_wire_request["body"])
        self.last_wire_response = deepcopy(raw)
        d = raw.get("document", raw)
        if not isinstance(d, dict):
            raise ContractError("retrieval_protocol", "Document must be an object", fatal=True)
        actual = raw.get("docid", d.get("docid"))
        if actual is not None and str(actual) != docid:
            raise ContractError("retrieval_protocol", "Returned document identity mismatch", fatal=True)
        text = d.get("content", d.get("contents", d.get("text")))
        if not isinstance(text, str) or not text.strip():
            raise ContractError("retrieval_protocol", "Document text missing", fatal=True)
        return {"docid": docid, "content": text, "identity_echoed": actual is not None}


class LocalCorpus:
    """Deterministic lexical fixture/development retriever, NOT official BC+ BM25."""
    def __init__(self, documents: list[dict]):
        self.documents = {}
        for d in documents:
            if not isinstance(d, dict) or set(d) != {"docid", "title", "content"} or not all(
                    isinstance(v, str) and v.strip() for v in d.values()):
                raise ValueError("Corpus rows require exactly docid/title/content strings")
            if d["docid"] in self.documents:
                raise ValueError("Duplicate document identity")
            self.documents[d["docid"]] = deepcopy(d)
        self.identity = {"kind": "local-lexical", "index_id": digest(documents)}

    def search(self, query, top_k):
        words = set(re.findall(r"\w+", query.casefold()))
        ranked = []
        for key, d in self.documents.items():
            score = len(words & set(re.findall(r"\w+", (d["title"] + " " + d["content"]).casefold())))
            if score:
                ranked.append((-score, key, {"docid": key, "title": d["title"], "snippet": d["content"][:400]}))
        return [r[2] for r in sorted(ranked)[:top_k]]

    def get_document(self, docid):
        return deepcopy(self.documents[docid])


class ByteCounter:
    identity = {"kind": "utf8_bytes", "calibrated_provider_tokens": False}
    def __call__(self, wire):
        return len(canonical(wire).encode("utf-8"))


class HFCounter:
    def __init__(self, local_path):
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(local_path, local_files_only=True, trust_remote_code=False)
        self.identity = {"kind": "local_hf_template_estimate", "calibrated_provider_tokens": False,
            "vocab_hash": digest(self.tokenizer.get_vocab()), "template_hash": digest(self.tokenizer.chat_template),
            "special_tokens_hash": digest(self.tokenizer.special_tokens_map)}

    def __call__(self, wire):
        if "system" in wire:
            raise ValueError("HF counter is not verified for Anthropic wire formatting")
        kwargs = {"tokenize": True, "add_generation_prompt": True}
        if wire.get("tools"):
            kwargs["tools"] = wire["tools"]
        return len(self.tokenizer.apply_chat_template(wire["messages"], **kwargs))
