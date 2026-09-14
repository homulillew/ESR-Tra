import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from esr_harness_v3 import ContractError
from .test_http_review import server_fixture


def module():
    spec = importlib.util.spec_from_file_location('trace_single_v3', Path(__file__).resolve().parents[2]/'scripts/trace_single_v3.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_capture_preserves_wire_and_persistent_request_cap(tmp_path):
    m = module()
    with server_fixture('success') as (base, seen):
        endpoint = base+'/v1/chat/completions'
        capture = m.Capture(tmp_path, tmp_path/'budget.sqlite', 1, endpoint)
        body = {'messages': [{'role': 'user', 'content': 'Synthetic input'}], 'model': 'loopback-model'}
        raw = capture.post(endpoint, body, api_key='local-test-key')
        assert len(raw['choices'][0]['message']['tool_calls']) == 2
        assert json.loads((tmp_path/'http/0001_policy/request.body.json').read_text()) == body
        assert json.loads((tmp_path/'http/0001_policy/response.body').read_bytes()) == raw
        capture.close()
        capture = m.Capture(tmp_path, tmp_path/'budget.sqlite', 1, endpoint)
        try:
            with pytest.raises(ContractError, match='cap exhausted'):
                capture.post(endpoint, body, api_key='local-test-key')
            assert len(seen) == 1
            assert 'local-test-key' not in (tmp_path/'http/0001_policy/request.meta.json').read_text()
        finally:
            capture.close()


def test_capture_keeps_failure_body_but_redacts_credential(tmp_path):
    m = module()
    with server_fixture('policy_401') as (base, seen):
        endpoint = base+'/v1/chat/completions'
        capture = m.Capture(tmp_path, tmp_path/'budget.sqlite', 1, endpoint)
        try:
            with pytest.raises(ContractError, match='HTTP 401'):
                capture.post(endpoint, {'messages': []}, api_key='local-test-key')
            assert len(seen) == 1
            assert 'local-test-key' not in (tmp_path/'http/0001_policy/response.body').read_text()
            assert json.loads((tmp_path/'http/0001_policy/response.meta.json').read_text())['credential_redacted']
            assert capture.db.execute('SELECT status FROM requests').fetchone()[0] == 'failed_unknown'
        finally:
            capture.close()


def test_existing_cpu_index_contract(tmp_path):
    m = module()
    path = tmp_path/'index.sqlite'
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE docs(docid TEXT,content TEXT,url TEXT); CREATE VIRTUAL TABLE search USING fts5(content,content='docs',content_rowid='rowid');")
    db.execute('INSERT INTO metadata VALUES (?,?)', ('identity', json.dumps({'complete': True, 'documents': 1})))
    db.execute('INSERT INTO docs VALUES (?,?,?)', ('original-id', 'Record: Mira is director.', 'https://fixture.test/record'))
    db.execute("INSERT INTO search(search) VALUES ('rebuild')")
    db.commit()
    db.close()
    index = m.LocalIndex(path)
    try:
        assert index.search('Mira OR "', 5)[0]['docid'] == 'original-id'
        assert index.get_document('original-id')['content'] == 'Record: Mira is director.'
    finally:
        index.close()
