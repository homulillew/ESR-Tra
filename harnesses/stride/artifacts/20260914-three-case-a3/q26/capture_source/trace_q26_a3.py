"""Private one-episode capture; release policy, tools, CPU ranking remain unchanged."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from collections import Counter

import stride_search
from stride_search import Config, Harness
from stride_search.archive import Archive
from stride_search.contract import PROTOCOL, ContractError, canonical
from stride_search.cpu_index import SQLiteFTS5
from stride_search.diagnostics import diagnose
from stride_search.experiment import source_hashes
from stride_search.providers import ByteCounter, HTTP, OpenAIModel, _NoRedirect, usage_of

RELEASE = '5d7752be94a9d40aa757383d8899504bc0f81e81'

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def config():
    return Config(max_model_calls=32, max_actions=100, max_backend_calls=60,
        max_batch=4, max_queries_per_search=3, max_output_tokens=4096,
        max_total_output_tokens=24000, context_limit=96000, response_reserve=4096,
        read_chars=3000, recent_groups=4, max_notes=6, max_document_chars=2_000_000,
        max_seconds=900, notes_enabled=True, reserve_finish=True, require_sources=True,
        context_mode='rolling', nonblocking_notes=True, repair_context=True,
        delivery_preflight=True, disclose_retriever=True, compiled_query_cache=False,
        evidence_shelf_size=3, recall_navigation=True, centered_recall=True,
        answer_prefix='', answer_suffix='')

class Budget:
    """Use the existing project ledger, including failed/unknown sends; never create it."""
    def __init__(self, path, run, limit=32):
        self.db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw',
                                  uri=True, isolation_level=None)
        self.run, self.limit = str(run), limit
        self.db.execute('PRAGMA synchronous=FULL')
        caps = self.db.execute('SELECT cap FROM budget').fetchall()
        if len(caps) != 1 or type(caps[0][0]) is not int:
            raise ValueError('Invalid existing budget cap')
        self.before = self.snapshot()
        if self.before['remaining'] < limit or self.before['this_run']:
            raise ValueError('BLOCKED_BUDGET: insufficient allowance or already-started run')

    def snapshot(self):
        cap = self.db.execute('SELECT cap FROM budget').fetchone()[0]
        used = self.db.execute('SELECT count(*) FROM requests').fetchone()[0]
        own = self.db.execute('SELECT count(*) FROM requests WHERE run=?', (self.run,)).fetchone()[0]
        return dict(cap=cap, used=used, remaining=cap-used, this_run=own)

    def take(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            s = self.snapshot()
            if s['remaining'] <= 0 or s['this_run'] >= self.limit:
                raise ContractError('request_budget', 'Persistent attempt budget exhausted', fatal=True)
            n = self.db.execute('INSERT INTO requests(run,role,status) VALUES (?,?,?)',
                                (self.run, 'policy', 'unknown')).lastrowid
            self.db.execute('COMMIT')
            return n
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def finish(self, n, status, http_status, usage):
        self.db.execute('UPDATE requests SET status=?,http_status=?,usage=? WHERE id=?',
                        (status, http_status, canonical(usage), n))

    def close(self):
        self.db.close()

class CaptureOpener:
    """Capture exactly the body given to urllib, without recording request headers."""
    def __init__(self, root, budget, secret, expected_url, opener=None):
        self.root, self.budget, self.secret = Path(root), budget, secret.encode()
        self.url = expected_url
        self.opener = opener or urllib.request.build_opener(_NoRedirect())
        self.rows = []

    def open(self, request, timeout):
        if request.full_url != self.url or request.get_method() != 'POST':
            raise ContractError('capture_endpoint', 'Unexpected model endpoint', fatal=True)
        if self.secret and self.secret in request.data:
            raise ContractError('credential_in_body', 'Credential in request body', fatal=True)
        number = len(self.rows) + 1
        folder = self.root / 'http' / f'{number:03d}'
        folder.mkdir(parents=True, exist_ok=False)
        (folder/'request.body').write_bytes(request.data)
        row = {'sequence': number, 'utc_start': utc(), 'http_status': None,
               'requested_model': json.loads(request.data)['model'], 'returned_model': None,
               'finish_reason': None, 'usage': {}, 'input_tokens': None, 'output_tokens': None,
               'cache_read_tokens': None, 'cache_write_tokens': None,
               'request_bytes': len(request.data), 'response_bytes': None,
               'request_body_sha256': hashlib.sha256(request.data).hexdigest(),
               'sanitized_response': False}
        ledger_id = self.budget.take()  # charged atomically before the actual send
        row['ledger_id'] = ledger_id
        save(folder/'attempt-start.json', row)
        self.rows.append(row)
        started = time.monotonic()
        data = None
        status = 'unknown'
        try:
            with self.opener.open(request, timeout=timeout) as response:
                row['http_status'] = response.status
                data = response.read(8_000_001)
            status = 'response_received'
        except urllib.error.HTTPError as exc:
            row['http_status'] = exc.code
            data = exc.read(8_000_001)
            row['error_type'] = type(exc).__name__
            status = 'http_error'
            raise
        except Exception as exc:
            row['error_type'] = type(exc).__name__
            status = 'unknown'
            raise
        finally:
            row['utc_end'] = utc()
            row['latency_seconds'] = time.monotonic() - started
            if data is not None:
                row['response_bytes'] = len(data)
                redacted = bool(self.secret and self.secret in data)
                safe = data.replace(self.secret, b'[REDACTED]') if redacted else data
                row['sanitized_response'] = redacted
                row['response_representation'] = ('sanitized_response != original_raw_bytes'
                                                  if redacted else 'original response body bytes')
                (folder/'response.body').write_bytes(safe)
                row['saved_response_body_sha256'] = hashlib.sha256(safe).hexdigest()
                try:
                    raw = json.loads(safe)
                    row['returned_model'] = raw.get('model')
                    choices = raw.get('choices', [])
                    row['finish_reason'] = choices[0].get('finish_reason') if choices else None
                    row['usage'] = raw.get('usage', {})
                    row.update(usage_of(raw, 'openai'))
                except (ValueError, TypeError, AttributeError, IndexError):
                    pass
            self.budget.finish(ledger_id, status, row['http_status'], row['usage'])
            save(folder/'metadata.json', row)
            print(json.dumps({'http': number, 'status': row['http_status'],
                  'seconds': round(row['latency_seconds'], 3), 'finish_reason': row['finish_reason']}), flush=True)
        if row['sanitized_response']:
            raise ContractError('credential_echo', 'Credential echo sealed in sanitized form', fatal=True)
        return io.BytesIO(data)

def table(path, rows, fields):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: canonical(v) if isinstance(v, (dict, list)) else v for k,v in row.items()})

def export(root):
    """Read-only export of every event/request/response; no new model or CPU query."""
    root = Path(root)
    a = Archive(root/'episode.sqlite', readonly=True)
    try:
        events = list(a.events())
        report = a.report()
        terminal = report['terminal']
        timed = [json.loads(s) for s in (root/'events-timed.jsonl').read_text(encoding='utf-8').splitlines()]
        timestamps = {r['seq']: r['utc'] for r in timed}
        requests = {e['payload']['round']: e for e in events if e['kind']=='model_request'}
        responses = {e['payload']['round']: e for e in events if e['kind']=='model_response'}
        wires = {r: a.load_request(e['payload']['request']) for r,e in requests.items()}
        http = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(root.glob('http/*/metadata.json'))]
        correspondence = []
        for r,wire in wires.items():
            p = root/'http'/f'{r:03d}'/'request.body'
            correspondence.append({'round':r,'http_body_exists':p.exists(),
                'json_equivalent':p.exists() and json.loads(p.read_bytes())==wire,
                'canonical_serialization_matches_sent_body':p.exists() and canonical(wire).encode()==p.read_bytes()})
        with (root/'trajectory.jsonl').open('x',encoding='utf-8') as f:
            for e in events:
                f.write(canonical({**e,'utc':timestamps.get(e['seq'])})+'\n')
        with (root/'FULL_INTERACTION.md').open('x',encoding='utf-8') as f:
            f.write('# Complete private interaction\n\nAll requests, provider responses, events and referenced objects are included without omission. HTTP body files preserve captured bytes unless metadata explicitly marks sanitization. Event times are capture append timestamps.\n')
            for e in events:
                f.write(f"\n## Event {e['seq']}: {e['kind']}\n\nUTC: {timestamps.get(e['seq'])}\n\n```json\n{json.dumps(e,ensure_ascii=False,indent=2)}\n```\n")
                p=e['payload']
                if e['kind']=='model_request':
                    f.write('\nActual archived request:\n```json\n'+json.dumps(wires[p['round']],ensure_ascii=False,indent=2)+'\n```\n')
                for key in ('object','raw','raw_wire','group','notes'):
                    if isinstance(p.get(key),str) and len(p[key])==64:
                        f.write(f'\nReferenced {key}:\n```\n'+a.get(p[key])+'\n```\n')
                if e['kind']=='model_failure':
                    response=root/'http'/f"{p['round']:03d}"/'response.body'
                    if response.exists():
                        f.write('\nCaptured error body (bytes available separately):\n```\n'+response.read_bytes().decode('utf-8',errors='replace')+'\n```\n')
        rounds=[]; visibility=[]; actions=[]; queries=[]; evidence=[]
        for r,e in requests.items():
            p=e['payload']; resp=responses.get(r,{}).get('payload',{})
            rounds.append({'round':r,'utc':timestamps.get(e['seq']),'final':p['final'],
                'compacted':p['compacted'],'visible':p['visible_evidence'],'shelf_restored':p.get('evidence_shelf',[]),
                'shelf_evicted':p.get('shelf_evicted_for_capacity',[]),'wire_bytes':len(canonical(wires[r]).encode()),
                'usage':resp.get('usage',{}),'http':http[r-1] if r<=len(http) else None})
            for ref in sorted({v['payload']['ref'] for v in events if v['kind']=='evidence_registered'},key=lambda s:int(s[1:])):
                visibility.append({'round':r,'ref':ref,'visible':ref in p['visible_evidence'],
                    'shelf_restored':ref in p.get('evidence_shelf',[]),'shelf_evicted':ref in p.get('shelf_evicted_for_capacity',[])})
        for e in events:
            p=e['payload']
            if e['kind']=='action_result':
                later=[r for r in wires if r>p['round']]
                next_r=min(later) if later else None
                receipt=next((m for m in wires.get(next_r,{}).get('messages',[]) if m['role']=='tool' and m.get('tool_call_id')==p['tool_call_id'] and m.get('content')==canonical(p['result'])),None)
                actions.append({**p,'seq':e['seq'],'utc':timestamps.get(e['seq']),
                    'next_request':next_r,'next_input_receipt':bool(receipt),
                    'action_commit':'NOT_A_SEPARATE_STRIDE_EVENT; action_result and round_end are recorded',
                    'receipt_not_required_after_terminal':not later and p['tool']=='finish' and p['result']['ok']})
            elif e['kind']=='query_execution':
                backend=next((v for v in events if v['seq']>e['seq'] and v['kind'] in ('backend_response','backend_error','query_execution','action_execution')),None)
                docs=[]
                if not p['cached'] and backend and backend['kind']=='backend_response':
                    docs=a.json(backend['payload']['object'])
                if p['cached']:
                    previous=next((v for v in reversed(queries) if v['cache_key']==p['cache_key']),None)
                    docs=previous['result_docs'] if previous else []
                mapping={row[1]:f'd{row[0]}' for row in a.db.execute('SELECT n,backend FROM docs')}
                queries.append({**p,'seq':e['seq'],'utc':timestamps.get(e['seq']),
                    'terms':(p['compiled'] or {}).get('terms'), 'expression':(p['compiled'] or {}).get('expression'),
                    'result_docs':docs,'returned_dN':[mapping.get(d['docid']) for d in docs],
                    'returned_docids':[d['docid'] for d in docs]})
            elif e['kind']=='evidence_registered':
                ref=p['ref']; visible=[r for r,v in requests.items() if ref in v['payload']['visible_evidence']]
                acks=[v for v in events if v['kind']=='delivery_ack' and ref in v['payload']['evidence']]
                restored=[r for r,v in requests.items() if ref in v['payload'].get('evidence_shelf',[])]
                snap=next((v for v in events if v['kind']=='snapshot' and v['payload']['document']==p['document']),None)
                evidence.append({**a.evidence(ref),'created_utc':timestamps.get(e['seq']),
                    'backend_snapshot_utc':timestamps.get(snap['seq']) if snap else None,
                    'first_request':min(visible) if visible else None,'first_ack_round':acks[0]['payload']['round'] if acks else None,
                    'first_ack_utc':timestamps.get(acks[0]['seq']) if acks else None,
                    'visible_rounds':visible,'shelf_restored_rounds':restored,'final_cited':ref in terminal.get('refs',[])})
        table(root/'ROUND_TABLE.csv',rounds,['round','utc','final','compacted','visible','shelf_restored','shelf_evicted','wire_bytes','usage','http'])
        table(root/'QUERY_EXECUTION.csv',queries,['round','seq','utc','query','terms','expression','top_k','equivalence_key','cache_key','cached','returned_dN','returned_docids','result_docs'])
        table(root/'VISIBILITY_TABLE.csv',visibility,['round','ref','visible','shelf_restored','shelf_evicted'])
        table(root/'EVIDENCE_TABLE.csv',evidence,['ref','document','snapshot','start','end','text','sha256','backend_snapshot_utc','created_utc','first_request','first_ack_round','first_ack_utc','visible_rounds','shelf_restored_rounds','final_cited'])
        table(root/'TOOL_INTEGRITY.csv',actions,['round','seq','utc','tool_call_id','tool','arguments','executed','result','next_request','next_input_receipt','action_commit','receipt_not_required_after_terminal'])
        save(root/'diagnostics.json',diagnose(root/'episode.sqlite',include_text=True))
        save(root/'metrics.sanitized.json',{k:v for k,v in report.items() if k not in ('header','model_identity','terminal')})
        save(root/'result.json',{'terminal':terminal,'formal_correct':None,'http_attempts':len(http)})
        save(root/'INTEGRITY_CHECKS.json',{'archive':a.verify(),'request_correspondence':correspondence,
            'request_bytes_note':'Compared captured urllib Request.data with deterministic Archive reconstruction; not TCP framing bytes',
            'all_json_equivalent':all(r['json_equivalent'] for r in correspondence),
            'http_attempts':len(http),'formal_correct':None})
        save(root/'analysis-data.json',{'rounds':rounds,'actions':actions,'queries':queries,'evidence':evidence,'http':http})
    finally:
        a.close()

def run(plan_path):
    plan_path=Path(plan_path)
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    repo=Path(plan['worktree'])
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()!=RELEASE:
        raise ValueError('BLOCKED_VERSION_MISMATCH')
    if source_hashes()!=plan['source_hashes'] or sha(__file__)!=plan['collector_sha256']:
        raise ValueError('Frozen source identity mismatch')
    if config().to_dict()!=plan['config'] or PROTOCOL!='stride-search-3' or stride_search.__version__!='0.1.0a3':
        raise ValueError('Frozen configuration mismatch')
    if not Path(stride_search.__file__).resolve().is_relative_to(repo.resolve()):
        raise ValueError('Imported source outside frozen worktree')
    key=os.environ.get('ESR_API_KEY')
    base=os.environ.get('ESR_BASE_URL')
    if not key or base!=plan['base_url']:
        raise ValueError('BLOCKED_NO_AUTHORIZATION: missing project environment')
    question_path=Path(plan['question_path'])
    if sha(question_path)!=plan['question_sha256']:
        raise ValueError('Question changed')
    q=json.loads(question_path.read_text(encoding='utf-8-sig'))
    if set(q)!={'qid','question'} or q['qid']!='26':
        raise ValueError('Expected original question-only q26')
    root=Path(plan['output'])
    if root.exists(): raise FileExistsError(root)
    budget=Budget(plan['budget_path'],str(root),32)
    index=SQLiteFTS5(plan['index_path'],index_id=plan['index_id'],timeout_seconds=45)
    if index.identity!=plan['index_identity']:
        index.close(); budget.close()
        raise ValueError('CPU index identity mismatch')
    root.mkdir(parents=True,exist_ok=False)
    capture=CaptureOpener(root,budget,key,base.rstrip('/')+'/chat/completions')
    model=OpenAIModel(base,'EB-GLM-5.2',revision='user-configured-EB-GLM-5.2',
        temperature=0,expected_response_model='glm-5.2',api_key=key,
        http=HTTP(allow_network=True,timeout=180,opener=capture))
    save(root/'manifest.json',{**plan,'utc_started':utc(),'budget_before':budget.before,
        'model_identity':model.identity,'counter':ByteCounter.identity,
        'python':sys.version,'sqlite':sqlite3.sqlite_version,'package_version':stride_search.__version__,
        'protocol':PROTOCOL,'import_path':stride_search.__file__,
        'capacity_units':{'context_limit':'UTF-8 bytes','response_reserve':'UTF-8 bytes','max_output_tokens':'provider output tokens'},
        'credential_source':'ESR_API_KEY environment; credential not persisted',
        'transport_environment':{'NO_PROXY':os.environ.get('NO_PROXY')},
        'formal_correct':None})
    save(root/'question.json',q)
    (root/'question.txt').write_text(q['question'],encoding='utf-8')
    h=Harness(q['question'],index,path=root/'episode.sqlite',config=config(),counter=ByteCounter())
    with (root/'events-timed.jsonl').open('x',encoding='utf-8',buffering=1) as timing:
        timing.write(canonical({'seq':1,'utc':utc(),'kind':'episode'})+'\n')
        original_append=h.archive.append
        def captured_append(kind,payload):
            event=original_append(kind,payload)
            timing.write(canonical({'seq':event['seq'],'utc':utc(),'kind':kind})+'\n')
            return event
        h.archive.append=captured_append
        try:
            h.run(model)
        except Exception as exc:
            save(root/'capture-exception.json',{'type':type(exc).__name__,'utc':utc()})
        finally:
            h.close(); index.close()
            save(root/'budget-after.json',budget.snapshot())
            budget.close()
    export(root)
    print(json.dumps({'output':str(root),'http_attempts':len(capture.rows)}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True)
    run(parser.parse_args().plan)
