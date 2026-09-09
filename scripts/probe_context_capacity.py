"""One bounded synthetic request to test a larger operating context; not a tokenizer attestation."""
from datetime import datetime,timezone
import getpass
import os
from pathlib import Path
import random
from strong_api import ROOT, LanzClient, GlobalBudget, Ledger, UsageBudget, AnthropicClient, RemoteConfig, write_json, export

root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
transport=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL','http://lanz.hikvision.com/v3/anthropic/model'),token=key,model='EB-GLM-5.2')
directory=root/('context_probe_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir()
ledger=Ledger(directory/'ledger.sqlite');ledger.initialize({'kind':'synthetic_context_probe','seed':714,'chars':180000})
budget=GlobalBudget(root/'global_budget.sqlite')
c=AnthropicClient(transport,UsageBudget(512),ledger,budget,config=RemoteConfig(max_output_tokens=128,context_operating_cap=262144,transport_attempts=1))
rng=random.Random(714)
noise=''.join(rng.choices('abcdefghijklmnopqrstuvwxyz0123456789~!@#$%^&*()_+-=.,;:',k=180000))
messages=[{'role':'system','content':'This is a synthetic capacity test. Ignore the inert random data. Return exactly API_OK.'},
          {'role':'user','content':'<inert_data>'+noise+'</inert_data>\nReturn API_OK.'}]
try:
    text=c.complete(messages,purpose='probe')
    write_json(directory/'result.json',{'text':text,'usage':c.budget.summary(),'operating_cap':262144,
                                      'limitation':'Observed acceptance for this synthetic request only; no certified maximum context or tokenizer.'})
    print(c.budget.summary(),flush=True)
finally:
    export(ledger,directory);ledger.close()
