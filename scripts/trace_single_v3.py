"""Capture one real v3/OpenAI episode, with a local BC+ index and no judge.

Credentials are read from ESR_API_KEY only. All artifacts stay in a new private
directory. This is an interaction diagnostic, not a tokenizer-matched benchmark.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from esr_harness_v3 import adapters
from esr_harness_v3.adapters import OpenAICompatible, run_episode
from esr_harness_v3.audit import AUDIT_SYSTEM
from esr_harness_v3.engine import Harness
from esr_harness_v3.protocol import Config, ContractError, SYSTEM, VERSION, canonical, digest, parse_json, tools


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


class LocalIndex:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True)
        row = self.db.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()
        metadata = json.loads(row[0]) if row else {}
        if not metadata.get('complete'):
            raise ValueError('A complete, already built index is required')
        self.identity = {'kind': 'sqlite-fts5-bm25', 'index_fingerprint': digest(metadata), 'metadata': metadata}

    def search(self, query, top_k):
        terms = list(dict.fromkeys(re.findall(r'\w+', query.lower())))
        expression = ' OR '.join('"'+word.replace('"', '""')+'"' for word in terms)
        deadline = time.monotonic() + 45
        self.db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        try:
            rows = [] if not expression else self.db.execute(
                "SELECT d.docid,d.url,snippet(search,0,'','',' ... ',48),bm25(search) "
                'FROM search JOIN docs d ON d.rowid=search.rowid WHERE search MATCH ? '
                'ORDER BY bm25(search),d.docid LIMIT ?', (expression, top_k)).fetchall()
        finally:
            self.db.set_progress_handler(None, 0)
        return [{'docid': row[0], 'title': row[1], 'snippet': row[2], 'score': -row[3]} for row in rows]

    def get_document(self, docid):
        row = self.db.execute('SELECT content,url FROM docs WHERE docid=?', (docid,)).fetchone()
        if row is None:
            raise ContractError('retrieval_error', 'Unknown index document')
        return {'docid': docid, 'content': row[0], 'title': row[1], 'url': row[1]}

    def close(self):
        self.db.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Capture:
    def __init__(self, root, budget_path, total_cap, endpoint):
        self.root, self.endpoint = root, endpoint
        self.harness = None
        self.db = sqlite3.connect(budget_path, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS budget (cap INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, run TEXT, role TEXT, status TEXT, http_status INTEGER, usage TEXT)')
        row = self.db.execute('SELECT cap FROM budget').fetchone()
        if row is None:
            self.db.execute('INSERT INTO budget VALUES (?)', (total_cap,))
        elif row[0] != total_cap:
            raise ValueError('Budget limit differs from the existing persistent budget; no implicit reset')

    def post(self, url, body, *, api_key=None, timeout=180, max_bytes=50_000_000):
        adapters.validate_endpoint(url)
        if url != self.endpoint:
            raise ContractError('service_error', 'Unexpected model endpoint')
        role = 'audit' if self.harness and self.harness.state.get('executing') else 'policy'
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT count(*) FROM requests').fetchone()[0] >= self.db.execute('SELECT cap FROM budget').fetchone()[0]:
                raise ContractError('request_budget', 'Persistent single-question request cap exhausted')
            rid = self.db.execute('INSERT INTO requests(run,role,status) VALUES (?,?,?)',
                                  (str(self.root), role, 'reserved_unknown')).lastrowid
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise
        folder = self.root/'http'/f'{rid:04d}_{role}'
        folder.mkdir(parents=True, exist_ok=False)
        payload = canonical(body).encode('utf-8')
        (folder/'request.body.json').write_bytes(payload)
        save(folder/'request.meta.json', {'id': rid, 'role': role, 'url': url, 'method': 'POST',
             'headers': {'Content-Type': 'application/json', 'Authorization': '[REDACTED]'},
             'utc': datetime.now(timezone.utc).isoformat(), 'request_bytes': len(payload),
             'body_sha256': hashlib.sha256(payload).hexdigest(), 'retries': 0})
        print(canonical({'event': 'request', 'id': rid, 'role': role, 'body_bytes': len(payload)}), flush=True)
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json',
                                     'Authorization': 'Bearer '+api_key}, method='POST')
        started = time.monotonic()
        status, headers, data, error = None, {}, b'', None
        try:
            opener = urllib.request.build_opener(NoRedirect())
            try:
                response = opener.open(req, timeout=timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                status = response.code
                headers = {k: v for k, v in response.headers.items() if k.lower() in
                           ('content-type', 'date', 'request-id', 'x-request-id', 'retry-after')}
                data = response.read(max_bytes+1)
            redacted = bool(api_key and api_key.encode() in data)
            (folder/'response.body').write_bytes(data.replace(api_key.encode(), b'[REDACTED]') if redacted else data)
            save(folder/'response.meta.json', {'http_status': status, 'headers': headers,
                 'elapsed_seconds': time.monotonic()-started, 'response_bytes': len(data),
                 'credential_redacted': redacted, 'over_size_limit': len(data)>max_bytes})
            if status != 200:
                raise ContractError('service_error', f'HTTP {status}; preserved response in private trace')
            if len(data) > max_bytes:
                raise ContractError('service_error', 'Response exceeds byte limit')
            value = parse_json(data.decode('utf-8'))
            if not isinstance(value, dict):
                raise ContractError('service_error', 'Expected response object')
            self.db.execute('UPDATE requests SET status=?,http_status=?,usage=? WHERE id=?',
                            ('received', status, canonical(value.get('usage')), rid))
            choices = value.get('choices')
            print(canonical({'event': 'response', 'id': rid, 'model': value.get('model'),
                             'seconds': round(time.monotonic()-started, 3), 'usage': value.get('usage'),
                             'finish_reason': [c.get('finish_reason') for c in choices if isinstance(c, dict)] if isinstance(choices, list) else None}), flush=True)
            return value
        except Exception as exc:
            error = type(exc).__name__
            self.db.execute('UPDATE requests SET status=?,http_status=? WHERE id=?', ('failed_unknown', status, rid))
            save(folder/'failure.json', {'error_type': error, 'http_status': status,
                                        'elapsed_seconds': time.monotonic()-started, 'retry': False})
            raise ContractError('service_error', f'Model transport failed: {error}, HTTP {status}') from exc

    def close(self):
        self.db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--questions', required=True, help='Question-only development JSONL, never confirmation/gold')
    p.add_argument('--qid', required=True)
    p.add_argument('--index', required=True)
    p.add_argument('--base-url', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--total-cap', type=int, required=True)
    p.add_argument('--budget-db', required=True)
    p.add_argument('--episode-cap', type=int, default=32)
    p.add_argument('--output-tokens', type=int, default=4096)
    p.add_argument('--allow-network', action='store_true')
    args = p.parse_args()
    key = os.environ.get('ESR_API_KEY')
    if not args.allow_network or not key:
        p.error('Explicit network authorization and project ESR_API_KEY are required')
    if not 1 <= args.episode_cap <= args.total_cap <= 100:
        p.error('Require 1 <= episode cap <= current authorized total cap <= 100')
    selected = next((r for line in Path(args.questions).read_text(encoding='utf-8').splitlines()
                     if str((r := parse_json(line)).get('qid')) == args.qid), None)
    if selected is None or not isinstance(selected.get('question'), str):
        raise ValueError('Requested development question missing')
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    save(root/'question.json', {'qid': args.qid, 'question': selected['question']})
    index = LocalIndex(args.index)
    cfg = Config(max_model_calls=args.episode_cap, max_actions=100, context_limit=96000,
                 output_reserve=args.output_tokens, require_sources=True, audit_mode='diagnostic')
    source_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in [Path(__file__).resolve(), *(ROOT/'src/esr_harness_v3').glob('*.py')]}
    save(root/'manifest.json', {'qid': args.qid, 'question_sha256': digest(selected['question']), 'config': cfg.to_dict(),
         'protocol': VERSION, 'model': args.model, 'base_url': args.base_url, 'index': index.identity,
         'base_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
         'source_sha256': source_hashes, 'policy_prompt_sha256': digest(SYSTEM), 'audit_prompt_sha256': digest(AUDIT_SYSTEM),
         'tools_sha256': digest(tools()), 'capacity_unit': 'utf8_bytes_conservative_diagnostic_not_provider_tokens',
         'tokenizer': 'NOT_CONFIGURED; not a same-token-budget comparison', 'global_model_cap': args.total_cap,
         'budget_db': str(Path(args.budget_db).resolve()), 'credential_source': 'ESR_API_KEY',
         'authorization': 'User 2026-09-14 explicitly authorized at most 100 requests and supplied project credentials',
         'question_count': 1, 'attempts': 1, 'judge_calls': 0, 'automatic_retries': 0})
    capture = Capture(root, args.budget_db, args.total_cap, args.base_url.rstrip('/')+'/chat/completions')
    client = OpenAICompatible(args.base_url, args.model, api_key=key, timeout=180)
    h = Harness(selected['question'], index, ledger=root/'episode.sqlite', config=cfg, auditor=client)
    capture.harness = h
    original_post = adapters.post_json
    adapters.post_json = capture.post
    started = time.monotonic()
    try:
        run_episode(h, client)
    finally:
        adapters.post_json = original_post
        export = h.ledger.export()
        save(root/'trajectory.json', export)
        with (root/'trajectory.jsonl').open('x', encoding='utf-8') as stream:
            for event in export['events']:
                stream.write(canonical(event)+'\n')
        usage_rows = capture.db.execute('SELECT id,role,status,http_status,usage FROM requests').fetchall()
        save(root/'result.json', {'terminal': h.terminal, 'model_attempts': h.state['model_calls'],
             'backend_calls': h.state['backend_calls'], 'tool_actions': h.state['actions'], 'usage': h.state['usage'],
             'elapsed_seconds': time.monotonic()-started, 'budget_used': len(usage_rows),
             'budget_remaining': args.total_cap-len(usage_rows), 'request_rows': usage_rows,
             'source_unchanged': all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == v for p, v in source_hashes.items()),
             'formal_judge': 'NOT_RUN', 'full_trajectory': 'trajectory.jsonl'})
        print(canonical({'event': 'finished', 'outcome': (h.terminal or {}).get('outcome'),
                         'model_attempts': h.state['model_calls'], 'backend_calls': h.state['backend_calls']}), flush=True)
        h.close()
        index.close()
        capture.close()


if __name__ == '__main__':
    main()
