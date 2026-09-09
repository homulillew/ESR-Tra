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
    def __init__(self, max_completion_tokens: int = 24000, events: list[dict] | None = None):
        if max_completion_tokens < 1:
            raise ValueError("Generation budget must be positive")
        self.limit, self.prompt_tokens, self.completion_tokens = max_completion_tokens, 0, 0
        self.unknown_usage_requests = 0
        for event in events or []:
            if event.get("type") == "generation":
                self.add(event.get("usage"))

    @property
    def remaining(self):
        return max(0, self.limit - self.completion_tokens)

    def add(self, usage: dict | None):
        if usage is None:
            self.unknown_usage_requests += 1
        else:
            self.prompt_tokens += usage["prompt_tokens"]
            self.completion_tokens += usage["completion_tokens"]

    def summary(self):
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "completion_budget": self.limit, "unknown_usage_requests": self.unknown_usage_requests}


class ChatClient:
    def __init__(self, config: ChatConfig, counter: Callable, budget: UsageBudget, ledger: Ledger,
                 transport: Callable = post_json):
        self.config, self.counter, self.budget, self.ledger, self.transport = config, counter, budget, ledger, transport
        self.identity = {"chat": asdict(config), "tokenizer": getattr(counter, "identity", {"type": type(counter).__name__})}

    def fits(self, messages: list[dict]) -> bool:
        reserve = min(self.config.max_output_tokens, self.budget.remaining)
        return self.counter(messages, self.config.thinking) + reserve <= self.config.max_context_tokens

    def complete(self, messages: list[dict], purpose: str = "policy") -> str:
        if self.budget.remaining <= 0:
            raise HarnessError("generation_budget_exhausted", "Combined policy+audit generation budget exhausted")
        if not self.fits(messages):
            raise HarnessError("context_overflow", "Full required context does not fit; nothing was silently truncated")
        body = {"model": self.config.model, "messages": messages,
                "max_tokens": min(self.config.max_output_tokens, self.budget.remaining),
                "temperature": self.config.temperature,
                "chat_template_kwargs": {"enable_thinking": self.config.thinking}}
        headers = {}
        if os.getenv(self.config.api_key_env):
            headers["Authorization"] = "Bearer " + os.environ[self.config.api_key_env]
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        for attempt in range(self.config.transport_attempts):
            started = time.monotonic()
            try:
                response = self.transport(url, body, timeout=self.config.timeout, headers=headers)
            except HarnessError as exc:
                self.budget.add(None)
                self.ledger.append({"type": "generation", "purpose": purpose, "request": body,
                                    "error_code": exc.code, "error": str(exc), "usage": None,
                                    "elapsed_seconds": time.monotonic() - started})
                retryable = str(exc).startswith(("HTTP 5", "Request failed:"))
                if not retryable or attempt + 1 == self.config.transport_attempts:
                    raise
                time.sleep(0.25 * (attempt + 1))
                continue
            usage = response.get("usage")
            valid_usage = (isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                                          for k in ("prompt_tokens", "completion_tokens")))
            measured = {k: usage[k] for k in ("prompt_tokens", "completion_tokens")} if valid_usage else None
            self.budget.add(measured)
            self.ledger.append({"type": "generation", "purpose": purpose, "request": body,
                                "response": response, "usage": measured,
                                "elapsed_seconds": time.monotonic() - started})
            if measured is None:
                raise HarnessError("service_error", "Provider did not return usable token usage; budget is unknown")
            try:
                choice = response["choices"][0]
                text = choice["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise HarnessError("service_error", "Malformed chat completion response") from exc
            if not isinstance(text, str):
                raise HarnessError("protocol_error", "No textual JSON action/verdict returned")
            if measured["completion_tokens"] > body["max_tokens"]:
                raise HarnessError("generation_budget_exhausted", "Provider exceeded the requested output limit")
            return text
        raise AssertionError("unreachable")
