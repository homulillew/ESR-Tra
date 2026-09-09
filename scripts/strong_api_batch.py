"""Serial, bounded schedule over already frozen question files. No agent implementation."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import yaml

from strong_api import ROOT, GlobalBudget, LanzClient, episode, write_json, snapshot


def main():
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['pilot','development','confirmation'])
    p.add_argument('--replicate',type=int,default=0)
    p.add_argument('--take',type=int,default=15)
    p.add_argument('--arms',nargs='+',choices=['B','E-off','E-soft'],default=['B'])
    a=p.parse_args()
    if a.replicate not in range(3) or a.take not in range(1,16): p.error('Invalid bounded schedule')
    if a.stage=='pilot' and (a.arms!=['B'] or a.replicate>=2): p.error('Pilot permits baseline only, at most two passes')
    root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
    if a.stage=='confirmation' and not (root/'FINAL_FREEZE.json').exists(): p.error('Confirmation still sealed')
    settings=yaml.safe_load((ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    source=root/'dataset_splits'/f'{a.stage}.questions.jsonl'
    rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines() if x.strip()]
    if any(set(r)!={'qid','question'} for r in rows): raise ValueError('Labels are forbidden in rollout input')
    chosen=rows[:a.take]
    conditions=snapshot()
    # Register all scheduled denominators before the first episode, including anything later interrupted.
    schedule={'stage':a.stage,'replicate':a.replicate,'arms':a.arms,'qids':[r['qid'] for r in chosen],
              'conditions':conditions,'status':'registered; unexecuted entries must remain visible'}
    schedule_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_json(root/f'schedule_{schedule_id}.json',schedule)
    key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
    if not key: raise ValueError('Missing credential')
    transport=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL',settings['provider']['base_url']),token=key,model=settings['provider']['model'])
    budget=GlobalBudget(root/'global_budget.sqlite',input_limit=settings['max_input_tokens_all_remote_calls'],
                        output_limit=settings['max_completion_tokens_all_remote_calls'],episode_limit=settings['max_real_episodes_total'],
                        probe_limit=settings['max_auxiliary_connectivity_requests'])
    outputs=[]
    for n,row in enumerate(chosen):
        # Alternate which arm goes first while keeping within-question adjacent time blocks.
        arms=a.arms if (n+a.replicate)%2==0 else list(reversed(a.arms))
        for arm in arms:
            # Do not silently repeat an already registered replicate in the same source version.
            for old in root.glob(f'*_{a.stage}_{arm}_{row["qid"]}_{a.replicate}/manifest.json'):
                previous=json.loads(old.read_text(encoding='utf-8'))
                if previous.get('source_hashes')==conditions['source_hashes']:
                    raise ValueError('This source-version replicate already exists; inspect it rather than resample')
            result,directory=episode(root,budget,transport,settings,question=row['question'],qid=row['qid'],arm=arm,
                                     category=a.stage,replicate=a.replicate,index=Path(settings['dataset_root'])/'indexes/esr-sqlite-bm25-20260909.sqlite')
            outputs.append(directory.name)
            terminal=(result.get('terminal') or {}).get('outcome')
            if terminal in {None,'service_error'} or result['invalid_actions']>=3:
                write_json(root/f'schedule_{schedule_id}_paused.json',{'runs':outputs,'reason':'infrastructure or repeated protocol failures; remaining schedule not executed'})
                print('Batch paused; inspect saved failures before continuing.',flush=True)
                return
    write_json(root/f'schedule_{schedule_id}_completed.json',{'runs':outputs})
    print(json.dumps(budget.summary()),flush=True)


if __name__=='__main__':main()
