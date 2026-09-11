"""Pure reference resolution and atomic state updates; no semantic judge."""
from __future__ import annotations

from copy import deepcopy
from .protocol import ContractError, digest


def initial_state(question: str) -> dict:
    return {'question': question, 'claims': {}, 'claim_history': {}, 'invalid': {},
            'next_claim': 1, 'focus': None, 'note': '', 'draft': None,
            'documents': {}, 'snapshots': {}, 'observations': {}, 'searches': [], 'cursors': {},
            'exposed': [], 'published_claims': {}, 'published_documents': [], 'published_cursors': [],
            'next_document': 1, 'next_observation': 1, 'next_cursor': 1,
            'model_calls': 0, 'actions': 0, 'backend_calls': 0,
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'unknown_calls': 0},
            'history': [], 'segment': 0, 'segment_header': None, 'segment_claims': {},
            'this_candidate': None, 'audits': {}, 'conflicts': {}, 'last_audit': None,
            'feedback': None, 'last_changes': {}, 'terminal': None}


def raw_ref(ref: str, state: dict, exposed: set[str]) -> str:
    oid, _, part = ref.partition(':')
    view = state['observations'].get(oid)
    if view is None or oid not in exposed:
        raise ContractError('unexposed_reference', f'{ref}: observation not delivered in this episode')
    if part and ref not in view['paragraphs']:
        raise ContractError('unknown_paragraph', f'{ref}: paragraph was never issued')
    return ref


def claim_sources(state: dict, cid: str, version: int, trail=()) -> list[str]:
    if cid in trail:
        raise ContractError('dependency_cycle', ' -> '.join((*trail, cid)))
    record = state['claim_history'].get(cid, {}).get(str(version))
    if record is None:
        raise ContractError('unknown_version', f'{cid}@{version}')
    current = state['claims'].get(cid)
    if current is None or current['retired'] or current['meaning_version'] != record['meaning_version']:
        raise ContractError('stale_claim', f'{cid}@{version}: premise no longer current')
    sources = set(record['direct_refs'])
    for parent, edge in record['premises'].items():
        sources.update(claim_sources(state, parent, edge['version'], (*trail, cid)))
    if not record['finding'] or not sources:
        raise ContractError('ungrounded_claim', f'{cid}: no current sourced finding')
    return sorted(sources)


def resolve_refs(refs: list[str], state: dict, binding: dict, *, own: dict | None = None) -> dict:
    """Return explicit choices separately from expanded lineage. Never guess a ref."""
    own = own or {}
    direct, premises, trace, all_sources = set(), {}, [], set()
    allowed = set(binding['observations'])
    for value in refs:
        ref = value
        if ref == 'this':
            ref = binding.get('this')
            if not ref:
                raise ContractError('this_unavailable', 'No unique, fully rendered current observation; select an explicit o handle')
        if ref.startswith('o'):
            direct.add(raw_ref(ref, state, allowed))
            all_sources.add(ref)
            trace.append({'selector': value, 'resolved': ref, 'kind': 'raw', 'origin': 'decision_snapshot'})
        elif ref.startswith('c'):
            version = own.get(ref, binding['claims'].get(ref))
            if version is None:
                raise ContractError('unpublished_claim', f'{ref}: use a claim handle received before this response')
            sources = claim_sources(state, ref, version)
            current = state['claims'][ref]
            record = state['claim_history'][ref][str(version)]
            if current['version'] != version:
                raise ContractError('stale_binding', f'{ref}: retrieve its latest record before citing')
            premises[ref] = {'version': version, 'meaning_version': record['meaning_version']}
            all_sources.update(sources)
            trace.append({'selector': value, 'resolved': ref, 'version': version, 'kind': 'premise',
                          'origin': 'own_committed_update' if ref in own else 'decision_snapshot'})
        else:
            raise ContractError('reference_type', f'{ref}: only delivered observations or existing claim premises are evidence')
    return {'direct_refs': sorted(direct), 'premises': premises, 'sources': sorted(all_sources), 'trace': trace}


