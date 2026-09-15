"""Exact query-term coverage within a fixed, unchanged CPU BM25 candidate pool."""
from copy import deepcopy
import math
import re

from .contract import ContractError, digest

POOL_SIZE = 20
RULE = {
    'version': 'search-coverage-rank-v1', 'compiler': 'cpu-or-1',
    'adapter': 'stride-cpu-or-1', 'candidate_pool_size': POOL_SIZE,
    'query_terms': 'casefold and deduplicate the original compiler terms',
    'document_terms': 'Unicode regex word extraction then casefold; full title and original snippet',
    'ranking': 'distinct query-term coverage descending; stable original rank on ties',
    'return_count': 'original validated top_k from 1 through 20',
    'score': 'original backend score unchanged',
    'cache': 'final selected rows; key binds rule identity and pool size',
    'source_scope': 'only selected rows register document handles; navigation is not evidence',
}


def identity():
    return {'version': RULE['version'], 'rule': deepcopy(RULE), 'rule_sha256': digest(RULE)}


def require_retriever(retriever):
    if (retriever.identity.get('adapter') != RULE['adapter']
            or not callable(getattr(retriever, 'compile_query', None))):
        raise ValueError('Coverage ranking requires the declared stride-cpu-or-1 adapter and compiler')


def query_terms(compiled):
    if (not isinstance(compiled, dict) or compiled.get('compiler') != RULE['compiler']
            or not isinstance(compiled.get('terms'), list)
            or not all(isinstance(t, str) and t for t in compiled['terms'])
            or not isinstance(compiled.get('expression'), str)):
        raise ContractError('retrieval_protocol', 'Coverage ranking requires valid cpu-or-1 compiler metadata', fatal=True)
    return list(dict.fromkeys(t.casefold() for t in compiled['terms']))


def query_spec(spec):
    key, equivalent, compiled = spec
    query_terms(compiled)
    binding = identity()
    return digest([key, binding, POOL_SIZE]), digest([equivalent, binding, POOL_SIZE]), compiled


def capabilities(original):
    result = deepcopy(original)
    result['upstream_ranking'] = result.get('ranking', 'not declared')
    result['ranking'] = 'Local distinct query-term coverage descending within upstream top 20; original rank breaks ties'
    result['coverage_reranking'] = identity()
    return result


def rank(rows, compiled, top_k):
    terms = query_terms(compiled)
    if type(top_k) is not int or not 1 <= top_k <= POOL_SIZE:
        raise ContractError('retrieval_protocol', 'Coverage top_k must be an integer from 1 through 20', fatal=True)
    if not isinstance(rows, list) or len(rows) > POOL_SIZE:
        raise ContractError('retrieval_protocol', 'Coverage candidate pool must contain at most 20 hits', fatal=True)
    seen, audit = set(), []
    for original_rank, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or not isinstance(row.get('docid'), str) or not row['docid']
                or row['docid'] in seen or not isinstance(row.get('title'), str)
                or not isinstance(row.get('snippet'), str)
                or type(row.get('score')) not in (int, float)
                or (isinstance(row['score'], float) and not math.isfinite(row['score']))):
            raise ContractError('retrieval_protocol', 'Malformed or duplicate coverage candidate', fatal=True)
        seen.add(row['docid'])
        words = {m.group().casefold() for m in re.finditer(r'\w+', row['title'] + ' ' + row['snippet'])}
        matched = [term for term in terms if term in words]
        audit.append({'docid': row['docid'], 'original_rank': original_rank,
                      'covered_terms': matched, 'coverage': len(matched), 'row_sha256': digest(row)})
    ordered = sorted(audit, key=lambda item: -item['coverage'])
    for new_rank, item in enumerate(ordered, 1):
        item['reranked_rank'] = new_rank
        item['selected'] = new_rank <= top_k
    selected = [deepcopy(rows[item['original_rank'] - 1]) for item in ordered[:top_k]]
    return selected, {'identity': identity(), 'query_terms': terms, 'requested_top_k': top_k,
                      'candidate_pool_size': POOL_SIZE, 'candidate_count': len(rows),
                      'candidate_pool_sha256': digest(rows), 'candidates': audit,
                      'selected_docids': [row['docid'] for row in selected],
                      'selected_rows_sha256': digest(selected)}
