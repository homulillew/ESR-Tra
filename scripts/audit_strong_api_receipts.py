"""Read-only cross-check of durable global charges, episode receipts and exports."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def audit(root):
    with readonly(root/'global_budget.sqlite') as db:
        charges={r[0]:dict(zip(['purpose','settled','usage','input','output'],r[1:])) for r in db.execute(
            'select id,purpose,settled,usage,input_charged,output_charged from requests')}
    locations={};mismatches=[];models=Counter();missing_exports=[];checked_exports=0;settled_checked=0
    for path in sorted(root.rglob('ledger.sqlite')):
        relative=path.relative_to(root)
        if any(p.startswith(('test-temp','analysis-temp')) for p in relative.parts):continue
        with readonly(path) as db:
            events=[json.loads(r[0]) for r in db.execute('select payload from events order by seq')]
        requests=[e for e in events if e['type']=='generation_request' and e['request_id'] in charges]
        if not requests:continue
        generations={e['request_id']:e for e in events if e['type']=='generation'}
        for request in requests:
            rid=request['request_id'];charge=charges[rid]
            if rid in locations:mismatches.append({'kind':'duplicate_request_receipt','request_id':rid})
            locations[rid]=str(relative)
            if charge['purpose']!=request['purpose']:mismatches.append({'kind':'purpose','request_id':rid})
            generation=generations.get(rid,{})
            if generation.get('response',{}).get('model'):models[generation['response']['model']]+=1
            if charge['settled']:
                usage=generation.get('usage')
                if (usage!=json.loads(charge['usage']) or not usage
                    or usage['prompt_tokens']!=charge['input'] or usage['completion_tokens']!=charge['output']):
                    mismatches.append({'kind':'usage_or_charge','request_id':rid,'ledger':str(relative)})
                else:settled_checked+=1
            elif charge['input']!=request['reserved_input_tokens'] or charge['output']!=request['reserved_completion_tokens']:
                mismatches.append({'kind':'unknown_reservation','request_id':rid})
        for kind,name in [('generation_request','provider_requests.jsonl'),('generation','provider_responses.jsonl')]:
            export=path.parent/name
            if not export.exists():
                missing_exports.append(str(export.relative_to(root)));continue
            actual=[json.loads(line) for line in export.read_text(encoding='utf-8').splitlines() if line.strip()]
            expected=[e for e in events if e['type']==kind]
            if actual!=expected:mismatches.append({'kind':'export_differs_from_ledger','file':str(export.relative_to(root))})
            else:checked_exports+=1
    return {'timestamp':datetime.now(timezone.utc).isoformat(),'global_requests':len(charges),
            'charged_input_tokens':sum(c['input'] for c in charges.values()),
            'charged_output_tokens':sum(c['output'] for c in charges.values()),
            'unknown_or_outstanding_requests':sum(not c['settled'] for c in charges.values()),
            'requests_with_ledger':len(locations),'settled_receipts_verified':settled_checked,
            'exports_verified':checked_exports,'returned_models':dict(models),'mismatches':mismatches,
            'global_requests_without_episode_ledger':[r for r in charges if r not in locations],
            'missing_exports':missing_exports,
            'scope':'Read-only snapshot; active episodes may lack exports. Probe-specific receipts outside ledgers require separate review. No semantic correctness or full input-isolation claim.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='runs/strong_api_esr/CURRENT');args=p.parse_args()
    root=Path(args.root)
    if root.is_file():root=Path(root.read_text().strip())
    result=audit(root)
    output=root/('receipt_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'output':str(output),**result}))
    raise SystemExit(bool(result['mismatches']))
