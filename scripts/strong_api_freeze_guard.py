"""Fail closed if an experiment tries to use changed confirmation conditions."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

PROCEDURE_SOURCES = ['scripts/strong_api.py','scripts/strong_api_batch.py','scripts/evaluate_strong_api.py',
                     'scripts/compare_strong_api.py','scripts/summarize_strong_api.py','scripts/strong_api_freeze_guard.py']


def online_source_hashes(snapshot):
    return {k:v for k,v in snapshot['source_hashes'].items()
            if k.startswith(('src/esr_harness/','api/')) or k=='scripts/strong_api.py'}


def checked_index_fingerprint(root,index,required=False):
    record_path=root/'index_fingerprint.json'
    if not record_path.exists() and not required:return None
    record=json.loads(record_path.read_text(encoding='utf-8-sig'))
    path=Path(index).resolve();stat=path.stat()
    expected_time=datetime.fromisoformat(record['last_write_utc'].replace('Z','+00:00')).timestamp()
    if path!=Path(record['path']).resolve() or stat.st_size!=record['bytes'] or abs(stat.st_mtime-expected_time)>0.00001:
        raise ValueError('Index differs from the file whose full SHA256 was verified')
    return record


def check_episode_input(root,category,qid,question,arm):
    if category not in {'pilot','development','confirmation'}:return
    if category=='confirmation' and not (root/'FINAL_FREEZE.json').exists():
        raise ValueError('Confirmation remains sealed')
    source=root/f'dataset_splits/{category}.questions.jsonl'
    rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines()]
    if {'qid':qid,'question':question} not in rows:
        raise ValueError('Episode differs from frozen question input')
    if category=='pilot':
        if arm!='B':raise ValueError('Pilot allows baseline only')
        if len(list(root.glob(f'*_pilot_B_{qid}_*/manifest.json')))>=2:
            raise ValueError('Pilot allowance exhausted across all versions')


def check_final_freeze(root, snapshot, settings, arms=None):
    freeze=json.loads((root/'FINAL_FREEZE.json').read_text(encoding='utf-8'))
    online=online_source_hashes(snapshot)
    if online!=freeze['online_sources'] or settings!=freeze['settings']:
        raise ValueError('Confirmation online sources/config changed after freeze')
    for source in PROCEDURE_SOURCES:
        if snapshot['source_hashes'].get(source)!=freeze['source_snapshot']['source_hashes'].get(source):
            raise ValueError('Confirmation procedure changed after freeze: '+source)
    if arms is not None and arms!=freeze['confirmation_plan']['arms']:
        raise ValueError('Confirmation arms differ from frozen baseline/candidate plan')
    for name,expected in freeze['sealed_files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Sealed split or judge protocol changed: '+name)
    return freeze
