"""Independent post-rollout answer grading using a locally pinned official BC+ template."""
import argparse
from datetime import datetime,timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys

from strong_api import ROOT, GlobalBudget, LanzClient, Ledger, AnthropicClient, RemoteConfig, UsageBudget, write_json, export
import yaml


def evaluate(directory, gold, template, transport, budget, *, max_requests=0):
    result=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    meta=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    terminal=result.get('terminal') or {}
    if (directory/'evaluation.json').exists():
        return json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))
    if meta['category']=='confirmation' and not (directory.parent/'FINAL_FREEZE.json').exists():
        raise ValueError('Confirmation is sealed until final freeze')
    if not terminal:
        raise ValueError('Cannot evaluate a still-running episode')
    if terminal.get('outcome')!='submitted':
        grade={'correct':False,'submitted':False,'method':'non-submission counts as incorrect','judge_requests':0}
    else:
        if meta['provider']['config']['model'] != transport.model:
            raise ValueError('Judge route must match this rollout model; do not silently grade old cohorts with a new model')
        question=gold[meta['qid']]['query']; answer=gold[meta['qid']]['answer']
        prompt=template.format(question=question,response=terminal['answer'],correct_answer=answer)
        judge_dir=directory/('judge_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));judge_dir.mkdir()
        ledger=Ledger(judge_dir/'ledger.sqlite');ledger.initialize({'kind':'offline_judge','qid':meta['qid'],'protocol':'official_grader_template_pinned'})
        c=AnthropicClient(transport,UsageBudget(2048),ledger,budget,config=RemoteConfig(model=transport.model,max_output_tokens=1024,temperature=0.0,max_requests=max_requests))
        messages=[{'role':'user','content':prompt}]; grade=None
        try:
            for attempt in range(2):
                text=c.complete(messages,purpose='judge')
                matches=re.findall(r'^\s*(?:\*\*)?correct(?:\*\*)?\s*:\s*(?:\*\*)?(yes|no)(?:\*\*)?\s*$',text,re.I|re.M)
                if len(matches)==1:
                    grade={'correct':matches[0].lower()=='yes','submitted':True,'method':'official_BC+_grader_with_'+transport.model,
                           'judge_text':text,'judge_requests':attempt+1,'usage':c.budget.summary()}
                    break
                messages += [{'role':'assistant','content':text},{'role':'user','content':"Repair only the output format: include exactly one line correct: yes or correct: no under the original grading criteria."}]
            if grade is None: grade={'correct':None,'submitted':True,'parse_error':True,'method':'judge_protocol_failure'}
        finally:
            export(ledger,judge_dir);ledger.close()
    write_json(directory/'evaluation.json',grade)
    return grade


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dirs',nargs='+',required=True);p.add_argument('--root',default=str(ROOT/'runs/strong_api_esr/CURRENT'))
    p.add_argument('--max-requests-per-answer',type=int,default=0,help='Bound all judge requests including repairs and transport retries; 0 keeps the existing default')
    a=p.parse_args();root=Path(a.root)
    if root.is_file(): root=Path(root.read_text().strip())
    config=yaml.safe_load((ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
    if not key: raise ValueError('Missing credential')
    transport=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL',config['provider']['base_url']),token=key,model=config['provider']['model'])
    budget=GlobalBudget(root/'global_budget.sqlite')
    template=(root/'evaluation_protocol/grader_template.txt').read_text(encoding='utf-8')
    selected=[root/r for r in a.run_dirs]
    for directory in selected:
        meta=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        if meta['category']=='confirmation' and not (root/'FINAL_FREEZE.json').exists():
            raise ValueError('Confirmation is sealed; references must not be loaded')
        if not json.loads((directory/'summary.json').read_text(encoding='utf-8')).get('terminal'):
            raise ValueError('All requested rollouts must finish before references are loaded')
        if meta['category']=='confirmation':
            from strong_api import snapshot
            from strong_api_freeze_guard import check_final_freeze
            check_final_freeze(root,snapshot(),config)
    # Load references only for completed requested runs, outside every rollout process.
    ids={json.loads((d/'manifest.json').read_text(encoding='utf-8'))['qid'] for d in selected}
    gold={}
    with (Path(config['dataset_root'])/'data/prepared/browsecomp_plus_decrypted.jsonl').open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if str(row['query_id']) in ids: gold[str(row['query_id'])]={'query':row['query'],'answer':row['answer']}
    for d in selected:
        r=evaluate(d,gold,template,transport,budget,max_requests=a.max_requests_per_answer)
        print(json.dumps({'run_id':d.name,'correct':r.get('correct'),'submitted':r.get('submitted'),'parse_error':r.get('parse_error',False)}),flush=True)
    print(json.dumps(budget.summary()),flush=True)
