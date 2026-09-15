"""Bounded harness-acquired raw windows attached to successful native searches."""
from copy import deepcopy

from .contract import ContractError, digest, text_hash
from .goal_read import select_window


SYSTEM = "\nSuccessful search may also contain explicitly marked harness-acquired raw_windows. These are original snapshot passages, not model-issued read calls. Search/find/recall snippets remain navigation, not evidence. A raw window becomes citable only after delivery in a subsequent model input; lexical selection does not verify a claim.\n"
SYSTEM_INSTRUCTION = SYSTEM
SEARCH_DESCRIPTION = (
    "Search the corpus with the original query parameters. Hits and snippets are navigation, not evidence. "
    "After a successful search, the harness may open only the first query's first document and attach "
    "one original raw_windows passage selected using that query's literal terms, at most min(read_chars,3000) "
    "Unicode characters. At most six distinct documents are automatically attempted per episode; "
    "empty results, previously attempted documents and exhausted allowance do not fall back to other hits. "
    "No lexical match produces no window. Cached snapshots may be reused; fetching consumes the shared "
    "backend and time budgets. This is automatic work within search, not a native read call. "
    "Only explicitly attached original raw windows can become evidence after subsequent input delivery. "
    "Use native read on a received document to choose another range; existing parameter limits, "
    "query interpretation, cache/replay behavior and source-binding rules remain in force."
)
RULE = {
    "version": "search-raw-window-v1", "selection": "results[0].hits[0]; no fallback or rotation",
    "goal": "original first query string", "selector": "paragraph-lexical-v1",
    "window_limit": "min(config.read_chars,3000) Unicode characters",
    "document_attempt_limit": 6, "deduplication": "episode-wide document ref",
    "attempt_commit": "before snapshot; no-match and later withholding consume",
    "backend_exhausted": "skip without attempt if snapshot absent",
    "error": "fatal; preserve original navigation and partial archive; no retry",
    "capacity": "original whole-call withholding", "authorization": "original subsequent delivery ack",
    "accounting": "one native search action; automatic attempts separately logged; shared backend/time",
    "tool_description": "replace exact contradictory profile sentences; preserve other guidance; append SEARCH_DESCRIPTION",
}
DESCRIPTION_REPLACEMENTS = {
    "Find candidate documents in the configured corpus; it does NOT open their full text.":
        "Find candidate documents in the configured corpus; the harness may attach a limited original source window.",
    "Results are navigation, NOT raw evidence.":
        "Hits and snippets are navigation, NOT raw evidence.",
}


def identity():
    return {"version": RULE["version"], "rule": deepcopy(RULE), "rule_sha256": digest(RULE),
            "instruction_sha256": text_hash(SYSTEM), "search_description_sha256": text_hash(SEARCH_DESCRIPTION),
            "description_replacements_sha256": digest(DESCRIPTION_REPLACEMENTS)}


def adapt_tools(tools):
    result = deepcopy(tools)
    for tool in result:
        if tool.get("function", {}).get("name") == "search":
            description = tool["function"].get("description", "")
            for original, replacement in DESCRIPTION_REPLACEMENTS.items():
                description = description.replace(original, replacement)
            tool["function"]["description"] = description + "\n" + SEARCH_DESCRIPTION
    return result


class SearchRawState:
    def __init__(self):
        self.attempted = set()

    def attach(self, h, result, *, round_no, call_id):
        result = deepcopy(result)
        parent = {"round": round_no, "tool_call_id": call_id,
                  "navigation_object": h.archive.put_json(result)}
        h.archive.append("search_raw_navigation", parent)

        def finish(status, *, evidence=None, selection=None, **details):
            state = {"version": RULE["version"], "status": status,
                     "attempts_used": len(self.attempted), "attempt_limit": 6, **details,
                     **({"selection": selection} if selection is not None else {})}
            result["raw_windows"] = [] if evidence is None else [{
                "evidence": evidence, "selection": selection,
                "kind": "harness_acquired_raw_window",
                "previously_received": evidence["ref"] in h.exposed,
                "source_query_index": 0, "source_document": evidence["document"]}]
            result["search_raw"] = state
            h.archive.append("search_raw_" + status, {**parent, **state,
                **({"evidence": evidence["ref"], "selection": selection} if evidence else {}),
                "result_object": h.archive.put_json(result)})
            return result, [] if evidence is None else [evidence["ref"]]

        batches = result.get("results", [])
        if not batches or not batches[0].get("hits"):
            return finish("skip", reason="first_query_no_hits")
        ref = batches[0]["hits"][0]["ref"]
        if ref in self.attempted:
            return finish("skip", reason="document_already_attempted", document=ref)
        if len(self.attempted) >= 6:
            return finish("skip", reason="document_attempt_limit", document=ref)
        try:
            h._time_check()
            cached = bool(h.archive.doc(ref)["snapshot"])
            if not cached and h.remaining()["backend_calls"] <= 0:
                return finish("skip", reason="backend_budget_no_snapshot", document=ref)
            self.attempted.add(ref)
            h.archive.append("search_raw_attempt", {**parent, "document": ref,
                "query_index": 0, "query": batches[0]["query"],
                "attempt_number": len(self.attempted), "snapshot_cached": cached})
            snapshot = h._snapshot(ref)
            selection = select_window(h.archive.get(snapshot), batches[0]["query"], min(h.config.read_chars, 3000))
            h._time_check()
            if not selection["matched"]:
                return finish("no_match", document=ref, selection=selection)
            view = h.archive.window(ref, selection["start"], selection["end"] - selection["start"])
            return finish("success", evidence=view, selection=selection, document=ref)
        except Exception as exc:
            code = exc.code if isinstance(exc, ContractError) else "search_raw_failure"
            h.archive.append("search_raw_error", {**parent, "document": ref,
                "code": code, "exception_type": type(exc).__name__,
                "attempts_used": len(self.attempted), "attempt_consumed": ref in self.attempted})
            raise ContractError(code, "Automatic search raw acquisition failed; no retry", fatal=True) from exc
