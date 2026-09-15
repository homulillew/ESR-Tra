from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import threading
import urllib.request

from jsonschema import Draft202012Validator
import pytest
from stride_search import Config, Harness
from stride_search.contract import ContractError, SCHEMAS, canonical, loads, validate
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import HTTP, LocalCorpus, OpenAIModel
from stride_search.validation_feedback import MAX_MESSAGE, format_validation_error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/field_feedback'))
from matrix import acceptance_matrix


def message(name, value):
    with pytest.raises(ContractError) as error:
        validate(name, value, feedback='field')
    assert error.value.code == 'arguments_invalid'
    return str(error.value)


@pytest.mark.parametrize('args,accepted', [
    ({'answer': 47, 'refs': []}, False),
    ({'answer': 'synthetic', 'refs': []}, True),
    ({'answer': '  "literal"\n', 'refs': ['e9']}, True),
    ({'answer': '   ', 'refs': []}, False),
    ({'answer': '', 'refs': []}, False),
    ({'answer': 'synthetic', 'refs': 'e9'}, False),
    ({'answer': 'synthetic', 'refs': [47]}, False),
    ({'refs': []}, False),
    ({'answer': 'synthetic'}, False),
    ({'answer': 'synthetic', 'refs': [], 'extra': 'SECRET'}, False),
    ({'answer': 'synthetic', 'refs': [], 'abstain': True, 'reason': 'unavailable'}, False),
    ({'abstain': True, 'reason': 'unavailable'}, True),
    ({}, False),
])
def test_same_legality_no_mutation(args, accepted):
    original = deepcopy(args)
    for mode in ('legacy', 'field'):
        if accepted:
            assert validate('finish', args, feedback=mode) is None
        else:
            with pytest.raises(ContractError) as error:
                validate('finish', args, feedback=mode)
            assert error.value.code == 'arguments_invalid'
        assert args == original


@pytest.mark.parametrize('name,value,path,expected', [
    ('finish', {'answer': 47, 'refs': []}, '/answer', 'expected type string; received type integer'),
    ('finish', {'answer': 'synthetic', 'refs': 'sensitive'}, '/refs', 'expected type array; received type string'),
    ('finish', {'answer': 'synthetic', 'refs': [False]}, '/refs/0', 'expected type string; received type boolean'),
    ('finish', {'refs': []}, '/answer', 'required property missing'),
    ('finish', {'answer': '  ', 'refs': []}, '/answer', 'must match schema pattern'),
    ('search', {'queries': 'sensitive'}, '/queries', 'expected type array; received type string'),
])
def test_real_field_and_rule(name, value, path, expected):
    msg = message(name, value)
    assert json.dumps(path) in msg and expected in msg
    assert 'sensitive' not in msg and len(msg) <= MAX_MESSAGE
    if name == 'search':
        assert '/answer' not in msg


def test_conflicting_branches_never_choose_intent():
    msg = message('finish', {'answer': 'secret', 'refs': [], 'abstain': True, 'reason': 'secret'})
    assert 'branch conflict' in msg and 'secret' not in msg
    assert 'delete' not in msg and 'omit' not in msg
    assert 'branch ambiguous' in message('finish', {})


def test_const_discriminator_and_nested_anyof():
    schema = {'oneOf': [
        {'type': 'object', 'additionalProperties': False, 'properties': {'op': {'const': 'x'},
         'payload': {'anyOf': [{'type': 'array', 'items': {'type': 'string'}}, {'type': 'object'}]}},
         'required': ['op', 'payload']},
        {'type': 'object', 'additionalProperties': False, 'properties': {'op': {'const': 'y'}}, 'required': ['op']}]}
    error = next(Draft202012Validator(schema).iter_errors({'op': 'x', 'payload': [False]}))
    msg = format_validation_error('synthetic', error)
    assert '"/payload/0"' in msg and 'received type boolean' in msg


def test_open_object_branches_remain_ambiguous():
    schema = {'oneOf': [{'type': 'object', 'properties': {'left': {'type': 'string'}}, 'required': ['left']},
                        {'type': 'object', 'properties': {'right': {'type': 'string'}}, 'required': ['right']}]}
    error = next(Draft202012Validator(schema).iter_errors({'left': False}))
    assert 'branch ambiguous' in format_validation_error('synthetic', error)


def test_overlapping_oneof_is_not_missing_type():
    error = next(Draft202012Validator({'oneOf': [{'type': 'string'}, {'type': 'string'}]}).iter_errors('secret'))
    msg = format_validation_error('synthetic', error)
    assert 'multiple matching alternatives' in msg and 'secret' not in msg


@pytest.mark.parametrize('key', ['a/b~c', 'line\nname', 'x' * 10000])
def test_pointer_escaping_and_bounds(key):
    error = next(Draft202012Validator({'type': 'object', 'additionalProperties': {'type': 'string'}}).iter_errors({key: False}))
    msg = format_validation_error('synthetic', error)
    assert len(msg) <= MAX_MESSAGE and '\n' not in msg
    match = re.search(r'pointer ("(?:\\.|[^"\\])*")', msg)
    ptr = json.loads(match[1]); assert ptr == '' or ptr.startswith('/')
    assert not re.search(r'~(?![01])', ptr)
    if len(key) < 100:
        assert ptr == '/' + key.replace('~', '~0').replace('/', '~1')
    else:
        assert 'ancestor' in msg and 'path omitted' in msg


