"""Actual-wire projection and provenance checks, without online model calls."""
from copy import deepcopy

import pytest

from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.context import build
from stride_search.contract import digest, loads, text_hash
from stride_search.decision_protocol import identity
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.history_projection import project
from stride_search.providers import AnthropicModel, HTTP


SEARCH = ('search', {'queries': ['Lumen']})
READ = ('read', {'ref': 'd1'})
STOP = ('finish', {'abstain': True, 'reason': 'fixture'})


def make(protocol='middle-history-v1', **kwargs):
    return Harness('Who directed Lumen?', smoke_corpus(), decision_protocol=protocol,
                   config=Config(max_model_calls=8), **kwargs)


def step(h, action=SEARCH, text='reason'):
    model = ScriptedModel([native(action, content=text)])
    h._step(model)
    return model.requests[0]


def preview(h, *, model=None, final=False, counter=None, groups=None):
    return build(h, model or ScriptedModel([]), counter or h.counter,
                 final=final, output_limit=h.config.max_output_tokens, groups=groups)


def assistants(wire):
    return [m for m in wire['messages'] if m['role'] == 'assistant']


@pytest.mark.parametrize('count', [0, 1, 2, 3, 4])
@pytest.mark.parametrize('final', [False, True])
def test_only_middle_prose_differs_from_baseline(count, final):
    hs = [make(p) for p in ['baseline', 'middle-history-v1']]
    try:
        for h in hs:
            for i in range(count):
                step(h, SEARCH if i == 0 else READ, f'prose {i}')
        base, changed = [preview(h, final=final) for h in hs]
        expected = deepcopy(base['wire'])
        for message in assistants(expected)[1:-1]:
            message['content'] = None
        assert changed['wire'] == expected  # Includes tools, parameters, control and raw results.
        assert changed['visible'] == base['visible']
        assert changed['documents'] == base['documents']
        assert changed['capacity'] == hs[1].counter(changed['wire'])
        assert [g['messages'][0]['content'] for g in changed['groups']] == [f'prose {i}' for i in range(count)]
        assert [c['source_round'] for c in changed['history_projection']['changes']] == list(range(2, count))
    finally:
        for h in hs:
            h.close()


def test_first_complete_group_is_not_necessarily_first_model_request():
    h = make()
    try:
        h._step(ScriptedModel([native(content='no action')]))
        assert h.first_complete_round is None
        for i in range(3):
            step(h, text=f'group {i}')
        plan = preview(h)
        assert h.first_complete_round == 2
        assert [m['content'] for m in assistants(plan['wire'])] == ['group 0', None, 'group 2']
        assert plan['history_projection']['episode_first_complete_round'] == 2
    finally:
        h.close()


def test_evicted_episode_first_group_is_neither_restored_nor_replaced():
    h = make()
    try:
        for i in range(4):
            step(h, text=f'group {i}')
        h.groups = h.groups[-2:]  # Persisted rolling eviction.
        plan = preview(h)
        assert [m['content'] for m in assistants(plan['wire'])] == [None, 'group 3']
        assert plan['history_projection']['episode_first_complete_round'] == 1
        assert plan['history_projection']['first_complete_group_present'] is False
        assert plan['history_projection']['retained_group_rounds'] == [3, 4]
    finally:
        h.close()


def test_capacity_loop_preflight_and_repeated_build_do_not_mutate_groups_or_archive():
    h = make()
    try:
        for i in range(4):
            step(h, text=f'group {i}')
        before, seq, first = deepcopy(h.groups), h.archive.seq, h.first_complete_round
        def counter(wire):
            return h.config.context_limit if len(assistants(wire)) > 2 else 1
        plans = [preview(h, counter=counter, groups=h.groups) for _ in range(2)]
        assert plans[0] == plans[1]
        assert plans[0]['compacted'] and len(plans[0]['groups']) == 2
        assert [m['content'] for m in assistants(plans[0]['wire'])] == [None, 'group 3']
        assert h.groups == before and h.archive.seq == seq and h.first_complete_round == first
        assert [g['messages'][0]['content'] for g in plans[0]['groups']] == ['group 2', 'group 3']
        # The real fit_result_group preflights above did not create extra request events.
        assert len([e for e in h.archive.events() if e['kind'] == 'history_projection']) == 4
    finally:
        h.close()


def test_prospective_first_group_during_preflight_is_local_only():
    h = make()
    try:
        message = native(SEARCH, content='first')['choices'][0]['message']
        group = {'round': 3, 'messages': [message], 'evidence': [], 'documents': []}
        plan = preview(h, groups=[group])
        assert plan['history_projection']['episode_first_complete_round'] == 3
        assert assistants(plan['wire'])[0]['content'] == 'first'
        assert h.first_complete_round is None and h.groups == []
    finally:
        h.close()


