"""Four predeclared fixed-prefix diagnostics; no rollout continuation or gold access."""
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sqlite3
from strong_api import ROOT,GlobalBudget,LanzClient,Ledger,AnthropicClient,RemoteConfig,UsageBudget,write_json,export,snapshot
from esr_harness.protocol import canonical,parse_object,validate,HarnessError
from esr_harness.audit import validate_report,status
import yaml


def events(directory):
    db=sqlite3.connect((directory/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    result=[json.loads(r[0]) for r in db.execute('select payload from events order by seq')];db.close()
    if not (directory/'summary.json').exists():raise ValueError('Source episode must finish first')
    return result


def main():
    root=Path((ROOT/'runs/strong_api_esr/CURRENT').read_text().strip())
    settings=yaml.safe_load((ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    key=os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
    if not key:raise ValueError('Missing credential')
    transport=LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL',settings['provider']['base_url']),token=key,model=settings['provider']['model'])
    budget=GlobalBudget(root/'global_budget.sqlite')
    plans=[('policy','20260909T112404438386Z_development_B_149_0','a1'),
           ('policy','20260909T112516263737Z_development_E-off_149_0','a1'),
           ('policy','20260909T112516263737Z_development_E-off_149_0','a15'),
           ('audit','20260909T112842871118Z_development_E-soft_149_0','first_failed_report')]
    group=root/('dispatch_diagnostics_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));group.mkdir()
    write_json(group/'plan.json',{'plan':plans,'policy_max_calls':3,'audit_max_repair_calls':1,'no_semantic_tool_execution':True,
                                'sampling':'same temperature/output cap; transport retries remain bounded and charged','source':snapshot()})
    for n,(kind,source,aid) in enumerate(plans):
        saved=events(root/source);directory=group/f'{n}_{kind}';directory.mkdir()
        rid=group.name+'_'+str(n);budget.episode(rid,'diagnostic')
        ledger=Ledger(directory/'ledger.sqlite');ledger.initialize({'kind':'fixed_prefix_diagnostic','source_run':source,'source_action':aid})
        client=AnthropicClient(transport,UsageBudget(8192),ledger,budget,
            config=RemoteConfig(model=transport.model,max_output_tokens=4096,temperature=0.6,context_operating_cap=128000,
                                policy_tool_interface='dispatcher'))
        write_json(directory/'manifest.json',{'source_run':source,'source_action':aid,'kind':kind,'provider':client.identity})
        if kind=='policy':
            action=next(e for e in saved if e['type']=='tool' and e['action_id']==aid)
            decision=next(e for e in saved if e['type']=='decision' and e['decision_id']==action['decision_id'])
            messages=decision['messages']
            contract=json.loads(messages[0]['content'].split('\nTools:\n',1)[1])
        else:
            request=next(e for e in saved if e['type']=='generation_request' and e['purpose']=='audit')
            generation=next(e for e in saved if e['type']=='generation' and e['request_id']==request['request_id'])
            report=next(b['input'] for b in generation['response']['content'] if b['type']=='tool_use')
            body=request['request'];payload=json.loads(body['messages'][0]['content'])
            all_views={e['result']['observation']['observation_id']:e['result']['observation'] for e in saved if e['type']=='tool' and 'observation' in e['result']}
            views={v['observation_id']:all_views[v['observation_id']] for v in payload['observations']}
            assert all(views[v['observation_id']]['text']==v['text'] for v in payload['observations'])
            try:validate_report(report,payload,views)
            except HarnessError as exc:feedback=str(exc)
            else:raise ValueError('Expected a failed report, not a successful control')
            messages=[{'role':'system','content':body['system']+'\nSchema:\n'+canonical(body['tools'][0]['input_schema'])},
                      *body['messages'],{'role':'assistant','content':canonical(report)},
                      {'role':'user','content':'Repair protocol only; keep all original evidence: '+feedback}]
        try:
            text=client.complete(messages,purpose='diagnostic');parsed=parse_object(text)
            if kind=='policy':
                if set(parsed)!={'action','arguments'}:raise HarnessError('protocol_error','Exactly one action envelope required')
                definition=next((t for t in contract if t['name']==parsed['action']),None)
                if definition is None:raise HarnessError('protocol_error','Action not available in original prefix')
                validate(parsed['arguments'],definition['parameters'],'arguments')
                result={'valid':True,'action':parsed['action'],'proposal':parsed,'executed':False}
            else:
                validate_report(parsed,payload,views)
                result={'valid':True,'audit_status':status(parsed),'report':parsed,'semantic_correctness':'not established by schema/quote validation'}
        except HarnessError as exc:
            result={'valid':False,'error_code':exc.code,'error':str(exc)}
        finally:export(ledger,directory);ledger.close()
        write_json(directory/'result.json',{**result,'usage':client.budget.summary()})
        with budget.db:budget.db.execute('update episodes set status=? where id=?',('diagnostic_finished',rid))
        print(json.dumps({'kind':kind,'source_action':aid,'valid':result['valid'],'action':result.get('action'),'audit_status':result.get('audit_status'),'error':result.get('error')}),flush=True)
    print(json.dumps(budget.summary()),flush=True)


if __name__=='__main__':main()
