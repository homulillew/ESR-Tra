"""Print semantically distinct response groups for offline human review."""
import argparse
import json
from pathlib import Path


def inspect(root, evidence=True):
    data = json.loads((Path(root) / 'REVIEW_DIGEST.json').read_text(encoding='utf-8'))
    metrics = dict(data['metrics']); metrics['terminal'] = dict(metrics['terminal'])
    metrics['terminal'].pop('basis', None)
    metrics.pop('first_request_capabilities', None)
    print('METRICS', json.dumps(metrics, ensure_ascii=True))
    groups = {}
    for row in data['rounds']:
        summary = {'content': row['content'], 'actions': [
            {'tool': action['tool'], 'arguments': action['arguments'], 'executed': action['executed'],
             'ok': action['result'].get('ok'), 'code': action['result'].get('code'),
             'evidence_ref': action['result'].get('evidence', {}).get('ref'),
             'matches': action['result'].get('matches')}
            for action in row['actions']]}
        groups.setdefault(json.dumps(summary, sort_keys=True), []).append(row['round'])
    for key, rounds in groups.items():
        print('ROUNDS', rounds, key)
    if evidence:
        for ev in data['evidence']:
            print('EVIDENCE', json.dumps({k: ev[k] for k in ('ref', 'document', 'start', 'end', 'text',
                   'first_request', 'visible_rounds', 'shelf_restored_rounds', 'final_cited')}, ensure_ascii=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root'); p.add_argument('--no-evidence', action='store_true')
    args = p.parse_args(); inspect(args.root, not args.no_evidence)
