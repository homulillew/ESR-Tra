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
