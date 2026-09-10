"""Fresh, source-grounded semantic audit. The model's interpretations are not sources."""
from typing import Protocol
from copy import deepcopy
from .protocol import AUDIT_SCHEMA, HarnessError, canonical, digest, parse_object, validate

from .prompts import AUDIT_PROMPT_VERSION, AUDIT_SYSTEM, AUDIT_SPAN_PROMPT_VERSION, AUDIT_SPAN_SYSTEM
from .prompts import TASK_FIRST_AUDIT, TASK_FIRST_AUDIT_VERSION, LITERAL_ANSWER_AUDIT
from .audit_spans import SPAN_SCHEMA, source_span_packet, expand_references

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
    def __init__(self, client, attempts=2, *, citation_mode='quotes', span_max_chars=1200, profile='atomic'):
        if attempts not in {1, 2}:
            raise ValueError("Audit protocol repair must be bounded")
        if citation_mode not in {'quotes','source_spans'}:
            raise ValueError('Unknown auditor citation mode')
        if not 100 <= span_max_chars <= 4000:
            raise ValueError('Invalid audit span size')
        if profile not in {'atomic', 'task_first', 'task_first_literal'}:
            raise ValueError('Unknown auditor profile')
        self.profile = profile
        self.client, self.attempts = client, attempts
        self.citation_mode,self.span_max_chars=citation_mode,span_max_chars
        self.system=AUDIT_SPAN_SYSTEM if citation_mode=='source_spans' else AUDIT_SYSTEM
        if profile in {'task_first', 'task_first_literal'}:
            self.system = TASK_FIRST_AUDIT + self.system
        if profile == 'task_first_literal':
            self.system = LITERAL_ANSWER_AUDIT + self.system
        self.schema=SPAN_SCHEMA if citation_mode=='source_spans' else AUDIT_SCHEMA
        self.identity = {"client": client.identity,
                         "prompt": AUDIT_SPAN_PROMPT_VERSION if citation_mode=='source_spans' else AUDIT_PROMPT_VERSION,
                         "system_hash": digest(self.system), "schema_hash": digest(self.schema),
                         'citation_mode':citation_mode,'span_max_chars':span_max_chars if citation_mode=='source_spans' else None}
        if profile in {'task_first', 'task_first_literal'}:
            self.identity.update(profile=profile, prompt=TASK_FIRST_AUDIT_VERSION + '+' + self.identity['prompt'])
        if profile == 'task_first_literal':
            self.identity['prompt'] = 'literal-answer-2.1.0+' + self.identity['prompt']

    def audit(self, question, state, views):
        payload = {"question": question, **state,
                   "observations": [{"observation_id": v["observation_id"], "docid": v["docid"], "text": v["text"]} for v in views]}
        references={}
        if self.citation_mode=='source_spans':
            payload['observations'],references=source_span_packet(views,self.span_max_chars)
        schema = deepcopy(self.schema)
        schema["properties"]["claims"].update(minItems=len(state["claims"]), maxItems=len(state["claims"]))
        claim_props=schema['properties']['claims']['items']['properties']
        # Detach the shared ID schema before specializing only claim_id.
        claim_props['claim_id']={**claim_props['claim_id'],'enum':[c['claim_id'] for c in state['claims']]}
        if self.citation_mode=='source_spans':
            quotes=schema['properties']['claims']['items']['properties']['quotes']
            if references:quotes['items']['properties']['span_id']['enum']=list(references)
            else:quotes['maxItems']=0
        messages = [{"role": "system", "content": self.system + "\nSchema:\n" + canonical(schema)},
                    {"role": "user", "content": literal_answer_packet(payload) if self.profile == 'task_first_literal' else canonical(payload)}]
        last = ""
        for attempt in range(self.attempts):
            reply = self.client.complete(messages, purpose="audit")
            try:
                proposed=parse_object(reply)
                if self.citation_mode=='source_spans':
                    validate(proposed,schema,'audit')
                    report=expand_references(proposed,references)
                else:report=proposed
                validated=validate_report(report, state, {v["observation_id"]: v for v in views})
                if self.citation_mode=='source_spans' and hasattr(self.client,'ledger'):
                    selected={q['span_id'] for row in proposed['claims'] for q in row['quotes']}
                    self.client.ledger.append({'type':'audit_citation_resolution','proposed_report':proposed,
                                               'selected_source_spans':{sid:references[sid] for sid in sorted(selected)},
                                               'expanded_report':validated,'verdict_modified':False})
                return validated
            except HarnessError as exc:
                last = str(exc)
                if attempt + 1 < self.attempts:
                    messages += [{"role": "assistant", "content": reply},
                                 {"role": "user", "content": "Repair protocol only; keep all original evidence: " + last}]
        raise HarnessError("audit_protocol_error", last)


def literal_answer_packet(payload):
    """Render the exact answer once outside JSON; derive no semantic requirement."""
    rest = dict(payload)
    answer = rest.pop('answer')
    if answer is None:
        candidate = 'Candidate answer: null (no answer bound).'
    else:
        nonce = 0
        while True:
            marker = digest([answer, nonce])
            begin, end = 'BEGIN_ANSWER_' + marker, 'END_ANSWER_' + marker
            if begin not in answer and end not in answer:
                break
            nonce += 1
        candidate = begin + '\n' + answer + '\n' + end
    return candidate + '\n\nAudit inputs (candidate answer above):\n' + canonical(rest)
