"""Bounded observation-triggered prompts; no semantic progress or quality oracle."""
from copy import deepcopy

import pytest

from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.context import build
from stride_search.contract import ContractError, canonical, loads
from stride_search.decision_protocol import SEARCH_PIVOT, identity
from stride_search.fixtures import ScriptedModel, native, smoke_corpus


SEARCH = ('search', {'queries': ['Lumen']})
READ = ('read', {'ref': 'd1'})
STOP = ('finish', {'abstain': True, 'reason': 'fixture'})


def make(protocol='search-pivot-v1', calls=10, **kwargs):
    return Harness('Who directed Lumen?', smoke_corpus(), decision_protocol=protocol,
                   config=Config(max_model_calls=calls, **kwargs))


def control(wire):
    return loads(wire['messages'][-1]['content'].split('\n', 1)[1])


def preview(h, model=None, **kwargs):
    return build(h, model or ScriptedModel([]), h.counter, final=False,
                 output_limit=h.config.max_output_tokens, **kwargs)


def step(h, *calls):
    model = ScriptedModel([native(*calls)])
    h._step(model)
    return model.requests[0]


def test_two_completed_search_rounds_trigger_without_rewriting_query_or_tools():
    h = make()
    try:
        first, second = step(h, SEARCH), step(h, SEARCH)
        assert 'search_pivot' not in control(first)
        assert 'search_pivot' not in control(second)
        third = step(h, SEARCH)
        trigger = control(third)['search_pivot']
        assert trigger['source_rounds'] == [1, 2]
        assert trigger['instruction'] == SEARCH_PIVOT
        assert third['tools'] == first['tools']
        actions = [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result']
        assert all(loads(a['arguments']) == SEARCH[1] for a in actions)
        assert h.model_calls == 3 and h.search_pivot.used == 1
        assert h.backend_calls == 1  # Cached execution still counts as a search round.
    finally:
        h.close()


def test_read_in_search_round_resets_on_delivery_not_extraction():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH, READ)
        assert not h.exposed  # Window is pending, not acknowledged yet.
        wire = preview(h)['wire']
        assert 'search_pivot' not in control(wire)
        step(h, SEARCH)
        assert h.exposed == {'e1'}
        assert 'search_pivot' not in control(preview(h)['wire'])
        step(h, SEARCH)
        assert control(preview(h)['wire'])['search_pivot']['source_rounds'] == [3, 4]
    finally:
        h.close()


@pytest.mark.parametrize('calls', [3, 4])
def test_last_two_model_requests_never_trigger(calls):
    h = make(calls=calls)
    try:
        step(h, SEARCH)
        step(h, SEARCH)
        assert 'search_pivot' not in control(preview(h)['wire'])
    finally:
        h.close()


def test_final_suppresses_trigger_even_with_model_budget():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH)
        plan = build(h, ScriptedModel([]), h.counter, final=True,
                     output_limit=h.config.max_output_tokens)
        assert 'search_pivot' not in control(plan['wire'])
        assert h.search_pivot.used == 0
    finally:
        h.close()


def test_episode_cap_two_and_no_extra_decisions():
    h = make(calls=12)
    try:
        requests = [step(h, SEARCH) for _ in range(8)]
        assert [i + 1 for i, w in enumerate(requests) if 'search_pivot' in control(w)] == [3, 5]
        assert h.search_pivot.used == 2 and h.model_calls == 8
        assert len([e for e in h.archive.events() if e['kind'] == 'search_pivot']) == 2
    finally:
        h.close()


def test_build_and_delivery_preflight_are_idempotent():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH)  # fit_result_group has already previewed the next request.
        before = deepcopy(vars(h.search_pivot))
        seq = h.archive.seq
        plans = [preview(h) for _ in range(3)]
        assert plans[0] == plans[1] == plans[2]
        assert vars(h.search_pivot) == before and h.archive.seq == seq
        assert h.search_pivot.used == 0
        step(h, SEARCH)
        assert h.search_pivot.used == 1
    finally:
        h.close()


def test_failed_capacity_build_does_not_spend_trigger_but_send_attempt_does():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH)
        with pytest.raises(ContractError, match='cannot fit'):
            build(h, ScriptedModel([]), lambda wire: h.config.context_limit,
                  final=False, output_limit=h.config.max_output_tokens)
        assert h.search_pivot.used == 0
        model = ScriptedModel([RuntimeError('fixture transport failure')])
        h._step(model)
        assert len(model.requests) == 1 and h.search_pivot.used == 1
        assert h.terminal['outcome'] == 'model_transport'
    finally:
        h.close()


