"""Pure, deterministic projection of visible assistant prose, never source data."""
from copy import deepcopy

from .contract import digest, text_hash


RULE = {
    "version": "middle-history-v1",
    "preserve": ["episode_first_complete_group", "latest_complete_group"],
    "missing_first": "do_not_restore_or_promote_surviving_group",
    "eligibility": "complete_group_with_nonempty_tool_calls",
    "replacement": "assistant.content=null",
    "anthropic": "remove_text_blocks_only_from_projection_copy",
    "provider_reasoning": "preserve",
    "final": "same_projection_rule",
    "extra_prompt": False,
    "extra_model_calls": 0,
}


def identity():
    return {"version": RULE["version"], "rule": deepcopy(RULE),
            "rule_sha256": digest(RULE),
            "kind": "deterministic_visible_assistant_prose_projection"}


def project(history, *, first_round, latest_round):
    """Return message copies and audit data; callers retain original groups."""
    messages, changes = [], []
    for group in history:
        copied = deepcopy(group["messages"])
        assistant = copied[0]
        if (group["round"] not in {first_round, latest_round}
                and assistant.get("role") == "assistant" and assistant.get("tool_calls")):
            prose = assistant.get("content")
            native_text = [b for b in assistant.get("_anthropic_blocks", []) if b.get("type") == "text"]
            if isinstance(prose, str) or native_text:
                before = digest(assistant)
                assistant["content"] = None
                if "_anthropic_blocks" in assistant:
                    assistant["_anthropic_blocks"] = [b for b in assistant["_anthropic_blocks"]
                                                       if b.get("type") != "text"]
                changes.append({"source_round": group["round"],
                    "original_message_sha256": before, "projected_message_sha256": digest(assistant),
                    "removed_content_sha256": text_hash(prose) if isinstance(prose, str) else None,
                    "removed_content_chars": len(prose) if isinstance(prose, str) else 0,
                    "removed_content_utf8_bytes": len(prose.encode("utf-8")) if isinstance(prose, str) else 0,
                    "removed_native_text": [{"sha256": text_hash(b["text"]), "chars": len(b["text"]),
                                              "utf8_bytes": len(b["text"].encode("utf-8"))} for b in native_text],
                    "tool_call_ids": [c["id"] for c in assistant["tool_calls"]]})
        messages.extend(copied)
    return messages, {"identity": identity(), "episode_first_complete_round": first_round,
        "latest_complete_round": latest_round,
        "first_complete_group_present": any(g["round"] == first_round for g in history),
        "retained_group_rounds": [g["round"] for g in history], "changes": changes}


ONCE_RULE = {
    "version": "once-prose-reset-v1",
    "consecutive_search_rounds": 3,
    "minimum_remaining_model_calls": 3,
    "max_triggers": 1,
    "observation": "successful_search_receipt_executed_and_ok_without_new_delivered_source_passage",
    "eligibility": "retained_complete_group_with_nonempty_tool_calls",
    "preserve_first_latest": False,
    "replacement": "assistant.content=null",
    "anthropic": "remove_text_blocks_only_from_projection_copy",
    "preserve": ["tools", "arguments", "receipts", "evidence", "notes", "repair", "provider_reasoning"],
    "final": "never_trigger",
    "commit": "after_request_archive_before_send_attempt",
    "duration": "one_actual_request_then_original_history",
    "extra_prompt": False,
    "extra_model_calls": 0,
}


def once_identity():
    return {"version": ONCE_RULE["version"], "rule": deepcopy(ONCE_RULE),
            "rule_sha256": digest(ONCE_RULE),
            "kind": "one_request_visible_assistant_prose_omission_not_independent_planner"}


def project_once(history):
    messages, audit = project(history, first_round=None, latest_round=None)
    for key in ("episode_first_complete_round", "latest_complete_round", "first_complete_group_present"):
        audit.pop(key)
    audit["identity"] = once_identity()
    return messages, audit


CONTINUOUS_RULE = {
    "version": "continuous-prose-omission-v1",
    "eligibility": "retained_complete_group_with_nonempty_tool_calls",
    "replacement": "assistant.content=null",
    "anthropic": "remove_text_blocks_only_from_projection_copy",
    "preserve_first_latest": False,
    "preserve": ["tool_calls", "arguments", "receipts", "evidence", "notes", "gap", "repair", "provider_reasoning"],
    "final": "same_projection_rule",
    "duration": "every_request_build_including_preflight",
    "mutation": "projection_copies_only; no trigger state",
    "extra_prompt": False,
    "extra_model_calls": 0,
}


def continuous_identity():
    return {"version": CONTINUOUS_RULE["version"], "rule": deepcopy(CONTINUOUS_RULE),
            "rule_sha256": digest(CONTINUOUS_RULE),
            "kind": "continuous_visible_assistant_prose_projection"}


def project_continuous(history):
    messages, audit = project(history, first_round=None, latest_round=None)
    for key in ("episode_first_complete_round", "latest_complete_round", "first_complete_group_present"):
        audit.pop(key)
    audit["identity"] = continuous_identity()
    return messages, audit