def test_reasoning_notes_and_repair_are_not_projected():
    h = make()
    try:
        for _ in range(3):
            step(h)
        h.groups[1]['messages'][0]['reasoning_content'] = 'provider-private reasoning'
        h.notes['x'] = {'order': 1, 'key': 'x', 'text': 'keep note', 'anchors': []}
        h.repair = {'preview': 'keep uncommitted response'}
        before = deepcopy(h.groups)
        plan = preview(h)
        assert assistants(plan['wire'])[1]['reasoning_content'] == 'provider-private reasoning'
        control = loads(plan['wire']['messages'][-1]['content'].split('\n', 1)[1])
        assert control['current_notes_not_evidence'] == list(h.notes.values())
        assert control['uncommitted_response_not_evidence'] == h.repair
        assert h.groups == before
    finally:
        h.close()


def test_anthropic_native_wire_filters_text_only_and_preserves_signed_thinking():
    h = make()
    model = AnthropicModel('http://fixture.invalid', 'fixture', revision='fixture', http=HTTP())
    try:
        for i in range(3):
            step(h, text=f'prose {i}')
        for i, group in enumerate(h.groups):
            raw = {'role': 'assistant', 'model': 'fixture', 'stop_reason': 'tool_use', 'content': [
                {'type': 'thinking', 'thinking': f'think {i}', 'signature': f'sig {i}'},
                {'type': 'text', 'text': f'prose {i}'},
                {'type': 'tool_use', 'id': 'call_0', 'name': 'search', 'input': SEARCH[1]},
                {'type': 'redacted_thinking', 'data': f'opaque {i}'},
                {'type': 'text', 'text': 'tail'}]}
            group['messages'][0] = model.parse(raw).message
        before = deepcopy(h.groups)
        wire = preview(h, model=model)['wire']
        blocks = assistants(wire)
        assert blocks[0]['content'] == before[0]['messages'][0]['_anthropic_blocks']
        assert blocks[-1]['content'] == before[-1]['messages'][0]['_anthropic_blocks']
        assert blocks[1]['content'] == [b for b in before[1]['messages'][0]['_anthropic_blocks'] if b['type'] != 'text']
        results = [b for m in wire['messages'] for b in m['content'] if b['type'] == 'tool_result']
        assert [b['tool_use_id'] for b in results] == ['call_0'] * 3
        assert [b['content'] for b in results] == [g['messages'][1]['content'] for g in before]
        assert h.groups == before
    finally:
        h.close()


@pytest.mark.parametrize('prose', [None, ''])
def test_null_empty_and_non_tool_messages(prose):
    original = [{'round': i, 'messages': [{'role': 'assistant', 'content': prose,
                 'tool_calls': [] if i == 2 else [{'id': 'a'}]}]} for i in range(1, 4)]
    before = deepcopy(original)
    messages, audit = project(original, first_round=1, latest_round=3)
    assert messages == [g['messages'][0] for g in original]
    assert audit['changes'] == [] and original == before


def test_actual_request_audit_and_original_sqlite_groups_survive_replay(tmp_path):
    path = tmp_path / 'middle.sqlite'
    h = make(path=path)
    try:
        for i in range(3):
            step(h, SEARCH if i == 0 else READ, f'original {i}')
        wire = step(h, STOP)
        assert h.model_calls == 4 and h.search_pivot is None
    finally:
        h.close()
    a = Archive(path, readonly=True)
    try:
        events = list(a.events())
        audits = [e['payload'] for e in events if e['kind'] == 'history_projection']
        assert len(audits) == 4 and audits[-1]['round'] == 4
        change = audits[-1]['changes'][0]
        assert change['source_round'] == 2
        assert change['removed_content_sha256'] == text_hash('original 1')
        assert change['removed_content_chars'] == len('original 1')
        assert audits[-1]['identity'] == identity('middle-history-v1')
        groups = [a.json(e['payload']['group']) for e in events if e['kind'] == 'round_end']
        assert groups[1]['messages'][0]['content'] == 'original 1'
        assert digest(groups[1]['messages'][0]) == change['original_message_sha256']
        requests = [e['payload'] for e in events if e['kind'] == 'model_request']
        assert a.load_request(requests[-1]['request']) == wire
        assert assistants(wire)[1]['content'] is None
        a.verify()
    finally:
        a.db.close()


def test_formal_cli_accepts_new_identity():
    flags = ['run', '--base-url', 'http://fixture.invalid', '--model', 'fixture',
             '--model-revision', 'fixture', '--retrieval-url', 'http://fixture.invalid',
             '--index-id', 'fixture', '--counter', 'utf8_bytes', '--question-file', 'fixture',
             '--db', 'fixture.sqlite', '--max-model-calls', '6', '--context-limit', '96000',
             '--response-reserve', '4096', '--decision-protocol', 'middle-history-v1']
    assert cli.parser().parse_args(flags).decision_protocol == 'middle-history-v1'
