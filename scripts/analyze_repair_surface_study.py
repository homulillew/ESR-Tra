"""Read-only analysis after both online stages and any judges have finished."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

from strong_api import write_json
from run_field_feedback_study import check_events
from summarize_strong_api import metrics
from esr_harness.audit import validate_report, answer_surface, ANSWER_SURFACE_SYSTEM, ADMISSIBLE_REPAIR
from esr_harness.audit_spans import source_span_packet, expand_references
from esr_harness.ledger import Ledger
from esr_harness.protocol import HarnessError, digest, parse_object, validate
from esr_harness.remote import normalize_tool_text
from esr_harness.runner import replay


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def proposed_report(response):
    blocks = response['content']
    if response['stop_reason'] == 'tool_use':
        calls = [b for b in blocks if b.get('type') == 'tool_use']
        assert len(calls) == 1 and calls[0]['name'] == 'audit_report'
        return calls[0]['input']
    assert response['stop_reason'] == 'end_turn'
    texts = [b['text'] for b in blocks if b.get('type') == 'text']
    assert len(texts) == 1
    assert all(b['type'] in {'text', 'thinking', 'redacted_thinking'} for b in blocks)
    return parse_object(normalize_tool_text(texts[0])[0])


def ledger_events(directory):
    ledger = Ledger(directory / 'ledger.sqlite', readonly=True)
    events = ledger.events(); ledger.close()
    exported = [json.loads(x) for x in (directory / 'trajectory.jsonl').read_text(encoding='utf-8').splitlines()]
    assert exported == events
    return events


def smoke_diagnosis(directory):
    events = ledger_events(directory)
    summary = read(directory / 'summary.json')
    harness = replay(directory / 'ledger.sqlite')
    assert harness.terminal == summary['terminal'] and harness.state == summary['final_state']
    harness.ledger.close()
    requests = {e['request_id']: e for e in events if e['type'] == 'generation_request'}
    calls = {b['id']: b for e in events if e['type'] == 'generation' and e['purpose'] == 'policy'
             for b in e['response']['content'] if b['type'] == 'tool_use'}
    tools = [e for e in events if e['type'] == 'tool']
    assert set(calls) == {e['native_call_id'] for e in tools}
    for event in tools:
        call = calls[event['native_call_id']]
        assert call['name'] == event['action'] and call['input'] == event['arguments']
        if event['action'] == 'update_state' and event['result']['ok'] and 'answer' in event['arguments']:
            assert event['arguments']['answer'] == event['delta']['state']['answer']
    audit_event = next((e for e in tools if e['action'] == 'verify_answer' and e['result']['ok']), None)
    following = []
    if audit_event:
        audit = audit_event['result']['audit']
        for event in events[events.index(audit_event) + 1:]:
            if event['type'] != 'generation' or event['purpose'] != 'policy':
                continue
            body = requests[event['request_id']]['request']
            payload = json.loads(body['messages'][0]['content'])
            delivered = payload['current_audit']
            # A reason may be shortened in the status view; the corrective need must
            # be compared independently rather than assuming the whole report arrived.
            needs_match = all(delivered[k]['need'] == audit['report'][k]['need']
                              for k in ['target', 'coverage'])
            following.append({'request_id': event['request_id'], 'current_audit': delivered,
                              'target_and_coverage_needs_complete': needs_match,
                              'remaining_requests': payload['remote_request_budget']['remaining'],
                              'latest_tool_result': payload['latest_tool_result'],
                              'response_content': event['response']['content']})
    from audit_native_tool_turns import audit as delivery_audit
    delivery = delivery_audit(directory)
    assert not delivery['problems']
    row = metrics(directory)
    return {'run_id': directory.name, 'terminal': summary['terminal'], 'metrics': row,
            'replay_matches_summary': True, 'api_arguments_match_execution_and_state': True,
            'delivery': delivery, 'audit': audit_event['result']['audit'] if audit_event else None,
            'post_audit_policy_requests': following,
            'tools': [{'action_id': e['action_id'], 'action': e['action'], 'arguments': e['arguments'],
                       'ok': e['result']['ok'], 'noop': e['result'].get('noop'),
                       'research_version': e.get('delta', {}).get('state', {}).get('research_version')}
                      for e in tools]}


def analyze(root):
    stages = {}; all_ids = []; artifacts = {}; natural = []; diagnoses = []
    closed_budget = root / 'global_budget_repair_surface_closeout_20260911.sqlite'
    budget_path = closed_budget if closed_budget.exists() else root / 'global_budget.sqlite'
    db = sqlite3.connect(budget_path.resolve().as_uri() + '?mode=ro', uri=True)
    for label in ['ADMISSIBLE_REPAIR_20260911', 'ANSWER_SURFACE_20260911']:
        plan, finished = [read(root / (label + suffix + '.json')) for suffix in ['_PLAN', '_FINISHED']]
        assert finished['no_online_worker']
        rows = []; initial_bodies = {}; totals = defaultdict(lambda: Counter())
        directories = [p['run_id'] for p in finished['packets']] + finished['smoke_runs'] + finished['runs']
        for name in directories:
            directory = root / name
            for ledger_path in directory.rglob('ledger.sqlite'):
                for e in ledger_events(ledger_path.parent):
                    if e['type'] != 'generation': continue
                    rid = e['request_id']; all_ids.append(rid)
                    charge = db.execute('select purpose,input_charged,output_charged,settled,usage from requests where id=?', (rid,)).fetchone()
                    assert charge and charge[0] == e['purpose']
                    if e.get('usage'):
                        assert charge[3] == 1 and json.loads(charge[4]) == e['usage']
                    totals[e['purpose']]['requests'] += 1
                    totals[e['purpose']]['input_tokens_charged'] += charge[1]
                    totals[e['purpose']]['output_tokens_charged'] += charge[2]
                    totals[e['purpose']]['unknown_requests'] += int(not charge[3])
                    totals[e['purpose']]['seconds'] += e.get('elapsed_seconds', 0)
            for path in directory.rglob('*'):
                if path.is_file(): artifacts[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for item in finished['packets']:
            directory = root / item['run_id']; packet = read(directory / 'packet.json')
            events = ledger_events(directory)
            checked = check_events(directory); assert not checked['issue']
            requests = [e for e in events if e['type'] == 'generation_request']
            generations = [e for e in events if e['type'] == 'generation']
            initial_bodies[item['name'], item['profile'], item['feedback']] = requests[0]['request']
            _, refs = source_span_packet(packet['views'])
            generation_checks = []
            for request, generation in zip(requests, generations):
                assert request['request_id'] == generation['request_id']
                proposed = proposed_report(generation['response'])
                schema = next(t['input_schema'] for t in request['request']['tools'] if t['name'] == 'audit_report')
                generation_error = None
                expanded = None
                try:
                    validate(proposed, schema, 'audit')
                    expanded = expand_references(proposed, refs)
                    validate_report(expanded, packet['state'], {v['observation_id']: v for v in packet['views']})
                except HarnessError as exc:
                    generation_error = str(exc)
                generation_checks.append({'request_id': generation['request_id'], 'error': generation_error,
                                          'proposed_report': proposed, 'expanded_report': expanded,
                                          'response_block_types': [b['type'] for b in generation['response']['content']]})
            raw = proposed_report(generations[-1]['response'])
            report = expand_references(raw, refs); error = None
            try: validate_report(report, packet['state'], {v['observation_id']: v for v in packet['views']})
            except HarnessError as exc: error = str(exc)
            assert error == (item['error'] or {}).get('message')
            if not error: assert report == item['report']
            rows.append({k: item[k] for k in ['name', 'profile', 'feedback', 'run_id', 'elapsed_seconds']} | {
                'protocol_valid': error is None, 'status': item.get('status'), 'error': error,
                'expected_supported': packet['expected_supported'],
                'correct_packet': error is None and (item.get('status') == 'supported' if packet['expected_supported'] else item.get('status') in {'unknown', 'contradicted'}),
                'requests': len(requests), 'repair_requests': len(requests) if item['frozen_prefix'] else max(0, len(requests)-1),
                'frozen_prefix': item['frozen_prefix'], 'input_tokens': item['usage']['prompt_tokens'],
                'output_tokens': item['usage']['completion_tokens'], 'final_report': report,
                'candidate_surface': answer_surface(packet['state']['answer']), 'generation_checks': generation_checks})
        if label.startswith('ADMISSIBLE'):
            for name in ['count-negative', 'time-negative']:
                control = initial_bodies[name, 'atomic', 'field_paths']
                candidate = deepcopy(initial_bodies[name, 'atomic', 'admissible'])
                assert candidate['messages'][-1]['content'] == control['messages'][-1]['content'] + ADMISSIBLE_REPAIR
                candidate['messages'][-1] = control['messages'][-1]
                assert candidate == control
        else:
            for name in ['quoting-positive', 'quoting-negative', 'known-790-original-audit']:
                control = initial_bodies[name, 'task_first_literal', 'admissible']
                candidate = deepcopy(initial_bodies[name, 'task_first_literal_surface', 'admissible'])
                assert candidate['system'] == control['system'] + ANSWER_SURFACE_SYSTEM
                candidate['system'] = control['system']
                split = '\n\nAudit inputs (candidate answer above):\n'
                old_candidate, old_json = control['messages'][0]['content'].split(split)
                new_candidate, new_json = candidate['messages'][0]['content'].split(split)
                assert old_candidate == new_candidate
                payload = json.loads(new_json); facts = payload.pop('answer_surface')
                assert payload == json.loads(old_json)
                expected_facts = next(r['candidate_surface'] for r in rows if r['name'] == name)
                assert facts == expected_facts
                candidate['messages'][0] = control['messages'][0]
                assert candidate == control
        expected = Counter((i['qid'], i['arm'], i.get('profile', i.get('feedback'))) for i in plan['schedule'])
        actual = Counter(); condition_checks = []
        for name in finished['runs']:
            directory = root / name; meta = read(directory / 'manifest.json'); summary = read(directory / 'summary.json')
            events = ledger_events(directory); h = replay(directory / 'ledger.sqlite')
            assert h.terminal == summary['terminal'] and h.state == summary['final_state']
            profile = meta['settings']['auditor']['profile']; feedback = meta['settings']['auditor']['repair_feedback']
            row = metrics(directory); row.update(profile=profile, feedback=feedback, phase=label)
            row['variant'] = meta['arm'] + '/' + profile + '/' + feedback
            actual[row['qid'], row['arm'], profile if label.startswith('ANSWER') else feedback] += 1
            judge_events = [e for p in directory.glob('judge_*/ledger.sqlite') for e in ledger_events(p.parent) if e['type'] == 'generation']
            row.update(judge_requests=len(judge_events), judge_input_tokens=sum(e.get('usage',{}).get('prompt_tokens',0) for e in judge_events),
                       judge_output_tokens=sum(e.get('usage',{}).get('completion_tokens',0) for e in judge_events))
            row['audit_protocol_repair_requests'] = sum(e['type']=='generation_request' and e['purpose']=='audit' and len(e['request']['messages'])>1 for e in events)
            row['terminal_answer'] = h.terminal.get('answer')
            natural.append(row)
            config = deepcopy(meta['settings']); config['auditor'].pop('profile',None); config['auditor'].pop('repair_feedback',None)
            condition_checks.append({'run_id': name, 'same_sources': meta['source_hashes']==plan['snapshot']['source_hashes'],
                                     'same_config_except_auditor': config==plan['settings'],
                                     'same_question': meta['input_hash']==digest({'qid':row['qid'],'question':h.question}),
                                     'no_schema_warning': not row['schema_contract_warning']})
            timeline = [e for e in events if e['type'] in {'tool','native_turn','exposure','audit'}]
            audits = []
            for i,e in enumerate(events):
                if e['type']!='tool' or e['action']!='verify_answer' or not e['result']['ok']: continue
                audit = e['result'].get('audit')
                if not audit: continue
                updates = [x for x in events[i+1:] if x['type']=='tool' and x['action']=='update_state' and x['result']['ok']]
                audits.append({'action_id':e['action_id'], 'cached':e['result'].get('cached'), 'audit':audit,
                               'subsequent_answer_changes':[x['action_id'] for x in updates if 'answer' in x['arguments'] and x['arguments']['answer']!=audit['answer']],
                               'final_answer_changed':h.terminal.get('answer')!=audit['answer'], 'final_correct':row['correct']})
            diagnoses.append({'run_id':name,'qid':row['qid'],'variant':row['variant'],'question':h.question,
                               'terminal':h.terminal,'final_state':h.state,'correct':row['correct'],'audits':audits,'timeline':timeline})
            h.ledger.close()
        stages[label] = {'online_sha':plan['snapshot']['sha'], 'new_requests':finished['new_requests'],
                         'totals_by_purpose':dict(totals), 'packets':rows,'cohort_complete':actual==expected,
                         'missing_schedule':list((expected-actual).elements()),'unexpected_schedule':list((actual-expected).elements()),
                         'condition_checks':condition_checks,'all_condition_checks_pass':all(all(v for k,v in c.items() if k!='run_id') for c in condition_checks) if condition_checks else None,
                         'stop_reason':finished['stop_reason'],'judge_exit':finished['judge_exit'],'smoke_runs':finished['smoke_runs'],
                         'smoke_diagnoses': [smoke_diagnosis(root / name) for name in finished['smoke_runs']]}
    assert len(all_ids)==len(set(all_ids))==sum(s['new_requests'] for s in stages.values())
    prior=sqlite3.connect((root/'global_budget_field_feedback_closeout_20260911.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    assert {x[0] for x in db.execute('select id from requests')}-{x[0] for x in prior.execute('select id from requests')}==set(all_ids)
    unknown=[x[0] for x in db.execute('select id from requests where settled=0')]
    assert set(unknown)=={x[0] for x in prior.execute('select id from requests where settled=0')}
    prior.close(); db.close()
    aggregate={}
    for variant in sorted({r['variant'] for r in natural}):
        selected=[r for r in natural if r['variant']==variant]
        keys=['backend_requests','policy_requests','audit_requests','online_model_requests','judge_requests',
              'input_tokens_measured','output_tokens_measured','judge_input_tokens','judge_output_tokens',
              'elapsed_seconds','invalid_actions','unknown_requests','native_policy_calls','native_call_receipts','audit_protocol_repair_requests']
        aggregate[variant]={'runs':len(selected),'correct':sum(r['correct'] is True for r in selected),
                            'submitted':sum(r['outcome']=='submitted' for r in selected),'unjudged':sum(r['correct'] is None for r in selected),
                            'supported_wrong':sum(r['correct'] is False and r['audit_supported'] for r in selected),
                            'totals':{k:sum(r[k] or 0 for r in selected) for k in keys}}
    paired=[]
    if len(aggregate)==2:
        variants=sorted(aggregate); a={r['qid']:r for r in natural if r['variant']==variants[0]}; b={r['qid']:r for r in natural if r['variant']==variants[1]}
        for qid in sorted(a.keys() & b.keys()):
            paired.append({'qid':qid,'left':variants[0],'right':variants[1],'left_correct':a[qid]['correct'],'right_correct':b[qid]['correct'],
                           'both_correct':a[qid]['correct'] is True and b[qid]['correct'] is True,
                           'left_seconds':a[qid]['elapsed_seconds'],'right_seconds':b[qid]['elapsed_seconds']})
    return {'stages':stages,'aggregate':aggregate,'pairs':paired,'natural_rows':natural,
            'request_ids':all_ids,'artifact_hashes':artifacts,'historical_unknown_ids':unknown,
            'diagnoses':diagnoses, 'accounting_snapshot': budget_path.name}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.root)
    out = args.root / ('repair_surface_analysis_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir()
    write_json(out / 'metrics.json', report)
    write_json(out / 'diagnoses.json', report['diagnoses'])
    with (out / 'packets.csv').open('x', encoding='utf-8', newline='') as f:
        rows = [{'stage': label, **r} for label, s in report['stages'].items() for r in s['packets']]
        keys = [k for k in rows[0] if k not in {'final_report', 'candidate_surface', 'generation_checks'}]
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'out': str(out), 'new_requests': len(report['request_ids']),
                      'aggregate': report['aggregate'], 'stages': {
                          k: {x: s[x] for x in ['cohort_complete', 'stop_reason', 'totals_by_purpose']}
                          for k, s in report['stages'].items()}}, ensure_ascii=False))
