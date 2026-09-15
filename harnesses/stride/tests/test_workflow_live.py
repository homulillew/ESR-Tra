"""Local transport fixtures only; no model-quality claims."""
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

path = Path(__file__).resolve().parents[1] / 'experiments/workflow_v1/validate_live.py'
spec = importlib.util.spec_from_file_location('workflow_live_fixture', path)
live = importlib.util.module_from_spec(spec); sys.modules[spec.name] = live; spec.loader.exec_module(live)


def ledger(tmp_path):
    path = tmp_path / 'fixture-budget.sqlite'
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE budget(cap INTEGER); INSERT INTO budget VALUES(1000);'
                    'CREATE TABLE requests(id INTEGER PRIMARY KEY,run TEXT,role TEXT,status TEXT,http_status INTEGER,usage TEXT);'
                    "INSERT INTO requests(run,role,status) VALUES('prior','policy','unknown');")
    db.close()
    return live.RoleBudget(path, 'fixture', 80)


def test_role_caps_preserve_existing_unknown_charge_and_seal(tmp_path):
    budget = ledger(tmp_path)
    try:
        assert budget.before['used'] == 1
        budget.role = 'judge'
        with pytest.raises(ValueError, match='sealed'): budget.take()
        budget.role = 'policy'
        for _ in range(72): budget.take()
        with pytest.raises(ValueError, match='exhausted'): budget.take()
        budget.policy_sealed = True
        with pytest.raises(ValueError, match='restart'): budget.take()
        budget.role = 'judge'
        for _ in range(6): budget.take()
        with pytest.raises(ValueError, match='exhausted'): budget.take()
        assert budget.snapshot() == dict(cap=1000, used=79, remaining=921, this_run=78)
    finally: budget.close()


def test_transport_failure_charged_before_send_and_retained(tmp_path):
    budget = ledger(tmp_path)
    class Transport:
        def open(self, request, timeout):
            assert budget.snapshot()['this_run'] == 1
            raise TimeoutError('fixture')
    cap = live.LimitedCapture(tmp_path / 'capture', budget, '', 'http://fixture.invalid/chat/completions',
                              limit=1, check=lambda: None, opener=Transport())
    request = urllib.request.Request(cap.url, data=b'{"model":"fixture"}', method='POST')
    try:
        with pytest.raises(TimeoutError): cap.open(request, 1)
        with pytest.raises(ValueError, match='cap'): cap.open(request, 1)
        assert budget.snapshot()['this_run'] == 1
        assert (cap.root / 'http/001/attempt-start.json').is_file()
        assert (cap.root / 'http/001/metadata.json').is_file()
        assert budget.db.execute("SELECT status FROM requests WHERE run='fixture'").fetchone()[0] == 'unknown'
    finally: budget.close()


@pytest.mark.parametrize('profile', ['legacy', 'full'])
def test_fresh_cli_capture_export_and_seal(tmp_path, monkeypatch, profile):
    budget = ledger(tmp_path); corpus = smoke_corpus()
    question = tmp_path / 'question.txt'; question.write_text('Who was the first director of Lumen Observatory?')
    replies = [native(('search', {'queries':['Lumen']})), native(('read', {'ref':'d1'})),
               native(('finish', {'answer':'Ada Rowan', 'refs':['e1']}))]
    class Response(io.BytesIO): status = 200
    class Transport:
        sent = 0
        def open(self, request, timeout):
            assert budget.snapshot()['this_run'] == self.sent + 1
            raw = replies[self.sent]; self.sent += 1
            return Response(json.dumps(raw).encode())
    folder = tmp_path / 'episode'
    cap = live.LimitedCapture(folder, budget, '', 'http://fixture.invalid/chat/completions',
                              limit=4, check=lambda: None, opener=Transport())
    model = OpenAIModel('http://fixture.invalid', 'fixture', revision='fixture',
                       http=HTTP(allow_network=True, opener=cap), temperature=0, expected_response_model='fixture')
    config = Config(max_model_calls=4, max_actions=200, max_backend_calls=120,
                    max_output_tokens=4096, max_total_output_tokens=48000,
                    context_limit=96000, response_reserve=4096, max_seconds=600).to_dict()
    s = dict(slot='fixture', qid=0, profile=profile, config=config, workflow=WorkflowConfig.profile(profile).identity())
    m = dict(model_identity=model.identity, base_url='http://fixture.invalid', index_path='unused',
             index_id='fixture', index_identity=corpus.identity)
    m['index_identity']['query_timeout_seconds'] = 45
    monkeypatch.setattr(live, 'question_path', lambda qid: question)
    monkeypatch.setattr(live.cli, '_retriever', lambda args, http: corpus)
    monkeypatch.setattr(live.cli, '_model', lambda args, http: model)
    try:
        row = live.policy_slot(s, m, folder, cap)
        assert row['status'] == 'submitted' and row['attempts'] == 3
        assert row['terminal']['answer'] == 'Ada Rowan'
        assert live.read(folder / 'INTEGRITY_CHECKS.json')['all_json_equivalent']
        assert (folder / 'all-objects.json').is_file() and (folder / 'SEALED.json').is_file()
        assert (folder / 'FULL_INTERACTION.md').is_file()
    finally: budget.close()


def test_gold_unread_until_policy_sealed(tmp_path):
    with pytest.raises(ValueError, match='seal missing'):
        live.judge_cases(tmp_path, [], tmp_path / 'nonexistent-gold')
    assert not (tmp_path / 'gold-access.json').exists()
