"""Explicit matched cohorts and question-cluster bootstrap; no gold or model calls."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
from summarize_strong_api import metrics


def online_conditions(meta):
    return {'sources':{k:v for k,v in meta['source_hashes'].items() if k.startswith(('src/esr_harness/', 'api/'))},
            'settings':meta['settings'], 'provider':meta['provider']}


def effect(pairs):
    def ratio(key, subset):
        base=sum(a[key] for a,b in subset)
        return sum(b[key] for a,b in subset)/base-1 if base else None
    common=[(a,b) for a,b in pairs if a['correct'] is True and b['correct'] is True]
    result={'accuracy_difference_pp':100*mean(int(b['correct'] is True)-int(a['correct'] is True) for a,b in pairs),
            'baseline_accuracy':mean(a['correct'] is True for a,b in pairs),
            'esr_accuracy':mean(b['correct'] is True for a,b in pairs),
            'both_correct_pairs':len(common),
            'correct_completion_time_change':ratio('elapsed_seconds',common)}
    for key in ['backend_requests','online_model_requests','input_tokens_measured','input_tokens_charged','output_tokens_measured','charged_output_tokens']:
        result[key+'_change']=ratio(key,pairs)
        result['both_correct_'+key+'_change']=ratio(key,common)
    return result


def clustered(pairs_by_question, strata, draws=5000):
    groups=defaultdict(list)
    for qid in pairs_by_question:groups[strata.get(qid,'unstratified')].append(qid)
    rng=random.Random(714);samples=defaultdict(list)
    for _ in range(draws):
        ids=[rng.choice(group) for group in groups.values() for _ in group]
        e=effect([pair for qid in ids for pair in pairs_by_question[qid]])
        for k,v in e.items():
            if v is not None:samples[k].append(v)
    def interval(values):
        values.sort();n=len(values)
        return [values[int((n-1)*.025)], values[int((n-1)*.975)]]
    return {k:{'percentile_95':interval(v),'defined_draws':len(v)} for k,v in samples.items()}


def compare(root, stage, esr, replicates, reference_run):
    if stage=='confirmation' and not (root/'FINAL_FREEZE.json').exists():
        raise ValueError('Confirmation remains sealed')
    ref=json.loads((root/reference_run/'manifest.json').read_text(encoding='utf-8'))
    conditions=online_conditions(ref)
    rows=[json.loads(x) for x in (root/f'dataset_splits/{stage}.questions.jsonl').read_text(encoding='utf-8').splitlines()]
    qids=[q['qid'] for q in rows]
    cohort={}
    for path in root.glob(f'*_{stage}_*/manifest.json'):
        meta=json.loads(path.read_text(encoding='utf-8'))
        if meta['arm'] not in ['B',esr] or meta['qid'] not in qids or meta['replicate'] not in range(replicates):continue
        if online_conditions(meta)!=conditions:continue
        key=(meta['qid'],meta['arm'],meta['replicate'])
        if key in cohort:raise ValueError('Duplicate matching cohort entry; explicit adjudication required')
        cohort[key]=metrics(path.parent)
    expected={(q,a,r) for q in qids for a in ['B',esr] for r in range(replicates)}
    if expected-set(cohort):
        raise ValueError('Incomplete predeclared cohort, missing '+repr(sorted(expected-set(cohort))))
    if any(row['correct'] is None for row in cohort.values()):
        raise ValueError('Submitted answers require completed independent grading')
    pairs={q:[(cohort[(q,'B',r)],cohort[(q,esr,r)]) for r in range(replicates)] for q in qids}
    if stage=='development':
        selection=json.loads((root/'dataset_splits/development_selection.json').read_text(encoding='utf-8'))
        strata={d['qid']:d['difficulty'] for d in selection['candidates']}
    else:
        selection=json.loads((root/'dataset_splits/selection.json').read_text(encoding='utf-8'))
        strata={d['qid']:d['prior'] for d in selection['candidates']}
    result={'stage':stage,'esr':esr,'questions':len(qids),'replicates':replicates,'planned_episodes':len(expected),
            'conditions':conditions,'point_estimates':effect([p for ps in pairs.values() for p in ps]),
            'bootstrap':clustered(pairs,strata),'bootstrap_unit':'question; all replicates resampled together within frozen strata',
            'bootstrap_seed':714,'bootstrap_draws':5000,
            'both_correct_analysis':'conditional on both submitted answers correct; not an unconditional speed claim',
            'unknown_requests':sum(r['unknown_requests'] for r in cohort.values()),
            'pricing':'unavailable; token and request costs only, no fabricated currency estimate',
            'runs':list(cohort.values()),'per_question':{q:effect(ps) for q,ps in pairs.items()}}
    out=root/('comparison_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
    (out/'paired_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    import csv
    with (out/'paired_results.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['qid',*next(iter(result['per_question'].values())).keys()])
        writer.writeheader();writer.writerows({'qid':q,**v} for q,v in result['per_question'].items())
    print(json.dumps({'output':str(out),'point_estimates':result['point_estimates'],'questions':len(qids)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['development','confirmation'])
    p.add_argument('--esr',choices=['E-off','E-soft'],required=True);p.add_argument('--replicates',type=int,required=True)
    p.add_argument('--reference-run',required=True);p.add_argument('--root',default='runs/strong_api_esr/CURRENT');a=p.parse_args()
    if a.replicates not in range(1,4):p.error('Replicates must be 1..3')
    root=Path(a.root)
    if root.is_file():root=Path(root.read_text().strip())
    compare(root,a.stage,a.esr,a.replicates,a.reference_run)
