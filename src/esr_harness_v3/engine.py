"""Runnable ESR v3 episode engine. Real receipts, frozen refs, no guessed answers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
import time
import uuid

from .audit import aggregate, audit_identity, audit_messages, audit_payload, validate_report
from .context import byte_counter, render, view_card
from .protocol import Config, ContractError, VERSION, canonical, completion_message, digest, parse_json, validate_action
from .state import answer_bundle, apply_update, claim_sources, initial_state, resolve_refs
from .store import Ledger


@dataclass(frozen=True)
class Decision:
    id: str
    payload_json: str
    binding_json: str

    @property
    def payload(self):
        return parse_json(self.payload_json)

    @property
    def binding(self):
        return parse_json(self.binding_json)


def _normal_message(raw):
    if not isinstance(raw, dict) or raw.get('role', 'assistant') != 'assistant':
        raise ContractError('policy_protocol_error', 'Expected an assistant message')
    calls = raw.get('tool_calls', [])
    if not isinstance(calls, list) or not calls:
        raise ContractError('policy_protocol_error', 'Return an explicit tool call; free text is not silently submitted')
    ids = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get('id'), str) or not call['id'] or call.get('type') != 'function':
            raise ContractError('policy_protocol_error', 'Each native tool call needs its original unique id and function type')
        f = call.get('function')
        if not isinstance(f, dict) or not isinstance(f.get('name'), str) or not isinstance(f.get('arguments'), str):
            raise ContractError('policy_protocol_error', 'Each native call must contain name and JSON argument string')
        ids.append(call['id'])
    if len(ids) != len(set(ids)):
        raise ContractError('policy_protocol_error', 'Duplicate native tool_call id; no calls executed')
    message = {'role': 'assistant', 'content': raw.get('content'), 'tool_calls': deepcopy(calls)}
    if raw.get('reasoning_content') is not None:
        message['reasoning_content'] = raw['reasoning_content']
    return message


class Harness:
    def __init__(self, question: str, retriever, *, ledger=':memory:', config=None, auditor=None,
                 counter=None, counter_name='utf8_bytes', resume=False):
        self.config = config or Config()
        self.retriever, self.auditor = retriever, auditor
        self.counter, self.counter_name = counter or byte_counter, counter_name
        counter_identity = deepcopy(getattr(self.counter, 'identity', None))
        auditor_identity = audit_identity(auditor) if auditor is not None else None
        self.ledger = Ledger(ledger)
        self._active = None
        saved = self.ledger.latest_state()
        if saved is not None:
            if not resume:
                self.ledger.close()
                raise ContractError('ledger_exists', 'Choose a new ledger or explicit resume; old experiments are not overwritten')
            if (saved['question'] != question or self.ledger.events[0]['payload']['config'] != self.config.to_dict()
                    or self.ledger.events[0]['payload']['retriever'] != retriever.identity
                    or self.ledger.events[0]['payload']['capacity_unit'] != counter_name
                    or self.ledger.events[0]['payload'].get('counter_identity') != counter_identity
                    or self.ledger.events[0]['payload'].get('auditor') != auditor_identity):
                self.ledger.close()
                raise ContractError('resume_mismatch', 'Question/config/auditor/counter must match the saved episode')
            self._s = saved
            if saved.get('inflight') or saved.get('executing'):
                self.end('interrupted')
        else:
            if not isinstance(question, str) or not question.strip():
                raise ValueError('question must be nonempty')
            self._s = initial_state(question)
            self.ledger.append('header', {'protocol': VERSION, 'config': self.config.to_dict(),
                                          'retriever': deepcopy(retriever.identity), 'capacity_unit': counter_name,
                                          'counter_identity': counter_identity, 'auditor': auditor_identity}, self._s)

    @property
    def state(self):
        return deepcopy(self._s)

    @property
    def terminal(self):
        return deepcopy(self._s['terminal'])

    def _save(self, kind, payload, state=None):
        target = self._s if state is None else state
        self.ledger.append(kind, payload, target)
        self._s = deepcopy(target)

    def begin(self) -> Decision:
        if self._active is not None or self._s['terminal'] is not None:
            raise ContractError('decision_state', 'An episode is terminal or already has an in-flight decision')
        if self._s['model_calls'] >= self.config.max_model_calls:
            self.end('model_budget_exhausted')
            raise ContractError('model_budget', 'No model request budget remains')
        plan = render(self._s, self.config, self.counter, self.counter_name)
        request = {k: plan[k] for k in ('messages', 'tools', 'max_tokens')}
        decision = Decision(uuid.uuid4().hex, canonical(request), canonical(plan['binding']))
        state = self.state
        state.update(history=plan['history'], segment_header=plan['header'],
                     segment_claims=plan['header_claims'], segment=plan['segment'])
        state['model_calls'] += 1
        state['usage']['unknown_calls'] += 1
        state['inflight'] = decision.id
        self._save('policy_request', {'decision': decision.id, 'request': request, 'binding': plan['binding'],
                                     'capacity': plan['capacity'], 'compacted': plan['compacted']}, state)
        self._active = (decision, plan)
        return decision

    def _usage(self, state, usage):
        if isinstance(usage, dict):
            p, c = usage.get('prompt_tokens'), usage.get('completion_tokens')
            if type(p) is int and p >= 0 and type(c) is int and c >= 0:
                state['usage']['input_tokens'] += p
                state['usage']['output_tokens'] += c
                state['usage']['unknown_calls'] -= 1

    def fail(self, decision, error):
        self._check_decision(decision)
        state = self.state
        state['inflight'] = None
        state['feedback'] = {'kind': 'service_error', 'detail': str(error)[:1000], 'semantic_verdict': None}
        self._save('policy_failure', {'decision': decision.id, 'error': str(error)[:1000]}, state)
        self._active = None
        self.end('service_error')

    def _check_decision(self, decision):
        if not self._active or decision != self._active[0] or self._s.get('inflight') != decision.id:
            raise ContractError('decision_snapshot', 'Unknown, modified, stale or already-consumed decision')

    def respond(self, decision, message, *, raw=None, usage=None, sampling=None):
        self._check_decision(decision)
        plan = self._active[1]
        binding = decision.binding
        state = self.state
        self._usage(state, usage)
        state['inflight'], state['executing'] = None, decision.id
        state['exposed'] = sorted(set(state['exposed']) | set(binding['visible_observations']))
        state['published_claims'].update(binding['rendered_claims'])
        state['published_documents'] = binding['documents']
        state['published_cursors'] = binding['cursors']
        # Explicitly retain absent sampling as absent; never re-tokenize to invent training data.
        self._save('policy_response', {'decision': decision.id, 'raw': deepcopy(raw if raw is not None else message),
                                      'usage': usage, 'sampling': deepcopy(sampling)}, state)
        try:
            if raw is not None:
                completion_message(raw)
            assistant = _normal_message(message)
        except ContractError as exc:
            self._active = None
            state = self.state
            state['executing'] = None
            state['feedback'] = {'kind': exc.code, 'detail': str(exc), 'committed': False}
            state['history'].append({'messages': [plan['tail'], {'role': 'user', 'content': canonical(state['feedback'])}],
                                     'observations': [], 'claims': {}, 'documents': [], 'cursors': []})
            self._save('policy_protocol_failure', {'decision': decision.id, 'error': str(exc)}, state)
            if exc.code == 'incomplete_response':
                self.end(exc.code)
            return [{'ok': False, 'code': exc.code, 'message': str(exc), 'executed': False}]
        calls = assistant['tool_calls']
        names = [c['function']['name'] for c in calls]
        invalid_group = None
        if len(calls) > self.config.max_tool_calls:
            invalid_group = 'Too many calls; none executed. Every declared call receives a result.'
        elif names.count('update_state') > 1:
            invalid_group = 'At most one atomic update per response; combine revisions in one delta.'
        own, receipts, outputs, raw_ids, issued_claims, issued_docs, issued_cursors = {}, [], [], [], {}, [], []
        read_indices = [i for i, n in enumerate(names) if n in ('open_page', 'read_evidence')]
        any_read_error = False
        if read_indices:
            state = self.state
            state['this_candidate'] = None
            self._save('reading_batch_start', {'decision': decision.id, 'indices': read_indices}, state)
        stop = invalid_group
        fatal_after_batch = None
        for index, call in enumerate(calls):
            name = call['function']['name']
            aid = f'a{self._s["actions"] + 1}'
            state = self.state
            state['actions'] += 1
            self._save('action_attempt', {'action_id': aid, 'decision': decision.id, 'tool_call_id': call['id'],
                                         'name': name, 'raw_arguments': call['function']['arguments']}, state)
            if stop or self._s['actions'] > self.config.max_actions or self._s['terminal']:
                reason = stop or 'Action budget/terminal state prevents execution'
                result = {'ok': False, 'code': 'not_executed', 'message': reason, 'executed': False}
                stop = reason
            else:
                try:
                    args = parse_json(call['function']['arguments'])
                    validate_action(name, args)
                    if (name == 'verify_answer' and self.auditor is not None and self.config.audit_mode != 'off'
                            and self.config.max_actions - self._s['actions'] < len(calls) - index):
                        raise ContractError('audit_action_budget', 'Reserve an action for the post-audit decision, including every unexecuted suffix receipt')
                    result, state = self._dispatch(name, args, binding, own, aid)
                    result = {'ok': True, 'executed': True, **result}
                    state['last_action'] = {'name': name, 'result': deepcopy(result)}
                    self._save('action_commit', {'action_id': aid, 'name': name, 'arguments': args,
                                                'result': result, 'binding': binding, 'own_versions': own}, state)
                    if name == 'update_state':
                        for r in result['changes']['records']:
                            issued_claims[r['id']] = r['version']
                            if r['id'] in binding['claims']:
                                own[r['id']] = r['version']
                    if name in ('verify_answer', 'submit_answer'):
                        stop = 'Feedback/terminal boundary: a new policy decision is required'
                    raw_ids.extend(result.get('delivered_observations', []))
                    issued_docs.extend(result.get('issued_documents', []))
                    issued_cursors.extend(result.get('issued_cursors', []))
                    issued_claims.update(result.get('issued_claims', {}))
                except ContractError as exc:
                    result = {'ok': False, 'code': exc.code, 'message': str(exc), 'executed': True, 'committed': False}
                    state = self.state
                    state['feedback'] = {'kind': exc.code, 'detail': str(exc), 'committed': False,
                                         'legal_sources': [{'ref': o, 'title': state['observations'][o]['title']}
                                                           for o in state['exposed'][-4:]]}
                    self._save('action_rejected', {'action_id': aid, 'name': name, 'result': result}, state)
                    if exc.code in ('service_error', 'audit_service_error'):
                        fatal_after_batch = exc.code
                    stop = 'Earlier action failed; no dependent suffix is executed'
            if index in read_indices and not result['ok']:
                any_read_error = True
            receipts.append(result)
            outputs.append({'role': 'tool', 'tool_call_id': call['id'], 'content': canonical(result)})
        state = self.state
        if read_indices:
            state['this_candidate'] = raw_ids[0] if len(raw_ids) == 1 and not any_read_error else None
        group = {'messages': [plan['tail'], assistant, *outputs], 'observations': sorted(set(raw_ids)),
                 'claims': issued_claims, 'documents': sorted(set(issued_docs)), 'cursors': sorted(set(issued_cursors))}
        state['history'].append(group)
        state['executing'] = None
        self._save('batch_complete', {'decision': decision.id, 'receipts': receipts}, state)
        self._active = None
        if fatal_after_batch:
            self.end(fatal_after_batch)
        elif not self._s['terminal'] and self._s['actions'] >= self.config.max_actions:
            self.end('action_budget_exhausted')
        return receipts

    def _backend(self, name, argument, function):
        state = self.state
        state['backend_calls'] += 1
        self._save('backend_request', {'method': name, 'arguments': argument}, state)
        start = time.monotonic()
        try:
            result = function()
        except Exception as exc:
            self.ledger.append('backend_failure', {'method': name, 'error_type': type(exc).__name__,
                                                   'seconds': time.monotonic() - start})
            raise ContractError('service_error', f'{name} failed: {type(exc).__name__}') from exc
        self.ledger.append('backend_response', {'method': name, 'result': deepcopy(result), 'seconds': time.monotonic() - start})
        return result

    def _cursor(self, state, value):
        cursor = f'k{state["next_cursor"]}'
        state['next_cursor'] += 1
        state['cursors'][cursor] = deepcopy(value)
        return cursor

    def _dispatch(self, name, args, binding, own, aid):
        if name == 'search':
            return self._search(args, aid)
        if name == 'open_page':
            return self._open(args, binding, aid)
        if name == 'read_evidence':
            return self._read(args, binding)
        if name == 'update_state':
            state, effects = apply_update(self._s, args, binding)
            for record in effects['records']:
                record['created_by_action'] = aid
                # History carries semantic snapshots; provenance is a separate event, not mutated past evidence.
            if state['feedback']:
                state['feedback']['actual_effects'] = {k: effects[k] for k in ('answer_changed', 'focus_changed', 'changed_claims', 'noop')}
                state['feedback']['current_draft_answer'] = (state['draft'] or {}).get('answer')
                state['feedback']['current_draft_surface'] = self._surface((state['draft'] or {}).get('answer'))
            return {'changes': effects}, state
        if name == 'verify_answer':
            return self._verify(args, binding, own, aid)
        return self._submit(args, binding, own)

    def _search(self, args, aid):
        query, top_k = args['query'], args.get('top_k', 5)
        cache_key = digest([self.retriever.identity, query, top_k])
        previous = next((r for r in reversed(self._s['searches']) if r['cache_key'] == cache_key), None)
        if previous is not None:
            rows = previous['hits']
        else:
            rows = self._backend('search', args, lambda: self.retriever.search(query, top_k))
        if not isinstance(rows, list):
            raise ContractError('retrieval_error', 'Search must return a list')
        state, hits = self.state, []
        for row in rows[:top_k]:
            if not isinstance(row, dict) or not str(row.get('docid', '')):
                raise ContractError('retrieval_error', 'Each hit requires a backend docid')
            backend_id = str(row['docid'])
            handle = next((k for k, v in state['documents'].items() if v['backend_id'] == backend_id), None)
            if handle is None:
                handle = f'd{state["next_document"]}'
                state['next_document'] += 1
                state['documents'][handle] = {'backend_id': backend_id, 'title': str(row.get('title', '')),
                                               'navigation_actions': [], 'snapshot_hashes': []}
            state['documents'][handle]['navigation_actions'].append(aid)
            hits.append({'ref': handle, 'docid': backend_id, 'title': str(row.get('title', ''))[:500],
                         'snippet': str(row.get('snippet', ''))[:1000],
                         'opened': bool(state['documents'][handle]['snapshot_hashes'])})
        state['searches'].append({'action': aid, 'query': query, 'cache_key': cache_key,
                                   'hits': hits, 'cache_source': previous['action'] if previous else None})
        return {'hits': hits, 'cache_source': previous['action'] if previous else None,
                'issued_documents': [h['ref'] for h in hits]}, state

    def _open(self, args, binding, aid):
        if 'cursor' in args:
            cur = self._get_cursor(args['cursor'], binding, 'window')
            state = self.state
            document, sha, start = cur['document'], cur['snapshot'], cur['start']
        else:
            document = args['ref']
            if document not in binding['documents']:
                raise ContractError('unpublished_document', 'Open only a search hit received before this response')
            meta = self._s['documents'][document]
            response = self._backend('get_document', {'docid': meta['backend_id']},
                                     lambda: self.retriever.get_document(meta['backend_id']))
            nested = response.get('document', response) if isinstance(response, dict) else {}
            actual = str(response.get('docid', nested.get('docid', meta['backend_id']))) if isinstance(response, dict) else ''
            text = nested.get('content', nested.get('contents', nested.get('text', '')))
            if actual != meta['backend_id'] or not isinstance(text, str) or not text.strip():
                raise ContractError('retrieval_error', 'Document identity/text mismatch')
            snapshot = {'backend_id': actual, 'title': str(nested.get('title', meta['title'])), 'text': text}
            sha = digest(snapshot)
            state = self.state
            state['snapshots'][sha] = snapshot
            if sha not in state['documents'][document]['snapshot_hashes']:
                state['documents'][document]['snapshot_hashes'].append(sha)
            query = args.get('query') or next((s['query'] for s in reversed(state['searches'])
                                              if any(h['ref'] == document for h in s['hits'])), '')
            terms = re.findall(r'\w+', query.lower())
            lower, width = text.lower(), self.config.observation_chars
            candidates = {0}
            for term in set(terms):
                for match in list(re.finditer(re.escape(term), lower))[:32]:
                    candidates.add(max(0, match.start() - width // 4))
            start = max(candidates, key=lambda pos: (sum(t in lower[pos:pos + width] for t in set(terms)), -pos))
        snapshot = state['snapshots'][sha]
        full = snapshot['text']
        end = min(len(full), start + self.config.observation_chars)
        oid = f'o{state["next_observation"]}'
        state['next_observation'] += 1
        text = full[start:end]
        paragraphs = {}
        for n, local_start in enumerate(range(0, len(text), self.config.paragraph_chars), 1):
            local_end = min(len(text), local_start + self.config.paragraph_chars)
            paragraphs[f'{oid}:p{n}'] = {'text': text[local_start:local_end], 'start': start + local_start, 'end': start + local_end}
        view = {'id': oid, 'document': document, 'snapshot': sha, 'title': snapshot['title'],
                'text': text, 'start': start, 'end': end, 'document_chars': len(full),
                'paragraphs': paragraphs, 'created_by_action': aid, 'selection': 'local_literal_window'}
        state['observations'][oid] = view
        cursor = self._cursor(state, {'kind': 'window', 'document': document, 'snapshot': sha, 'start': end}) if end < len(full) else None
        return {'observation': view_card(view), 'next_cursor': cursor, 'delivered_observations': [oid],
                'issued_cursors': [cursor] if cursor else []}, state

    def _get_cursor(self, cursor, binding, kind):
        if cursor not in binding['cursors'] or cursor not in self._s['cursors'] or self._s['cursors'][cursor]['kind'] != kind:
            raise ContractError('cursor_invalid', f'{cursor}: use an issued cursor of the correct operation')
        return self._s['cursors'][cursor]

    def _read(self, args, binding):
        state = self.state
        if 'ref' in args:
            ref = args['ref']
            if ref.startswith('c'):
                if ref not in binding['claims']:
                    raise ContractError('unpublished_claim', ref)
                record = deepcopy(state['claims'][ref])
                return {'record': record, 'applicability': state['invalid'].get(ref, 'current_not_verified'),
                        'issued_claims': {ref: record['version']}}, state
            oid = ref.split(':')[0]
            if oid not in binding['observations']:
                raise ContractError('unexposed_reference', 'History search returns handles before raw recovery')
            view = state['observations'][oid]
            if ':' in ref and ref not in view['paragraphs']:
                raise ContractError('unknown_paragraph', ref)
            # Recover the exact whole immutable window; no new hidden text is introduced.
            return {'observation': view_card(view), 'requested': ref, 'delivered_observations': [oid]}, state
        if 'cursor' in args:
            rows = deepcopy(self._get_cursor(args['cursor'], binding, 'history')['rows'])
        else:
            q = args['query'].casefold()
            terms = q.split()
            candidates = []
            for oid, view in state['observations'].items():
                if oid in state['exposed']:
                    candidates.append({'kind': 'observation', 'ref': oid, 'title': view['title'], 'text': view['text']})
            for search in state['searches']:
                for hit in search['hits']:
                    if hit['ref'] in state['published_documents']:
                        candidates.append({'kind': 'search_hit', 'ref': hit['ref'], 'title': hit['title'],
                                           'text': search['query'] + ' ' + hit['snippet']})
            for cid, version in state['published_claims'].items():
                record = state['claims'][cid]
                candidates.append({'kind': 'claim', 'ref': cid, 'title': record['requirement'], 'text': record['finding']})
            for event in self.ledger.events:
                if event['kind'] == 'action_commit' and event['payload']['name'] == 'update_state':
                    note = event['payload']['arguments'].get('note')
                    if note:
                        candidates.append({'kind': 'model_note_not_evidence', 'ref': None, 'title': 'Research note', 'text': note})
            rows = [r for r in reversed(candidates) if all(t in (r['title'] + ' ' + r['text']).casefold() for t in terms)]
        page, remaining = rows[:self.config.history_page_size], rows[self.config.history_page_size:]
        # Directory excerpts are navigation only; exact body recovery uses ref, not the excerpt as a new source.
        page = [{**r, 'text': r['text'][:500], 'excerpt_only': True} for r in page]
        cursor = self._cursor(state, {'kind': 'history', 'rows': remaining}) if remaining else None
        return {'history': page, 'next_cursor': cursor, 'issued_cursors': [cursor] if cursor else []}, state

    def _basis(self, args, binding, own, use_draft=False):
        if use_draft and not args:
            draft = self._s['draft']
            if draft is None:
                raise ContractError('no_candidate', 'Supply answer+refs or create a shown draft; no empty remote audit')
            basis = deepcopy(draft['basis'])
            for cid, edge in basis['premises'].items():
                claim_sources(self._s, cid, edge['version'])
            return draft['answer'], basis
        answer = args['answer']
        return answer, resolve_refs(args.get('refs', []), self._s, binding, own=own)

    def _bundle(self, answer, basis):
        return answer_bundle(self._s, answer, basis, {'require_sources': self.config.require_sources,
                                                      'source_policy': 'actual_delivered_raw', 'protocol': VERSION})

    def _matching(self, bundle):
        identity = audit_identity(self.auditor) if self.auditor is not None else None
        for record in reversed(list(self._s['audits'].values())):
            candidate = deepcopy(bundle)
            # A report's own newly stored objections do not retroactively invalidate that report.
            candidate['conflicts'] = {k: v for k, v in candidate['conflicts'].items() if v['audit_id'] != record['id']}
            if record['identity'] == identity and digest(candidate) == record['bundle_hash']:
                return record
        return None

    def _verify(self, args, binding, own, aid):
        if self.config.audit_mode == 'off' or self.auditor is None:
            raise ContractError('audit_unavailable', 'No auditor configured; diagnostic submission remains explicit')
        answer, basis = self._basis(args, binding, own, True)
        bundle = self._bundle(answer, basis)
        cached = self._matching(bundle)
        remaining = self.config.max_model_calls - self._s['model_calls']
        need = (0 if cached else self.config.audit_attempts) + 1
        if remaining < need:
            raise ContractError('audit_budget', f'Need {need} requests including a post-audit policy decision; remaining={remaining}')
        if cached:
            state = self.state
            state['last_audit'] = cached['id']
            state['feedback'] = self._audit_feedback(cached, state)
            return {'audit': {'id': cached['id'], 'answer': cached['bundle']['answer'],
                              'report': deepcopy(cached['report']), 'status': cached['status']}, 'cached': True}, state
        payload = audit_payload(bundle, self._s)
        messages = audit_messages(bundle, payload)
        report, raw = None, None
        for attempt in range(self.config.audit_attempts):
            if self.counter(messages, []) + self.config.output_reserve > self.config.context_limit:
                raise ContractError('audit_context_capacity', 'Whole audit packet cannot fit; never silently drop evidence')
            state = self.state
            state['model_calls'] += 1
            state['usage']['unknown_calls'] += 1
            request = {'messages': deepcopy(messages), 'max_tokens': self.config.output_reserve}
            self._save('audit_request', {'action_id': aid, 'attempt': attempt + 1, 'request': request,
                                         'bundle_hash': digest(bundle), 'identity': audit_identity(self.auditor)}, state)
            try:
                raw = self.auditor.complete(request)
            except Exception as exc:
                self.ledger.append('audit_failure', {'action_id': aid, 'error_type': type(exc).__name__})
                raise ContractError('audit_service_error', f'Auditor request failed: {type(exc).__name__}') from exc
            state = self.state
            self._usage(state, raw.get('usage') if isinstance(raw, dict) else None)
            self._save('audit_response', {'action_id': aid, 'raw': raw,
                                          'wire_request': deepcopy(getattr(self.auditor, 'last_request', None))}, state)
            try:
                content = completion_message(raw).get('content')
                report = validate_report(parse_json(content), bundle, payload)
                break
            except (KeyError, IndexError, TypeError, ContractError) as exc:
                self.ledger.append('audit_protocol_failure', {'action_id': aid, 'error': str(exc)[:2000]})
                if attempt + 1 == self.config.audit_attempts:
                    raise ContractError('audit_protocol_error', f'Bounded audit repair exhausted: {str(exc)[:1000]}') from exc
                # An empty/ill-typed choices array is itself the malformed report.
                # Keep its full raw receipt above and never crash while making feedback.
                content = canonical(raw)[:4000]
                messages += [{'role': 'assistant', 'content': content},
                             {'role': 'user', 'content': 'Repair the complete report using the unchanged original packet. Do not change verdict merely to pass schema. Error: ' + str(exc)[:1500]}]
        state = self.state
        rid = 'v' + str(len(state['audits']) + 1)
        record = {'id': rid, 'bundle_hash': digest(bundle), 'bundle': bundle, 'identity': audit_identity(self.auditor),
                  'report': report, 'status': aggregate(report), 'created_by_action': aid}
        state['audits'][rid] = record
        state['last_audit'] = rid
        for key, row in report['checks'].items():
            if row['verdict'] != 'contradicted':
                continue
            scope = 'answer:' + digest(answer) if key in ('target', 'coverage') else next(
                (k for k in bundle['records'] if k.startswith(key + '@')), key)
            conflict = {'scope': scope, 'check': key, 'explanation': row['explanation'],
                        'witness_refs': row['refs'], 'audit_id': rid, 'label': 'Auditor opinion, not established truth'}
            state['conflicts'][digest(conflict)] = conflict
        state['feedback'] = self._audit_feedback(record, state)
        return {'audit': {'id': rid, 'answer': answer, 'report': report, 'status': record['status']}, 'cached': False}, state

    @staticmethod
    def _surface(answer):
        return None if answer is None else {'length': len(answer), 'ascii_double_quotes': answer.count('"'),
                                            'first_character': answer[:1], 'last_character': answer[-1:]}

    def _audit_feedback(self, record, state):
        return {'kind': 'audit_opinion', 'audit_id': record['id'], 'answer': record['bundle']['answer'],
                'status': record['status'], 'checks': record['report']['checks'],
                'answer_surface': self._surface(record['bundle']['answer']),
                'actual_effects': {'answer_changed': False}, 'not_a_fact_override': True}

    def _submit(self, args, binding, own):
        state = self.state
        if args.get('decision') == 'abstain':
            terminal = {'outcome': 'abstained', 'answer': '', 'reason': args['reason'], 'draft': state['draft']}
        else:
            answer, basis = self._basis(args, binding, own)
            if self.config.require_sources and not basis['sources']:
                raise ContractError('sources_required', 'This experiment requires a nonempty actual source path')
            bundle = self._bundle(answer, basis)
            record = self._matching(bundle)
            if self.config.audit_mode == 'hard' and (record is None or record['status'] != 'supported'):
                raise ContractError('audit_required', 'Hard mode needs a matching whole-answer supported audit; no stale certificate reuse')
            terminal = {'outcome': 'submitted', 'answer': answer, 'basis': basis, 'bundle': bundle,
                        'audit_status': record['status'] if record else 'unverified',
                        'audit_id': record['id'] if record else None,
                        'external_basis': bool(basis['sources'])}
        state['terminal'] = terminal
        return {'terminal': terminal}, state

    def end(self, reason):
        if not self._s['terminal']:
            state = self.state
            state['terminal'] = {'outcome': reason, 'answer': '', 'draft': state['draft']}
            self._save('end', {'reason': reason}, state)
        return self.terminal

    def close(self):
        self.ledger.close()