def test_long_secret_and_nested_error_budget():
    secret = 'DO_NOT_ECHO_' * 20000
    msg = message('finish', {'answer': secret, 'refs': []})
    assert len(msg) <= MAX_MESSAGE and 'DO_NOT_ECHO' not in msg
    schema = {'anyOf': [{'type': 'string'}, {'type': 'object'}]}
    for _ in range(12):
        schema = {'anyOf': [schema, {'type': 'string'}]}
    error = next(Draft202012Validator(schema).iter_errors(False))
    assert len(format_validation_error('synthetic', error)) <= MAX_MESSAGE


@pytest.mark.parametrize('raw,code', [
    ('{"answer":"a","answer":"b","refs":[]}', 'duplicate_key'),
    ('{"answer":NaN,"refs":[]}', 'invalid_json'),
    ('{"answer":Infinity,"refs":[]}', 'invalid_json'),
    ('{"answer":', 'invalid_json'),
])
def test_original_parser_path(raw, code):
    for mode in ('legacy', 'field'):
        response = native(('finish', {'abstain': True, 'reason': 'placeholder'}))
        response['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = raw
        h = Harness('Synthetic parsing test', smoke_corpus(), config=Config(max_model_calls=2), validation_feedback=mode)
        try:
            h._step(ScriptedModel([response]))
            event = next(e['payload'] for e in h.archive.events() if e['kind'] == 'action_result')
            assert event['result']['code'] == code and event['executed'] is False
            assert event['arguments'] == raw and h.terminal is None
        finally:
            h.close()


@pytest.mark.parametrize('mode', ['legacy', 'field'])
def test_schema_valid_source_still_rejected(mode):
    h = Harness('Synthetic source boundary', smoke_corpus(), config=Config(max_model_calls=2), validation_feedback=mode)
    try:
        args = {'answer': 'synthetic', 'refs': ['e9']}
        validate('finish', args, feedback=mode)
        h._step(ScriptedModel([native(('finish', args))]))
        result = next(e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result')
        assert result['code'] == 'unreceived_reference' and h.terminal is None
    finally:
        h.close()


@pytest.mark.parametrize('answer', ['47', '  "47"\n'])
def test_scripted_http_roundtrip_preserves_id_and_message(answer):
    """SCRIPTED: explicit synthetic next response, no claim of model self-repair."""
    replies = [native(('search', {'queries': ['Synthetic instrument count'], 'top_k': 1})),
               native(('read', {'ref': 'd1'})), native(('finish', {'answer': 47, 'refs': ['e1']})),
               native(('finish', {'answer': answer, 'refs': ['e1']}))]
    for index, response in enumerate(replies):
        response['choices'][0]['message']['tool_calls'][0]['id'] = f'scripted_round_{index + 1}'
    wrong = replies[2]['choices'][0]['message']['tool_calls'][0]
    received = []; queue = deepcopy(replies)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200); self.end_headers(); self.wfile.write(canonical(queue.pop(0)).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    corpus = LocalCorpus([{'docid': 'synthetic-count', 'title': 'Synthetic instrument count',
                           'content': 'Synthetic archive: the instrument count was 47.'}])
    h = Harness('SCRIPTED: what was the instrument count?', corpus,
                config=Config(max_model_calls=6), validation_feedback='field')
    model = OpenAIModel(f'http://127.0.0.1:{server.server_port}/v1', 'fixture', revision='SCRIPTED',
        http=HTTP(allow_network=True, opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))))
    try:
        assert h.run(model)['outcome'] == 'submitted'
        assert h.terminal['answer'] == answer and h.terminal['refs'] == ['e1']
        assert h.model_calls == 4 and not queue
        final = received[-1]
        receipt = next(loads(m['content']) for m in final['messages'] if m.get('tool_call_id') == wrong['id'])
        feedback = loads(final['messages'][-1]['content'].split('\n', 1)[1])['feedback']
        assert receipt['message'] == feedback['message'] and '/answer' in receipt['message']
        assert {k: receipt[k] for k in ('code', 'executed', 'action_slot_charged', 'blocks_finish')} == {
            'code': 'arguments_invalid', 'executed': False, 'action_slot_charged': True, 'blocks_finish': True}
        assert feedback['no_automatic_parameter_repair'] is True
        actual = next(c for m in final['messages'] for c in m.get('tool_calls', []) if c['id'] == wrong['id'])
        assert actual == wrong
        assert h.config.max_model_calls == 6 and final['tools'] != []
    finally:
        h.close(); server.shutdown(); server.server_close(); thread.join()


def test_default_remains_legacy_and_switch_is_explicit():
    with pytest.raises(ContractError) as exc:
        validate('finish', {'answer': 47, 'refs': []})
    assert str(exc.value) == 'finish: invalid fields near []; follow the supplied schema'
    assert 'validation_feedback' not in Config().to_dict()
    with pytest.raises(ValueError):
        Harness('Synthetic', smoke_corpus(), validation_feedback='unknown')


def test_acceptance_matrix():
    result = acceptance_matrix()
    assert result['same_acceptance_set'] and result['cases'] > 1000
