"""Read-only verification of native pairing and actual evidence delivery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from esr_harness.runner import replay


def visible_texts(value):
    found = {}
    if isinstance(value, dict):
        if isinstance(value.get('observation_id'), str) and isinstance(value.get('text'), str):
            found.setdefault(value['observation_id'], set()).add(value['text'])
        values = value.values()
    elif isinstance(value, list):
        values = value
    elif isinstance(value, str):
        # The provider adapter may merge adjacent user messages into multiple
        # JSON payloads separated by whitespace. Decode each without losing a
        # legacy text result that precedes the current budget card.
        values = []
        remaining = value.lstrip()
        while remaining.startswith(('{', '[')):
            try:
                parsed, end = json.JSONDecoder().raw_decode(remaining)
            except ValueError:
                break
            values.append(parsed)
            remaining = remaining[end:].lstrip()
    else:
        return {}
    for child in values:
        for oid, texts in visible_texts(child).items():
            found.setdefault(oid, set()).update(texts)
    return found


def audit(directory):
    h = replay(directory / 'ledger.sqlite')
    problems = []
    requests, deliveries, pairs = 0, 0, 0
    decision = None
    bodies = {}
    for event in h.ledger.events():
        if event['type'] == 'decision':
            decision = event['decision_id']
        if event['type'] == 'generation_request' and event['purpose'] == 'policy':
            requests += 1
            body = event['request']
            bodies[decision] = body
            pending = []
            for message in body['messages']:
                blocks = message['content'] if isinstance(message['content'], list) else []
                calls = [b['id'] for b in blocks if b.get('type') == 'tool_use']
                results = [b['tool_use_id'] for b in blocks if b.get('type') == 'tool_result']
                if pending:
                    if message['role'] != 'user' or results != pending:
                        problems.append({'kind':'unpaired_history', 'request_id':event['request_id']})
                    pairs += len(results)
                    pending = []
                elif results:
                    problems.append({'kind':'orphan_results', 'request_id':event['request_id']})
                if calls:
                    pending = calls
            if pending:
                problems.append({'kind':'missing_final_results', 'request_id':event['request_id']})
        if event['type'] == 'exposure' and event['delivery'] == 'response_received':
            actual = visible_texts(bodies.get(event['decision_id'], {}).get('messages', []))
            for oid in event['observation_ids']:
                deliveries += 1
                if h.observations[oid]['text'] not in actual.get(oid, set()):
                    problems.append({'kind':'missing_delivered_body', 'decision_id':event['decision_id'], 'observation_id':oid})
    for tid, turn in h.native_turns.items():
        if not turn['complete'] or set(turn['results']) != {str(i) for i in range(len(turn['calls']))}:
            problems.append({'kind':'missing_call_receipt', 'decision_id':tid})
    for action in h.actions:
        if 'native_call_index' in action:
            expected = h.native_turns[action['decision_id']]['calls'][action['native_call_index']]['id']
            if action.get('native_call_id') != expected:
                problems.append({'kind':'action_call_id_mismatch','action_id':action['action_id']})
    result = {'run_id':directory.name, 'policy_requests':requests, 'native_turns':len(h.native_turns),
              'multi_call_turns':sum(len(t['calls'])>1 for t in h.native_turns.values()),
              'call_receipts':sum(len(t['results']) for t in h.native_turns.values()),
              'history_pairs_checked':pairs, 'evidence_deliveries_checked':deliveries, 'problems':problems}
    h.ledger.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dirs', nargs='+', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    results = [audit(p) for p in args.run_dirs]
    encoded = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded+'\n')
    print(encoded)
    sys.exit(int(any(r['problems'] for r in results)))
