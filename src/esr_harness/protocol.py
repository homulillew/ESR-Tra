"""2.1 tool contract. Models write semantic deltas; the harness owns bookkeeping."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from .v2.protocol import HarnessError, canonical, digest, parse_object

VERSION = "2.1.0"
SCHEMA_VERSION = 3  # Deliberately incompatible with v2 ledgers; never auto-migrate.

def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required, "additionalProperties": False}

def string(max_length=1200, min_length=1):
    return {"type": "string", "minLength": min_length, "maxLength": max_length}

def array(items, max_items=32):
    return {"type": "array", "items": items, "maxItems": max_items}

def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}

ID = string(128)
IDS = {**array(ID), "uniqueItems": True}
FOCUS = obj({"claim_id": ID, "need": string(1000)})
CLAIM = obj({"claim_id": ID, "requirement": string(16000), "finding": string(1800, 0), "observation_ids": IDS})
CLAIM_UPDATE = obj({"claim_id": ID, "requirement": string(16000), "finding": string(1800, 0), "observation_ids": IDS}, [])
STATE_SCHEMA = obj({"target": string(16000), "answer": nullable(string(2000)),
                    "claims": {**array(CLAIM, 16), "minItems": 1}, "focus": nullable(FOCUS)})
SCHEMAS = {
    "search": obj({"query": string(2000), "focus": FOCUS, "anchor_refs": IDS,
                   "top_k": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"]),
    "open_page": obj({"docid": ID, "search_action_id": ID, "query": string(2000),
                      "offset": {"type": "integer", "minimum": 0}}, ["docid"]),
    "read_evidence": obj({"observation_id": ID, "directory_cursor": string(128)}, []),
    "update_state": {**obj({"target": string(16000), "answer": nullable(string(2000)),
                            "claim_updates": array(CLAIM_UPDATE, 16), "retire_claim_ids": IDS,
                            "focus": nullable(FOCUS), "dismiss_observation_ids": IDS,
                            "attempt_note": string(1000), "attempt_id": ID,
                            "revision_reason": string(1200)}, []), "minProperties": 1},
    "verify_answer": obj({}),
    "submit_answer": obj({"decision": {"enum": ["answer", "abstain"]}, "reason": string(1200)}, []),
    "finish": obj({"answer": string(2000)}),
}
DESCRIPTIONS = {
    "search": "Find navigation candidates for current focus.need. Optional focus changes purpose, not proof. Exact fixed-index requests can use cache; inspect unread hits rather than repeat.",
    "open_page": "Open a real search hit. Parent search ID is optional. query and offset are mutually exclusive. Returns an immutable, capacity-admitted observation.",
    "read_evidence": "Replay an observation exactly, even if already cited. Alternatively directory_cursor='start' (or returned cursor) lists archived view IDs. Choose exactly one mode.",
    "update_state": "Local delta, not full-state rewrite. Omitted fields stay unchanged; answer=null withdraws a candidate. Pair finding with its observation_ids. New claims omit ID; returned IDs can be used next turn. Task revisions/retirements need a reason. Findings are interpretations, not verdicts.",
    "verify_answer": "Fresh full-question audit of current interpretations and actual evidence. Partial answer=null is allowed but cannot pass target. Same semantic input uses cache; focus/attempt notes do not invalidate it.",
    "submit_answer": "End with current state.answer (default decision=answer) or explicitly abstain. No alternative answer argument. Preserve the configured hard/soft/off evidence label.",
    "finish": "Baseline only: end with the answer itself.",
}
VERDICT = {"enum": ["supported", "unknown", "contradicted"]}
QUOTE = obj({"observation_id": ID, "quote": string(4000)})
CHECK = obj({"status": VERDICT, "reason": string(1200), "need": string(1000, 0)})
AUDIT_SCHEMA = obj({"target": CHECK, "coverage": CHECK,
                    "claims": array(obj({"claim_id": ID, "status": VERDICT,
                                         "quotes": array(QUOTE, 16), "reason": string(1200),
                                         "need": string(1000, 0)}), 16)})

def validate(value, schema, path="arguments"):
    """The small JSON Schema subset used here; exported schemas share this source."""
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            try:
                validate(value, option, path)
                return
            except HarnessError:
                pass
        raise HarnessError("protocol_error", f"{path}: no permitted type matches")
    if "enum" in schema and value not in schema["enum"]:
        raise HarnessError("protocol_error", f"{path}: invalid enum")
    kind = schema.get("type")
    checks = {"null": lambda: value is None, "object": lambda: isinstance(value, dict),
              "array": lambda: isinstance(value, list), "string": lambda: isinstance(value, str),
              "integer": lambda: type(value) is int}
    if kind and not checks[kind]():
        raise HarnessError("protocol_error", f"{path}: expected {kind}")
    if kind == "object":
        extra = set(value) - set(schema["properties"]) if not schema.get("additionalProperties") else set()
        missing = set(schema["required"]) - set(value)
        if extra or missing or len(value) < schema.get("minProperties", 0):
            raise HarnessError("protocol_error", f"{path}: missing={sorted(missing)}, extra={sorted(extra)} or empty delta")
        for key in value:
            if key in schema["properties"]:
                validate(value[key], schema["properties"][key], f"{path}.{key}")
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
            raise HarnessError("protocol_error", f"{path}: integer out of range")

@dataclass(frozen=True)
class Config:
    mode: str = "esr"
    audit_mode: str = "hard"
    max_actions: int = 64
    search_top_k: int = 5
    view_chars: int = 8000
    chunk_top_k: int = 3
    stagnant_after: int = 3
    recent_actions: int = 4
    directory_page_size: int = 8
    max_pending_views: int = 4
    cache_search: bool = True

    def __post_init__(self):
        if self.mode not in {"esr", "baseline"} or self.audit_mode not in {"hard", "soft", "off"}:
            raise ValueError("Invalid mode/audit mode")
        for key in ("max_actions", "search_top_k", "view_chars", "chunk_top_k", "stagnant_after", "directory_page_size", "max_pending_views"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be a positive integer")
        if type(self.recent_actions) is not int or self.recent_actions < 0 or type(self.cache_search) is not bool:
            raise ValueError("Invalid history/cache configuration")
        if self.search_top_k > 50 or self.chunk_top_k > 20 or self.directory_page_size > 32:
            raise ValueError("Retrieval/directory limits exceeded")

    def to_dict(self):
        return asdict(self)

    @property
    def tools(self):
        names = ["search", "open_page", "read_evidence"]
        if self.mode == "baseline":
            names += ["finish"]
        else:
            names += ["update_state"]
            if self.audit_mode != "off":
                names += ["verify_answer"]
            names += ["submit_answer"]
        return [{"name": n, "description": DESCRIPTIONS[n], "parameters": SCHEMAS[n]} for n in names]
