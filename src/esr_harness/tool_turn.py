"""Lossless native decisions, bounded retrieval scheduling and paired delivery.

One writer executes calls sequentially. A started call without a committed result
is uncertain on restart and is never automatically executed again.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from .protocol import HarnessError, canonical, validate
from .state import edit_focus

TOOL_TURN_VERSION = "native-retrieval-turn-1"
READ_TOOLS = {"search", "open_page", "read_evidence"}
RESERVED_RESULT_BYTES = 8192  # Admission estimate, not a bound on backend output.


@dataclass(frozen=True)
class NativeTurn:
    request_id: str
    content: list
    declared_tools: list

    @property
    def calls(self):
        if not isinstance(self.content, list) or any(not isinstance(b, dict) for b in self.content):
            raise HarnessError('protocol_error', 'Malformed native content blocks; raw response retained')
        return [deepcopy(b) for b in self.content if b.get("type") == "tool_use"]


def result_content(result):
    from .context import compact_result, visible_view
    rendered = compact_result(result)
    if result.get("observation"):
        rendered["observation"] = visible_view(result["observation"])
    return canonical(rendered)


def undelivered(h):
    return [t for t in h.native_turns.values() if not t["delivered"]]


def result_blocks(turn):
    blocks = []
    for i, call in enumerate(turn["calls"]):
        receipt = turn["results"].get(str(i))
        # Incomplete turns are rendered only by prospective admission, never sent.
        content = result_content(receipt) if receipt else canonical({"admission_reservation": "x" * RESERVED_RESULT_BYTES})
        blocks.append({"type": "tool_result", "tool_use_id": call["id"],
                       "is_error": not receipt["ok"] if receipt else True, "content": content})
    return blocks


def native_messages(h, messages):
    """Share one native encoder; preserve full baseline groups, current ESR groups."""
    turns = list(h.native_turns.values()) if h.config.mode == "baseline" else undelivered(h)
    if not turns:
        return messages
    if h.config.mode == "baseline":
        # Legacy text actions, if any, remain intact (fixtures and text fallback).
        paired = {t["decision_id"] for t in turns}
        result = [messages[0], {"role": "user", "content": canonical({"question": h.question})}]
        # Merge legacy and native entries chronologically, keeping groups intact.
        entries = []
        for t in turns:
            entries.append((t["sequence"], [{"role": "assistant", "content": deepcopy(t["content"])},
                                           {"role": "user", "content": result_blocks(t)}]))
        for action in h.actions:
            if action["decision_id"] not in paired:
                sequence = next(i for i, e in enumerate(h.ledger.events()) if e.get("type") == "tool" and e["action_id"] == action["action_id"])
                entries.append((sequence, [{"role": "assistant", "content": canonical({"action": action["action"], "arguments": action["arguments"]})},
                                           {"role": "user", "content": result_content(action["result"])}]))
        for _, group in sorted(entries, key=lambda item: item[0]):
            result.extend(group)
        return result + [messages[-1]]
    card = json.loads(messages[-1]["content"])
    attached_ids = {r["observation"]["observation_id"] for t in turns for r in t["results"].values() if r.get("observation")}
    card["visible_evidence"] = [v for v in card["visible_evidence"] if v["observation_id"] not in attached_ids]
    card["evidence_in_tool_results"] = sorted(attached_ids)
    result = [messages[0], {"role": "user", "content": canonical(card)}]
    for t in turns:
        result += [{"role": "assistant", "content": deepcopy(t["content"])},
                   {"role": "user", "content": result_blocks(t)}]
    return result


def error(code, message, *, execution="not_executed"):
    return {"ok": False, "error_code": code, "error": message, "execution": execution}


def prepare(h, turn):
    calls = turn.calls
    ids = [c.get("id") for c in calls]
    if not calls or any(not isinstance(i, str) or not i or len(i) > 256 for i in ids) or len(set(ids)) != len(ids):
        exc = HarnessError("protocol_error", "Native tool IDs must be nonempty, unique strings; no call executed")
        exc.proposal = {"native_tool_calls": calls}
        raise exc
    if len(calls) > h.config.max_tool_calls:
        problem = error("batch_limit", f"At most {h.config.max_tool_calls} calls per decision; resend a bounded group")
        return calls, [(None, problem) for c in calls]
    if len(calls) > 1 and any(c.get("name") not in READ_TOOLS for c in calls):
        problem = error("serial_action_required", "A multi-call group permits only independent search/open_page/read_evidence. State updates, audit and ending require their own decision.")
        return calls, [(None, problem) for c in calls]
    declared = {t["name"] for t in turn.declared_tools}
    plan = []
    explicit = []
    for call in calls:
        name, args = call.get("name"), deepcopy(call.get("input"))
        try:
            if name not in declared:
                raise HarnessError("protocol_error", "Tool was not offered in this decision")
            if name == "update_state" and isinstance(args, dict):
                core = {k: v for k, v in args.items() if k not in {"attempt_note", "attempt_id"}}
                validate(core, {**h.config.tool_schema(name), "minProperties": 0})
            else:
                validate(args, h.config.tool_schema(name))
            if len(calls) > 1:
                if name == "search" and args.get("focus") is not None:
                    explicit.append(edit_focus(h.state, args["focus"])["focus"])
                if name == "open_page":
                    parent = args.get("search_action_id") or next((sid for sid, s in reversed(list(h.searches.items())) if args["docid"] in {r["docid"] for r in s["hits"]}), None)
                    if parent not in h.searches or args["docid"] not in {r["docid"] for r in h.searches[parent]["hits"]}:
                        raise HarnessError("unexposed_reference", "Open must refer to a search hit known before this decision")
                    args["search_action_id"] = parent
                if name == "read_evidence" and args.get("observation_id") not in h.observations and "directory_cursor" not in args:
                    raise HarnessError("unexposed_reference", "Read must refer to an observation known before this decision")
            plan.append((args, None))
        except HarnessError as exc:
            plan.append((None, error(exc.code, str(exc))))
    if explicit and any(f != explicit[0] for f in explicit):
        problem = error("batch_focus_conflict", "Searches in one group must use the same focus; choose separate decisions for different focus edits")
        return calls, [(None, problem) for c in calls]
    # A leading explicit focus can be inherited, matching sequential single calls;
    # a later focus change cannot silently reattribute an earlier read/search.
    if explicit:
        focus = h.state["focus"]
        scopes = []
        for c, (args, failure) in zip(calls, plan):
            if failure:
                continue
            if c["name"] == "search" and args.get("focus") is not None:
                focus = args["focus"]
            scopes.append(focus)
        if any(f != scopes[0] for f in scopes):
            return calls, [(None, error("batch_focus_conflict", "Group changes focus after an earlier call; split the decisions")) for c in calls]
    return calls, plan


def execute_turn(h, turn, decision_id):
    if decision_id in h.native_turns:
        raise ValueError('Decision already journaled; recover existing records instead of executing again')
    calls, plan = prepare(h, turn)
    h._commit({"type": "native_turn", "decision_id": decision_id, "request_id": turn.request_id,
               "content": deepcopy(turn.content), "calls": calls, "version": TOOL_TURN_VERSION,
               "sequence": len(h.ledger.events())})
    # Admission reserves the complete group, including not-yet-produced results.
    blocked = None
    pending_add = set()
    possible_new_views = 0
    cited = {o for c in h.state['claims'] for o in c['observation_ids']}
    for call, (args, failure) in zip(calls, plan):
        if failure:
            continue
        if call['name'] == 'open_page':
            possible_new_views += 1  # Conservatively reserve even if a duplicate is possible.
        elif call['name'] == 'read_evidence' and args.get('observation_id') is not None:
            oid = args['observation_id']
            if oid not in cited | h.pending:
                pending_add.add(oid)
    if len(calls) > h.config.max_actions - h.attempts:
        blocked = error("budget_exhausted", "Insufficient action slots for this entire group")
    elif len(calls) > 1 and len(h.pending) + possible_new_views + len(pending_add) > h.config.max_pending_views:
        blocked = error('context_capacity', 'Insufficient pending-view slots for this entire group; process existing views or request fewer calls')
    elif h.admission and not h.admission(h):
        blocked = error("context_capacity", "Entire group and result reservations do not fit; request fewer calls")
    for i, (call, (args, failure)) in enumerate(zip(calls, plan)):
        rejected = blocked or failure
        if rejected:
            h._commit({"type": "native_result", "decision_id": decision_id, "index": i, "result": deepcopy(rejected)})
            continue
        h._commit({"type": "native_call_started", "decision_id": decision_id, "index": i})
        h.native_active = (decision_id, i)
        try:
            result = h.execute(call["name"], args, decision_id=decision_id)
        except Exception as exc:
            # Do not log exception text (could contain credentials or request headers).
            result = error("service_error", f"Tool raised {type(exc).__name__}; outcome unknown, not retried", execution="unknown")
            h._commit({"type": "native_result", "decision_id": decision_id, "index": i, "result": result})
        finally:
            h.native_active = None
        if str(i) not in h.native_turns[decision_id]["results"]:
            h._commit({"type": "native_result", "decision_id": decision_id, "index": i, "result": result})
        if not result["ok"] and result.get("error_code") in {"service_error", "context_capacity", "request_budget_exhausted", "generation_budget_exhausted", "budget_exhausted"}:
            blocked = error("previous_call_failed", "Not executed after a capacity, budget or uncertain service failure")
    h._commit({"type": "native_turn_complete", "decision_id": decision_id})


def recover_incomplete(h):
    for t in list(h.native_turns.values()):
        if t["complete"]:
            continue
        for i in range(len(t["calls"])):
            if str(i) not in t["results"]:
                started = i in t["started"]
                h._commit({"type": "native_result", "decision_id": t["decision_id"], "index": i,
                           "result": error("interrupted_tool_turn", "Interrupted group; no automatic replay", execution="unknown" if started else "not_executed")})
        h._commit({"type": "native_turn_complete", "decision_id": t["decision_id"]})
        if h.terminal is None:
            h.end("service_error")
    # A crash can also happen after provider dispatch/response but before the
    # parsed native turn is committed. Stop with the raw receipt; do not sample
    # the same decision again or infer exposure from an unfinished execution.
    events = h.ledger.events()
    decisions = [(i, e) for i, e in enumerate(events) if e['type'] == 'decision']
    if decisions and h.terminal is None:
        index, decision = decisions[-1]
        handled = any(e['type'] in {'tool', 'native_turn'} and e.get('decision_id') == decision['decision_id'] for e in events[index+1:])
        if not handled:
            h.ledger.append({'type':'interrupted_decision','decision_id':decision['decision_id'], 'automatic_retry':False})
            h.end('service_error')
