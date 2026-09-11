"""Recheck frozen-prefix isolation and measured cost without inference or gold."""
import argparse
from collections import defaultdict
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from run_field_feedback_study import LABEL, events, check_events
from strong_api import write_json
from esr_harness.audit import validate_report, status, AuditConsistencyError
from esr_harness.audit_spans import source_span_packet, expand_references
from esr_harness.protocol import HarnessError, digest


def analyze(root):
    phase = json.loads((root / (LABEL + '_FINISHED.json')).read_text(encoding='utf-8'))
    plan = json.loads((root / (LABEL + '_PLAN.json')).read_text(encoding='utf-8'))
    assert phase['no_online_worker']
    db = sqlite3.connect((root / 'global_budget.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    rows, request_ids, hashes, bodies = [], [], {}, {}
    for item in phase['packets']:
        directory = root / item['run_id']
        ev = events(directory)
        requests = [e for e in ev if e['type'] == 'generation_request']
        responses = [e for e in ev if e['type'] == 'generation']
        checked = check_events(directory)
        assert not checked['issue']
        packet = json.loads((directory / 'packet.json').read_text(encoding='utf-8'))
        _, refs = source_span_packet(packet['views'])
        report = expand_references(responses[-1]['response']['content'][0]['input'], refs)
        problems, error = [], None
        try: validate_report(report, packet['state'], {v['observation_id']: v for v in packet['views']})
        except HarnessError as exc:
            error = str(exc)
            if isinstance(exc, AuditConsistencyError): problems = exc.problems
        assert error == (item['error'] or {}).get('message')
        if not error: assert report == item['report']
        if item['frozen_prefix']:
            source = json.loads((directory / 'frozen_prefix.json').read_text(encoding='utf-8'))
            assert digest(source) == plan['prefix_hashes'][item['name']]
            assert len(requests) == len(responses) == 1
            comparable = deepcopy(requests[0]['request'])
            if item['feedback'] == 'generic': assert comparable == source['repair_request']
            comparable['messages'][-1] = source['repair_request']['messages'][-1]
            assert comparable == source['repair_request']
            bodies[item['name'], item['feedback']] = requests[0]['request']
        for req, resp in zip(requests, responses):
            assert req['request_id'] == resp['request_id']
            rid = req['request_id']; request_ids.append(rid)
            charged = db.execute('select purpose,input_charged,output_charged,settled,usage from requests where id=?', (rid,)).fetchone()
            assert charged[0] == req['purpose'] == 'audit' and charged[3] == 1
            assert json.loads(charged[4]) == resp['usage']
            assert (charged[1], charged[2]) == (resp['usage']['prompt_tokens'], resp['usage']['completion_tokens'])
        rows.append({k: item[k] for k in ['name', 'feedback', 'profile', 'run_id', 'elapsed_seconds']} | {
            'protocol_valid': error is None, 'valid_negative': error is None and status(report) in {'contradicted', 'unknown'},
            'incorrect_supported': error is None and status(report) == 'supported',
            'status': status(report), 'error': error, 'error_fields': [p['path'] for p in problems],
            'requests': len(requests), 'input_tokens': sum(e['usage']['prompt_tokens'] for e in responses),
            'output_tokens': sum(e['usage']['completion_tokens'] for e in responses),
            'verdict_rows': {k: v for k, v in report.items() if k in {'target', 'coverage'}}})
        for path in directory.iterdir():
            if path.is_file(): hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(request_ids) == len(set(request_ids)) == phase['new_requests']
    for name, feedback in bodies:
        if feedback != 'generic': continue
        control, candidate = bodies[name, 'generic'], deepcopy(bodies[name, 'field_paths'])
        assert control['messages'][-1] != candidate['messages'][-1]
        candidate['messages'][-1] = control['messages'][-1]
        assert candidate == control
    groups = defaultdict(dict)
    for feedback in ['generic', 'field_paths']:
        selected = [r for r in rows if r['feedback'] == feedback]
        groups[feedback] = {key: sum(r[key] for r in selected) for key in [
            'protocol_valid', 'valid_negative', 'incorrect_supported', 'requests', 'input_tokens', 'output_tokens', 'elapsed_seconds']}
        groups[feedback]['n'] = len(selected)
    used = db.execute('select count(*) from requests').fetchone()[0]
    unknown = [r[0] for r in db.execute('select id from requests where settled=0')]
    started = db.execute("select count(*) from episodes where status='started'").fetchone()[0]
    units = db.execute('select count(*) from episodes').fetchone()[0]
    db.close()
    return {'label': LABEL, 'online_snapshot_sha': plan['snapshot']['sha'], 'groups': dict(groups),
            'rows': rows, 'request_ids': request_ids, 'artifact_hashes': hashes,
            'new_requests': phase['new_requests'], 'global_used': used, 'global_unknown_ids': unknown,
            'started_units': started, 'registered_units': units,
            'paired_prefixes_identical_except_repair_feedback': True,
            'natural_runs': phase['runs'], 'unexecuted_development_schedule': plan['schedule'] if not phase['runs'] else None,
            'stop_reason': phase['stop_reason'],
            'scope': 'Fixed historical failing reports; one fresh repair per condition. Format and overall negative status are separate from task accuracy. No natural-policy repair conversion measured.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.root)
    prefix = args.root / ('field_feedback_analysis_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    write_json(prefix.with_suffix('.json'), result)
    with prefix.with_suffix('.csv').open('x', encoding='utf-8', newline='') as f:
        columns = [k for k in result['rows'][0] if k != 'verdict_rows']
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader(); writer.writerows(result['rows'])
    print(json.dumps({'output': str(prefix.with_suffix('.json')), 'groups': result['groups'],
                      'new_requests': result['new_requests'], 'stop_reason': result['stop_reason'],
                      'paired_prefixes_identical_except_repair_feedback': result['paired_prefixes_identical_except_repair_feedback']}))
