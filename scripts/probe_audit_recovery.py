"""Offline fixed-input protocol diagnostic; never feeds its result back to a rollout."""
from datetime import datetime,timezone
import getpass
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from strong_api import ROOT, LanzClient, GlobalBudget, Ledger, UsageBudget, AnthropicClient, RemoteConfig, ModelAuditor, write_json, export

root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
original=root/'20260909T094445291635Z_known-regression_E-soft_594_0'
db=sqlite3.connect((original/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)
events=[json.loads(r[0]) for r in db.execute('SELECT payload FROM events ORDER BY seq')];db.close()
first=next(e for e in events if e['type']=='generation_request' and e['purpose']=='audit')
payload=json.loads(first['request']['messages'][0]['content'])
views={e['delta']['observation']['observation_id']:e['delta']['observation'] for e in events if e['type']=='tool' and 'observation' in e['delta']}
state={k:payload[k] for k in ('target','answer','claims')}
key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
transport=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL','http://lanz.hikvision.com/v3/anthropic/model'),token=key,model='EB-GLM-5.2')
directory=root/('audit_diagnostic_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir()
ledger=Ledger(directory/'ledger.sqlite');ledger.initialize({'kind':'fixed_input_audit_protocol_diagnostic','original_request_id':first['request_id']})
budget=GlobalBudget(root/'global_budget.sqlite');budget.episode(directory.name,'diagnostic')
c=AnthropicClient(transport,UsageBudget(8192),ledger,budget,config=RemoteConfig(context_operating_cap=128000))
wrapper=SimpleNamespace(identity=c.identity,complete=lambda messages,purpose: c.complete(messages,purpose='diagnostic'))
try:
    result=ModelAuditor(wrapper).audit(payload['question'],state,[views[v['observation_id']] for v in payload['observations']])
    write_json(directory/'result.json',{'report':result,'usage':c.budget.summary(),'not_a_rollout':True})
    print({'valid_report':True,'claim_ids':[x['claim_id'] for x in result['claims']],'usage':c.budget.summary()},flush=True)
finally:
    export(ledger,directory);ledger.close()
    with budget.db:budget.db.execute('UPDATE episodes SET status=? WHERE id=?',('finished',directory.name))
