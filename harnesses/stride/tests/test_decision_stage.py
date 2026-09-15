"""Allowance and formal CLI stage integration, entirely synthetic transport."""
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import urllib.request
import pytest
from stride_search import Config
from stride_search.fixtures import native, smoke_corpus
from stride_search.providers import HTTP, OpenAIModel
from stride_search.workflow_contract import WorkflowConfig

DIRECTORY = Path(__file__).resolve().parents[1] / "experiments/autonomous_search"
sys.path.insert(0, str(DIRECTORY))
from budget import renew, EpochBudget
spec = importlib.util.spec_from_file_location("decision_stage_fixture", DIRECTORY / "run_stage.py")
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)


def ledger(tmp_path):
    path = tmp_path / "budget.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE budget(cap INTEGER); INSERT INTO budget VALUES(90);"
            "CREATE TABLE requests(id INTEGER PRIMARY KEY,run TEXT,role TEXT,status TEXT,http_status INTEGER,usage TEXT);"
            "INSERT INTO requests(run,role,status) VALUES('old','policy','unknown');"
            "INSERT INTO requests(run,role,status,http_status,usage) VALUES('old','judge','response_received',200,'{}');")
    return path


def test_renew_preserves_history_and_is_idempotent_after_spending(tmp_path):
    path = ledger(tmp_path)
    with sqlite3.connect(path) as db:
        old = db.execute("SELECT * FROM requests ORDER BY id").fetchall()
    record = renew(path, "fixture-epoch", 1000)
    budget = EpochBudget(path, "stage", "fixture-epoch", 2, 1)
    try:
        assert budget.window()["epoch_remaining"] == 1000
        budget.take()
        assert renew(path, "fixture-epoch", 1000) == record
        assert budget.window()["epoch_remaining"] == 999
        assert budget.db.execute("SELECT * FROM requests WHERE run='old' ORDER BY id").fetchall() == old
        assert budget.db.execute("SELECT count(*) FROM allowance_epochs").fetchone()[0] == 1
        with pytest.raises(ValueError): renew(path, "fixture-epoch", 1001)
        assert budget.window()["epoch_remaining"] == 999
    finally: budget.close()


def test_role_caps_seal_unknown_charge_and_new_epoch_invalidates_old(tmp_path):
    path = ledger(tmp_path); renew(path, "first", 1000)
    budget = EpochBudget(path, "stage", "first", 2, 1)
    try:
        budget.role = "judge"
        with pytest.raises(ValueError): budget.take()
        budget.role = "invalid"
        with pytest.raises(ValueError): budget.take()
        budget.role = "policy"
        budget.take(); budget.take()
        with pytest.raises(ValueError): budget.take()
        budget.policy_sealed = True
        with pytest.raises(ValueError): budget.take()
        budget.role = "judge"; budget.take()
        with pytest.raises(ValueError): budget.take()
        assert budget.window()["epoch_used"] == 3
        assert budget.db.execute("SELECT count(*) FROM requests WHERE run='stage' AND status='unknown'").fetchone()[0] == 3
        renew(path, "second", 1000)
        with pytest.raises(ValueError): budget.take()
    finally: budget.close()


def test_transport_timeout_retains_unknown_charge(tmp_path):
    path = ledger(tmp_path); renew(path, "epoch", 1000)
    budget = EpochBudget(path, "stage", "epoch", 2, 1)
    class Transport:
        def open(self, request, timeout):
            assert budget.window()["epoch_used"] == 1
            raise TimeoutError("synthetic")
    capture = stage.LimitedCapture(tmp_path / "capture", budget, "", "http://fixture.invalid/chat/completions",
                                  limit=1, check=lambda: None, opener=Transport())
    try:
        request = urllib.request.Request(capture.url, data=b'{"model":"fixture"}', method="POST")
        with pytest.raises(TimeoutError): capture.open(request, 1)
        with pytest.raises(ValueError): capture.open(request, 1)
        assert budget.window()["epoch_used"] == 1
        assert (capture.root / "http/001/attempt-start.json").is_file()
        assert budget.db.execute("SELECT status FROM requests WHERE run='stage'").fetchone()[0] == "unknown"
    finally: budget.close()


