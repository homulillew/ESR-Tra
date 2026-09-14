"""Join immutable rollouts with external labels and provider usage, offline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from trace_question_a3 import save, table, utc


def summarize(cohort_path, judge_dir, output):
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    cohort = read(cohort_path); judge_dir = Path(judge_dir); output = Path(output)
    completed = read(Path(cohort['status_dir']) / 'completed.json')
    if [r['qid'] for r in completed['finished']] != cohort['qids']:
        raise ValueError('Incomplete cohort')
    gold = {r['qid']: r for r in read(judge_dir / 'all-cases.json')}
    labels = {r['qid']: r for r in read(judge_dir / 'results/judgments.json')}
    if set(labels) != {q for q, c in gold.items() if c['terminal'] == 'submitted'}:
        raise ValueError('Judge labels must cover every submitted answer exactly')
    output.mkdir(parents=True, exist_ok=False)
    rows = []; policy_http = []; validations = []
    for entry in cohort['plans']:
        plan = read(entry['path']); root = Path(plan['output']); qid = plan['qid']
        post = read(root / 'POSTHOC_CHECKS.json'); metrics = post['metrics']; data = read(root / 'analysis-data.json')
        policy_http.extend(data['http']); label = labels.get(qid)
        if label and label['head'] != gold[qid]['head']:
            raise ValueError('Judge label bound to a different source head')
        errors = Counter(a['result'].get('code') for a in data['actions'] if not a['result'].get('ok'))
        terminal = metrics['terminal']; submitted = terminal['outcome'] == 'submitted'
        row = {'qid': qid, 'slot': plan['slot'], 'head': gold[qid]['head'],
               'outcome': terminal['outcome'], 'submitted': submitted, 'answer': terminal.get('answer', ''),
               'refs': terminal.get('refs', []), 'gold_answer': gold[qid]['correct_answer'],
               'judge_correct': label['correct'] if label else None,
               'score_correct': label['correct'] if label else False,
               'scoring_basis': 'post_run_semantic_judge' if label else 'no_formal_answer',
               'judge_attempts': 1 if label else 0, 'policy_attempts': metrics['http_attempts'],
               'native_calls': metrics['native_calls'], 'executed_actions': metrics['executed_actions'],
               'action_counts': metrics['action_counts'], 'action_error_counts': dict(errors),
               'query_executions': metrics['query_execution_count'], 'query_cache_hits': metrics['exact_query_cache_hits'],
               'backend_calls': metrics['backend_calls'], 'backend_by_kind': metrics['backend_by_kind'],
               'evidence_windows': len(data['evidence']), 'compaction_requests': metrics['compaction_requests'],
               'shelf_restore_requests': metrics['shelf_restore_requests'],
               'shelf_capacity_evictions': metrics['shelf_capacity_evictions'],
               'shelf_wire_bytes': metrics['direct_shelf_restore_wire_bytes'],
               'wire_body_bytes': metrics['total_wire_body_bytes'], 'elapsed_seconds': terminal['elapsed_seconds'],
               'http_seconds': metrics['http_latency_seconds'], 'backend_seconds': metrics['backend_latency_seconds'],
               'usage': read(root / 'SUPPLEMENTAL_CHECKS.json')['usage_normalized'],
               'formal_final_rounds': metrics['final_request_rounds'],
               'evidence_review': f'../q{qid}/EVIDENCE_AUDIT.md',
               'interaction_review': f'../q{qid}/INTERACTION_ANALYSIS.md'}
        rows.append(row)
        integ = read(root / 'INTEGRITY_CHECKS.json'); supp = read(root / 'SUPPLEMENTAL_CHECKS.json')
        validations.append({'qid': qid, 'head': integ['archive']['head'], 'question_exact': metrics['first_request_question_exact'],
             'request_json_equivalent': integ['all_json_equivalent'],
             'response_json_equivalent': all(v['response_json_equivalent'] for v in supp['response_correspondence']),
             'native_execution_order': all(v['ids_match_in_order'] for v in supp['native_execution_order']),
             'raw_windows_exact': supp['raw_windows_match_saved_snapshot']})
    judge_http = [read(p) for p in sorted((judge_dir / 'results/http').glob('*/metadata.json'))]
    def usage(http):
        result = {}
        for field in ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens'):
            values = [r.get(field) for r in http]
            result[field] = {'total': sum(values) if all(v is not None for v in values) else None,
                 'known_sum': sum(v for v in values if v is not None), 'missing_calls': sum(v is None for v in values)}
        return result
    first = read(cohort['plans'][0]['path'])
    ledger = sqlite3.connect(Path(first['budget_path']).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        cap = ledger.execute('SELECT cap FROM budget').fetchone()[0]
        used = ledger.execute('SELECT count(*) FROM requests').fetchone()[0]
        budget = {'cap': cap, 'used': used, 'remaining': cap - used,
                  'role_counts': dict(ledger.execute('SELECT role,count(*) FROM requests GROUP BY role'))}
    finally:
        ledger.close()
    summary = {'utc': utc(), 'qids': cohort['qids'], 'total': len(rows),
         'submitted': sum(r['submitted'] for r in rows), 'outcomes': dict(Counter(r['outcome'] for r in rows)),
         'correct': sum(r['score_correct'] for r in rows),
         'policy_attempts': len(policy_http), 'judge_attempts': len(judge_http),
         'total_attempts': len(policy_http) + len(judge_http), 'budget_after': budget,
         'policy_usage': usage(policy_http), 'judge_usage': usage(judge_http),
         'policy_wire_bytes': sum(r['request_bytes'] for r in policy_http),
         'judge_wire_bytes': sum(r['request_bytes'] for r in judge_http),
         'policy_http_seconds': sum(r['latency_seconds'] for r in policy_http),
         'judge_http_seconds': sum(r['latency_seconds'] for r in judge_http),
         'policy_elapsed_seconds_sum': sum(r['elapsed_seconds'] for r in rows),
         'money_cost': None, 'money_cost_reason': 'No verified service pricing supplied',
         'scoring_note': 'Non-submission scores false, judge_correct remains null; no fabricated semantic judge calls',
         'confidence_note': 'project_judge_result.confidence is parsed from candidate response/default 1.0, not judge certainty',
         'independence_note': 'Separate post-run calls to the same configured model family, not a different judge deployment'}
    save(output / 'cases.json', rows); save(output / 'summary.json', summary)
    save(output / 'TRACE_VALIDATION.json', validations)
    table(output / 'RESULTS.csv', rows, ['qid','outcome','answer','gold_answer','judge_correct','score_correct',
           'scoring_basis','policy_attempts','judge_attempts','native_calls','executed_actions','query_executions',
           'query_cache_hits','backend_calls','evidence_windows','compaction_requests','shelf_restore_requests',
           'elapsed_seconds','head','action_error_counts'])
    print(json.dumps(summary))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cohort', required=True)
    p.add_argument('--judge-dir', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); summarize(a.cohort, a.judge_dir, a.output)