def apply_update(state: dict, patch: dict, binding: dict) -> tuple[dict, dict]:
    """Stage the complete proposal first, including interdependent existing revisions."""
    out = deepcopy(state)
    existing, touched, proposals = state['claims'], set(), {}
    for change in patch.get('revise', []):
        cid = change['claim']
        if cid in touched or cid not in binding['claims'] or cid not in existing or existing[cid]['retired']:
            raise ContractError('revision_target', f'{cid}: choose one issued, non-retired claim once')
        if binding['claims'][cid] != existing[cid]['version']:
            raise ContractError('stale_binding', f'{cid}: revision target differs from decision snapshot')
        touched.add(cid)
        proposals[cid] = change
    retired = set(patch.get('retire', []))
    if retired & touched:
        raise ContractError('revision_target', 'Cannot revise and retire the same claim in one proposal')
    for cid in retired:
        if cid not in binding['claims'] or cid not in existing or existing[cid]['retired']:
            raise ContractError('revision_target', f'{cid}: cannot retire unknown/retired claim')
        if binding['claims'][cid] != existing[cid]['version']:
            raise ContractError('stale_binding', f'{cid}: retirement snapshot changed')
    new_ids = []
    for change in patch.get('add', []):
        cid = f"c{out['next_claim']}"
        out['next_claim'] += 1
        new_ids.append(cid)
        proposals[cid] = change
    pending, built, building, resolution = set(proposals), {}, set(), {}

    def build(cid):
        if cid in built:
            return
        if cid in building:
            raise ContractError('dependency_cycle', f'Cycle in proposal at {cid}')
        building.add(cid)
        change = proposals[cid]
        old = existing.get(cid)
        requirement = change.get('requirement', old['requirement'] if old else '').strip()
        finding = change.get('finding', old['finding'] if old else '')
        requirement_changed = old is not None and requirement != old['requirement']
        if requirement_changed and 'finding' not in change:
            finding, selectors = '', []
        elif 'finding' in change:
            selectors = change['refs']
        else:
            selectors = None
        if selectors is not None:
            for parent in selectors:
                if parent.startswith('c'):
                    if parent in new_ids or parent not in binding['claims']:
                        raise ContractError('unpublished_claim', f'{parent}: new IDs cannot be guessed inside this proposal')
                    if parent in retired:
                        raise ContractError('stale_claim', f'{parent}: premise is retired by this proposal')
                    if parent in pending:
                        build(parent)
            own = {c: r['version'] for c, r in built.items() if c in binding['claims']}
            resolved = resolve_refs(selectors, out, binding, own=own)
            direct, premises = resolved['direct_refs'], resolved['premises']
            if finding.strip() and not resolved['sources']:
                raise ContractError('ungrounded_claim', 'A finding needs a raw-source path; use note for hypotheses/plans')
            if not finding.strip() and selectors:
                raise ContractError('empty_finding', 'Empty findings cannot carry support refs')
        else:
            direct, premises = deepcopy(old['direct_refs']), deepcopy(old['premises'])
            resolved = {'trace': [], 'sources': []}
        semantic = (not old or requirement_changed or finding != old['finding'] or
                    premises != old['premises'] or not set(direct) >= set(old['direct_refs']))
        identical = (old is not None and not old['retired'] and not semantic and direct == old['direct_refs'])
        if identical:
            record = deepcopy(old)
        else:
            record = {'id': cid, 'version': old['version'] + 1 if old else 1,
                      'meaning_version': old['meaning_version'] + int(semantic) if old else 1,
                      'requirement': requirement, 'finding': finding, 'direct_refs': direct,
                      'premises': premises, 'retired': False}
            out['claims'][cid] = record
            out['claim_history'].setdefault(cid, {})[str(record['version'])] = deepcopy(record)
        built[cid], resolution[cid] = record, resolved
        building.remove(cid)

    for cid in proposals:
        build(cid)
    for cid in retired:
        old = existing[cid]
        record = {**deepcopy(old), 'version': old['version'] + 1,
                  'meaning_version': old['meaning_version'] + 1, 'retired': True}
        out['claims'][cid] = record
        out['claim_history'][cid][str(record['version'])] = deepcopy(record)
    for key in ('focus', 'note'):
        if key in patch:
            out[key] = patch[key]
    own = {c: r['version'] for c, r in built.items() if c in binding['claims']}
    if 'draft' in patch:
        draft = patch['draft']
        out['draft'] = None if draft is None else {'answer': draft['answer'],
            'basis': resolve_refs(draft['refs'], out, binding, own=own), 'raw_refs': deepcopy(draft['refs'])}
    out['invalid'] = {}
    for cid, record in out['claims'].items():
        if record['retired']:
            out['invalid'][cid] = 'retired'
            continue
        try:
            claim_sources(out, cid, record['version'])
        except ContractError as exc:
            if exc.code == 'dependency_cycle':
                raise
            out['invalid'][cid] = exc.code
    changed = [cid for cid, r in out['claims'].items() if r != state['claims'].get(cid)]
    semantic_changed = [cid for cid in changed if cid in existing and
                        out['claims'][cid]['meaning_version'] != existing[cid]['meaning_version']]
    effects = {'created': new_ids, 'changed_claims': changed, 'semantic_changed': semantic_changed,
               'newly_invalid': sorted(set(out['invalid']) - set(state['invalid'])),
               'answer_changed': (out['draft'] or {}).get('answer') != (state['draft'] or {}).get('answer'),
               'focus_changed': out['focus'] != state['focus'], 'note_changed': out['note'] != state['note'],
               'records': [deepcopy(out['claims'][c]) for c in changed], 'resolutions': resolution}
    effects['noop'] = not changed and all(out[k] == state[k] for k in ('draft', 'focus', 'note'))
    if semantic_changed:
        out['segment'] += 1
        out['segment_header'] = None
        out['segment_claims'] = {}
        out['history'] = []
    out['last_changes'] = deepcopy(effects)
    return out, effects


