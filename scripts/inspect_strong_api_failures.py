"""Export concrete first errors and capacity receipts; no guesses about unseen gold evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def inspect(directory):
    meta=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    db=sqlite3.connect((directory/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    events=[json.loads(r[0]) for r in db.execute('SELECT payload FROM events ORDER BY seq')];db.close()
    actions=[e for e in events if e['type']=='tool']
    errors=[e for e in actions if not e['result']['ok']]
    requests=[e for e in events if e['type']=='generation_request']
    generations=[e for e in events if e['type']=='generation']
    measured=[e for e in generations if e.get('usage')]
    terminal=summary.get('terminal') or {}
    row={'run_id':directory.name,'qid':meta['qid'],'arm':meta['arm'],'category':meta['category'],
         'outcome':terminal.get('outcome'),'confirmed_first_protocol_or_tool_error':errors[0] if errors else None,
         'all_failed_actions':errors,'last_completed_action':actions[-1] if actions else None,
         'max_actual_input_tokens':max((e['usage']['prompt_tokens'] for e in measured),default=None),
         'last_input_reservation':requests[-1]['reserved_input_tokens'] if requests else None,
         'last_request_id':requests[-1]['request_id'] if requests else None,
         'audit_request_ids':[e['request_id'] for e in requests if e['purpose']=='audit'],
         'transport_errors':[e for e in generations if e.get('error_code')],
         'calibration_excluded':(directory/'difficulty_calibration_exclusion.json').exists(),
         'semantic_failure_classification':'unresolved; requires completed trajectory and separate offline evidence/answer review',
         'evidence_paths':['ledger.sqlite','provider_requests.jsonl','provider_responses.jsonl','trajectory.jsonl']}
    if terminal.get('outcome')=='context_overflow':
        row['confirmed_terminal_mechanism']='Conservative capacity gate stopped expansion; not evidence of intrinsic question difficulty or provider maximum window'
    return row


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dirs',nargs='+',required=True);a=p.parse_args()
    root=Path(Path('runs/strong_api_esr/CURRENT').read_text().strip())
    rows=[inspect(root/name) for name in a.run_dirs]
    out=root/('failure_review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
    (out/'failure_taxonomy.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'runs':len(rows),'content':'full failed arguments and result paths retained privately'}))
