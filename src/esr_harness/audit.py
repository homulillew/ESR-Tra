"""Fresh, source-grounded semantic audit. The model's interpretations are not sources."""
from typing import Protocol
from copy import deepcopy
from .protocol import AUDIT_SCHEMA, HarnessError, canonical, digest, parse_object, validate

from .prompts import AUDIT_PROMPT_VERSION, AUDIT_SYSTEM

class Auditor(Protocol):
    identity: dict
    def audit(self, question, state, views): ...


def validate_report(report, state, views):
    validate(report, AUDIT_SCHEMA, "audit")
    expected = {c["claim_id"]: c for c in state["claims"]}
    got = [c["claim_id"] for c in report["claims"]]
    if len(got) != len(set(got)) or set(got) != set(expected):
        raise HarnessError("audit_protocol_error", f"audit.claims: expected exactly {sorted(expected)}, received {got}; do not invent or decompose claim IDs")
    if state["answer"] is None and report["target"]["status"] != "unknown":
        raise HarnessError("audit_protocol_error", "No bound answer: target must be unknown")
    for v in [report["target"], report["coverage"], *report["claims"]]:
        if v["status"] != "supported" and not v["need"].strip():
            raise HarnessError("audit_protocol_error", "Unresolved verdict requires a concrete need")
        if v["status"] == "supported" and v["need"].strip():
            raise HarnessError("audit_protocol_error", "Supported verdict cannot also declare a missing relation")
    quotation_errors=[]
    for ci,v in enumerate(report["claims"]):
        if v["status"] in {"supported", "contradicted"} and not v["quotes"]:
            raise HarnessError("audit_protocol_error", "Support/contradiction requires raw quotes")
        allowed = set(expected[v["claim_id"]]["observation_ids"])
        for qi,q in enumerate(v["quotes"]):
            oid = q["observation_id"]
            path=f'audit.claims[{ci}].quotes[{qi}] (claim_id={v["claim_id"]}, observation_id={oid})'
            if oid not in allowed or oid not in views:
                quotation_errors.append(path+": Quote is outside this claim's permitted evidence")
            elif not any(q["quote"] in part for part in views[oid]["raw_parts"]):
                quotation_errors.append(path+": Quotation does not occur verbatim in this raw observation")
    if quotation_errors:
        raise HarnessError("audit_protocol_error", '; '.join(quotation_errors)+
                           '. Check every listed source ID and exact quote against the supplied raw text. If support is absent, report unknown with a concrete need; do not invent or paraphrase quotes.')
    return report


def status(report):
    values = [report["target"]["status"], report["coverage"]["status"], *[c["status"] for c in report["claims"]]]
    return "contradicted" if "contradicted" in values else "supported" if all(v == "supported" for v in values) else "unknown"


def unresolved(report):
    return ["@" + k for k in ("target", "coverage") if report[k]["status"] != "supported"] + [c["claim_id"] for c in report["claims"] if c["status"] != "supported"]


class ModelAuditor:
    def __init__(self, client, attempts=2):
        if attempts not in {1, 2}:
            raise ValueError("Audit protocol repair must be bounded")
        self.client, self.attempts = client, attempts
        self.identity = {"client": client.identity, "prompt": AUDIT_PROMPT_VERSION, "system_hash": digest(AUDIT_SYSTEM), "schema_hash": digest(AUDIT_SCHEMA)}

    def audit(self, question, state, views):
        payload = {"question": question, **state,
                   "observations": [{"observation_id": v["observation_id"], "docid": v["docid"], "text": v["text"]} for v in views]}
        schema = deepcopy(AUDIT_SCHEMA)
        schema["properties"]["claims"].update(minItems=len(state["claims"]), maxItems=len(state["claims"]))
        schema["properties"]["claims"]["items"]["properties"]["claim_id"]["enum"] = [c["claim_id"] for c in state["claims"]]
        messages = [{"role": "system", "content": AUDIT_SYSTEM + "\nSchema:\n" + canonical(schema)},
                    {"role": "user", "content": canonical(payload)}]
        last = ""
        for attempt in range(self.attempts):
            reply = self.client.complete(messages, purpose="audit")
            try:
                return validate_report(parse_object(reply), state, {v["observation_id"]: v for v in views})
            except HarnessError as exc:
                last = str(exc)
                if attempt + 1 < self.attempts:
                    messages += [{"role": "assistant", "content": reply},
                                 {"role": "user", "content": "Repair protocol only; keep all original evidence: " + last}]
        raise HarnessError("audit_protocol_error", last)