def answer_bundle(state: dict, answer: str, basis: dict, contract: dict) -> dict:
    records, scopes = {}, {'answer:' + digest(answer)}
    def include(cid, version):
        key = f'{cid}@{version}'
        if key in records:
            return
        claim_sources(state, cid, version)
        record = deepcopy(state['claim_history'][cid][str(version)])
        records[key] = record
        scopes.add(key)
        for parent, edge in record['premises'].items():
            include(parent, edge['version'])
    for cid, edge in basis['premises'].items():
        include(cid, edge['version'])
    sources = {}
    for ref in basis['sources']:
        oid, _, part = ref.partition(':')
        view = state['observations'][oid]
        text = view['paragraphs'][ref]['text'] if part else view['text']
        sources[ref] = {'text': text, 'hash': digest(text), 'observation': oid,
                        'document': view['document'], 'snapshot': view['snapshot']}
    relevant = {k: deepcopy(v) for k, v in state['conflicts'].items() if v['scope'] in scopes}
    for conflict in relevant.values():
        for ref in conflict['witness_refs']:
            oid, _, part = ref.partition(':')
            view = state['observations'][oid]
            text = view['paragraphs'][ref]['text'] if part else view['text']
            if oid not in sources:
                sources.setdefault(ref, {'text': text, 'hash': digest(text), 'observation': oid,
                                         'document': view['document'], 'snapshot': view['snapshot']})
    return {'question': state['question'], 'answer': answer, 'contract': deepcopy(contract),
            'direct_refs': basis['direct_refs'], 'premises': basis['premises'],
            'records': records, 'sources': sources, 'conflicts': relevant,
            'checks': ['target', 'coverage', *sorted({r['id'] for r in records.values()})]}
