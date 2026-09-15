"""Deterministic integration checks; no claims about real policy quality."""
import json
import pytest
from stride_search import Config, Harness, cli
from stride_search.contract import canonical, INTEGER_ANSWER
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import ByteCounter
from stride_search.workflow_contract import WorkflowConfig
from test_workflow_v1 import make, step, SEARCH, READ, FINISH


def test_withheld_navigation_is_not_reused_until_received():
    class Counter(ByteCounter):
        hide = True
        def __call__(self, wire):
            return 10**8 if self.hide and '"hits":' in canonical(wire).replace('\\"', '"') else 1
    counter = Counter()
    h = Harness('Q', smoke_corpus(), counter=counter, workflow=WorkflowConfig.profile('full'))
    try:
        result = step(h, SEARCH)[0]['result']
        assert result['code'] == 'result_capacity'
        assert not h.workflow.observations and not h.published_docs
        counter.hide = False
        result = step(h, SEARCH)[0]['result']['results'][0]
        assert result['view'] == 'full' and result['observation']['prior_deliveries'] == 0
        assert not h.published_docs
        step(h, ('finish', {'abstain': True, 'reason': 'fixture'}))
        assert h.published_docs and h.workflow.observations
    finally: h.close()


def test_changed_snippet_is_not_collapsed():
    h = make()
    try:
        step(h, SEARCH)
        key = next(iter(h.search_cache)); h.search_cache[key][0]['snippet'] += ' New fixture detail.'
        result = step(h, SEARCH)[0]['result']['results'][0]
        assert result['view'] == 'full' and 'New fixture' in result['hits'][0]['snippet']
    finally: h.close()


def test_gap_noop_does_not_reset_stagnation_and_bounds_history():
    h = make(WorkflowConfig(enabled=True, gap_state=True, repetition='observe'))
    gap = dict(subject='Lumen', question='Who?', kind='locate', status='open', evidence_refs=[],
               navigation_refs=[], next_action='read', basis='Need a source.')
    try:
        step(h, SEARCH); step(h, SEARCH); step(h, SEARCH)
        step(h, ('update_gap', gap)); before = h.workflow.stall_rounds
        assert before >= 2
        revision = h.workflow.gap['revision']
        r = step(h, ('update_gap', gap))[0]['result']
        assert not r['changed'] and h.workflow.stall_rounds == before and h.workflow.gap['revision'] == revision
        for i in range(5): step(h, ('update_gap', {**gap, 'basis': f'fixture revision {i}'}))
        assert len(h.workflow.gap_history) == 4 and not h.exposed
        assert step(h, ('update_gap', {**gap, 'evidence_refs':['e9']}))[0]['result']['code'] == 'unreceived_reference'
    finally: h.close()


def test_duplicate_recovery_error_does_not_poison_valid_finish():
    h = make()
    try:
        step(h, SEARCH); step(h, READ); step(h, SEARCH); step(h, SEARCH); step(h, SEARCH)
        result = step(h, SEARCH, FINISH)
        assert result[0]['result']['code'] == 'duplicate_query_blocked'
        assert result[0]['result']['blocks_finish'] is False
        assert h.terminal['outcome'] == 'submitted'
    finally: h.close()


def test_goal_window_and_evidence_replay_are_exact():
    h = make()
    try:
        step(h, SEARCH)
        v = step(h, ('read', {'ref':'d1','goal':'first director','length':70}))[0]['result']['evidence']
        assert v['text'] == h.archive.get(v['snapshot'])[v['start']:v['end']]
        assert step(h, ('read', {'ref':v['ref']}))[0]['result']['evidence'] == v
    finally: h.close()


def live_flags(command):
    return [command,'--base-url','http://fixture.invalid','--model','fixture','--model-revision','fixture',
            '--retrieval-url','http://fixture.invalid','--index-id','fixture','--counter','utf8_bytes']


def test_cli_token_reserve_rejected_before_model_or_question(tmp_path, monkeypatch):
    args = cli.parser().parse_args(live_flags('run') + ['--allow-network','--accept-counter-estimate',
        '--question-file',str(tmp_path/'absent'), '--db',str(tmp_path/'none.sqlite'), '--max-model-calls','3',
        '--context-limit','96000','--response-reserve','10','--max-output-tokens','4096'])
    args.counter = 'hf_tokens'
    monkeypatch.setattr(cli, '_counter', lambda _: ByteCounter())
    monkeypatch.setattr(cli, '_model', lambda *_: pytest.fail('model accessed before capacity guard'))
    with pytest.raises(ValueError, match='Token-mode'):
        cli.execute(args)


@pytest.mark.parametrize('status', ['NOT_RUN','http_error'])
def test_cohort_cli_exit_code_preserves_failure(tmp_path, monkeypatch, status):
    monkeypatch.setattr(cli, 'execute', lambda _: {'rows':[{'status':status}]})
    assert cli.main(live_flags('cohort') + ['--plan','fixture','--output',str(tmp_path),
                                         '--max-total-model-calls','3']) == 2
