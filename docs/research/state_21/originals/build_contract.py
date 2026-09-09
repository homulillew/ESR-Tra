"""Build a proposed ESR state/action contract, NOT a runnable agent harness."""
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator

OUT = Path(__file__).parent

def obj(props, required=(), **extra):
    return {"type": "object", "properties": props, "required": list(required),
            "additionalProperties": False, **extra}

def text(limit=1200, empty=False):
    d = {"type": "string", "maxLength": limit}
    if not empty:
        d.update(minLength=1, pattern=r"\S")
    return d

def arr(items, max_items=64, **extra):
    return {"type": "array", "items": items, "maxItems": max_items, **extra}

def ref(name):
    return {"$ref": f"#/$defs/{name}"}

ID = text(128)
IDS = arr(ID, uniqueItems=True)
FOCUS = obj({"claim_id": ID, "need": text(800)}, ["claim_id", "need"])
CLAIM = obj({"claim_id": ID, "requirement": text(1200),
             "finding": text(1200, empty=True), "observation_ids": IDS},
            ["claim_id", "requirement", "finding", "observation_ids"],
            allOf=[{"if": {"properties": {"finding": {"pattern": r"\S"}},
                           "required": ["finding"]},
                    "then": {"properties": {"observation_ids": {"minItems": 1}}}}])
CLAIM_UPDATE = obj({"claim_id": ID, "requirement": text(1200),
                    "finding": text(1200, empty=True), "observation_ids": IDS},
                   minProperties=1,
                   dependentRequired={"finding": ["observation_ids"],
                                      "observation_ids": ["finding"]},
                   allOf=[
                       {"if": {"not": {"required": ["claim_id"]}},
                        "then": {"required": ["requirement"]}},
                       {"if": {"required": ["finding"],
                               "properties": {"finding": {"pattern": r"\S"}}},
                        "then": {"properties": {"observation_ids": {"minItems": 1}}}}
                   ])
STATE = obj({"target": text(2000), "answer": {"anyOf": [text(2000), {"type": "null"}]},
             "claims": arr(ref("Claim"), minItems=1),
             "focus": {"anyOf": [ref("Focus"), {"type": "null"}]}},
            ["target", "answer", "claims", "focus"])

