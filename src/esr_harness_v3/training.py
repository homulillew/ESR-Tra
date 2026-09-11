"""Provenance export, NOT an implemented GRPO optimizer or inferred token alignment."""
from __future__ import annotations

from copy import deepcopy
import math
from .protocol import ContractError


def training_export(ledger, *, require_rl=False):
    requests, responses, actions = {}, {}, {}
    for event in ledger.verify():
        p = event['payload']
        if event['kind'] == 'policy_request':
            requests[p['decision']] = p
        elif event['kind'] == 'policy_response':
            responses[p['decision']] = p
        elif event['kind'] == 'action_attempt':
            actions.setdefault(p['decision'], []).append(p)
    records, missing = [], []
    for did, request in requests.items():
        response = responses.get(did)
        if response is None:
            missing.append({'decision': did, 'reason': 'no_policy_response'})
            continue
        sample = response.get('sampling')
        valid = isinstance(sample, dict)
        if valid:
            tokens, probs, spans = sample.get('token_ids'), sample.get('old_logprobs'), sample.get('action_spans')
            valid = (isinstance(tokens, list) and bool(tokens) and all(type(t) is int and t >= 0 for t in tokens)
                     and isinstance(probs, list) and len(tokens) == len(probs)
                     and all(type(p) in (int, float) and math.isfinite(p) for p in probs)
                     and isinstance(spans, list) and bool(sample.get('tokenizer_identity')))
            if valid:
                ids, previous = set(), 0
                for span in spans:
                    if not isinstance(span, dict):
                        valid = False
                        break
                    start, end, tid = span.get('start'), span.get('end'), span.get('tool_call_id')
                    if type(start) is not int or type(end) is not int or not previous <= start < end <= len(tokens) or not isinstance(tid, str) or tid in ids:
                        valid = False
                        break
                    ids.add(tid)
                    previous = end
                expected = {a['tool_call_id'] for a in actions.get(did, [])}
                valid = valid and ids == expected
        if not valid:
            missing.append({'decision': did, 'reason': 'exact_sampling_or_action_alignment_missing'})
        records.append({'decision': did, 'request': deepcopy(request['request']), 'binding': deepcopy(request['binding']),
                        'response': deepcopy(response['raw']), 'sampling': deepcopy(sample), 'sampling_complete': bool(valid),
                        'actions': deepcopy(actions.get(did, []))})
    ready = bool(records) and not missing
    if require_rl and not ready:
        raise ContractError('rl_not_ready', 'Exact sampler tokens/logprobs/spans are absent or invalid; no retokenization fallback')
    return {'rl_ready': ready, 'records': records, 'missing': missing,
            'limitations': 'No causal-credit identification, reward computation, or GRPO training is performed here.'}
