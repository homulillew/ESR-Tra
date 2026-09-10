"""One 2.1 decision loop with protected delivery and explicit request receipts."""
from types import SimpleNamespace
from copy import deepcopy
from .engine import Harness
from .context import visible_ids, visible_view
from .ledger import Ledger
from .protocol import Config, HarnessError, SCHEMA_VERSION, canonical, digest, obj, parse_object, string, validate

from .prompts import POLICY_PROMPT_VERSION, policy_system
from .tool_turn import NativeTurn, execute_turn, native_messages, recover_incomplete, undelivered, TOOL_TURN_VERSION


def messages_for(harness, client):
    system = {"role": "system", "content": policy_system(harness.config) + "\nTools:\n" + canonical(harness.available_tools())}
    limits = [0] if harness.config.mode == "baseline" else range(harness.config.recent_actions, -1, -1)
    for limit in limits:
        card = harness.context(limit)
        budget = getattr(client, "budget", None)
        if budget:
            card["budget"] = budget.summary()
        messages = [system, {"role": "user", "content": canonical(card)}]
        if harness.config.mode == "baseline":
            # Ordinary ReAct history, retained verbatim without state tables or model summaries.
            history = []
            rendered_views = {}
            for event in harness.actions:
                result = deepcopy(event["result"])
                if "observation" in result:
                    view = result["observation"]
                    oid = view["observation_id"]
                    if oid in rendered_views:
                        result["observation"] = {"observation_id": oid, "identical_body_at_action": rendered_views[oid]}
                    else:
                        result["observation"] = visible_view(view, harness.documents[view["docid"]]["title"])
                        rendered_views[oid] = event["action_id"]
                history.extend([{"role": "assistant", "content": canonical({"action": event["action"], "arguments": event["arguments"]})},
                                {"role": "user", "content": canonical(result)}])
            # Neutral initial metadata followed by chronological full actions/results. No duplicated bodies.
            initial = {"question": harness.question}
            current = {"remaining_actions": card["remaining_actions"], "budget": card.get("budget"),
                       "failed_proposal": card.get("failed_proposal")}
            messages = [system, {"role": "user", "content": canonical(initial)}, *history,
                        {"role": "user", "content": canonical(current)}]
        if hasattr(client, "context_status"):
            current_payload = parse_object(messages[-1]["content"])
            mapped = native_messages(harness, messages) if harness.config.max_tool_calls > 1 else messages
            current_payload["context_budget"] = client.context_status(mapped)
            if hasattr(client,'request_status') and client.request_status()['limit'] is not None:
                current_payload['remote_request_budget']=client.request_status()
            messages[-1]["content"] = canonical(current_payload)
        if harness.config.max_tool_calls > 1:
            messages = native_messages(harness, messages)
        if client.fits(messages):
            return messages
    raise HarnessError("context_overflow", "Required state, pending and latest result do not fit; none were dropped")