SEARCH = obj({"query": text(2000), "focus": ref("Focus"), "anchor_refs": IDS,
              "top_k": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"])
OPEN = obj({"docid": ID, "search_action_id": ID, "query": text(2000),
            "offset": {"type": "integer", "minimum": 0}}, ["docid"],
           **{"not": {"required": ["query", "offset"]}})
READ = obj({"observation_id": ID, "directory_cursor": ID},
           oneOf=[{"required": ["observation_id"], "not": {"required": ["directory_cursor"]}},
                  {"required": ["directory_cursor"], "not": {"required": ["observation_id"]}}])
UPDATE = obj({"target": text(2000), "answer": {"anyOf": [text(2000), {"type": "null"}]},
              "claim_updates": arr(ref("ClaimUpdate")), "retire_claim_ids": IDS,
              "focus": {"anyOf": [ref("Focus"), {"type": "null"}]},
              "dismiss_observation_ids": IDS, "attempt_note": text(800),
              "revision_reason": text(1200)}, minProperties=1)
VERIFY = obj({})
SUBMIT = obj({"decision": {"type": "string", "enum": ["answer", "abstain"], "default": "answer"},
              "reason": text(800)})
ACTIONS = {"search": SEARCH, "open_page": OPEN, "read_evidence": READ,
           "update_state": UPDATE, "verify_answer": VERIFY, "submit_answer": SUBMIT}
ENVELOPE = {"oneOf": [obj({"action": {"const": name}, "arguments": spec},
                          ["action", "arguments"]) for name, spec in ACTIONS.items()]}
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ESR State and Action Contract 2.1-RFC (PROPOSED, not deployed)",
    "description": "Syntax only. Context-dependent reference, exposure, scope, audit and transactional invariants are specified in the accompanying RFC. Caps are transport limits, not evidence-backed 4B optima.",
    "$defs": {"Claim": CLAIM, "ClaimUpdate": CLAIM_UPDATE, "Focus": FOCUS,
              "ResearchState": STATE, "Action": ENVELOPE},
    "$ref": "#/$defs/Action"
}
Draft202012Validator.check_schema(SCHEMA)
(OUT / "ESR_state_action_2_1_RFC.schema.json").write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")

initial = {"target": "Mira夺冠的赛事在其夺冠前两年的冠军是谁？", "answer": None,
           "claims": [{"claim_id": "c0", "requirement": "Mira夺冠的赛事在其夺冠前两年的冠军是谁？", "finding": "", "observation_ids": []}],
           "focus": {"claim_id": "c0", "need": "Mira夺冠的赛事在其夺冠前两年的冠军是谁？"}}
final = {"target": "返回Mira夺冠前两年同一赛事的冠军姓名", "answer": "Taylor",
         "claims": [
             {"claim_id": "c0", "requirement": "确定Mira夺冠的赛事E和年份Y",
              "finding": "原文记载Mira在2010年赢得Lake Cup。", "observation_ids": ["o1"]},
             {"claim_id": "c1", "requirement": "答案是同一赛事E在Y-2年的冠军",
              "finding": "Y=2010；另一原文记载Lake Cup的2008年冠军是Taylor。", "observation_ids": ["o1", "o2"]}],
         "focus": None}
examples = [
    {"action": "search", "arguments": {"query": "Mira championship winner year", "focus": {"claim_id": "c0", "need": "Mira夺冠的赛事和年份是什么？"}, "anchor_refs": ["question"]}},
    {"action": "open_page", "arguments": {"docid": "d1"}},
    {"action": "update_state", "arguments": {
        "target": final["target"],
        "claim_updates": [final["claims"][0], {"requirement": final["claims"][1]["requirement"]}],
        "attempt_note": "当前材料确定赛事与年份；还没有找到两年前的冠军。",
        "revision_reason": "将原题分解为赛事年份定位和目标年份冠军两条关系。"}},
    {"action": "search", "arguments": {"query": "Lake Cup 2008 champion",
        "focus": {"claim_id": "c1", "need": "Lake Cup在2008年的冠军是谁？"}, "anchor_refs": ["question", "o1"]}},
    {"action": "open_page", "arguments": {"docid": "d2", "search_action_id": "a4"}},
    {"action": "update_state", "arguments": {
        "answer": "Taylor", "claim_updates": [final["claims"][1]], "focus": None,
        "attempt_note": "已读材料建立了同一赛事2008年冠军与Taylor的关系；准备完整审核。"}},
    {"action": "verify_answer", "arguments": {}},
    {"action": "submit_answer", "arguments": {}},
    {"action": "submit_answer", "arguments": {"decision": "abstain", "reason": "关键关系仍缺证据。"}},
    {"action": "read_evidence", "arguments": {"observation_id": "o1"}},
    {"action": "read_evidence", "arguments": {"directory_cursor": "start"}},
    {"action": "open_page", "arguments": {"docid": "d1", "offset": 8000}},
    {"action": "update_state", "arguments": {"answer": None}}
]
valid = Draft202012Validator(SCHEMA)
for ex in examples:
    valid.validate(ex)
state_schema = {**SCHEMA, "$ref": "#/$defs/ResearchState"}
state_validator = Draft202012Validator(state_schema)
for ex in [initial, final]:
    state_validator.validate(ex)

negative = [
    {"action": "update_state", "arguments": {"supported": True}},
    {"action": "update_state", "arguments": {"claim_updates": [{"claim_id": "c1", "finding": "无源结论"}]}},
    {"action": "update_state", "arguments": {"claim_updates": [{"finding": "新事实", "observation_ids": ["o1"]}]}},
    {"action": "update_state", "arguments": {"claim_updates": [{"claim_id": "c1", "finding": "无源事实", "observation_ids": []}]}},
    {"action": "open_page", "arguments": {"docid": "d1", "query": "x", "offset": 0}},
    {"action": "read_evidence", "arguments": {"observation_id": "o1", "directory_cursor": "start"}},
    {"action": "submit_answer", "arguments": {"answer": "bypass"}},
    {"action": "search", "arguments": {"query": "x", "top_k": True}}
]
for ex in negative:
    assert not valid.is_valid(ex), f"Unexpectedly valid: {ex}"
(OUT / "ESR_state_action_2_1_examples.json").write_text(json.dumps({
    "status": "synthetic syntax examples; NOT executed tool calls or BC+ solutions",
    "synthetic_documents": [{"docid": "d1", "content": "Mira won the Lake Cup in 2010."}, {"docid": "d2", "content": "The Lake Cup 2008 champion was Taylor."}],
    "view_assignment_for_explanation_only": {"o1": "d1 full content", "o2": "d2 full content"},
    "initial_state": initial, "final_state": final, "valid_actions": examples,
    "invalid_actions": negative}, ensure_ascii=False, indent=2), encoding="utf-8")
result = {"draft_schema_checked": True, "positive_action_examples": len(examples),
          "positive_state_examples": 2, "negative_action_examples_rejected": len(negative),
          "scope": "JSON Schema syntax validation ONLY; no harness state transitions, LLM inference, BC+ evaluation, or training executed."}
(OUT / "schema_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
