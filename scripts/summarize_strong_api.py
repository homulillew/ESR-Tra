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
    errors=Counter(e['result'].get('error_code') for e in actions if not e['result']['ok'])
    same_reads=sum(a['action']=='read_evidence' and b['action']=='read_evidence' and a['arguments']==b['arguments']
                   for a,b in zip(actions,actions[1:]))
    row={'run_id':directory.name,'category':manifest['category'],'qid':manifest['qid'],'arm':manifest['arm'],
         'replicate':manifest['replicate'],'sha':manifest['sha'],'context_cap':manifest['settings']['provider']['context_operating_cap'],
         'outcome':terminal.get('outcome'),'correct':correct,'judged':bool(evaluation),'actions':len(actions),
         'invalid_actions':sum(errors.values()),'backend_requests':len(retrieval),'backend_searches':op['search'],
         'backend_documents':op['get_document'],'policy_requests':kinds['policy'],'audit_requests':kinds['audit'],
         'online_model_requests':len(requests),'input_tokens_measured':sum(u['prompt_tokens'] for u in measured),
         'output_tokens_measured':sum(u['completion_tokens'] for u in measured),
         'cache_read_tokens_measured':sum(u.get('cache_read_input_tokens',0) for u in measured),
         'cache_creation_tokens_measured':sum(u.get('cache_creation_input_tokens',0) for u in measured),
         'unknown_requests':len(unknown),'charged_output_tokens':summary.get('usage',{}).get('charged_completion_tokens'),
         'elapsed_seconds':summary['elapsed_seconds'],'correct_completion_seconds':summary['elapsed_seconds'] if correct is True else None,
         'policy_seconds':sum(e['elapsed_seconds'] for e in generations if e['purpose']=='policy'),
         'audit_seconds':sum(e['elapsed_seconds'] for e in generations if e['purpose']=='audit'),
         'backend_seconds':sum(e['elapsed_seconds'] for e in retrieval),'consecutive_identical_reads':same_reads,
         'search_cache_hits':summary['search_cache_hits'],'audit_cache_hits':summary['audit_cache_hits'],
         'zero_search':action_counts['search']==0,'zero_open':action_counts['open_page']==0,
         'audit_supported':terminal.get('evidence_status')=='supported','errors':dict(errors),'action_counts':dict(action_counts)}
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
