"""The single, versioned contract for inference tools and audits (no RL code)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

VERSION = "2.0.0"


class HarnessError(Exception):
    """An expected, classified failure, never a semantic audit verdict."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_object(text: str) -> dict:
    """Accept one JSON object, optionally fenced; never extract a nested example."""
    text = text.strip()
    if text.startswith("<think>"):
        closing = text.find("</think>")
        if closing < 0:
            raise HarnessError("protocol_error", "Unclosed thinking wrapper")
        text = text[closing + len("</think>"):].strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[8:-4]
    elif text.startswith("```\n") and text.endswith("\n```"):
        text = text[4:-4]
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except (ValueError, TypeError) as exc:
        raise HarnessError("protocol_error", "Expected one strict JSON object") from exc
    if not isinstance(value, dict):
        raise HarnessError("protocol_error", "Expected a JSON object, not a list/scalar")
    return value


def obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def string(max_length: int = 1000, min_length: int = 1) -> dict:
    return {"type": "string", "minLength": min_length, "maxLength": max_length}


def array(items: dict, max_items: int = 16, min_items: int = 0) -> dict:
    return {"type": "array", "items": items, "maxItems": max_items, "minItems": min_items}


ID = string(128)
IDS = {**array(ID, 32), "uniqueItems": True}
CLAIM = obj({"claim_id": ID, "requirement": string(800), "observation_ids": IDS})
SCHEMAS = {
    "search": obj({"query": string(2000), "top_k": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"]),
    "open_page": obj({"docid": ID, "search_action_id": ID, "query": string(2000),
                      "offset": {"type": "integer", "minimum": 0}}, ["docid", "search_action_id"]),
    "read_evidence": obj({"observation_id": ID}),
    "update_state": obj({"answer": string(2000, 0), "answer_kind": {"enum": ["answer", "abstain"]},
                         "target": string(1000), "claims": array(CLAIM, 16),
                         "revision_reason": string(1000), "dismiss_observation_ids": IDS},
                        ["answer", "answer_kind", "target", "claims"]),
    "verify_answer": obj({}),
    "submit_answer": obj({}),
    "finish": obj({"answer": string(2000)}),
}
DESCRIPTIONS = {
    "search": "Find candidate documents; snippets are navigation, NOT citable evidence.",
    "open_page": "Open a returned docid. Optional query selects passages; offset requests a raw window. Returns immutable observation_id.",
    "read_evidence": "Replay ANY previously returned observation exactly; registration is not required.",
    "update_state": "Atomically replace the compact answer/requirements. Cite observation IDs; explicitly dismiss irrelevant pending views. Requirement changes need revision_reason.",
    "verify_answer": "Fresh-context per-requirement audit. Identical inputs use cache. Errors are not semantic gaps.",
    "submit_answer": "Finish using current state. Hard mode requires support; soft/off preserve the true audit label. Abstention is separate.",
    "finish": "Baseline only: finish with the answer itself, not a search plan.",
}
VERDICT = {"enum": ["supported", "unknown", "contradicted"]}
QUOTE = obj({"observation_id": ID, "quote": string(4000)})
AUDIT_SCHEMA = obj({
    "target": obj({"status": VERDICT, "reason": string(1200)}),
    "coverage": obj({"status": VERDICT, "reason": string(1200)}),
    "claims": array(obj({"claim_id": ID, "status": VERDICT,
                         "quotes": array(QUOTE, 16), "reason": string(1200)}), 16),
})


def validate(value: Any, schema: dict, path: str = "arguments") -> None:
    """Small strict validator for the subset used above; schema and runtime cannot drift."""
    if "enum" in schema and value not in schema["enum"]:
        raise HarnessError("protocol_error", f"{path}: invalid enum value")
    kind = schema.get("type")
    valid = {"object": lambda: isinstance(value, dict), "array": lambda: isinstance(value, list),
             "string": lambda: isinstance(value, str), "integer": lambda: type(value) is int}
    if kind and not valid[kind]():
        raise HarnessError("protocol_error", f"{path}: expected {kind}")
    if kind == "object":
        extra = set() if schema.get("additionalProperties") else set(value) - set(schema["properties"])
        missing = set(schema["required"]) - set(value)
        if extra or missing:
            raise HarnessError("protocol_error", f"{path}: missing={sorted(missing)}, extra={sorted(extra)}")
        for key, item in value.items():
            if key in schema["properties"]:
                validate(item, schema["properties"][key], f"{path}.{key}")
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema["maxItems"]:
            raise HarnessError("protocol_error", f"{path}: invalid item count")
        if schema.get("uniqueItems") and len({canonical(v) for v in value}) != len(value):
            raise HarnessError("protocol_error", f"{path}: duplicate items")
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value.strip()) <= schema["maxLength"]:
            raise HarnessError("protocol_error", f"{path}: invalid string length")
    elif kind == "integer":
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            raise HarnessError("protocol_error", f"{path}: out of range")


@dataclass(frozen=True)
class Config:
    mode: str = "esr"
    audit_mode: str = "hard"
    max_actions: int = 64
    search_top_k: int = 5
    view_chars: int = 8000
    chunk_top_k: int = 3
    stagnant_after: int = 6
    recent_actions: int = 6

    def __post_init__(self):
        if self.mode not in {"esr", "baseline"} or self.audit_mode not in {"hard", "soft", "off"}:
            raise ValueError("Invalid mode/audit_mode")
        for name in ("max_actions", "search_top_k", "view_chars", "chunk_top_k", "stagnant_after", "recent_actions"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.search_top_k > 50 or self.chunk_top_k > 20:
            raise ValueError("Retrieval limits exceeded")

    def to_dict(self):
        return asdict(self)

    @property
    def tools(self) -> list[dict]:
        names = ["search", "open_page", "read_evidence"]
        if self.mode == "baseline":
            names += ["finish"]
        else:
            names += ["update_state"]
            if self.audit_mode != "off":
                names += ["verify_answer"]
            names += ["submit_answer"]
        return [{"name": n, "description": DESCRIPTIONS[n], "parameters": SCHEMAS[n]} for n in names]
