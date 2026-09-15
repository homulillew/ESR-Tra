"""One temporary native read-only tool surface; no message or action rewriting."""
from copy import deepcopy
from .contract import digest

RULE = {'version': 'read-only-once-v1', 'consecutive_rounds': 3,
        'observation': 'successful search receipt executed and ok; no new raw passage delivered',
        'minimum_remaining_model_calls': 3, 'max_triggers': 1, 'final': False,
        'navigation': 'retained group documents or rendered control pages; intersect read authorization',
        'tools': 'original read schema only; original batch limit; no forced tool choice',
        'messages': 'unchanged', 'extra_model_calls': 0,
        'commit': 'after actual request archive before send; failed send consumes',
        'capacity': 'recompute tools and visible navigation on each candidate build'}


def identity():
    return {'version': RULE['version'], 'rule': deepcopy(RULE), 'rule_sha256': digest(RULE),
            'kind': 'temporary_tool_availability_not_verified_evidence'}


def project(harness, history, visible, issued, navigation, tools, final):
    state = harness.read_only.project(history, visible, harness.model_calls,
        remaining=harness.remaining()['model_calls'], final=final)
    pages = navigation.get('available_pages_not_ranked_for_relevance', []) if isinstance(navigation, dict) else navigation
    refs = {p['ref'] for p in pages}
    refs.update(ref for g in history for ref in g['documents'])
    refs &= set(harness.published_docs) | set(issued)
    refs = sorted(refs, key=lambda r: int(r[1:]))
    audit = None
    if not refs:
        state['trigger'] = None
    if state['trigger'] is not None:
        tools = [t for t in tools if t['function']['name'] == 'read']
        audit = {'identity': identity(), 'visible_read_documents': refs,
                 'visible_read_documents_sha256': digest(refs), 'native_tools_sha256': digest(tools)}
    return state, tools, audit
