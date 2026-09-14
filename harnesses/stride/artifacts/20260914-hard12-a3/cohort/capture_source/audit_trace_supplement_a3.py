"""Offline supplemental audit of completed archives; no model or index queries."""
import json
from pathlib import Path
import sys
from collections import Counter
from stride_search.archive import Archive
from stride_search.contract import canonical
from trace_question_a3 import save, table


def audit(root):
    root = Path(root)
    data = json.loads((root / 'analysis-data.json').read_text(encoding='utf-8'))
    a = Archive(root / 'episode.sqlite', readonly=True)
    try:
        events = list(a.events())
        times = {e['seq']: e['utc'] for e in map(json.loads, (root / 'trajectory.jsonl').read_text(encoding='utf-8').splitlines())}
        report = a.report()
        requests = {e['payload']['round']: a.load_request(e['payload']['request']) for e in events if e['kind'] == 'model_request'}
        responses = {}
        correspondence = []
        for e in events:
            if e['kind'] != 'model_response':
                continue
            p = e['payload']; raw = a.json(p['raw']); responses[p['round']] = raw
            captured = json.loads((root / 'http' / f"{p['round']:03d}" / 'response.body').read_bytes())
            correspondence.append({'round': p['round'], 'response_json_equivalent': raw == captured})
        links = []; last = 0
        for e in events:
            if e['kind'] != 'action_execution':
                continue
            p = e['payload']; ex = a.json(p['object'])
            backend = [v for v in events if last < v['seq'] < e['seq'] and v['kind'].startswith('backend_')]
            result_event = next(v for v in events if v['kind'] == 'action_result' and v['payload']['round'] == ex['round'] and v['payload']['tool_call_id'] == ex['tool_call_id'])
            links.append({'round': ex['round'], 'tool_call_id': ex['tool_call_id'], 'tool': ex['tool'],
                          'arguments': ex['arguments'], 'execution_seq': e['seq'], 'execution_utc': times[e['seq']],
                          'backend_events': backend, 'result_seq': result_event['seq'],
                          'result': ex['result'], 'executed': ex['executed']})
            last = e['seq']
        table(root / 'TOOL_EXECUTION_LINKS.csv', links, ['round', 'tool_call_id', 'tool', 'arguments', 'execution_seq', 'execution_utc', 'backend_events', 'result_seq', 'result', 'executed'])
        lifecycle = []
        for ev in data['evidence']:
            e = dict(ev)
            snap = next(v for v in events if v['kind'] == 'snapshot' and v['payload']['document'] == e['document'])
            prior = [v for v in events if v['seq'] < snap['seq'] and v['kind'] == 'backend_response']
            e['backend_response_utc'] = times[prior[-1]['seq']] if prior else None
            e['first_request_utc'] = next((r['utc'] for r in data['rounds'] if r['round'] == e['first_request']), None)
            e['original_group_visible_rounds'] = [r for r in e['visible_rounds'] if r not in e['shelf_restored_rounds']]
            e['shelf_evicted_rounds'] = [r['round'] for r in data['rounds'] if e['ref'] in r['shelf_evicted']]
            lifecycle.append(e)
        save(root / 'EVIDENCE_LIFECYCLE.json', lifecycle)
        rounds = []; order = []
        for r, raw in responses.items():
            message = raw['choices'][0]['message']
            declared = message.get('tool_calls', [])
            executed = [v for v in links if v['round'] == r]
            order.append({'round': r, 'ids_match_in_order': [v['id'] for v in declared] == [v['tool_call_id'] for v in executed]})
            rounds.append({'round': r, 'message': message, 'actions': executed,
                           'context': next(v for v in data['rounds'] if v['round'] == r)})
        save(root / 'ROUND_REVIEW_INPUT.json', rounds)
        usage = {}
        for field in ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens'):
            values = [h.get(field) for h in data['http']]
            usage[field] = {'total': sum(values) if all(v is not None for v in values) else None,
                            'known_sum': sum(v for v in values if v is not None),
                            'missing_calls': sum(v is None for v in values)}
        metrics_path = root / 'metrics.sanitized.json'
        metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
        save(root / 'metrics.archive-report-original.json', metrics)
        metrics['usage_normalized'] = usage
        metrics['usage_note'] = 'Archive empty sums are preserved in usage_known; absent provider fields are null in usage_normalized.'
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        save(root / 'SUPPLEMENTAL_CHECKS.json', {'response_correspondence': correspondence, 'native_execution_order': order,
             'usage_normalized': usage, 'report': report,
             'event_counts': dict(Counter(e['kind'] for e in events)),
             'raw_windows_match_saved_snapshot': all(a.get(e['snapshot'])[e['start']:e['end']] == e['text'] for e in lifecycle)})
        print(json.dumps({'root': str(root), 'rounds': len(rounds), 'response_match': all(v['response_json_equivalent'] for v in correspondence), 'order_match': all(v['ids_match_in_order'] for v in order)}))
    finally:
        a.close()


if __name__ == '__main__':
    audit(sys.argv[1])
