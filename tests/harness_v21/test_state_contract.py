from copy import deepcopy
import pytest
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config, HarnessError, SCHEMAS, STATE_SCHEMA, validate
from esr_harness.state import candidate_scope
from .helpers import env, opened, update


def test_bootstrap_can_research_without_answer():
    h=env(); assert h.state["answer"] is None
    assert h.state["focus"]["claim_id"] == "c0"
    assert h.execute("search", {"query": "Mira"})["ok"]


def test_local_delta_preserves_unmodified_fields():
    h=env(); o=opened(h)
    r=h.execute("update_state", {"claim_updates": [{"requirement": "second relationship"}]})
    assert r["added_claim_ids"] == ["c1"]
    old=deepcopy(h.state)
    assert update(h,o)["ok"]
    assert h.state["target"] == old["target"] and h.state["claims"][1] == old["claims"][1]

@pytest.mark.parametrize("patch", [
    {"claim_updates": [{"claim_id":"c0","finding":"x"}]},
    {"claim_updates": [{"claim_id":"c0","observation_ids":[]}]},
    {"claim_updates": [{"claim_id":"c0","finding":"x","observation_ids":[]}]},
    {"claim_updates": [{"claim_id":"c99","finding":"x","observation_ids":["o1"]}]},
    {"claim_updates": [{"finding":"new claim without requirement","observation_ids":["o1"]}]},
    {"claim_updates": [{"requirement":"new"}], "focus":{"claim_id":"c1","need":"not issued yet"}},
    {"retire_claim_ids":["c0"],"revision_reason":"all removed"},
    {"target":"different"}, {"answer_kind":"abstain"}, {"supported":True}, {},
])
def test_bad_delta_is_atomic(patch):
    h=env(); opened(h); before=deepcopy(h.state); n=h.next_claim
    assert not h.execute("update_state",patch)["ok"]
    assert h.state == before and h.next_claim == n


def test_unexposed_references_are_not_facts():
    h=env(); o=opened(h,expose=False)
    assert update(h,o)["error_code"] == "unexposed_reference"
    h.record_exposure([o],"delivered")
    assert update(h,o)["ok"]


def test_failed_delivery_does_not_grant_reference():
    h=env(); o=opened(h,expose=False)
    h.record_exposure([o],"timeout", "unknown")
    assert update(h,o)["error_code"] == "unexposed_reference"


def test_noop_and_focus_do_not_invalidate_audit():
    h=env(); update(h,opened(h)); first=h.execute("verify_answer")["audit"]
    version=h.state["research_version"]
    assert update(h)["noop"] and h.state["research_version"]==version
    h.execute("update_state", {"focus":{"claim_id":"c0","need":"Look at another route"}})
    assert h.current_audit["fingerprint"] == first["fingerprint"]
    assert h.execute("verify_answer")["cached"] and len(h.auditor.inputs)==1


def test_finding_changes_invalidate_audit():
    h=env(); update(h,opened(h)); h.execute("verify_answer")
    h.execute("update_state", {"claim_updates":[{"claim_id":"c0","finding":"A corrected relation","observation_ids":["o1"]}]})
    assert h.current_audit is None


def test_candidate_withdrawal_preserves_findings():
    h=env(); update(h,opened(h)); old=deepcopy(h.state["claims"])
    r=h.execute("update_state",{"answer":None})
    assert r["changes"]["candidate_revision"] and h.state["answer"] is None and h.state["claims"]==old


def test_new_ids_never_reuse_retired_ids():
    h=env(); h.execute("update_state",{"claim_updates":[{"requirement":"second"}]})
    assert h.execute("update_state",{"retire_claim_ids":["c1"],"revision_reason":"wrong decomposition"})["ok"]
    r=h.execute("update_state",{"claim_updates":[{"requirement":"third"}]})
    assert r["added_claim_ids"]==["c2"]


def test_retire_focus_must_select_issued_other_or_null():
    h=env(); h.execute("update_state",{"claim_updates":[{"requirement":"other"}]})
    assert not h.execute("update_state",{"retire_claim_ids":["c0"],"revision_reason":"revise"})["ok"]
    assert h.execute("update_state",{"retire_claim_ids":["c0"],"revision_reason":"revise","focus":None})["ok"]
    assert h.execute("search",{"query":"Lake"})["error_code"]=="focus_required"
    assert h.execute("search",{"query":"Lake","focus":{"claim_id":"c1","need":"Find other fact"}})["ok"]


