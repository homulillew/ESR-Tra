"""Register a reviewed request checkpoint without making model calls."""
import argparse
from pathlib import Path
import json
from strong_api import GlobalBudget, ROOT


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',default=str(ROOT/'runs/strong_api_esr/CURRENT'))
    p.add_argument('--total-limit',type=int,required=True,help='Absolute all-history request ceiling; increase requires explicit user authorization')
    p.add_argument('--user-authorization',help='Exact user instruction authorizing a higher total; omitted for routine checkpoints')
    p.add_argument('--checkpoint-limit',type=int,required=True,help='Absolute ceiling for the currently reviewed batch')
    p.add_argument('--reason',required=True)
    a=p.parse_args()
    root=Path(a.root)
    if root.is_file():root=Path(root.read_text(encoding='utf-8-sig').strip())
    if not (root/'global_budget.sqlite').exists():raise ValueError('Existing research budget required')
    budget=GlobalBudget(root/'global_budget.sqlite')
    budget.configure_request_limits(a.total_limit,a.checkpoint_limit,a.reason,user_authorization=a.user_authorization)
    print(json.dumps(budget.request_status()))
    budget.db.close()


if __name__=='__main__':main()
