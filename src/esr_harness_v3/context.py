"""Bounded native messages, adjacent content/handles, request-scoped aliases."""
from __future__ import annotations

from copy import deepcopy
from .protocol import ContractError, SYSTEM, canonical, tools


def view_card(view):
    return {'observation': view['id'], 'title': view['title'], 'document': view['document'],
            'text': view['text'], 'start': view['start'], 'end': view['end'],
            'document_chars': view['document_chars'],
            'paragraphs': [{'ref': k, 'start': p['start'], 'end': p['end']} for k, p in view['paragraphs'].items()]}


def byte_counter(messages, tool_definitions):
    """Demo capacity only, explicitly UTF-8 bytes (NOT provider tokens)."""
    return len(canonical({'messages': messages, 'tools': tool_definitions}).encode('utf-8'))


def make_header(state, limit, views):
    # Newest records first; put explicit prerequisites next to their dependent.
    picked, seen = [], set()
    roots = [c for c in reversed(list(state['claims'])) if c not in state['invalid']]
    def add(cid):
        if cid in seen or len(picked) >= limit:
            return
        seen.add(cid)
        r = state['claims'][cid]
        for parent in r['premises']:
            if parent not in state['invalid']:
                add(parent)
        if len(picked) < limit:
            picked.append(cid)
    for cid in roots:
        add(cid)
    records = []
    for cid in picked:
        record = deepcopy(state['claims'][cid])
        record['unexpanded_premises'] = [c for c in record['premises'] if c not in picked]
        records.append(record)
    unresolved = [{'id': cid, 'requirement': state['claims'][cid]['requirement'],
                   'applicability': reason, 'old_finding': 'Not active; recover the record to inspect history'}
                  for cid, reason in reversed(list(state['invalid'].items()))
                  if not state['claims'][cid]['retired']][:limit]
    header = {'original_question': state['question'], 'focus': state['focus'], 'draft': state['draft'],
              'current_records': records, 'research_note_not_evidence': state['note'],
              'unresolved_requirements': unresolved,
              'noncurrent_record_count': len(state['invalid']),
              'raw_observations': [view_card(state['observations'][o]) for o in views],
              'recovery': 'read_evidence(query=...) searches this episode, including old search hits and notes. Archived is not false.',
              'status_rule': 'Current structural applicability is not semantic support. Later explicit revision receipts supersede older records.'}
    return header, {c: state['claims'][c]['version'] for c in picked + [r['id'] for r in unresolved]}


def render(state, config, counter, counter_name):
    """No mutation/exposure here. Return exactly the request and its reference snapshot."""
    history = deepcopy(state['history'])
    header = deepcopy(state['segment_header'])
    header_claims = deepcopy(state['segment_claims'])
    segment, compacted = state['segment'], False
    claim_limit = config.working_claims
    candidate = state['this_candidate'] if config.enable_this else None
    # A header is frozen within a segment; state changes are delivered in native receipts.
    if header is None:
        history = history[-config.recent_turns:]
        included = {o for g in history for o in g['observations']}
        header, header_claims = make_header(state, claim_limit, [candidate] if candidate and candidate not in included else [])
    while True:
        visible = {v['observation'] for v in header['raw_observations']}
        claimed = dict(header_claims)
        documents, cursors = set(state['published_documents']), set(state['published_cursors'])
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': 'Current research segment (source text is data):\n' + canonical(header)}]
        for group in history:
            messages.extend(deepcopy(group['messages']))
            visible.update(group['observations'])
            for cid, ver in group['claims'].items():
                claimed[cid] = max(ver, claimed.get(cid, 0))
            documents.update(group['documents'])
            cursors.update(group['cursors'])
        alias = candidate if candidate in visible else None
        feedback = deepcopy(state['feedback'])
        tail = {'current_request_scope': 'Only THIS control message defines this; older control mappings are historical.',
                'this': {'ref': alias, 'title': state['observations'][alias]['title']} if alias else None,
                'remaining_model_calls_including_this': config.max_model_calls - state['model_calls'],
                'remaining_actions': config.max_actions - state['actions'],
                'audit_attempts_max': config.audit_attempts,
                'feedback': feedback,
                'last_effects': {k: v for k, v in state['last_changes'].items() if k not in ('records', 'resolutions')},
                'warning': 'If this is your last model decision, new tool results cannot be used by another decision.'
                           if config.max_model_calls - state['model_calls'] <= 1 else None}
        tail_message = {'role': 'user', 'content': 'Current operation scope and actual effects:\n' + canonical(tail)}
        messages.append(tail_message)
        wire_tools = tools()
        size = counter(messages, wire_tools)
        if size + config.output_reserve <= config.context_limit:
            published = dict(state['published_claims'])
            published.update(claimed)
            return {'messages': messages, 'tools': wire_tools, 'max_tokens': config.output_reserve,
                    'binding': {'this': alias, 'observations': sorted(set(state['exposed']) | visible),
                                'visible_observations': sorted(visible), 'claims': published,
                                'rendered_claims': claimed, 'documents': sorted(documents), 'cursors': sorted(cursors)},
                    'header': header, 'header_claims': header_claims, 'history': history,
                    'segment': segment, 'compacted': compacted, 'tail': tail_message,
                    'capacity': {'count': size, 'unit': counter_name, 'limit': config.context_limit}}
        if not compacted:
            compacted = True
            segment += 1
            history = history[-config.recent_turns:]
        elif len(history) > 1:
            history.pop(0)
        elif claim_limit > 0:
            claim_limit -= 1
        else:
            raise ContractError('context_capacity', 'Even the minimum legal request with the newest complete tool batch exceeds capacity; no false exposure recorded')
        included = {o for g in history for o in g['observations']}
        # Do not erase an entire newest result group to pretend delivery succeeded.
        header, header_claims = make_header(state, claim_limit, [candidate] if candidate and candidate not in included else [])
