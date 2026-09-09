"""Offline fixed-prefix diagnostic using only a previously returned search result."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from strong_api import ROOT, Ledger, Harness, Config, UsageBudget, GlobalBudget, AnthropicClient, RemoteConfig, write_json
from esr_harness.runner import messages_for
from esr_harness.protocol import HarnessError


def inspect(root,name):
    directory=root/name
    db=sqlite3.connect((directory/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    events=[json.loads(r[0]) for r in db.execute('select payload from events order by seq')];db.close()
    header=Ledger(directory/'ledger.sqlite',readonly=True)
    metadata=header.header;header.close()
    last_index=max(i for i,e in enumerate(events) if e['type']=='tool')
    action=events[last_index]
    if action['action']!='search' or not action['result']['ok']:
        raise ValueError('Diagnostic requires a last admitted search before context termination')
    calls=[]
    def recorded_search(query,top_k):
        assert query==action['arguments']['query']
        calls.append({'query':query,'top_k':top_k,'source':'saved provider-independent retrieval result; no backend request'})
        return action['result']['results']
    retriever=SimpleNamespace(identity=metadata['retriever'],deterministic=True,search=recorded_search)
    ledger=Ledger();ledger.initialize(metadata)
    for e in events[:last_index]:ledger.append(e)
    h=Harness(metadata['question'],retriever,config=Config(**metadata['config']),ledger=ledger,manifest=metadata['manifest'])
    transport=SimpleNamespace(base_url='http://offline.invalid',model='EB-GLM-5.2')
    # No complete()/HTTP method is ever called. GlobalBudget is not needed for rendering.
    client=AnthropicClient(transport,UsageBudget(24000,events=ledger.events()),ledger,None,
                           config=RemoteConfig(context_operating_cap=128000))
    def admissible(preview):
        try:return client.fits_for_admission(messages_for(preview,client))
        except HarnessError as exc:
            if exc.code=='context_overflow':return False
            raise
    h.admission=admissible
    result=h.execute(action['action'],action['arguments'])
    try:
        next_messages=messages_for(h,client);next_fits=True
    except HarnessError:
        next_messages=None;next_fits=False
    ledger.close()
    return {'source_run':name,'source_action_id':action['action_id'],'new_result':result,'next_prompt_fits':next_fits,
            'remote_requests':0,'backend_requests':0,'replayed_searches':calls,
            'diagnostic':'fixed recorded prefix; not a natural rollout or accuracy result','next_messages':next_messages}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dirs',nargs='+',required=True);a=p.parse_args()
    root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
    rows=[inspect(root,name) for name in a.run_dirs]
    out=root/('capacity_replay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
    write_json(out/'diagnostics.json',rows)
    for row in rows:print(json.dumps({k:row[k] for k in ['source_run','source_action_id','new_result','next_prompt_fits','remote_requests']}))