def run(harness, client):
    if harness.config.max_tool_calls > 1 and getattr(getattr(client, 'config', None), 'max_tool_calls', harness.config.max_tool_calls) != harness.config.max_tool_calls:
        raise ValueError('Policy adapter and harness tool-call limits differ')
    recover_incomplete(harness)
    def admissible(preview):
        try:
            messages = messages_for(preview, client)
            return client.fits_for_admission(messages) if hasattr(client, "fits_for_admission") else True
        except HarnessError as exc:
            if exc.code == "context_overflow":
                return False
            raise
    harness.admission = admissible
    while harness.terminal is None and harness.attempts < harness.config.max_actions:
        grouped_ids = set(harness.native_turns)
        legacy = [a for a in harness.actions if a['decision_id'] not in grouped_ids]
        # Grouped decisions use one error-stop unit; per-call failures remain in summary.
        # Native and text fallback order comes from journal events, never list concatenation.
        order = {e['decision_id']: i for i, e in enumerate(harness.ledger.events()) if e['type'] in {'decision', 'native_turn'}}
        entries = [(order.get(a['decision_id'], i), [a['result']]) for i, a in enumerate(legacy)]
        entries += [(order.get(t['decision_id'], t['sequence']), list(t['results'].values())) for t in harness.native_turns.values()]
        groups = [g for _, g in sorted(entries, key=lambda item: item[0])]
        errors = [g for g in groups if any(not r['ok'] for r in g)]
        consecutive=harness.config.max_consecutive_errors
        stop_reason=None
        if harness.config.max_execution_errors and len(errors) >= harness.config.max_execution_errors:
            stop_reason='total_execution_errors'
        elif consecutive and len(groups) >= consecutive and all(any(not r['ok'] for r in g) for g in groups[-consecutive:]):
            stop_reason='consecutive_execution_errors'
        elif harness.config.max_execution_errors and sum(r.get('error_code')=='audit_protocol_error' for g in groups for r in g)>=2:
            stop_reason='repeated_audit_protocol_failure'
        if stop_reason:
            harness.ledger.append({'type':'execution_stop','reason':stop_reason,
                                   'error_action_ids':[a['action_id'] for a in harness.actions if not a['result']['ok']],
                                   'error_decisions':len(errors)})
            harness.end('execution_error_limit')
            break
        decision_id = None
        action = None
        try:
            messages = messages_for(harness, client)
            ids = visible_ids(harness)
            turn_ids = [t['decision_id'] for t in undelivered(harness)]
            decision_id = f"d{len(harness.ledger.events()) + 1}"
            harness.ledger.append({"type": "decision", "decision_id": decision_id, "messages": messages,
                                   "compiler_version": TOOL_TURN_VERSION if harness.config.max_tool_calls > 1 else "workcard-2.1.5", "prompt_hash": digest(messages),
                                   "policy_prompt_version": POLICY_PROMPT_VERSION + ('+native-turn-1' if harness.config.max_tool_calls > 1 else ''),
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
                harness.record_exposure(ids, decision_id, "response_received" if received else "unknown", native_turn_ids=turn_ids)
                raise
            harness.record_exposure(ids, decision_id, native_turn_ids=turn_ids)
            if isinstance(text, NativeTurn):
                execute_turn(harness, text, decision_id)
                results = harness.native_turns[decision_id]['results'].values()
                fatal = next((r['error_code'] for r in results if not r['ok'] and r.get('error_code') in {'service_error', 'request_budget_exhausted', 'generation_budget_exhausted', 'budget_exhausted'}), None)
                if fatal and harness.terminal is None:
                    harness.end(fatal)
                continue
            # Preserve generated text even for injected clients that do not log API responses.
            harness.ledger.append({"type": "policy_output", "decision_id": decision_id, "text": text})
            action = parse_object(text)
            validate(action, obj({"action": string(64), "arguments": {"type": "object", "properties": {},
                                "required": [], "additionalProperties": True}}), "decision")
        except HarnessError as exc:
            if exc.code in {"context_overflow", "service_error", "generation_budget_exhausted",'request_budget_exhausted'}:
                harness.end(exc.code)
                break
            harness.record_protocol_error(str(exc), decision_id, exc.code, getattr(exc, "proposal", action))
            continue
        result = harness.execute(action["action"], action["arguments"], decision_id=decision_id)
        if not result["ok"] and result["error_code"] in {'generation_budget_exhausted','request_budget_exhausted','service_error'}:
            harness.end(result['error_code'])
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
    if harness.config.max_tool_calls > 1:
        turns = list(harness.native_turns.values())
        receipts = [r for t in turns for r in t['results'].values()]
        result['native_tools'] = {'contract': TOOL_TURN_VERSION, 'model_decisions':len(turns),
                                  'proposed_calls':sum(len(t['calls']) for t in turns), 'receipts':len(receipts),
                                  'not_executed':sum(r.get('execution')=='not_executed' for r in receipts),
                                  'unknown_outcomes':sum(r.get('execution')=='unknown' for r in receipts),
                                  'failed_calls':sum(not r['ok'] for r in receipts),
                                  'error_decisions':sum(any(not r['ok'] for r in t['results'].values()) for t in turns)}
        result['invalid_executed_actions'] = result['invalid_actions']
        result['invalid_actions'] = sum(not a['result']['ok'] for a in harness.actions if a['decision_id'] not in harness.native_turns) + sum(not r['ok'] for r in receipts)
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
