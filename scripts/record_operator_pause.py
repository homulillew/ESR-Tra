"""Record an already stopped research worker without fabricating a model answer or usage."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from strong_api import ROOT, Ledger, UsageBudget, export, write_json
from esr_harness.runner import replay,summary

p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--stop-record',required=True);a=p.parse_args()
root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip());directory=root/a.run_id
stop=json.loads(Path(a.stop_record).read_text(encoding='utf-8'))
if (directory/'summary.json').exists():raise ValueError('Already summarized; never overwrite')
h=replay(directory/'ledger.sqlite')
if h.terminal is not None:raise ValueError('Worker already has a terminal result; inspect before exporting')
draft=h.state['answer'];h.ledger.close()
ledger=Ledger(directory/'ledger.sqlite')
ledger.append({'type':'end','terminal':{'outcome':'operator_paused','answer':'','final_draft':draft,'evidence_status':'unverified',
                                      'reason':stop['reason']},'operator_stop_record':stop})
export(ledger,directory);ledger.close()
h=replay(directory/'ledger.sqlite')
meta=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
usage=UsageBudget(meta['settings']['max_completion_tokens_per_episode_including_audit'],events=h.ledger.events())
r=summary(h,usage);r['run_id']=a.run_id
r['elapsed_seconds']=(datetime.fromisoformat(stop['timestamp'])-datetime.fromisoformat(meta['timestamp_utc'])).total_seconds()
r['latency_measurement']='external wall clock; monotonic endpoint unavailable after forced stop'
write_json(directory/'summary.json',r);write_json(directory/'exit.json',{'exit_code':1,'terminal':h.terminal,'operator_paused':True})
h.ledger.close()
import sqlite3
db=sqlite3.connect(root/'global_budget.sqlite')
with db:db.execute('UPDATE episodes SET status=? WHERE id=?',('operator_paused',a.run_id))
print({'run_id':a.run_id,'outcome':'operator_paused','unknown_reservations_retained':usage.unknown_usage_requests})
