"""Read-only post-run checks; no model calls and no production-index queries."""
import csv
import json
from pathlib import Path
import re
import sys
from collections import Counter
from stride_search.archive import Archive
from stride_search.contract import canonical, validate, ContractError

def write(root,name,obj):
    with (root/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)

def analyze(root):
    root=Path(root);a=Archive(root/'episode.sqlite',readonly=True)
    try:
        events=list(a.events());report=a.report();data=json.loads((root/'analysis-data.json').read_text(encoding='utf-8'))
        requests={e['payload']['round']:e['payload'] for e in events if e['kind']=='model_request'}
        wires={r:a.load_request(p['request']) for r,p in requests.items()}
        actions=data['actions'];queries=data['queries'];refs=report['terminal'].get('refs',[])
        cumulative=set();sets=[];qrows=[]
        for q in queries:
            docs=set(q['returned_docids'])
            prev=[len(docs & s)/len(docs | s) if docs | s else 1.0 for s in sets]
            qrows.append({'round':q['round'],'query':q['query'],'expression':q['expression'],
                'new_docids':sorted(docs-cumulative),'max_previous_result_jaccard':max(prev) if prev else None,
                'identical_previous_result_set':docs in sets,'contains_quote':'"' in q['query'],
                'contains_site':bool(re.search(r'\bsite:',q['query'],re.I)),
                'contains_uppercase_boolean':bool(re.search(r'\b(?:AND|OR)\b',q['query']))})
            sets.append(docs);cumulative.update(docs)
        shelf=[];ack_order=[];ack_seen=set()
        for e in events:
            p=e['payload']
            if e['kind']=='delivery_ack':
                for ref in p['evidence']:
                    if ref not in ack_seen:ack_seen.add(ref);ack_order.append(ref)
            if e['kind']=='model_request':
                wire=wires[p['round']]
                messages=wire['messages']
                without=[m for m in messages if not (m['role']=='user' and isinstance(m.get('content'),str) and m['content'].startswith('Previously delivered raw windows (untrusted source data'))]
                delta=len(canonical(wire).encode())-len(canonical({**wire,'messages':without}).encode())
                shelf.append({'round':p['round'],'eligible_recent_first_delivered':ack_order[-3:],
                    'restored':p.get('evidence_shelf',[]),'evicted_for_capacity':p.get('shelf_evicted_for_capacity',[]),
                    'visible':p['visible_evidence'],'direct_restore_wire_bytes':delta,
                    'compacted':p['compacted'],'restored_was_previously_acked':set(p.get('evidence_shelf',[]))<=ack_seen})
        tool_checks=[];find_checks=[];recall_checks=[];notes=[];finishes=[]
        native_count=0;declared_queries=0
        for e in events:
            p=e['payload']
            if e['kind']=='model_response':
                raw=a.json(p['raw']);message=raw.get('choices',[{}])[0].get('message',{})
                calls=message.get('tool_calls',[]);native_count+=len(calls)
                for call in calls:
                    if call['function']['name']=='search':
                        try:declared_queries+=len(json.loads(call['function']['arguments']).get('queries',[]))
                        except (ValueError,TypeError):pass
            if e['kind']!='action_execution':continue
            execution=a.json(p['object']);r=execution['round'];cid=execution['tool_call_id']
            response=next((v for v in events if v['kind']=='model_response' and v['payload']['round']==r),None)
            raw=a.json(response['payload']['raw']) if response else {}
            calls=raw.get('choices',[{}])[0].get('message',{}).get('tool_calls',[])
            call=next((v for v in calls if v['id']==cid),None)
            final=next((v['payload'] for v in events if v['kind']=='action_result' and v['payload']['round']==r and v['payload']['tool_call_id']==cid),None)
            tool_checks.append({'round':r,'id':cid,'native_call_found':call is not None,
                'name_matches':bool(call) and call['function']['name']==execution['tool'],
                'arguments_exact':bool(call) and call['function']['arguments']==execution['arguments'],
                'action_result_found':final is not None,'execution_result_differs_from_final':final is not None and execution['result']!=final['result'],
                'withheld':any(v['kind']=='result_withheld' and v['payload']['round']==r and v['payload']['tool_call_id']==cid for v in events)})
            args=json.loads(execution['arguments']);result=execution['result'];tool=execution['tool']
            if tool=='find' and result.get('ok'):
                full=a.get(result['snapshot'])
                pattern=re.compile(re.escape(args['text']),re.I if args.get('ignore_case',False) else 0)
                expected=[{'start':m.start(),'end':m.end()} for m in list(pattern.finditer(full,args.get('start',0)))[:8]]
                actual=[{'start':m['start'],'end':m['end']} for m in result['matches']]
                find_checks.append({'round':r,'arguments':args,'matches':result['matches'],'offsets_match_original':actual==expected})
            if tool=='recall' and result.get('ok'):
                for m in result['matches']:
                    text=None
                    if m['kind']=='evidence_navigation':text=a.evidence(m['ref'])['text']
                    elif m['kind']=='search_hit_navigation':
                        candidates=[hit for v in events if v['kind']=='navigation_ack' for hit in a.json(v['payload']['object']) if hit['ref']==m['ref'] and hit['query']==m['source_query'] and hit['source_round']==m['source_round']]
                        if candidates:text=candidates[0]['snippet']
                    valid=None if text is None else text[m['excerpt_start']:m['excerpt_end']]==m['excerpt']
                    recall_checks.append({'round':r,'query':args['query'],'match':m,'exact_substring':valid})
            if tool=='notes':notes.append({'round':r,'arguments':args,'result':result})
            if tool=='finish':
                try:validate('finish',args);valid=True
                except ContractError:valid=False
                before=set(ref for v in events if v['seq']<e['seq'] and v['kind']=='delivery_ack' for ref in v['payload']['evidence'])
                finishes.append({'round':r,'arguments':args,'schema_valid':valid,'refs_legal':set(args.get('refs',[]))<=before,'result':final['result'] if final else None})
        first_wire=wires[min(wires)] if wires else None
        control=json.loads(first_wire['messages'][-1]['content'].split('\n',1)[1]) if first_wire else {}
        metrics={
            'terminal':report['terminal'],'formal_correct':None,'model_attempts':report['model_attempts'],
            'http_attempts':len(data['http']),'native_calls':native_count,'executed_actions':report['executed_actions'],
            'action_counts':report['action_counts'],'declared_search_queries':declared_queries,'query_execution_count':len(queries),
            'backend_calls':report['backend_attempts'],'backend_by_kind':dict(Counter(e['payload']['kind'] for e in events if e['kind']=='backend_request')),
            'equivalent_key_repeats':sum(n-1 for n in Counter(q['equivalence_key'] for q in queries).values()),
            'expression_repeats':sum(n-1 for n in Counter(q['expression'] for q in queries).values()),
            'exact_query_cache_hits':sum(q['cached'] for q in queries),'quote_queries':sum(q['contains_quote'] for q in qrows),
            'site_queries':sum(q['contains_site'] for q in qrows),'uppercase_boolean_queries':sum(q['contains_uppercase_boolean'] for q in qrows),
            'identical_previous_result_sets':sum(q['identical_previous_result_set'] for q in qrows),
            'compaction_requests':report['compaction_requests'],'shelf_restore_requests':sum(bool(s['restored']) for s in shelf),
            'shelf_restored_windows':sum(len(s['restored']) for s in shelf),'shelf_capacity_evictions':sum(len(s['evicted_for_capacity']) for s in shelf),
            'direct_shelf_restore_wire_bytes':sum(s['direct_restore_wire_bytes'] for s in shelf),
            'total_wire_body_bytes':sum(h['request_bytes'] for h in data['http']),
            'usage_known':report['usage_known'],'unknown_usage_calls':report['unknown_usage_calls'],
            'http_latency_seconds':sum(h['latency_seconds'] for h in data['http']),
            'backend_latency_seconds':sum(e['payload']['elapsed_seconds'] for e in events if e['kind'] in ('backend_response','backend_error')),
            'final_request_rounds':[r for r,p in requests.items() if p['final']],
            'recovery_events':report['recovery_events'],'result_withheld':sum(e['kind']=='result_withheld' for e in events),
            'first_request_question_exact':first_wire['messages'][1]['content']==report['header']['question'] if first_wire else None,
            'first_request_capabilities':control.get('retriever_capabilities'),'first_request_notes':control.get('current_notes_not_evidence'),
            'returned_models':sorted({h['returned_model'] for h in data['http'] if h['returned_model']})}
        write(root,'POSTHOC_CHECKS.json',{'metrics':metrics,'queries':qrows,'shelf':shelf,'tool_checks':tool_checks,
             'find_checks':find_checks,'recall_checks':recall_checks,'notes':notes,'finish_checks':finishes,
             'formal_evidence':{r:a.evidence(r) for r in refs},'limitations':['Direct shelf bytes are serialized request differences, not provider tokens or a causal cost ablation.','Result overlap is not semantic redundancy.','No external judge or production query is used.']})
        print(json.dumps(metrics,ensure_ascii=True,indent=2))
    finally:a.close()

if __name__=='__main__':analyze(sys.argv[1])
