from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from stride_search import Config, Harness
from stride_search import cli
from stride_search.archive import Archive
from stride_search.contract import (INTEGER_ANSWER, ContractError, SCHEMAS, answer_text,
                                    canonical, loads, tools, validate)
from stride_search.fixtures import ScriptedModel, native
from stride_search.providers import LocalCorpus


def corpus():
    return LocalCorpus([{'docid': 'synthetic', 'title': 'Instrument inventory',
                         'content': 'The instrument inventory contained 47 instruments.'}])


def script(args, raw=None):
    rows = [native(('search', {'queries': ['Instrument inventory'], 'top_k': 1})),
            native(('read', {'ref': 'd1'})), native(('finish', args))]
    for n, row in enumerate(rows):
        row['choices'][0]['message']['tool_calls'][0]['id'] = f'fixture_{n}'
    if raw is not None:
        rows[-1]['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = raw
    return ScriptedModel(rows)


@pytest.mark.parametrize('value', [47, 0, -47, '0012', '29/02', '21 years', '  "literal"\n'])
def test_real_execution_representation_archive_export_and_text_judge(tmp_path, value):
    model = script({'answer': value, 'refs': ['e1']})
    path = tmp_path / 'episode.sqlite'
    h = Harness('Synthetic inventory question', corpus(), path=path, answer_contract=INTEGER_ANSWER)
    try:
        result = h.run(model)
        expected = str(value) if type(value) is int else value
        assert result['outcome'] == 'submitted' and result['answer'] == expected and result['refs'] == ['e1']
        meta = result['answer_representation']
        assert meta['rule'] == INTEGER_ANSWER and meta['operation'] == ('decimal' if type(value) is int else 'identity')
        if type(value) is int:
            assert type(meta['input_value']) is int and meta['input_value'] == value
        event = [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]
        assert loads(event['arguments'])['answer'] == value
        assert type(loads(event['arguments'])['answer']) is type(value)
        advertised = next(t['function']['parameters'] for t in model.requests[-1]['tools'] if t['function']['name'] == 'finish')
        assert advertised['oneOf'][0]['properties']['answer']['type'] == ['string', 'integer']
    finally:
        h.close()
    report = cli.execute(cli.parser().parse_args(['replay', '--db', str(path)]))
    exported = json.loads(json.dumps(report))
    assert exported['answer_contract'] == INTEGER_ANSWER and exported['terminal']['answer'] == expected
    judge_path = Path(__file__).resolve().parents[3] / 'src/esr_grpo/judge.py'
    spec = importlib.util.spec_from_file_location('integer_fixture_judge', judge_path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    # Existing text judgment path, entirely offline. No factual quality claim.
    assert module.ExactMatchJudge().judge('fixture', exported['terminal']['answer'], expected).correct


@pytest.mark.parametrize('raw,code', [
    ('{"answer":true,"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":21.0,"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":2.1e1,"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":null,"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":[],"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":{},"refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":47,"answer":"47","refs":["e1"]}', 'duplicate_key'),
    ('{"answer":NaN,"refs":["e1"]}', 'invalid_json'),
    ('{"answer":Infinity,"refs":["e1"]}', 'invalid_json'),
    ('{"answer":47,"refs":"e1"}', 'arguments_invalid'),
    ('{"answer":47,"refs":[false]}', 'arguments_invalid'),
    ('{"answer":47,"refs":["e9"]}', 'unreceived_reference'),
    ('{"answer":47,"refs":[]}', 'sources_required'),
    ('{"answer":"  ","refs":["e1"]}', 'arguments_invalid'),
    ('{"answer":47,"refs":["e1"],"abstain":true,"reason":"fixture"}', 'arguments_invalid'),
])
def test_failure_boundaries_remain_enforced(raw, code):
    h = Harness('Synthetic', corpus(), answer_contract=INTEGER_ANSWER)
    model = script({}, raw)
    try:
        for _ in range(3):
            h._step(model)
        assert h.terminal is None
        result = [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]
        assert result['code'] == code
    finally:
        h.close()


def test_literal_contract_and_wrong_but_structurally_valid_answer():
    for value, outcome, prefix in [(47, None, '"'), ('"47"', 'submitted', '"'), (48, 'submitted', '')]:
        h = Harness('Synthetic: inventory was 47', corpus(), answer_contract=INTEGER_ANSWER,
                    config=Config(answer_prefix=prefix, answer_suffix=prefix))
        try:
            m = script({'answer': value, 'refs': ['e1']})
            for _ in range(3): h._step(m)
            assert (h.terminal or {}).get('outcome') == outcome
            if outcome:
                assert h.terminal['answer'] == str(value)
                assert h.terminal['semantic_status'] == 'not_automatically_verified'
            else:
                assert h.feedback['code'] == 'literal_contract'
        finally:
            h.close()


def test_only_declared_integer_acceptance_changes_and_other_tool_schemas_unchanged():
    old = tools(notes_enabled=True, final=False)
    new = tools(notes_enabled=True, final=False, answer_contract=INTEGER_ANSWER)
    assert old[:-1] == new[:-1]
    for value in [47, 0, -47, True, 1.0, None, [], {}, '', ' ', '0012', 'x' * 8001]:
        accepted = []
        for mode in ['legacy', INTEGER_ANSWER]:
            args = {'answer': value, 'refs': ['e1']}; before = deepcopy(args)
            try:
                validate('finish', args, answer_contract=mode); accepted.append(True)
            except ContractError:
                accepted.append(False)
            assert args == before
        assert accepted == ([False, True] if type(value) is int else [value == '0012', value == '0012'])
    with pytest.raises(ContractError):
        validate('search', {'queries': 'one string'}, answer_contract=INTEGER_ANSWER)
    with pytest.raises(ContractError):
        answer_text(10 ** 9000, answer_contract=INTEGER_ANSWER)
    with pytest.raises(ContractError):
        loads('{"answer":' + '1' * 9000 + '}')


def test_finish_order_blocking_error_and_prose_still_not_submitted():
    rows = [native(('finish', {'answer': 47, 'refs': []}), ('search', {'queries': ['inventory']})),
            native(('read', {'ref': 'd99'}), ('finish', {'answer': 47, 'refs': []})),
            native(content='The answer is 47.')]
    for raw, code in zip(rows, ['finish_order', 'not_executed', 'explicit_finish_required']):
        h = Harness('Synthetic', corpus(), answer_contract=INTEGER_ANSWER)
        try:
            h._step(ScriptedModel([raw])); assert h.terminal is None
            if code == 'explicit_finish_required': assert h.feedback['code'] == code
            else:
                results = [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result']
                assert any(r.get('code') == code for r in results)
        finally: h.close()


@pytest.mark.parametrize('value', [47, '0012'])
def test_formal_cli_run_defaults_enable_feature(tmp_path, monkeypatch, value):
    q = tmp_path / 'q.txt'; q.write_text('Synthetic inventory')
    model = script({'answer': value, 'refs': ['e1']})
    monkeypatch.setattr(cli, '_model', lambda *_: model)
    monkeypatch.setattr(cli, '_retriever', lambda *_: corpus())
    args = cli.parser().parse_args(['run', '--allow-network', '--accept-counter-estimate',
        '--base-url', 'http://fixture.invalid', '--model', 'fixture', '--model-revision', 'fixture',
        '--retrieval-url', 'http://fixture.invalid', '--index-id', 'fixture', '--counter', 'utf8_bytes',
        '--question-file', str(q), '--db', str(tmp_path / 'cli.sqlite'), '--max-model-calls', '6',
        '--context-limit', '96000', '--response-reserve', '4096'])
    report = cli.execute(args)
    assert report['terminal']['answer'] == str(value) and report['answer_contract'] == INTEGER_ANSWER
    assert cli.execute(cli.parser().parse_args(['schema', '--final']))[0]['function']['parameters']['oneOf'][0]['properties']['answer']['type'] == ['string', 'integer']


def test_recorded_original_r4_mechanical_submission(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/field_feedback'))
    from prefix_replay import load_prefix, replay
    case = Path(__file__).resolve().parents[1] / 'artifacts/20260914-hard12-a3/q778'
    tape = load_prefix(case, boundary=3); h, model = replay(tape, tmp_path / 'recorded.sqlite')
    original = loads((case / 'http/004/response.body').read_text(encoding='utf-8'))
    raw_args = original['choices'][0]['message']['tool_calls'][0]['function']['arguments']
    model.send = lambda wire: deepcopy(original)  # recorded action, no real HTTP
    try:
        h.set_answer_contract(INTEGER_ANSWER); h._step(model)
        assert h.terminal['outcome'] == 'submitted'
        assert h.terminal['answer'] == str(loads(raw_args)['answer'])
        assert h.terminal['answer_representation']['input_value'] == loads(raw_args)['answer']
        assert h.terminal['refs'] == ['e1'] and h.archive.report()['answer_contract'] == INTEGER_ANSWER
        assert [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]['arguments'] == raw_args
        old = Archive(case / 'episode.sqlite', readonly=True)
        try: assert old.report()['protocol'] == 'stride-search-3' and old.report()['terminal']['answer'] == ''
        finally: old.close()
    finally: h.close()
