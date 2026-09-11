"""Serial, bounded schedule over already frozen question files. No agent implementation."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import yaml

from strong_api import ROOT, GlobalBudget, LanzClient, episode, write_json, snapshot, systemic_failure
from strong_api_freeze_guard import online_source_hashes
from esr_harness.protocol import HarnessError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['pilot','development','confirmation'])
    p.add_argument('--replicate',type=int,default=0)
    p.add_argument('--take',type=int,default=15)
    p.add_argument('--start',type=int,default=0,help='Zero-based offset in the original frozen order; never reorders samples')
    p.add_argument('--arms',nargs='+',choices=['B','E-off','E-soft'],default=['B'])
    p.add_argument('--root',default=str(ROOT/'runs/strong_api_esr/CURRENT'))
    a=p.parse_args()
    if a.replicate not in range(3) or a.take not in range(1,16) or a.start not in range(15): p.error('Invalid bounded schedule')
    if a.stage=='pilot' and (a.arms!=['B'] or a.replicate>=2): p.error('Pilot permits baseline only, at most two passes')
    root=Path(a.root)
    if root.is_file():root=Path(root.read_text().strip())
    if a.stage=='confirmation' and not (root/'FINAL_FREEZE.json').exists(): p.error('Confirmation still sealed')
    settings=yaml.safe_load((ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    source=root/'dataset_splits'/f'{a.stage}.questions.jsonl'
    rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines() if x.strip()]
    if any(set(r)!={'qid','question'} for r in rows): raise ValueError('Labels are forbidden in rollout input')
    chosen=rows[a.start:a.start+a.take]
    if not chosen: p.error('No questions at this frozen offset')
    conditions=snapshot()
    if a.stage=='confirmation':
        from strong_api_freeze_guard import check_final_freeze
        check_final_freeze(root,conditions,settings,a.arms)
    # Register all scheduled denominators before the first episode, including anything later interrupted.
    schedule={'stage':a.stage,'replicate':a.replicate,'arms':a.arms,'start':a.start,'qids':[r['qid'] for r in chosen],
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
    for n,row in enumerate(chosen,start=a.start):
        # Alternate which arm goes first while keeping within-question adjacent time blocks.
        arms=a.arms if (n+a.replicate)%2==0 else list(reversed(a.arms))
        for arm in arms:
            if (root/'PAUSE_NEW_EPISODES.json').exists():
                write_json(root/f'schedule_{schedule_id}_paused.json',{'runs':outputs,'reason':'operator cooperative pause flag','remaining_schedule':'not executed'})
                print('Batch paused between episodes; current records retained.',flush=True)
                return
            try:
                budget.ensure_request_capacity(settings.get('max_remote_requests_per_episode',1))
            except HarnessError as exc:
                write_json(root/f'schedule_{schedule_id}_paused.json',{'runs':outputs,'reason':exc.code,
                           'remaining_schedule':'not executed','request_allowance':budget.request_status()})
                print('Batch paused before episode: '+str(exc),flush=True)
                return
            if a.stage=='pilot' and len(list(root.glob(f'*_pilot_B_{row["qid"]}_*/manifest.json')))>=2:
                raise ValueError('This pilot question already used its two-episode allowance across all versions')
            # Do not silently repeat an already registered replicate in the same source version.
            for old in root.glob(f'*_{a.stage}_{arm}_{row["qid"]}_{a.replicate}/manifest.json'):
                previous=json.loads(old.read_text(encoding='utf-8'))
                if (online_source_hashes(previous)==online_source_hashes(conditions)
                    and previous['settings']==settings
                    and previous['provider']['url']==transport.base_url+'/v1/messages'
                    and previous['provider']['config']['model']==transport.model):
                    raise ValueError('This source-version replicate already exists; inspect it rather than resample')
            result,directory=episode(root,budget,transport,settings,question=row['question'],qid=row['qid'],arm=arm,
                                     category=a.stage,replicate=a.replicate,index=Path(settings['dataset_root'])/'indexes/esr-sqlite-bm25-20260909.sqlite')
            outputs.append(directory.name)
            pause=systemic_failure(result,directory)
            if pause:
                write_json(root/f'schedule_{schedule_id}_paused.json',{'runs':outputs,'reason':pause,'remaining_schedule':'not executed'})
                print('Batch paused; inspect saved failures before continuing.',flush=True)
                return
    write_json(root/f'schedule_{schedule_id}_completed.json',{'runs':outputs})
    print(json.dumps(budget.summary()),flush=True)


if __name__=='__main__':main()
