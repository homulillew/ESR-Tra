"""Whole native result groups, original question, optional current notes; no summary LLM."""
from __future__ import annotations

from copy import deepcopy

from .contract import SYSTEM, ContractError, canonical, tools


def build(harness, model, counter, *, final: bool, output_limit: int, groups=None):
    config = harness.config
    history = list(harness.groups if groups is None else groups)
    active_notes = sorted(harness.notes.values(), key=lambda n: n["order"])
    nav = list(harness.doc_order)[-16:]
    feedback = harness.feedback
    repair = deepcopy(harness.repair)
    compacted = False
    while True:
        documents = []
        for ref in nav:
            doc = harness.archive.doc(ref)
            ranges = [harness.archive.evidence(e) for e in harness.evidence_order
                      if harness.archive.evidence(e)["document"] == ref][-4:]
            documents.append({"ref": ref, "title": doc["title"][:160], "read_ranges": [
                {"ref": v["ref"], "start": v["start"], "end": v["end"]} for v in ranges]})
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": harness.question}]
        visible, issued = set(), list(nav)
        for group in history:
            messages.extend(group["messages"])
            visible.update(group["evidence"])
            issued.extend(r for r in group["documents"] if r not in issued)
        scope = {"phase": "FINAL" if final else "RESEARCH", "remaining": harness.remaining(),
                 "current_notes_not_evidence": active_notes, "recent_document_index_not_evidence": documents,
                 "feedback": feedback, "uncommitted_response_not_evidence": repair, "literal_answer_contract": {
                    "prefix": config.answer_prefix, "suffix": config.answer_suffix,
                    "origin": "explicit experiment configuration, not inferred from question"},
                 "instruction": ("Only finish is available. Submit an explicit answer with delivered evidence or abstain."
                                 if final else "Read only useful passages. Notes and all-page cleanup are optional.")}
        messages.append({"role": "user", "content": "Current control state (data, not source evidence):\n" + canonical(scope)})
        wire = model.prepare(messages, tools(notes_enabled=config.notes_enabled, final=final, query_limit=config.max_queries_per_search), output_limit)
        size = counter(wire)
        if type(size) is not int or size < 0:
            raise ContractError("counter_error", "Counter returned an invalid size", fatal=True)
        if size + config.response_reserve <= config.context_limit:
            return {"wire": wire, "visible": sorted(visible, key=lambda r: int(r[1:])), "documents": issued,
                    "compacted": compacted, "groups": history, "capacity": size, "final": final,
                    "rendered_note_keys": [n["key"] for n in active_notes]}
        if config.context_mode == "full":
            raise ContractError("context_capacity", "Full-history arm cannot fit its actual wire request", fatal=True)
        compacted = True
        if len(history) > config.recent_groups:
            history = history[-config.recent_groups:]
        elif len(history) > 1:
            history.pop(0)
        elif nav:
            nav.pop(0)
        elif active_notes:
            active_notes.pop(0)
        elif repair and repair.get("preview"):
            # Keep a pointer/hash, not an invisible fabricated transcript.
            repair.update(preview="", truncated=True, omitted_for_capacity=True)
        else:
            # Never discard the newest tool group and claim that it was read.
            raise ContractError("context_capacity", "Original question and newest complete result group cannot fit", fatal=True)
