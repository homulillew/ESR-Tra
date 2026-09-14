"""Post-run, read-only process diagnostics. No model, gold answer or success oracle."""
from collections import Counter

from .archive import Archive
from .contract import digest


def diagnose(path, *, include_text=False):
    archive = Archive(path, readonly=True)
    try:
        report = archive.report()
        queries, views, source_refs = [], [], set()
        for event in archive.events():
            p = event['payload']
            if event['kind'] == 'query_execution':
                row = {k: p[k] for k in ('round', 'top_k', 'equivalence_key', 'cached')}
                row['query_sha256'] = digest(p['query'])
                if include_text:
                    row.update(query=p['query'], compiled=p['compiled'])
                queries.append(row)
            elif event['kind'] == 'model_request':
                views.append({'round': p['round'], 'compacted': p['compacted'],
                    'visible_evidence': p['visible_evidence'], 'shelf': p.get('evidence_shelf', []),
                    'shelf_evicted': p.get('shelf_evicted_for_capacity', [])})
            elif event['kind'] == 'delivery_ack':
                source_refs.update(p['evidence'])
        keys = Counter(q['equivalence_key'] for q in queries)
        return {'protocol': report['protocol'], 'head': report['head'],
            'outcome': report['terminal']['outcome'], 'formal_correct': None,
            'model_attempts': report['model_attempts'], 'backend_attempts': report['backend_attempts'],
            'queries': queries, 'equivalent_query_repeats': sum(n - 1 for n in keys.values()),
            'views': views, 'delivered_refs': sorted(source_refs, key=lambda s: int(s[1:])),
            'submitted_refs': report['terminal'].get('refs', []),
            'text_included': include_text,
            'limitations': ['Equivalence is compiler equality, not semantic identity or wasted-search proof',
                'Raw-window visibility/selection is not entailment or complete evidence coverage',
                'No live q26 replay or independent answer scoring is performed']}
    finally:
        archive.close()
