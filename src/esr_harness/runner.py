"""One 2.1 decision loop with protected delivery and explicit request receipts."""
from types import SimpleNamespace
from .engine import Harness
from .context import visible_ids
from .ledger import Ledger
from .protocol import Config, HarnessError, SCHEMA_VERSION, canonical, digest, obj, parse_object, string, validate

from .prompts import POLICY_PROMPT_VERSION, policy_system


def messages_for(harness, client):
    system = {"role": "system", "content": policy_system(harness.config) + "\nTools:\n" + canonical(harness.available_tools())}
    for limit in range(harness.config.recent_actions, -1, -1):
        card = harness.context(limit)
        budget = getattr(client, "budget", None)
        if budget:
            card["budget"] = budget.summary()
        messages = [system, {"role": "user", "content": canonical(card)}]
        if harness.config.mode == "baseline":
            # Ordinary ReAct history, retained verbatim without state tables or model summaries.
            history = []
            for event in harness.actions:
                history.extend([{"role": "assistant", "content": canonical({"action": event["action"], "arguments": event["arguments"]})},
                                {"role": "user", "content": canonical(event["result"])}])
            # Neutral initial metadata followed by chronological full actions/results. No duplicated bodies.
            initial = {"question": harness.question}
            current = {"remaining_actions": card["remaining_actions"], "budget": card.get("budget"),
                       "failed_proposal": card.get("failed_proposal")}
            messages = [system, {"role": "user", "content": canonical(initial)}, *history,
                        {"role": "user", "content": canonical(current)}]
        if client.fits(messages):
            return messages
    raise HarnessError("context_overflow", "Required state, pending and latest result do not fit; none were dropped")


def run(harness, client):
    def admissible(preview):
        try:
            messages_for(preview, client)
            return True
        except HarnessError as exc:
            if exc.code == "context_overflow":
                return False
            raise
    harness.admission = admissible
    while harness.terminal is None and harness.attempts < harness.config.max_actions:
        decision_id = None
        action = None
        try:
            messages = messages_for(harness, client)
            ids = visible_ids(harness)
            decision_id = f"d{len(harness.ledger.events()) + 1}"
            harness.ledger.append({"type": "decision", "decision_id": decision_id, "messages": messages,
                                   "compiler_version": "workcard-2.1.4", "prompt_hash": digest(messages),
                                   "policy_prompt_version": POLICY_PROMPT_VERSION,
                                   "policy_system_hash": digest(messages[0]["content"]),
                                   "visible_observation_ids": ids,
                                   "state_version": harness.state["research_version"],
                                   "client": getattr(client, "identity", {"fixture": type(client).__name__})})
            before = len(harness.ledger.events())
            try:
                text = client.complete(messages, purpose="policy")
            except HarnessError:
                events = harness.ledger.events()[before:]
                received = any(e.get("type") == "generation" and "response" in e for e in events)
                harness.record_exposure(ids, decision_id, "response_received" if received else "unknown")
                raise
            harness.record_exposure(ids, decision_id)
            # Preserve generated text even for injected clients that do not log API responses.
            harness.ledger.append({"type": "policy_output", "decision_id": decision_id, "text": text})
            action = parse_object(text)
            validate(action, obj({"action": string(64), "arguments": {"type": "object", "properties": {},
                                "required": [], "additionalProperties": True}}), "decision")
        except HarnessError as exc:
            if exc.code in {"context_overflow", "service_error", "generation_budget_exhausted"}:
                harness.end(exc.code)
                break
            harness.record_protocol_error(str(exc), decision_id, exc.code, getattr(exc, "proposal", action))
            continue
        result = harness.execute(action["action"], action["arguments"], decision_id=decision_id)
        if not result["ok"] and result["error_code"] == "generation_budget_exhausted":
            harness.end("generation_budget_exhausted")
    if harness.terminal is None:
        harness.end("budget_exhausted")
    return summary(harness, getattr(client, "budget", None))


def summary(harness, budget=None):
    # v2 objects are dispatched by replay rather than reinterpreted with 2.1 semantics.
    if harness.ledger.header.get("schema_version") == 2:
        from .v2.runner import summary as old_summary
        return old_summary(harness, budget)
    counts = {n: sum(a["action"] == n for a in harness.actions) for n in sorted({a["action"] for a in harness.actions})}
    result = {"contract": "2.1", "terminal": harness.terminal, "final_state": harness.state,
              "attempts": harness.attempts, "tool_calls": counts,
              "invalid_actions": sum(not a["result"]["ok"] for a in harness.actions),
              "documents": len(harness.documents), "observation_views": len(harness.observations),
              "exposed_observations": len(harness.exposed),
              "search_cache_hits": sum(bool(s["cache_source"]) for s in harness.searches.values()),
              "audit_cache_hits": sum(a["action"] == "verify_answer" and bool(a["result"].get("cached")) for a in harness.actions),
              "evidence_repairs": sum(len(a["result"].get("evidence_repair_ids", [])) for a in harness.actions),
              "candidate_revisions": sum(bool(a["delta"].get("changes", {}).get("candidate_revision")) for a in harness.actions),
              "manifest": harness.ledger.header}
    if budget:
        result["usage"] = budget.summary()
    return result


def replay(path):
    ledger = Ledger(path, readonly=True)
    header = ledger.header
    if header.get("schema_version") == 2:
        ledger.close()
        from .v2.runner import replay as replay_v2
        return replay_v2(path)
    if header.get("schema_version") != SCHEMA_VERSION:
        ledger.close()
        raise ValueError("Unsupported ledger schema; no auto-migration")
    def unavailable(*a, **k):
        raise RuntimeError("Read-only replay cannot invoke services")
    retriever = SimpleNamespace(identity=header["retriever"], search=unavailable, get_document=unavailable)
    auditor = SimpleNamespace(identity=header["auditor"], audit=unavailable) if header["auditor"] else None
    harness = Harness(header["question"], retriever, auditor, config=Config(**header["config"]), ledger=ledger, manifest=header["manifest"])
    harness.readonly = True
    return harness
