"""Finite, deterministic acceptance comparison. No model or retrieval calls."""
from itertools import product
from stride_search.contract import ContractError, validate


def acceptance_matrix():
    absent = object()
    values = {'answer': [absent, None, False, 47, 8.5, '', '   ', 'synthetic', '  "literal"\n'],
              'refs': [absent, None, 'synthetic', [], ['e9'], [False], ['e9', 'e9']],
              'abstain': [absent, True, False], 'reason': [absent, 'synthetic', ' '],
              'extra': [absent, 'synthetic']}
    total = accepted = rejected = 0; differences = []
    for i, combination in enumerate(product(*values.values())):
        args = {k: v for k, v in zip(values, combination) if v is not absent}
        outcomes = []
        for mode in ('legacy', 'field'):
            try:
                validate('finish', args, feedback=mode); outcomes.append('accepted')
            except ContractError as exc:
                outcomes.append(exc.code)
        total += 1; accepted += outcomes[0] == 'accepted'; rejected += outcomes[0] != 'accepted'
        if outcomes[0] != outcomes[1]:
            differences.append({'case_index': i, 'outcomes': outcomes})
    return {'cases': total, 'accepted': accepted, 'rejected': rejected,
            'acceptance_differences': differences, 'same_acceptance_set': not differences,
            'scope': 'Finite generated synthetic corpus, not proof over every possible JSON instance'}
