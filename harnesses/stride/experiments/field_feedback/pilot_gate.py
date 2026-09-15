"""Read-only gate for a proposed pilot. This blocked preparation cannot send HTTP."""
import argparse
from pathlib import Path
from reproduce import read, sha


def gate(plan_path, *, execute_approved_pilot=False):
    path = Path(plan_path)
    if sha(path) != path.with_suffix('.sha256').read_text(encoding='ascii').strip():
        raise ValueError('Frozen experiment plan changed')
    plan = read(path)
    if not execute_approved_pilot:
        return {'status': 'LIVE_NOT_RUN', 'readiness': plan['readiness'], 'real_model_calls': 0}
    if plan['readiness'] != 'READY':
        raise ValueError('BLOCKED_PREFIX_RECONSTRUCTION: exact original time balance unavailable')
    # Do not turn a plan-edit or a command-line switch into an unreviewed live run.
    raise ValueError('LIVE_NOT_RUN: no live executor is released in this blocked preparation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--execute-approved-pilot', action='store_true')
    args = parser.parse_args()
    try:
        print(gate(args.plan, execute_approved_pilot=args.execute_approved_pilot))
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')
