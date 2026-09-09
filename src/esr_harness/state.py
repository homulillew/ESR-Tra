"""Pure local state transactions. No I/O, no judge, no implicit success labels."""
from copy import deepcopy
from .protocol import HarnessError, STATE_SCHEMA, digest, validate


def initial_state(question):
    return {"research_version": 0, "target": question, "answer": None,
            "claims": [{"claim_id": "c0", "requirement": question, "finding": "", "observation_ids": []}],
            "focus": {"claim_id": "c0", "need": question if len(question) <= 1000 else
                      "Find evidence for the original question recorded in target and c0.requirement."}}


def candidate_scope(state):
    return digest({"target": state["target"], "answer": state["answer"]})


def purpose(state):
    if state["focus"] is None:
        raise HarnessError("focus_required", "Select a focus on an existing claim before researching")
    focus = state["focus"]
    claim = next(c for c in state["claims"] if c["claim_id"] == focus["claim_id"])
    return {**deepcopy(focus), "candidate_scope": candidate_scope(state),
            "requirement": claim["requirement"],
            "gap_key": digest([claim["claim_id"], claim["requirement"], candidate_scope(state)])}


def edit_focus(state, focus):
    result = deepcopy(state)
    if focus is not None:
        if focus["claim_id"] not in {c["claim_id"] for c in state["claims"]}:
            raise HarnessError("protocol_error", "focus must use an already issued active claim ID")
        focus = {"claim_id": focus["claim_id"], "need": focus["need"].strip()}
    if focus != state["focus"]:
        result["focus"] = deepcopy(focus)
        result["research_version"] += 1
    return result


def apply_delta(state, patch, *, next_claim, exposed_ids, observations):
    result = deepcopy(state)
    old = {c["claim_id"]: c for c in state["claims"]}
    claims = deepcopy(old)
    reason = patch.get("revision_reason", "").strip()
    changes = {"candidate_revision": False, "requirement_revision": [], "working_updates": [],
               "retired_claim_ids": [], "added_claim_ids": []}
    if "target" in patch:
        result["target"] = patch["target"].strip()
        if result["target"] != state["target"] and not reason:
            raise HarnessError("protocol_error", "Changing target requires revision_reason")
    if "answer" in patch:
        result["answer"] = patch["answer"].strip() if patch["answer"] is not None else None
    touched = set()
    for change in patch.get("claim_updates", []):
        if ("finding" in change) != ("observation_ids" in change):
            raise HarnessError("protocol_error", "Pair finding with observation_ids; no implicit stale sources")
        cid = change.get("claim_id")
        if cid is not None:
            if cid not in old or cid in touched:
                raise HarnessError("protocol_error", "Update only an existing claim once; new IDs are returned next turn")
        else:
            if not change.get("requirement"):
                raise HarnessError("protocol_error", "New claim requires requirement, not a guessed ID")
            cid = f"c{next_claim}"
            next_claim += 1
            claims[cid] = {"claim_id": cid, "requirement": change["requirement"].strip(),
                           "finding": "", "observation_ids": []}
            changes["added_claim_ids"].append(cid)
        touched.add(cid)
        if "requirement" in change:
            requirement = " ".join(change["requirement"].split())
            if cid in old and requirement != old[cid]["requirement"]:
                if not reason:
                    raise HarnessError("protocol_error", "Changing a requirement needs revision_reason")
                changes["requirement_revision"].append(cid)
            claims[cid]["requirement"] = requirement
        if "finding" in change:
            text, ids = change["finding"].strip(), sorted(change["observation_ids"])
            if text and not ids:
                raise HarnessError("protocol_error", "Nonempty finding requires exposed source observations")
            if not set(ids) <= exposed_ids or not set(ids) <= set(observations):
                raise HarnessError("unexposed_reference", "Findings may cite only observations delivered to the policy")
            claims[cid].update(finding=text, observation_ids=ids)
            if cid not in old or claims[cid] != old[cid]:
                changes["working_updates"].append(cid)
    retired = set(patch.get("retire_claim_ids", []))
    if retired:
        if not reason or not retired <= set(old) or retired & touched:
            raise HarnessError("protocol_error", "Retirement requires reason and old, non-updated IDs")
        for cid in retired:
            del claims[cid]
        changes["retired_claim_ids"] = sorted(retired)
    if not claims:
        raise HarnessError("protocol_error", "Cannot retire the last requirement")
    result["claims"] = sorted(claims.values(), key=lambda c: int(c["claim_id"][1:]))
    if "focus" in patch:
        focus = patch["focus"]
        if focus is not None and focus["claim_id"] not in old:
            raise HarnessError("protocol_error", "New claim IDs are usable only after receiving this response")
        result["focus"] = deepcopy(focus)
    if result["focus"] is not None:
        if result["focus"]["claim_id"] not in claims:
            raise HarnessError("protocol_error", "Retiring active focus requires another focus or explicit null")
        result["focus"]["need"] = result["focus"]["need"].strip()
    cited = {o for c in result["claims"] for o in c["observation_ids"]}
    dismissed = set(patch.get("dismiss_observation_ids", []))
    if not dismissed <= set(observations):
        raise HarnessError("protocol_error", "arguments.dismiss_observation_ids: unknown observation IDs " + str(sorted(dismissed-set(observations))))
    if cited & dismissed:
        raise HarnessError("protocol_error", "arguments.dismiss_observation_ids: remove cited IDs " + str(sorted(cited & dismissed)) +
                           " from the dismiss list. Citation already consumes these views. No research edits were committed; resend the proposal with this field corrected.")
    validate({k: v for k, v in result.items() if k != "research_version"}, STATE_SCHEMA, "state")
    changed = result != state
    result["research_version"] += int(changed)
    changes["candidate_revision"] = candidate_scope(result) != candidate_scope(state)
    return result, next_claim, changes, cited | dismissed
