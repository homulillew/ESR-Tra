"""Freeze nine development questions using baseline pilots only, never ESR outcomes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from summarize_strong_api import metrics


RULE = {
    'easy': 'At least two healthy pilots, both correct, each <=6 backend requests and <=12 model requests',
    'hard': 'At least two healthy pilots, none correct',
    'medium': 'Other healthy observations, including single healthy trials; high uncertainty',
    'diagnostic': 'No healthy pilot; not evidence of question difficulty',
    'health': 'Exclude explicit calibration exclusions, service/operator/context failures, protocol-stalled runs, or recorded judge disputes; retain original scores in primary records',
    'selection': 'Take first three per empirical stratum in original frozen order; fill shortages with remaining healthy candidates, then diagnostic candidates, all in original order; never call diagnostic failures hard',
    'uncertainty': 'All empirical labels provisional; one or two draws do not establish intrinsic difficulty',
}


def classify(rows):
    healthy = [r for r in rows if not r.get('calibration_excluded')
               and not r.get('evaluation_disputed')
               and r['outcome'] in {'submitted', 'abstained', 'budget_exhausted', 'generation_budget_exhausted'}
               and not r.get('systemic_pause')]
    if not healthy:
        return 'diagnostic', healthy
    if any(r['correct'] is None for r in healthy):
        raise ValueError('Every healthy submitted pilot must be judged before selection')
    if len(healthy) >= 2 and all(r['correct'] is True and r['backend_requests'] <= 6
                               and r['online_model_requests'] <= 12 for r in healthy):
        return 'easy', healthy
    if len(healthy) >= 2 and not any(r['correct'] is True for r in healthy):
        return 'hard', healthy
    return 'medium', healthy


def freeze(root):
    from strong_api import systemic_failure
    target = root/'dataset_splits/development.questions.jsonl'
    if target.exists():
        raise ValueError('Development set already frozen; never overwrite')
    if list(root.glob('*_development_*/manifest.json')) or list(root.glob('*_confirmation_*/manifest.json')):
        raise ValueError('Selection must precede ESR development and confirmation observations')
    pilot = [json.loads(x) for x in (root/'dataset_splits/pilot.questions.jsonl').read_text(encoding='utf-8').splitlines()]
    details = []
    for question in pilot:
        rows = []
        for manifest in sorted(root.glob(f'*_pilot_B_{question["qid"]}_*/manifest.json')):
            directory = manifest.parent
            if not (directory/'summary.json').exists():
                raise ValueError('Unfinished pilot must be accounted for first: '+directory.name)
            row = metrics(directory)
            row['calibration_excluded'] = (directory/'difficulty_calibration_exclusion.json').exists()
            row['evaluation_disputed'] = (directory/'evaluation_dispute.json').exists()
            row['systemic_pause'] = systemic_failure(json.loads((directory/'summary.json').read_text(encoding='utf-8')), directory)
            rows.append(row)
        if not rows or len(rows)>2:
            raise ValueError('Each frozen pilot must have one or two accounted episodes')
        level, healthy = classify(rows)
        details.append({'qid':question['qid'], 'difficulty':level, 'healthy_trials':len(healthy),
                        'uncertainty':'high' if len(healthy)>=2 else 'very high; single/no healthy observation',
                        'runs':rows})
    selected = []
    for level in ['easy', 'medium', 'hard']:
        selected.extend(d['qid'] for d in [d for d in details if d['difficulty']==level][:3])
    selected += [d['qid'] for d in details if d['qid'] not in selected and d['difficulty']!='diagnostic'][:9-len(selected)]
    selected += [d['qid'] for d in details if d['qid'] not in selected][:9-len(selected)]
    if len(selected)!=9:
        raise ValueError('Frozen pilot pool has fewer than nine candidates; inspect data without replacing samples')
    # Write in original hash order so treatment order cannot depend on difficulty/success.
    chosen = [q for q in pilot if q['qid'] in selected]
    data = ''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in chosen)
    record = {'rules':RULE, 'candidates':details, 'selected_qids':[q['qid'] for q in chosen],
              'selected_strata':dict(Counter(d['difficulty'] for d in details if d['qid'] in selected)),
              'question_file_sha256':hashlib.sha256(data.encode()).hexdigest(),
              'no_ESR_outcomes_used':True}
    with (target.parent/'development_selection.json').open('x',encoding='utf-8') as f:
        json.dump(record,f,indent=2)
    with target.open('x',encoding='utf-8',newline='\n') as f:
        f.write(data)
    print(json.dumps({k:record[k] for k in ['selected_qids','selected_strata','question_file_sha256']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='runs/strong_api_esr/CURRENT');a=p.parse_args()
    root=Path(a.root)
    if root.is_file():root=Path(root.read_text().strip())
    freeze(root)
