"""Adapter-specific query telemetry and delivery-scoped navigation, not semantic state."""
from __future__ import annotations

from copy import deepcopy
import re

from .contract import ContractError, canonical, digest, loads


def capabilities(retriever):
    value = deepcopy(getattr(retriever, 'capabilities', {
        'kind': retriever.identity.get('kind', 'unknown'), 'query_rule': 'not declared by this adapter',
        'warning': 'Do not assume web-search operators, phrase filtering or CPU OR semantics.'}))
    if not isinstance(value, dict) or len(canonical(value)) > 4000:
        raise ValueError('Retriever capabilities must be a bounded deployment declaration')
    return value


def query_spec(harness, query, top_k):
    compiler = getattr(harness.retriever, 'compile_query', None)
    compiled = compiler(query) if callable(compiler) else None
    if compiled is not None and (not isinstance(compiled, dict) or len(canonical(compiled)) > 20000):
        raise ContractError('retrieval_protocol', 'Malformed query compiler metadata', fatal=True)
    equivalent = digest([harness.retriever.identity, compiled if compiled is not None else query, top_k])
    cached_form = compiled if compiled is not None and harness.config.compiled_query_cache else query
    key = digest([harness.retriever.identity, cached_form, top_k])
    return key, equivalent, compiled


def accept_navigation(harness, groups):
    for group in groups:
        round_no = group['round']
        if round_no in harness.navigation_acked_rounds:
            continue
        harness.navigation_acked_rounds.add(round_no)
        added = []
        for message in group['messages']:
            if message['role'] != 'tool':
                continue
            result = loads(message['content'])
            if not result.get('ok'):
                continue
            for batch in result.get('results', []):
                if batch.get('view') == 'reuse':
                    continue
                for hit in batch['hits']:
                    if hit['ref'] not in harness.published_docs:
                        raise ContractError('archive_integrity', 'Navigation receipt outside acknowledged scope', fatal=True)
                    record = {'ref': hit['ref'], 'title': hit['title'], 'snippet': hit['snippet'],
                              'query': batch['query'], 'source_round': round_no,
                              'order': len(harness.navigation_history)}
                    harness.navigation_history.append(record); added.append(record)
        if added:
            harness.archive.append('navigation_ack', {'round': harness.model_calls,
                'source_round': round_no, 'object': harness.archive.put_json(added)})


def excerpt(text, terms, centered):
    start = 0
    if centered:
        matches = [m for t in terms if (m := re.search(re.escape(t), text, re.IGNORECASE))]
        if matches:
            start = max(0, min(m.start() for m in matches) - 120)
    end = min(len(text), start + 400)
    return {'excerpt': text[start:end], 'excerpt_start': start, 'excerpt_end': end}


def recall(harness, query):
    terms = list(dict.fromkeys(re.findall(r'\w+', query.casefold())))
    if not terms:
        raise ContractError('query_terms', 'Recall needs at least one lexical term')
    scored = []; center = harness.config.centered_recall
    for order, ref in enumerate(harness.evidence_order):
        view = harness.archive.evidence(ref); title = harness.archive.doc(view['document'])['title']
        score = sum(t in (title + ' ' + view['text']).casefold() for t in terms)
        if score:
            part = excerpt(view['text'], terms, center)
            scored.append((score, 2, order, {'ref': ref, 'title': title[:160], **part,
                'excerpt_offset_origin': 'evidence_window', 'window_start': view['start'],
                'kind': 'evidence_navigation'}))
    if harness.config.recall_navigation:
        best = {}
        for hit in harness.navigation_history:
            score = sum(t in (hit['title'] + ' ' + hit['snippet'] + ' ' + hit['query']).casefold() for t in terms)
            row = (score, 1, hit['order'], {'ref': hit['ref'], 'title': hit['title'][:160],
                **excerpt(hit['snippet'], terms, center), 'excerpt_offset_origin': 'saved_search_snippet',
                'source_query': hit['query'], 'source_round': hit['source_round'], 'kind': 'search_hit_navigation'})
            if score and (hit['ref'] not in best or row[:3] > best[hit['ref']][:3]): best[hit['ref']] = row
        scored.extend(best.values())
    for order, note in enumerate(harness.note_history):
        score = sum(t in note['text'].casefold() for t in terms)
        if score:
            scored.append((score, 0, order, {'key': note['key'], 'excerpt': note['text'],
                'active': harness.notes.get(note['key']) == note, 'kind': 'agent_note_not_evidence'}))
    rows = [r[3] for r in sorted(scored, key=lambda r: r[:3], reverse=True)[:8]]
    return {'matches': rows, 'retrieval': 'lexical_overlap_not_semantic', 'excerpt_only': True}, [], []
