"""Inspect saved requests for the confirmed shared-ID schema bug; no model calls."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path


def anomalies(body):
    tools=body.get('tools',[])
    if not tools and '\nTools:\n' in body.get('system',''):
        tools=[{'name':t['name'],'input_schema':t['parameters']} for t in json.loads(body['system'].split('\nTools:\n',1)[1])]
    by_name={t['name']:t.get('input_schema',{}) for t in tools}
    problems=[]
    for name,field in [('open_page','docid'),('search','focus')]:
        node=by_name.get(name,{}).get('properties',{}).get(field,{})
        if field=='focus':node=node.get('properties',{}).get('claim_id',{})
        if 'enum' in node:problems.append({'field':name+'.'+field,'enum':node['enum'],'kind':'policy_unintended_id_enum'})
    audit=by_name.get('audit_report',{}).get('properties',{}).get('claims',{}).get('items',{}).get('properties',{})
    quote_id=audit.get('quotes',{}).get('items',{}).get('properties',{}).get('observation_id',{})
    if 'enum' in quote_id and quote_id['enum']==audit.get('claim_id',{}).get('enum'):
        problems.append({'field':'audit.claims.quotes.observation_id','enum':quote_id['enum'],'kind':'audit_claim_ids_leaked_to_observation_ids'})
    return problems


def main():
    root=Path(Path('runs/strong_api_esr/CURRENT').read_text().strip())
    findings=[];checked=0
    for path in sorted(root.rglob('provider_requests.jsonl')):
        if any(p.startswith(('test-temp','analysis-temp')) for p in path.relative_to(root).parts):continue
        for line in path.read_text(encoding='utf-8').splitlines():
            event=json.loads(line);checked+=1
            found=anomalies(event.get('request',{}))
            if found:findings.append({'request_id':event['request_id'],'purpose':event['purpose'],
                                      'file':str(path.relative_to(root)),'problems':found})
    by_kind=Counter(p['kind'] for f in findings for p in f['problems'])
    affected=sorted({Path(f['file']).parts[0] for f in findings})
    record={'checked_requests':checked,'affected_requests':len(findings),'affected_directories':affected,
            'field_findings':dict(by_kind),'findings':findings,
            'meaning':'Saved provider contracts contained ID constraints inconsistent with runtime. Original scores remain observations under those faulty conditions; not qualified final comparisons. This does not establish that every model error was caused by the schema bug.'}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output=root/f'schema_audit_{stamp}.json'
    with output.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    for name in affected:
        directory=root/name
        if ((directory/'manifest.json').exists() and (directory/'summary.json').exists()
            and not (directory/'schema_contract_warning.json').exists()):
            with (directory/'schema_contract_warning.json').open('x',encoding='utf-8') as f:
                json.dump({'audit':output.name,'meaning':record['meaning'],'original_records_unchanged':True},f,indent=2)
    print(json.dumps({'output':str(output),'checked':checked,'affected_requests':len(findings),'affected_directories':len(affected),'field_findings':dict(by_kind)}))


if __name__=='__main__':main()