def test_completed_observations_survive_context_group_eviction():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH)
        assert control(preview(h, groups=[])['wire'])['search_pivot']['source_rounds'] == [1, 2]
        def tight_counter(wire):
            count = sum(m['role'] == 'assistant' for m in wire['messages'])
            return h.config.context_limit if count > 1 else 1
        plan = build(h, ScriptedModel([]), tight_counter, final=False,
                     output_limit=h.config.max_output_tokens)
        assert plan['compacted'] and len(plan['groups']) == 1
        assert control(plan['wire'])['search_pivot']['source_rounds'] == [1, 2]
    finally:
        h.close()


def test_declared_but_unexecuted_search_does_not_count():
    h = make()
    try:
        step(h, SEARCH)
        step(h, ('search', {'queries': []}))
        assert 'search_pivot' not in control(preview(h)['wire'])
        step(h, SEARCH)
        assert 'search_pivot' not in control(preview(h)['wire'])
    finally:
        h.close()


def test_no_tool_decision_breaks_consecutive_search_rounds():
    h = make()
    try:
        step(h, SEARCH)
        h._step(ScriptedModel([native(content='Still considering sources.')]))
        step(h, SEARCH)
        assert 'search_pivot' not in control(preview(h)['wire'])
    finally:
        h.close()


def test_withheld_window_does_not_reset_observation():
    h = make()
    try:
        step(h, SEARCH)
        step(h, SEARCH, READ)
        group = deepcopy(h.groups[-1])
        group['evidence'] = []
        for message in group['messages'][1:]:
            result = loads(message['content'])
            if 'evidence' in result:
                message['content'] = canonical({'ok': False, 'executed': True,
                                               'code': 'result_capacity'})
        # Same transformation as result preflight withholding; archive retains e1.
        h.groups[-1] = group
        h.search_pivot.complete(group)
        assert h.archive.evidence('e1')['text']
        assert control(preview(h)['wire'])['search_pivot']['source_rounds'] == [1, 2]
    finally:
        h.close()


@pytest.mark.parametrize('protocol', ['baseline', 'constraint-review-v1'])
def test_existing_protocol_wire_and_archive_have_no_pivot_state(protocol):
    h = make(protocol)
    try:
        for _ in range(3):
            wire = step(h, SEARCH)
            assert 'search_pivot' not in control(wire)
            assert SEARCH_PIVOT not in str(wire)
        assert h.search_pivot is None
        assert all(e['kind'] != 'search_pivot' for e in h.archive.events())
        # Disabled protocol does not add even internal build result fields.
        assert 'search_pivot_projection' not in preview(h)
    finally:
        h.close()


def test_pivot_inactive_wire_equals_baseline_and_uses_no_constraint_review():
    hs = [make(p) for p in ['baseline', 'search-pivot-v1']]
    try:
        assert preview(hs[0])['wire'] == preview(hs[1])['wire']
    finally:
        for h in hs:
            h.close()


def test_trigger_request_and_identity_survive_readonly_replay(tmp_path):
    path = tmp_path / 'pivot.sqlite'
    h = Harness('Who directed Lumen?', smoke_corpus(), path=path,
                decision_protocol='search-pivot-v1', config=Config(max_model_calls=8))
    try:
        step(h, SEARCH)
        step(h, SEARCH)
        wire = step(h, STOP)
    finally:
        h.close()
    archive = Archive(path, readonly=True)
    try:
        events = list(archive.events())
        trigger = next(e['payload'] for e in events if e['kind'] == 'search_pivot')
        assert trigger['round'] == 3 and trigger['source_rounds'] == [1, 2]
        assert trigger['protocol'] == identity('search-pivot-v1')
        request = [e['payload'] for e in events if e['kind'] == 'model_request'][-1]
        assert archive.load_request(request['request']) == wire
        assert control(wire)['search_pivot'] == {k: v for k, v in trigger.items() if k != 'round'}
        archive.verify()
    finally:
        archive.db.close()


def test_cli_existing_choices_enable_pivot():
    flags = ['run', '--base-url', 'http://fixture.invalid', '--model', 'fixture',
             '--model-revision', 'fixture', '--retrieval-url', 'http://fixture.invalid',
             '--index-id', 'fixture', '--counter', 'utf8_bytes', '--question-file', 'fixture',
             '--db', 'fixture.sqlite', '--max-model-calls', '6', '--context-limit', '96000',
             '--response-reserve', '4096', '--decision-protocol', 'search-pivot-v1']
    assert cli.parser().parse_args(flags).decision_protocol == 'search-pivot-v1'
