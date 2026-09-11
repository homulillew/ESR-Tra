"""Read-only receipt-based metrics. Never infer success from drafts or audit verdicts."""
import argparse
from collections import Counter
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3


def metrics(directory):
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    evaluation=json.loads((directory/'evaluation.json').read_text(encoding='utf-8')) if (directory/'evaluation.json').exists() else {}
    db=sqlite3.connect((directory/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    events=[json.loads(r[0]) for r in db.execute('SELECT payload FROM events ORDER BY seq')];db.close()
    requests=[e for e in events if e['type']=='generation_request']
    generations=[e for e in events if e['type']=='generation']
    retrieval=[e for e in events if e['type']=='retrieval']
    actions=[e for e in events if e['type']=='tool']
    measured=[e['usage'] for e in generations if e.get('usage')]
    kinds=Counter(e['purpose'] for e in requests)
    op=Counter(e['operation'] for e in retrieval)
    action_counts=Counter(e['action'] for e in actions)
    terminal=summary.get('terminal') or {}
    correct=evaluation.get('correct') if terminal.get('outcome')=='submitted' else False
    unknown=set(e['request_id'] for e in requests)-{e['request_id'] for e in generations if e.get('usage')}
    actual_by_request={e['request_id']:e['usage'] for e in generations if e.get('usage')}
    errors=Counter(e['result'].get('error_code') for e in actions if not e['result']['ok'])
    same_reads=sum(a['action']=='read_evidence' and b['action']=='read_evidence' and a['arguments']==b['arguments']
                   for a,b in zip(actions,actions[1:]))
    native_proposals=[sum(b.get('type')=='tool_use' for b in e.get('response',{}).get('content',[])) for e in generations]
    row={'run_id':directory.name,'category':manifest['category'],'qid':manifest['qid'],'arm':manifest['arm'],
         'replicate':manifest['replicate'],'sha':manifest['sha'],'context_cap':manifest['settings']['provider']['context_operating_cap'],
         'outcome':terminal.get('outcome'),'correct':correct,'judged':bool(evaluation),'actions':len(actions),
         'schema_contract_warning':(directory/'schema_contract_warning.json').exists(),
         'calibration_excluded':(directory/'difficulty_calibration_exclusion.json').exists(),
         'evaluation_disputed':(directory/'evaluation_dispute.json').exists(),
         'invalid_actions':sum(errors.values()),'backend_requests':len(retrieval),'backend_searches':op['search'],
         'native_tool_call_proposals':sum(native_proposals),'native_multi_call_responses':sum(n>1 for n in native_proposals),
         'accepted_tool_actions':sum(e['result']['ok'] for e in actions),
         'backend_documents':op['get_document'],'policy_requests':kinds['policy'],'audit_requests':kinds['audit'],
         'online_model_requests':len(requests),'input_tokens_measured':sum(u['prompt_tokens'] for u in measured),
         'input_tokens_charged':sum(actual_by_request[e['request_id']]['prompt_tokens'] if e['request_id'] in actual_by_request
                                    else e['reserved_input_tokens'] for e in requests),
         'output_tokens_measured':sum(u['completion_tokens'] for u in measured),
         'uncached_input_tokens_measured':sum(u.get('uncached_input_tokens',u['prompt_tokens']) for u in measured),
         'reasoning_tokens_known_sum':sum(u.get('reasoning_tokens') or 0 for u in measured),
         'reasoning_usage_unknown_requests':sum(u.get('reasoning_tokens') is None for u in measured)+len(unknown),
         'model_transport_retries':sum(e.get('transport_attempt',1)>1 for e in requests),
         'cache_read_tokens_measured':sum(u.get('cache_read_input_tokens',0) for u in measured),
         'cache_creation_tokens_measured':sum(u.get('cache_creation_input_tokens',0) for u in measured),
         'unknown_requests':len(unknown),'charged_output_tokens':summary.get('usage',{}).get('charged_completion_tokens'),
         'elapsed_seconds':summary['elapsed_seconds'],'correct_completion_seconds':summary['elapsed_seconds'] if correct is True else None,
         'policy_seconds':sum(e['elapsed_seconds'] for e in generations if e['purpose']=='policy'),
         'audit_seconds':sum(e['elapsed_seconds'] for e in generations if e['purpose']=='audit'),
         'backend_seconds':sum(e['elapsed_seconds'] for e in retrieval),'consecutive_identical_reads':same_reads,
         'unattributed_wall_seconds':summary['elapsed_seconds']-sum(e['elapsed_seconds'] for e in generations)-sum(e['elapsed_seconds'] for e in retrieval),
         'search_cache_hits':summary['search_cache_hits'],'audit_cache_hits':summary['audit_cache_hits'],
         'zero_search':action_counts['search']==0,'zero_open':action_counts['open_page']==0,
         'audit_supported':terminal.get('evidence_status')=='supported','errors':dict(errors),'action_counts':dict(action_counts)}
    row['backend_instrumented']=summary['manifest']['retriever'].get('type')=='sqlite_fts5_bm25'
    if 'native_tools' in summary:
        native=summary['native_tools']
        row.update(tool_contract=native['contract'], native_policy_decisions=native['model_decisions'],
                   native_policy_calls=native['proposed_calls'], native_call_receipts=native['receipts'],
                   native_not_executed=native['not_executed'], native_unknown_outcomes=native['unknown_outcomes'],
                   error_decisions=native['error_decisions'], invalid_actions=summary['invalid_actions'],
                   invalid_executed_actions=summary['invalid_executed_actions'])
    row['max_remote_requests']=manifest['settings'].get('max_remote_requests_per_episode')
    row['max_tool_calls_per_decision']=manifest['settings'].get('max_tool_calls_per_decision',1)
    if not row['backend_instrumented']:
        for key in ['backend_requests','backend_searches','backend_documents','backend_seconds','unattributed_wall_seconds']:
            row[key]=None
    return row


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='runs/strong_api_esr/CURRENT');a=p.parse_args()
    root=Path(a.root)
    if root.is_file():root=Path(root.read_text().strip())
    rows=[metrics(p.parent) for p in sorted(root.glob('*/summary.json'))]
    out=root/('analysis_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
    (out/'per_run_metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    if rows:
        fields=[k for k in rows[0] if k not in {'errors','action_counts'}]
        with (out/'per_run_metrics.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    for r in rows:
        print(json.dumps({k:r[k] for k in ['run_id','outcome','correct','actions','backend_requests','online_model_requests','elapsed_seconds']}))
    print('No cross-version aggregation; paired analysis requires an explicitly frozen cohort.')
