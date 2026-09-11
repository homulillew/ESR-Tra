from copy import deepcopy
import pytest
from esr_harness_v3 import Harness, Config
from esr_harness_v3.adapters import MemoryRetriever
from esr_harness_v3.protocol import canonical, parse_json

DOCS = [
    {'docid': 'A', 'title': 'Tournament A', 'content': 'Mira won the 2014 tournament. Her first title was in 2012. ' * 3},
    {'docid': 'B', 'title': 'Tournament B', 'content': 'Orin won the 2015 tournament. Orin was a web designer. ' * 3},
]


class AuditFixture:
    identity = {'kind': 'fixture-auditor-not-a-real-model'}
    def __init__(self, verdicts=('supported',), callback=None):
        self.verdicts, self.callback, self.calls = list(verdicts), callback, []

    def complete(self, request):
        self.calls.append(deepcopy(request))
        payload = parse_json(request['messages'][1]['content'])
        verdict = self.verdicts[min(len(self.calls) - 1, len(self.verdicts) - 1)]
        if self.callback:
            content = self.callback(payload)
        elif verdict == 'malformed':
            content = '{broken'
        else:
            sources = list(payload['raw_sources'])
            report = {'checks': {key: {'verdict': verdict, 'explanation': 'Fixture opinion only.',
                                      'refs': sources[:1] if key not in ('target', 'coverage') or verdict == 'contradicted' else []}
                                 for key in payload['expected_checks']}}
            content = canonical(report)
        return {'choices': [{'message': {'role': 'assistant', 'content': content}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'model': 'fixture'}


def send(h, actions, *, sampling=None):
    if isinstance(actions, tuple):
        actions = [actions]
    d = h.begin()
    msg = {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': f'tool_{d.id}_{i}', 'type': 'function', 'function': {'name': name, 'arguments': canonical(args)}}
        for i, (name, args) in enumerate(actions)]}
    return h.respond(d, msg, sampling=sampling)


def source(h, query='tournament'):
    result = send(h, ('search', {'query': query}))[0]
    assert result['ok']
    result = send(h, ('open_page', {'ref': result['hits'][0]['ref']}))[0]
    assert result['ok']
    return result['observation']['observation']


def add(h, finding='A fact', refs=None, requirement='Fact'):
    result = send(h, ('update_state', {'add': [{'requirement': requirement, 'finding': finding,
                                               'refs': ['this'] if refs is None else refs}]}))[0]
    assert result['ok'], result
    return result['changes']['created'][0]


@pytest.fixture
def h():
    value = Harness('Who won two years before Mira?', MemoryRetriever(DOCS))
    yield value
    value.close()
