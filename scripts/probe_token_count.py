"""One authorized count_tokens capability check; no model rollout or hidden retry."""
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import httpx
from strong_api import ROOT, LanzClient, GlobalBudget, write_json

root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
client=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL','http://lanz.hikvision.com/v3/anthropic/model'),token=key,model='EB-GLM-5.2')
body={'model':client.model,'messages':[{'role':'user','content':'Synthetic token counting fixture.'}]}
directory=root/('count_probe_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir()
budget=GlobalBudget(root/'global_budget.sqlite');rid=budget.reserve('probe',len(json.dumps(body).encode())+1024,0)
write_json(directory/'request.json',{'request_id':rid,'url':client.base_url+'/v1/messages/count_tokens','body':body})
try:
    r=httpx.post(client.base_url+'/v1/messages/count_tokens',headers=client._headers(),json=body,timeout=30)
    response={'status':r.status_code,'body':r.text.replace(key,'[REDACTED]')}
except Exception as exc:
    response={'error_type':type(exc).__name__}
write_json(directory/'response.json',response)
# No provider billing receipt means the input reservation remains conservatively charged.
print(json.dumps(response),flush=True)