def test_both_protocols_formal_cli_export_and_seal(tmp_path, monkeypatch):
    path = ledger(tmp_path); renew(path, "epoch", 1000)
    cases = tmp_path / "cases"; (cases / "q0").mkdir(parents=True)
    (cases / "q0/question.txt").write_text("Who was the first director of Lumen Observatory?", encoding="utf-8")
    monkeypatch.setattr(stage, "CASES", cases)
    wires = []; headers = []; rows = []
    for protocol in ["baseline", "constraint-review-v1"]:
        budget = EpochBudget(path, protocol, "epoch", 4, 1)
        corpus = smoke_corpus(); corpus.identity["query_timeout_seconds"] = 45
        replies = [native(("search", {"queries": ["Lumen"]})), native(("read", {"ref": "d1"})),
                   native(("finish", {"answer": "Ada Rowan", "refs": ["e1"]}))]
        class Response(io.BytesIO): status = 200
        class Transport:
            sent = 0
            def open(self, request, timeout):
                assert budget.snapshot()["this_run"] == self.sent + 1
                raw = replies[self.sent]; self.sent += 1
                return Response(json.dumps(raw).encode())
        folder = tmp_path / protocol
        capture = stage.LimitedCapture(folder, budget, "", "http://fixture.invalid/chat/completions",
                                       limit=4, check=lambda: None, opener=Transport())
        model = OpenAIModel("http://fixture.invalid", "fixture", revision="fixture",
                           http=HTTP(allow_network=True, opener=capture), temperature=0, expected_response_model="fixture")
        config = Config(max_model_calls=4, max_actions=200, max_backend_calls=120,
                        max_output_tokens=4096, max_total_output_tokens=48000,
                        context_limit=96000, response_reserve=4096, max_seconds=600).to_dict()
        slot = dict(slot=protocol, qid=0, protocol=protocol, config=config,
                    workflow=WorkflowConfig.profile("full").identity())
        manifest = dict(model_identity=model.identity, base_url="http://fixture.invalid",
                        index_path="unused", index_id="fixture", index_identity=corpus.identity)
        monkeypatch.setattr(stage.cli, "_retriever", lambda args, http: corpus)
        monkeypatch.setattr(stage.cli, "_model", lambda args, http: model)
        try:
            row = stage.policy_slot(slot, manifest, folder, capture); rows.append(row)
            assert row["status"] == "submitted" and row["attempts"] == 3
            assert row["terminal"]["answer"] == "Ada Rowan"
            for name in ["all-objects.json", "SEALED.json", "FULL_INTERACTION.md", "events-timed.jsonl"]:
                assert (folder / name).is_file()
            seal = stage.read(folder / "SEALED.json")
            assert all(stage.sha(folder / name) == digest for name, digest in seal["files"].items())
            assert stage.sha(folder / "SEALED.json") == row["seal_sha256"]
            wires.append(stage.read(folder / "http/001/request.body"))
            headers.append(stage.read(folder / "report.json")["header"])
            assert budget.snapshot()["this_run"] == 3
        finally: budget.close()
    assert rows[0].keys() == rows[1].keys()
    assert headers[0]["retriever"] == headers[1]["retriever"]
    assert headers[0]["config"] == headers[1]["config"]
    assert headers[0]["workflow_contract"] == headers[1]["workflow_contract"]
    assert headers[1]["decision_protocol"]["version"] == "constraint-review-v1"
    assert wires[0]["tools"] == wires[1]["tools"]
    wires[1]["messages"][0] = wires[0]["messages"][0]
    assert wires[0] == wires[1]


def test_judge_cannot_read_gold_before_policy_seal(tmp_path):
    with pytest.raises(ValueError, match="seal missing"):
        stage.judge_cases(tmp_path, [], tmp_path / "nonexistent-synthetic-gold")
    assert not (tmp_path / "gold-access.json").exists()
