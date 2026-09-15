"""Re-execute a recorded prefix using only its captured model/backend responses.

This is an isolated replay adapter, not general Harness.resume. It never opens a
production index or sends HTTP. Later requests are comparison oracles only.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path

from stride_search import Config, Harness
from stride_search.archive import Archive
from stride_search.context import build
from stride_search.contract import canonical, digest
from stride_search.providers import HTTP, OpenAIModel

from reproduce import read


class PrefixMismatch(ValueError):
    pass


class CapturedBackend:
    def __init__(self, header, events, objects):
        self.identity = deepcopy(header['retriever'])
        self.capabilities = deepcopy(header['search_capabilities'])
        self.compilations = {}
        self.calls = []
        pending = None
        for e in events:
            p = e['payload']
            if e['kind'] == 'query_execution':
                self.compilations[p['query']] = deepcopy(p['compiled'])
            elif e['kind'] == 'backend_request':
                if pending is not None:
                    raise PrefixMismatch('Overlapping historical backend requests')
                pending = p
            elif e['kind'] == 'backend_response':
                if pending is None or pending['kind'] != p['kind']:
                    raise PrefixMismatch('Historical backend pairing failed')
                self.calls.append((pending, deepcopy(p), deepcopy(objects[p['object']]),
                                   deepcopy(objects[p['raw_wire']]) if p['raw_wire'] else None))
                pending = None
        if pending:
            raise PrefixMismatch('Incomplete historical backend response')
        self.used = 0

    def compile_query(self, query):
        if query not in self.compilations:
            raise PrefixMismatch('Query absent from prefix; replay cannot fabricate new retrieval')
        return deepcopy(self.compilations[query])

    def _call(self, kind, args):
        if self.used >= len(self.calls):
            raise PrefixMismatch('No historical backend suffix is available')
        request, response, value, raw = self.calls[self.used]
        if request['kind'] != kind or request['arguments'] != args:
            raise PrefixMismatch('Historical backend arguments/order mismatch')
        self.used += 1
        self.last_wire_response = deepcopy(raw)
        self.last_wire_request = deepcopy(response.get('wire_request'))
        return deepcopy(value)

    def search(self, query, top_k):
        return self._call('search', {'query': query, 'top_k': top_k})

    def get_document(self, docid):
        return self._call('get_document', {'docid': docid})


class CapturedModel(OpenAIModel):
    def __init__(self, identity, requests, responses):
        super().__init__(identity['endpoint'], identity['model'], revision=identity['revision_label'],
            http=HTTP(allow_network=False), temperature=identity['temperature'],
            expected_response_model=identity['expected_response_model'], output_parameter=identity['output_parameter'])
        self.requests, self.responses = requests, responses
        self.used = 0; self.comparisons = []

    def send(self, wire):
        if self.used >= len(self.responses):
            raise PrefixMismatch('Prefix-only model cannot send or use a historical suffix')
        original = self.requests[self.used]
        same = canonical(wire).encode('utf-8') == original
        self.comparisons.append({'round': self.used + 1, 'json_equal': read_bytes(original) == wire,
                                  'serializer_bytes_equal': same})
        if not same:
            raise PrefixMismatch('Historical request differs from reconstructed request')
        raw = deepcopy(self.responses[self.used]); self.used += 1
        return raw


def read_bytes(data):
    import json
    return json.loads(data)


def load_prefix(case, boundary=4):
    """Only reachable prefix objects enter the replay tape; final SQL state is unused."""
    case = Path(case)
    a = Archive(case / 'episode.sqlite', readonly=True)
    try:
        events = []
        for e in a.events():
            if e['kind'] == 'model_request' and e['payload']['round'] > boundary:
                break
            events.append(e)
        if not events or events[-1]['kind'] != 'round_end' or events[-1]['payload']['round'] != boundary:
            raise PrefixMismatch('No complete requested prefix boundary')
        objects = {}
        # Only backend response objects are needed by the retriever. Model envelopes
        # come from the first boundary HTTP files and must match their archived objects.
        for e in events:
            if e['kind'] == 'backend_response':
                for key in ('object', 'raw_wire'):
                    ref = e['payload'].get(key)
                    if ref:
                        objects[ref] = a.json(ref)
        requests = [(case / 'http' / f'{i:03d}' / 'request.body').read_bytes() for i in range(1, boundary + 1)]
        responses = [read(case / 'http' / f'{i:03d}' / 'response.body') for i in range(1, boundary + 1)]
        for e in events:
            p = e['payload']
            if e['kind'] == 'model_request':
                assert a.load_request(p['request']) == read_bytes(requests[p['round'] - 1])
            if e['kind'] == 'model_response':
                assert a.json(p['raw']) == responses[p['round'] - 1]
        identity = next(e['payload'] for e in events if e['kind'] == 'model_identity')
        return {'header': events[0]['payload'], 'identity': identity, 'events': events,
                'objects': objects, 'requests': requests, 'responses': responses, 'boundary': boundary}
    finally:
        a.close()


def replay(tape, path, mode='legacy'):
    backend = CapturedBackend(tape['header'], tape['events'], tape['objects'])
    model = CapturedModel(tape['identity'], tape['requests'], tape['responses'])
    # A zero clock is used ONLY during offline reconstruction. No claim is made
    # that it restores the original monotonic elapsed-time balance for live use.
    h = Harness(tape['header']['question'], backend, path=path,
                config=Config(**tape['header']['config']), clock=lambda: 0.0)
    h.model_identity = deepcopy(model.identity)
    h.archive.append('model_identity', h.model_identity)
    try:
        for i in range(tape['boundary']):
            if i == tape['boundary'] - 1 and mode != 'legacy':
                h.validation_feedback = mode
            h._step(model)
            if h.terminal is not None:
                raise PrefixMismatch('Prefix unexpectedly terminated')
        if model.used != tape['boundary'] or backend.used != len(backend.calls):
            raise PrefixMismatch('Unconsumed prefix records')
        return h, model
    except Exception:
        h.close()
        raise


def next_payload(h, model):
    return build(h, model, h.counter, final=h.final_phase(),
                 output_limit=min(h.config.max_output_tokens, h.remaining()['output_reservation']))['wire']


def state(h):
    """All runtime mutable state except observational event hashes and the clock."""
    names = ('question', 'groups', 'group_refs', 'exposed', 'published_docs', 'evidence_order',
             'doc_order', 'notes', 'note_history', 'search_cache', 'search_capabilities',
             'navigation_history', 'navigation_acked_rounds', 'model_calls', 'action_slots',
             'declared_calls', 'backend_calls', 'output_charged', 'feedback', 'terminal', 'model_identity', 'repair')
    out = {}
    for name in names:
        value = deepcopy(getattr(h, name))
        out[name] = sorted(value) if isinstance(value, set) else value
    out['config'] = h.config.to_dict()
    out['docs'] = list(h.archive.db.execute('SELECT * FROM docs ORDER BY n'))
    out['evidence'] = list(h.archive.db.execute('SELECT * FROM evidence ORDER BY n'))
    out['historical_usage'] = [e['payload']['usage'] for e in h.archive.events() if e['kind'] == 'model_response']
    out['remaining'] = h.remaining(); out['phase'] = 'FINAL' if h.final_phase() else 'RESEARCH'
    return out


def prefix_event_diff(original, replayed):
    """Event payloads are exact, except the explicitly synthetic timing measurements."""
    def normalized(e):
        payload = deepcopy(e['payload'])
        if e['kind'] in ('model_response', 'backend_response'):
            payload.pop('elapsed_seconds', None)
        return {'seq': e['seq'], 'kind': e['kind'], 'payload': payload}
    if len(original) != len(replayed):
        return [{'kind': 'event_count', 'original': len(original), 'replayed': len(replayed)}]
    return [{'seq': a['seq'], 'kind': a['kind']} for a, b in zip(original, replayed) if normalized(a) != normalized(b)]


def pointer(parts):
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def differences(a, b, path=()):
    if type(a) is not type(b):
        return [{'path': pointer(path), 'before': a, 'after': b}]
    if isinstance(a, dict) and set(a) == set(b):
        return [d for k in a for d in differences(a[k], b[k], (*path, k))]
    if isinstance(a, list) and len(a) == len(b):
        return [d for i in range(len(a)) for d in differences(a[i], b[i], (*path, i))]
    return [] if a == b else [{'path': pointer(path), 'before': a, 'after': b}]


def request_diff(a, b, failed_id):
    raw = differences(a, b); allowed = {}; inner = []
    for i, m in enumerate(a['messages']):
        if m.get('role') == 'tool' and m.get('tool_call_id') == failed_id:
            allowed[f'/messages/{i}/content'] = ('', '/message')
        elif m.get('role') == 'user' and m.get('content', '').startswith('Current control state (data, not source evidence):\n'):
            allowed[f'/messages/{i}/content'] = ('Current control state (data, not source evidence):\n', '/feedback/message')
    assert len(allowed) == 2 and {d['path'] for d in raw} == set(allowed)
    for d in raw:
        prefix, expected = allowed[d['path']]
        before, after = d['before'], d['after']
        assert before.startswith(prefix) and after.startswith(prefix)
        nested = differences(read_bytes(before[len(prefix):].encode()), read_bytes(after[len(prefix):].encode()))
        assert len(nested) == 1 and nested[0]['path'] == expected
        inner.append({'wire_path': d['path'], 'decoded_path': expected, **{k: nested[0][k] for k in ('before', 'after')}})
    assert inner[0]['before'] == inner[1]['before'] and inner[0]['after'] == inner[1]['after']
    return {'wire_difference_count': len(raw), 'decoded_difference_count': len(inner),
            'differences': inner, 'whitelist_passed': True,
            'all_other_fields_unchanged': True, 'new_instruction_or_answer_example_added': False}


def timing_check(case, prefix_events):
    rows = []
    with (Path(case) / 'events-timed.jsonl').open(encoding='utf-8') as f:
        for line in f:
            row = read_bytes(line.encode())
            if row['seq'] > prefix_events[-1]['seq']:
                break
            rows.append(row)
    indexed = {r['seq']: r for r in rows}
    first, last = indexed[prefix_events[0]['seq']], indexed[prefix_events[-1]['seq']]
    delta = (datetime.fromisoformat(last['utc']) - datetime.fromisoformat(first['utc'])).total_seconds()
    return {'recorded_event_utc_delta_seconds': delta, 'original_monotonic_elapsed_seconds': None,
            'exact_time_balance_reconstructible': False,
            'reason': 'Collector records UTC after append. Harness.started and monotonic elapsed at the boundary are not recorded; event timestamps omit initialization and are a different clock.',
            'utc_delta_used_as_live_budget': False, 'copied_file_time_charged': False}
