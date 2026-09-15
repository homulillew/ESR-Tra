"""Continuous projection: actual prepared wire, delivery and archived originals."""
from copy import deepcopy

import pytest

from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.context import build
from stride_search.contract import canonical, digest
from stride_search.decision_protocol import identity
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import AnthropicModel, OpenAIModel, HTTP
from stride_search.workflow_contract import WorkflowConfig


PROTOCOL = 'continuous-prose-omission-v1'
SEARCH = ('search', {'queries': ['Lumen']})
READ = ('read', {'ref': 'd1'})


def make(protocol=PROTOCOL, **kwargs):
    return Harness('Who was the first director of Lumen Observatory?', smoke_corpus(),
                   config=Config(max_model_calls=8), decision_protocol=protocol, **kwargs)


def step(h, action=SEARCH, text='original reasoning'):
    model = ScriptedModel([native(action, content=text)])
    h._step(model)
    return model.requests[0]


def preview(h, **kwargs):
    return build(h, kwargs.pop('model', ScriptedModel([])), kwargs.pop('counter', h.counter),
                 final=kwargs.pop('final', False), output_limit=4096, **kwargs)


@pytest.mark.parametrize('provider', [OpenAIModel, AnthropicModel])
def test_first_actual_provider_preparation_bytes_equal_baseline(provider):
    hs = [make(p) for p in ['baseline', PROTOCOL]]
    model = provider('http://fixture.invalid', 'fixture', revision='fixture', http=HTTP())
    try:
        wires = [preview(h, model=model)['wire'] for h in hs]
        assert canonical(wires[0]).encode('utf-8') == canonical(wires[1]).encode('utf-8')
    finally:
        for h in hs:
            h.close()


@pytest.mark.parametrize('count', [0, 1, 3])
@pytest.mark.parametrize('final', [False, True])
def test_baseline_wire_only_differs_in_all_retained_prose(count, final):
    hs = [make(p) for p in ['baseline', PROTOCOL]]
    try:
        for h in hs:
            for i in range(count):
                step(h, SEARCH if i == 0 else READ, f'original {i}')
            if count:
                h.groups[-1]['messages'][0]['reasoning_content'] = 'preserved provider reasoning'
            h.notes['n'] = {'key': 'n', 'order': 1, 'text': 'keep note', 'anchors': []}
            h.repair = {'preview': 'keep repair'}
        originals = deepcopy(hs[1].groups)
        base, candidate = [preview(h, final=final) for h in hs]
        expected = deepcopy(base['wire'])
        for m in expected['messages']:
            if m['role'] == 'assistant':
                m['content'] = None
        assert candidate['wire'] == expected
        assert candidate['visible'] == base['visible']
        assert candidate['documents'] == base['documents']
        assert hs[1].groups == originals
        assert [v['source_round'] for v in candidate['history_projection']['changes']] == list(range(1, count + 1))
        assert hs[1].search_raw is None and hs[1].once_prose is None and hs[1].read_only is None
    finally:
        for h in hs:
            h.close()


def test_pure_capacity_rebuild_and_actual_preflight_do_not_commit_projection():
    h = make()
    try:
        for i in range(4):
            step(h, text=f'original {i}')
        original, seq = deepcopy(h.groups), h.archive.seq
        def counter(wire):
            assistants = [m for m in wire['messages'] if m['role'] == 'assistant']
            assert all(m['content'] is None for m in assistants)
            return h.config.context_limit if len(assistants) > 2 else 1
        first = preview(h, counter=counter)
        second = preview(h, counter=counter)
        assert first == second and first['compacted']
        assert [g['round'] for g in first['groups']] == [3, 4]
        assert [v['source_round'] for v in first['history_projection']['changes']] == [3, 4]
        assert h.groups == original and h.archive.seq == seq
        assert len([e for e in h.archive.events() if e['kind'] == 'history_projection']) == 4
        assert any(e['kind'] == 'delivery_preflight' for e in h.archive.events())
    finally:
        h.close()