def test_partial_audit_target_stays_unknown():
    h=env(); update(h,opened(h),answer=None)
    a=h.execute("verify_answer"); assert a["ok"] and a["audit"]["status"]=="unknown"
    assert a["audit"]["report"]["claims"][0]["status"]=="supported"
    assert not h.execute("submit_answer")["ok"]


def test_same_candidate_evidence_repair_vs_candidate_revision():
    h=env(); update(h,opened(h)); h.auditor.value="unknown"; h.execute("verify_answer")
    h.execute("update_state",{"claim_updates":[{"claim_id":"c0","finding":"Better extracted relation","observation_ids":["o1"]}]})
    h.auditor.value="supported"; assert h.execute("verify_answer")["evidence_repair_ids"]==["c0"]
    assert "evidence_repair_ids" not in h.execute("verify_answer")
    h.execute("update_state",{"answer":"Mira"}); h.auditor.value="unknown"; h.execute("verify_answer")
    h.execute("update_state",{"answer":"Robin"}); h.auditor.value="supported"
    assert h.execute("verify_answer")["evidence_repair_ids"]==[]


def test_requirement_revision_is_not_repair():
    h=env(); update(h,opened(h)); h.auditor.value="unknown"; h.execute("verify_answer")
    h.execute("update_state",{"claim_updates":[{"claim_id":"c0","requirement":"Changed question interpretation"}],"revision_reason":"incorrect decomposition"})
    h.auditor.value="supported"; assert h.execute("verify_answer")["evidence_repair_ids"]==[]


def test_conflict_evidence_cannot_be_erased_by_dropping_link():
    h=env(); update(h,opened(h)); h.auditor.value="contradicted"; h.execute("verify_answer")
    assert h.current_audit is not None  # Recording witnesses must not invalidate its own audit.
    h.execute("update_state",{"claim_updates":[{"claim_id":"c0","finding":"","observation_ids":[]}]})
    assert h.audit_packet()["claims"][0]["observation_ids"]==["o1"]
    h.execute("verify_answer"); assert h.auditor.inputs[-1][2][0]["observation_id"]=="o1"
    h.execute("update_state",{"answer":"New candidate"})
    assert h.audit_packet()["claims"][0]["observation_ids"]==[]
    h.execute("update_state",{"answer":"Taylor"})
    assert h.audit_packet()["claims"][0]["observation_ids"]==["o1"]

@pytest.mark.parametrize("mode,allowed",[("hard",False),("soft",True),("off",True)])
def test_gate_modes_keep_true_label(mode,allowed):
    h=env(config=Config(audit_mode=mode)); update(h,opened(h)); h.auditor.value="unknown"
    if mode!="off": h.execute("verify_answer")
    r=h.execute("submit_answer"); assert r["ok"]==allowed
    if allowed: assert r["terminal"]["evidence_status"] == ("unverified" if mode=="off" else "unknown")


def test_abstain_preserves_draft_without_salvage():
    h=env(); update(h,opened(h)); r=h.execute("submit_answer",{"decision":"abstain","reason":"not enough evidence"})
    assert r["terminal"]["answer"]=="" and r["terminal"]["final_draft"]=="Taylor"

@pytest.mark.parametrize("action,args",[("submit_answer",{"answer":"bypass"}),("search",{"query":"x","top_k":True}),
                                       ("open_page",{"docid":"d1","query":"x","offset":0}),
                                       ("finish",{"answer":"bypass"}),("read_evidence",{})])
def test_protocol_edges(action,args):
    h=env(); assert not h.execute(action,args)["ok"] and h.attempts==1


def test_update_journal_failure_cannot_mutate_memory(monkeypatch):
    h=env(); opened(h); before=deepcopy(h.state)
    def fail(event): raise OSError("disk full")
    monkeypatch.setattr(h.ledger,"append",fail)
    with pytest.raises(OSError): update(h)
    assert h.state==before
