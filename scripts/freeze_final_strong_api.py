"""Seal final conditions after complete development comparisons, before confirmation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from strong_api import ROOT, snapshot, write_json
import yaml


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(root, comparison, reason, tests):
    if (root/'FINAL_FREEZE.json').exists():raise ValueError('Final version already frozen; never overwrite')
    if list(root.glob('*_confirmation_*/manifest.json')):raise ValueError('Confirmation was already opened')
    result=json.loads(comparison.read_text(encoding='utf-8'))
    if result['stage']!='development' or result['replicates']!=2 or result['questions']!=9:
        raise ValueError('Require nine development questions with two paired replicates before final freeze')
    now=snapshot();settings=yaml.safe_load((ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    sources={k:v for k,v in now['source_hashes'].items() if k.startswith(('src/esr_harness/','api/'))}
    if sources!=result['conditions']['sources'] or settings!=result['conditions']['settings']:
        raise ValueError('Current online code/config differs from measured development version')
    test_bytes=tests.read_bytes()
    test_text=test_bytes.decode('utf-16' if test_bytes.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
    if ' passed' not in test_text or ' failed' in test_text or ' error' in test_text.lower():
        raise ValueError('Require a successful saved test log')
    files={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in [
        root/'dataset_splits/development.questions.jsonl',root/'dataset_splits/development_selection.json',
        root/'dataset_splits/confirmation.questions.jsonl',root/'dataset_splits/selection.json',
        root/'evaluation_protocol/grader_template.txt',root/'evaluation_protocol/source_metadata.json']}
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'candidate':result['esr'],'reason':reason,
            'source_snapshot':now,'online_sources':sources,'settings':settings,'sealed_files':files,
            'development_comparison':str(comparison),'development_comparison_sha256':sha(comparison),
            'test_log':str(tests),'test_log_sha256':sha(tests),
            'confirmation_plan':{'questions':9,'arms':['B',result['esr']],'replicates':3,'episodes':54,
                                 'order':'alternate within-question adjacent arms by original index plus replicate parity'},
            'judge':{'model':settings['provider']['model'],'temperature':0.0,'max_output_tokens':1024,
                     'protocol_repair_attempts':1,'protocol':'pinned official BC+ grader',
                     'limitation':'same gateway model as policy; correlated error risk; alias not weight-pinned'},
            'targets':settings['targets'],'no_confirmation_results_observed':True}
    write_json(root/'FINAL_FREEZE.json',record)
    print(json.dumps({'frozen':True,'candidate':result['esr'],'planned_confirmation_episodes':54}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--comparison',required=True);p.add_argument('--reason',required=True)
    p.add_argument('--tests',required=True);a=p.parse_args()
    root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
    freeze(root,Path(a.comparison),a.reason,Path(a.tests))
