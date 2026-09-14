"""Frozen ordered cohort, no reruns; reserve one post-run judge per question."""
import argparse
import json
from pathlib import Path
import sqlite3
import trace_hard_question_a3 as trace

NORMAL_TERMINALS = {'submitted', 'abstained', 'model_budget', 'action_budget', 'output_budget', 'time_budget', 'context_capacity'}


def remaining(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        cap = db.execute('SELECT cap FROM budget').fetchall()
        if len(cap) != 1 or type(cap[0][0]) is not int:
            raise ValueError('Invalid global ledger')
        used = db.execute('SELECT count(*) FROM requests').fetchone()[0]
        return cap[0][0] - used
    finally:
        db.close()


def preflight(path):
    cohort = json.loads(Path(path).read_text(encoding='utf-8'))
    if trace.sha(__file__) != cohort['runner_sha256']:
        raise ValueError('Frozen cohort runner changed')
    plans = []
    for entry in cohort['plans']:
        if trace.sha(entry['path']) != entry['sha256']:
            raise ValueError('Frozen case plan changed')
        p = json.loads(Path(entry['path']).read_text(encoding='utf-8'))
        if trace.sha(p['question_path']) != p['question_sha256']:
            raise ValueError('Frozen question changed')
        q = json.loads(Path(p['question_path']).read_text(encoding='utf-8'))
        if set(q) != {'qid', 'question'} or q['qid'] != p['qid']:
            raise ValueError('Question-only isolation failure')
        if p['config'] != trace.config().to_dict() or p['source_hashes'] != trace.source_hashes():
            raise ValueError('Frozen source/configuration changed')
        if p['collector_sha256'] != trace.sha(trace.__file__):
            raise ValueError('Frozen collector changed')
        if Path(p['output']).exists():
            raise FileExistsError(p['output'])
        plans.append(p)
    if [p['qid'] for p in plans] != cohort['qids'] or len(set(cohort['qids'])) != len(plans):
        raise ValueError('Wrong or duplicated question order')
    if len({p['output'] for p in plans}) != len(plans) or len({p['budget_path'] for p in plans}) != 1:
        raise ValueError('Invalid outputs or inconsistent ledgers')
    if cohort['judge_reserve'] != len(plans):
        raise ValueError('Exactly one reserved judge per question is required')
    required = sum(p['config']['max_model_calls'] for p in plans) + cohort['judge_reserve']
    if remaining(plans[0]['budget_path']) < required:
        raise ValueError('BLOCKED_BUDGET: full cohort plus judges not covered')
    return cohort, plans


def run(path):
    cohort, plans = preflight(path)
    root = Path(cohort['status_dir'])
    root.mkdir(parents=True, exist_ok=False)
    finished = []
    try:
        for i, (entry, plan) in enumerate(zip(cohort['plans'], plans)):
            required = sum(p['config']['max_model_calls'] for p in plans[i:]) + cohort['judge_reserve']
            if remaining(plan['budget_path']) < required:
                raise ValueError('BLOCKED_BUDGET: reserve lost before next case')
            trace.run(entry['path'])
            result = json.loads((Path(plan['output']) / 'result.json').read_text(encoding='utf-8'))
            terminal = result['terminal']['outcome']
            row = {'qid': plan['qid'], 'output': plan['output'], 'terminal': terminal,
                   'http_attempts': result['http_attempts'], 'utc': trace.utc()}
            finished.append(row); trace.save(root / f'{i:03d}.finished.json', row)
            print(json.dumps({'case_finished': row, 'remaining_cases': len(plans)-i-1}), flush=True)
            if terminal not in NORMAL_TERMINALS:
                raise RuntimeError('Cohort stopped for infrastructure/integrity/unknown terminal')
        trace.save(root / 'completed.json', {'finished': finished, 'utc': trace.utc(), 'judge_started': False})
    except Exception as exc:
        trace.save(root / 'stopped.json', {'type': type(exc).__name__, 'finished': finished,
                   'remaining_qids': [p['qid'] for p in plans[len(finished):]], 'utc': trace.utc(), 'retry': False})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if args.preflight_only:
        c, p = preflight(args.cohort)
        print(json.dumps({'preflight': 'passed', 'cases': len(p), 'max_policy': sum(x['config']['max_model_calls'] for x in p), 'judge_reserve': c['judge_reserve']}))
    else:
        run(args.cohort)