def test_bounded_workflow_final_also_omits_latest_and_first():
    h = make(workflow=WorkflowConfig.profile('full'))
    try:
        step(h)
        preview(h)  # Must not acknowledge the prospective observation.
        step(h, READ)
        h.workflow.ack(h.groups, ['e1'])
        h.workflow.recovery_started = True
        h.workflow.recovery_used = h.workflow.options.recovery_rounds
        plan = preview(h)
        assert plan['workflow_final'] and plan['final']
        assert [t['function']['name'] for t in plan['wire']['tools']] == ['finish']
        assert all(m['content'] is None for m in plan['wire']['messages'] if m['role'] == 'assistant')
    finally:
        h.close()


def test_anthropic_projection_preserves_signed_reasoning_and_tool_receipts():
    h = make()
    model = AnthropicModel('http://fixture.invalid', 'fixture', revision='fixture', http=HTTP())
    try:
        step(h)
        raw = {'role': 'assistant', 'model': 'fixture', 'stop_reason': 'tool_use', 'content': [
            {'type': 'thinking', 'thinking': 'keep', 'signature': 'signature'},
            {'type': 'text', 'text': 'omit'},
            {'type': 'tool_use', 'id': 'call_0', 'name': 'search', 'input': SEARCH[1]},
            {'type': 'redacted_thinking', 'data': 'opaque'}]}
        h.groups[0]['messages'][0] = model.parse(raw).message
        before = deepcopy(h.groups)
        wire = preview(h, model=model, final=True)['wire']
        assistant = next(m for m in wire['messages'] if m['role'] == 'assistant')
        assert assistant['content'] == [b for b in raw['content'] if b['type'] != 'text']
        receipt = next(b for m in wire['messages'] for b in m['content'] if b['type'] == 'tool_result')
        assert receipt['content'] == before[0]['messages'][1]['content']
        assert h.groups == before
    finally:
        h.close()


def test_cli_complete_source_submission_and_readonly_sqlite_replay(tmp_path, monkeypatch, capsys):
    question = tmp_path / 'question.txt'
    question.write_text('Who was the first director of Lumen Observatory?', encoding='utf-8')
    path = tmp_path / 'episode.sqlite'
    model = ScriptedModel([native(SEARCH, content='locate'), native(READ, content='read source'),
                           native(('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}), content='submit')])
    monkeypatch.setattr(cli, '_model', lambda args, http: model)
    monkeypatch.setattr(cli, '_retriever', lambda args, http: smoke_corpus())
    flags = ['run', '--base-url', 'http://fixture.invalid', '--model', 'fixture',
             '--model-revision', 'fixture', '--retrieval-url', 'http://fixture.invalid',
             '--index-id', 'fixture', '--counter', 'utf8_bytes', '--question-file', str(question),
             '--db', str(path), '--max-model-calls', '3', '--context-limit', '96000',
             '--response-reserve', '4096', '--decision-protocol', PROTOCOL,
             '--allow-network', '--accept-counter-estimate']
    assert cli.parser().parse_args(flags).decision_protocol == PROTOCOL
    assert cli.main(flags) == 0
    capsys.readouterr()
    a = Archive(path, readonly=True)
    try:
        events = list(a.events())
        terminal = next(e['payload'] for e in events if e['kind'] == 'terminal')
        assert terminal['outcome'] == 'submitted' and terminal['refs'] == ['e1']
        assert 'Ada Rowan' in a.evidence('e1')['text']
        requests = [e['payload'] for e in events if e['kind'] == 'model_request']
        audits = [e['payload'] for e in events if e['kind'] == 'history_projection']
        assert len(requests) == len(audits) == 3
        assert requests[-1]['final'] and requests[-1]['visible_evidence'] == ['e1']
        for req, audit, wire in zip(requests, audits, model.requests):
            assert a.load_request(req['request']) == wire
            assert audit['wire_sha256'] == digest(wire)
            assert audit['identity'] == identity(PROTOCOL)
        groups = [a.json(e['payload']['group']) for e in events if e['kind'] == 'round_end']
        assert [g['messages'][0]['content'] for g in groups] == ['locate', 'read source', 'submit']
        assert [m['content'] for m in model.requests[-1]['messages'] if m['role'] == 'assistant'] == [None, None]
        a.verify()
    finally:
        a.close()
    original = path.read_bytes()
    assert cli.main(['replay', '--db', str(path)]) == 0
    assert path.read_bytes() == original
