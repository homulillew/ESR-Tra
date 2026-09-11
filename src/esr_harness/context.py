"""Deterministic work-card rendering; archive size is not prompt size."""
from copy import deepcopy
from .state import candidate_scope
from .prompts import PENDING_GUIDANCE, STAGNATION_GUIDANCE


def visible_ids(harness):
    ids = set(harness.pending)
    for turn in harness.native_turns.values():
        if not turn['delivered']:
            ids.update(r['observation']['observation_id'] for r in turn['results'].values() if r.get('observation'))
    latest = harness.latest_result or {}
    if latest.get("observation"):
        ids.add(latest["observation"]["observation_id"])
    return sorted(ids, key=lambda x: int(x[1:]))


def visible_view(view, title=""):
    return {"observation_id": view["observation_id"], "docid": view["docid"], "title": title,
            "text": view["text"], "spans": view["spans"], "document_chars": view["document_chars"],
            "fully_visible": view["fully_visible"], "source": view["source"], "fallback": view["fallback"]}


def compact_result(result):
    result = deepcopy(result)
    if "observation" in result:
        result["observation"] = {"observation_id": result["observation"]["observation_id"],
                                 "body_location": "visible_evidence"}
    if "results" in result:
        # Snippets are navigation only; disclose snippet shortening, retain every hit ID.
        result["results"] = [{"docid": r["docid"], "title": r["title"][:200], "score": r["score"],
                              "snippet": r["snippet"][:300], "snippet_shortened": len(r["snippet"]) > 300}
                             for r in result["results"]]
    if "audit" in result:
        audit = result.pop("audit")
        result["audit_summary"] = {"status": audit["status"], "unresolved_ids": audit["unresolved_ids"]}
    return result


def attempt_cards(harness):
    focus = harness.state["focus"]
    notes = {a["delta"]["attempt_note"]["attempt_id"]: a["delta"]["attempt_note"]["text"]
             for a in harness.actions if "attempt_note" in a["delta"]}
    selected = [(sid, s) for sid, s in harness.searches.items()
                if focus is None or (s["purpose"] and s["purpose"]["claim_id"] == focus["claim_id"])]
    cards = []
    for sid, s in selected[-2:]:
        opened = [a for a in harness.actions if a["result"].get("retrieval_parent") == sid]
        cards.append({"attempt_id": sid, "query": s["query"], "need_at_search": (s["purpose"] or {}).get("need"),
                      "same_candidate_scope": (s["purpose"] or {}).get("candidate_scope") == candidate_scope(harness.state),
                      "cache_source": s["cache_source"], "new_hit_docids": s["new_hit_docids"],
                      "unopened_hits": [{"docid": r["docid"], "title": r["title"][:200]} for r in s["hits"]
                                        if r["docid"] not in harness.documents][:harness.config.directory_page_size],
                      "opened_view_ids": [a["result"]["observation"]["observation_id"] for a in opened],
                      "new_raw_chars": sum(a["delta"].get("new_chars", 0) for a in opened),
                      "actor_report_not_verified": notes.get(sid)})
    return cards


def audit_card(report):
    """Bound diagnostic verbosity, not source evidence. Full reports remain in the ledger."""
    def row(v):
        return {"status": v["status"], "reason": v["reason"][:240], "need": v["need"][:500],
                "diagnostic_shortened": len(v["reason"]) > 240 or len(v["need"]) > 500}
    return {"target": row(report["target"]), "coverage": row(report["coverage"]),
            "claims": [{"claim_id": c["claim_id"], **row(c),
                        "witness_observation_ids": sorted({q["observation_id"] for q in c["quotes"]})}
                       for c in report["claims"]]}


def workcard(harness, recent_limit=None):
    limit = harness.config.recent_actions if recent_limit is None else recent_limit
    ids = visible_ids(harness)
    views = [visible_view(harness.observations[o], harness.documents[harness.observations[o]["docid"]]["title"]) for o in ids]
    audit = harness.current_audit
    recent = harness.actions[-limit:] if limit else []
    latest_id = harness.actions[-1]["action_id"] if harness.actions else None
    directory_ids = list(harness.observations)[-harness.config.directory_page_size:]
    scope = candidate_scope(harness.state)
    conflicts = [{"claim_id": c["claim_id"], "answer": c["answer"], "requirement": c["requirement"],
                  "witness_observation_ids": sorted({q["observation_id"] for q in c["quotes"]}),
                  "quote_excerpt": c["quotes"][0]["quote"][:240], "label": "Previously reported conflict; re-check raw evidence"}
                 for c in harness.conflicts.values() if c["scope"] == scope]
    guidance = []
    if harness.pending and harness.config.mode == "esr":
        guidance.append(PENDING_GUIDANCE)
    searches = list(harness.searches.values())[-harness.config.stagnant_after:]
    if len(searches) >= harness.config.stagnant_after and all(not s["new_hit_docids"] for s in searches):
        guidance.append(STAGNATION_GUIDANCE)
    previous = None
    if harness.last_audit and audit is None:
        previous = {"answer_at_audit": harness.last_audit["answer"],
                    "diagnostics": audit_card(harness.last_audit["report"]),
                    "unresolved_ids": harness.last_audit["unresolved_ids"], "label": "STALE, not current verdict"}
    state = {k: deepcopy(v) for k, v in harness.state.items() if k != "research_version"}
    failed = harness.actions[-1] if harness.actions and not harness.actions[-1]["result"]["ok"] else None
    recovery = None
    if failed:
        prior = harness.actions[-2] if len(harness.actions) > 1 else None
        recovery = {"action_id": failed["action_id"], "action": failed["action"],
                    "arguments": deepcopy(failed["arguments"]), "error": deepcopy(failed["result"]),
                    "instruction": "Repair the identified field once, preserving valid research content. Do not guess evidence IDs.",
                    "local_repair_available": not (prior and not prior["result"]["ok"] and prior["action"] == failed["action"])}
    return {"question": harness.question, "mode": harness.config.mode, "audit_mode": harness.config.audit_mode,
            "action_readiness": harness.readiness(), "failed_proposal": recovery,
            "state": state if harness.config.mode == "esr" else None,
            "finding_scope_stale_ids": [cid for cid, s in harness.finding_scopes.items() if s != scope],
            "current_audit": audit_card(audit["report"]) if audit else None, "previous_issues": previous,
            "known_conflicts": conflicts[-8:], "known_conflict_count": len(conflicts), "focus_attempts": attempt_cards(harness) if harness.config.mode == "esr" else [],
            "pending_ids": sorted(harness.pending), "visible_evidence": views,
            "latest_tool_result": compact_result(harness.latest_result) if harness.latest_result else None,
            "recent_actions": [{"action_id": a["action_id"], "action": a["action"],
                                "ok": a["result"]["ok"], "error_code": a["result"].get("error_code")}
                               for a in recent if a["action_id"] != latest_id],
            "archive": {"count": len(harness.observations), "directory_cursor": "start",
                        "recent_views": [{"observation_id": o, "docid": harness.observations[o]["docid"],
                                          "title": harness.documents[harness.observations[o]["docid"]]["title"][:200]}
                                         for o in directory_ids]},
            "remaining_actions": harness.config.max_actions - harness.attempts, "guidance": guidance}
