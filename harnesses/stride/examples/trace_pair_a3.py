"""Run two frozen independent episodes only when the existing ledger covers both."""
import argparse
import json
from pathlib import Path
import sqlite3

import trace_question_a3 as trace


def preflight(pair_path):
    pair = json.loads(Path(pair_path).read_text(encoding='utf-8'))
    entries = pair['plans']
    if len(entries) != 2:
        raise ValueError('Expected exactly two independent episodes')
    plans = []
    for entry in entries:
        if trace.sha(entry['path']) != entry['sha256']:
            raise ValueError('Frozen plan changed')
        plan = json.loads(Path(entry['path']).read_text(encoding='utf-8'))
        question = json.loads(Path(plan['question_path']).read_text(encoding='utf-8-sig'))
        if (trace.sha(plan['question_path']) != plan['question_sha256'] or
                set(question) != {'qid', 'question'} or question['qid'] != plan['qid']):
            raise ValueError('Frozen question-only record changed')
        if Path(plan['output']).exists():
            raise FileExistsError(plan['output'])
        if plan['config'] != trace.config().to_dict():
            raise ValueError('Frozen configuration changed')
        if plan['source_hashes'] != trace.source_hashes() or plan['collector_sha256'] != trace.sha(trace.__file__):
            raise ValueError('Frozen source changed')
        plans.append(plan)
    if len({p['qid'] for p in plans}) != 2 or len({p['output'] for p in plans}) != 2:
        raise ValueError('Duplicate episode')
    ledgers = {str(Path(p['budget_path']).resolve()) for p in plans}
    if len(ledgers) != 1:
        raise ValueError('Both episodes must use the same existing ledger')
    db = sqlite3.connect(Path(next(iter(ledgers))).as_uri() + '?mode=ro', uri=True)
    try:
        caps = db.execute('SELECT cap FROM budget').fetchall()
        if len(caps) != 1 or type(caps[0][0]) is not int:
            raise ValueError('Invalid budget')
        used = db.execute('SELECT count(*) FROM requests').fetchone()[0]
        required = sum(p['config']['max_model_calls'] for p in plans)
        if caps[0][0] - used < required:
            raise ValueError(f'BLOCKED_BUDGET: remaining={caps[0][0]-used}, required={required}')
        for plan in plans:
            if db.execute('SELECT count(*) FROM requests WHERE run=?', (plan['output'],)).fetchone()[0]:
                raise ValueError('Episode already started')
    finally:
        db.close()
    return pair


def run(pair_path):
    pair = preflight(pair_path)
    for entry in pair['plans']:
        trace.run(entry['path'])
        plan = json.loads(Path(entry['path']).read_text(encoding='utf-8'))
        result = json.loads((Path(plan['output']) / 'result.json').read_text(encoding='utf-8'))
        # Conservative queue stop: preserve any non-submitted episode for review.
        if result['terminal']['outcome'] != 'submitted':
            raise RuntimeError('PAIR_STOPPED: episode did not submit; no retry')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if args.preflight_only:
        preflight(args.pair)
        print('PAIR_PREFLIGHT_OK: no network calls')
    else:
        run(args.pair)
