"""Six synthetic single-variable comparisons. No HTTP or model-quality claim.

Run after installing the package, from harnesses/stride:
    python examples/recovery_comparison.py --output /tmp/new-recovery
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from stride_search import Config, Harness
from stride_search.contract import canonical
from stride_search.experiment import source_hashes, write_new
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import LocalCorpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    s = native(('search', {'queries': ['Lumen'], 'top_k': 1}))
    r = native(('read', {'ref': 'd1'}))
    f = native(('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}))
    n = ('notes', {'op': 'put', 'key': 'clue', 'text': 'Fallible clue', 'anchors': ['e1']})
    cases = [
        ('final_note', 'nonblocking_notes', Config(max_model_calls=3), smoke_corpus,
         [s, r, native(n, ('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}))]),
        ('prose', 'repair_context', Config(max_model_calls=4), smoke_corpus,
         [s, r, native(content='UNCOMMITTED_DEMO: "Ada Rowan"', finish_reason='stop'), f]),
        ('large_group', 'delivery_preflight', Config(max_model_calls=3, context_limit=28000, response_reserve=2048),
         lambda: LocalCorpus([{'docid': 'large', 'title': 'LongArchive', 'content': 'X'*26000}]),
         [native(('search', {'queries': ['LongArchive'], 'top_k': 1})),
          native(*[('read', {'ref': 'd1', 'start': i*6000, 'length': 6000}) for i in range(4)]),
          native(('finish', {'abstain': True, 'reason': 'synthetic capacity test'}))]),
    ]
    write_new(out/'manifest.json', {'source_hashes': source_hashes(),
        'scope': 'a2 single-variable scripted comparisons, not exact a1 replay',
        'real_model_requests': 0, 'BCPlus': 'NOT_RUN',
        'schedule': [{'case': c[0], 'flag': c[1], 'enabled': enabled} for c in cases for enabled in (False, True)]})
    rows = []
    for name, flag, config, corpus_factory, responses in cases:
        for enabled in (False, True):
            slot = out/f'{name}_{int(enabled)}'
            slot.mkdir()
            h = Harness('Synthetic task; report only protocol behavior.', corpus_factory(),
                        path=slot/'episode.sqlite', config=replace(config, **{flag: enabled}))
            model = ScriptedModel(responses)
            try:
                h.run(model)
                report = h.archive.report()
                write_new(slot/'report.json', report)
                write_new(slot/'requests.json', model.requests)
                rows.append({'case': name, 'flag': flag, 'enabled': enabled,
                    'outcome': h.terminal['outcome'], 'model_decisions': h.model_calls,
                    'backend_fixture_calls': h.backend_calls, 'exposed': sorted(h.exposed),
                    'repair_marker_in_last_request': 'UNCOMMITTED_DEMO' in canonical(model.requests[-1]),
                    'action_error_counts': report['action_error_counts'], 'formal_accuracy': None})
            finally:
                h.close()
    write_new(out/'results.json', rows)
    print(canonical(rows))


if __name__ == '__main__':
    main()
