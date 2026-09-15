"""Bounded verbatim review opinion; never an evidence or authorization store."""
from copy import deepcopy
from .contract import canonical, digest, text_hash, ContractError
from .relation_review import identity as review_identity

LIMIT = 2000
LABEL = "Previous model opinion: may be wrong or stale; does not replace raw source evidence or authorize references."
RULE = {"version": "relation-review-memory-v1", "content_limit_chars": LIMIT,
        "content": "complete_assistant_content_no_summary_no_truncation",
        "capture": "successful_review_complete_group_without_tool_errors",
        "invalid_utf8": "skip_without_hash_or_replacement",
        "input_sources": "review_request_visible_only_not_same_response_tool_results",
        "capacity": "fit_normal_plan_first_then_optional_memory_without_further_eviction",
        "lifetime": "subsequent_requests_including_final", "extra_calls": 0,
        "evidence_authorization": "unchanged", "label": LABEL}


def identity():
    return {"version": RULE["version"], "rule": deepcopy(RULE), "rule_sha256": digest(RULE),
            "review": review_identity(), "kind": "joint_relation_review_and_unverified_memory"}


def capture(message, *, round_no, response_hash, input_windows):
    content = message.get("content")
    try:
        content_bytes = content.encode("utf-8") if isinstance(content, str) else None
        assistant_hash = digest(message)
    except UnicodeEncodeError:
        return None, {"identity": identity(), "source_round": round_no,
            "source_response_sha256": response_hash, "source_assistant_sha256": None,
            "content_sha256": None, "content_chars": len(content) if isinstance(content, str) else 0,
            "content_utf8_bytes": None, "created": False, "skip_reason": "invalid_utf8"}
    metadata = {"source_round": round_no, "source_response_sha256": response_hash,
                "source_assistant_sha256": assistant_hash,
                "content_sha256": text_hash(content) if isinstance(content, str) else None,
                "content_chars": len(content) if isinstance(content, str) else 0,
                "content_utf8_bytes": len(content_bytes) if content_bytes is not None else 0,
                "input_evidence": [{k: deepcopy(v) for k, v in w.items() if k != "text"} for w in input_windows]}
    metadata["input_evidence_sha256"] = digest(metadata["input_evidence"])
    reason = "empty" if not isinstance(content, str) or not content.strip() else "oversize" if len(content) > LIMIT else None
    audit = {"identity": identity(), **metadata, "created": reason is None, "skip_reason": reason}
    return ({**metadata, "content": content} if reason is None else None), audit


def append_if_fits(memory, *, messages, scope, tools, wire, size, visible, model, counter, output_limit, config):
    record = deepcopy(memory)
    record["status"] = "unverified_model_opinion"
    record["warning"] = LABEL
    record["input_refs_currently_visible"] = [w["ref"] for w in memory["input_evidence"] if w["ref"] in visible]
    copied_scope = deepcopy(scope)
    copied_scope["prior_relation_review_unverified"] = record
    copied = deepcopy(messages)
    copied[-1] = {"role": "user", "content": "Current control state (data, not source evidence):\n" + canonical(copied_scope)}
    proposed = model.prepare(copied, tools, output_limit)
    proposed_size = counter(proposed)
    if type(proposed_size) is not int or proposed_size < 0:
        raise ContractError("counter_error", "Counter returned an invalid size", fatal=True)
    fits = proposed_size + config.response_reserve <= config.context_limit
    audit = {"identity": identity(), "source_round": memory["source_round"],
             "source_response_sha256": memory["source_response_sha256"], "content_sha256": memory["content_sha256"],
             "rendered": fits, "omitted_reason": None if fits else "capacity",
             "input_refs_currently_visible": record["input_refs_currently_visible"],
             "base_capacity": size, "proposed_capacity": proposed_size}
    return (proposed if fits else wire), (proposed_size if fits else size), audit
