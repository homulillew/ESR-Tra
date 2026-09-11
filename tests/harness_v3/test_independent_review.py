"""Independent counterexamples for failure, reaction and sampling boundaries."""
from copy import deepcopy

import pytest

from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import MemoryRetriever, run_episode
from esr_harness_v3.protocol import canonical
from esr_harness_v3.training import training_export
from .conftest import AuditFixture, DOCS, send


class RepeatingPolicy:
    identity = {'kind': 'fixture-policy', 'model': 'fixed'}

    def __init__(self, name, args, finish_reason='tool_calls'):
        self.name, self.args, self.calls = name, args, 0
        self.finish_reason = finish_reason

    def complete(self, request):
        self.calls += 1
        return {'model': 'fixed', 'choices': [{'finish_reason': self.finish_reason, 'message': {
            'role': 'assistant', 'tool_calls': [{'id': f'call_{self.calls}', 'type': 'function',
                'function': {'name': self.name, 'arguments': canonical(self.args)}}]}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3}}


@pytest.mark.parametrize('suffix,limit', [(False, 1), (True, 2)])
def test_audit_requires_an_action_for_the_reserved_reaction(suffix, limit):
    auditor = AuditFixture()
    h = Harness('Q', MemoryRetriever(DOCS), auditor=auditor,
                config=Config(max_actions=limit, max_model_calls=8))
    try:
        actions = [('verify_answer', {'answer': 'A', 'refs': []})]
        if suffix:
            actions.append(('submit_answer', {'answer': 'A'}))
        result = send(h, actions)
        assert not auditor.calls, 'A paid audit must not be stranded by the action cap'
        assert result[0]['code'] == 'audit_action_budget'
    finally:
        h.close()


def test_audit_with_one_reaction_action_can_submit():
    auditor = AuditFixture()
    h = Harness('Q', MemoryRetriever(DOCS), auditor=auditor,
                config=Config(max_actions=2, max_model_calls=8))
    try:
        assert send(h, ('verify_answer', {'answer': 'A', 'refs': []}))[0]['ok']
        assert send(h, ('submit_answer', {'answer': 'A'}))[0]['ok']
        assert h.terminal['audit_status'] == 'supported'
    finally:
        h.close()


@pytest.mark.parametrize('choices', [[], [None], [{'message': None}]])
def test_malformed_audit_envelope_has_bounded_repair(choices):
    class BadAudit:
        identity = {'kind': 'fixture-malformed-envelope'}
        calls = 0

        def complete(self, request):
            self.calls += 1
            return {'choices': deepcopy(choices), 'usage': {'prompt_tokens': 10, 'completion_tokens': 3}}

    auditor = BadAudit()
    h = Harness('Q', MemoryRetriever(DOCS), auditor=auditor)
    try:
        result = send(h, ('verify_answer', {'answer': 'A', 'refs': []}))[0]
        assert result['code'] == 'audit_protocol_error'
        assert auditor.calls == 2 and not h.state['audits'] and not h.state['conflicts']
        assert h.state['usage']['input_tokens'] == 20
    finally:
        h.close()


def test_audit_service_failure_stops_further_policy_and_audit_requests():
    class FailedAudit:
        identity = {'kind': 'fixture-service-failure'}
        calls = 0

        def complete(self, request):
            self.calls += 1
            raise ContractError('service_error', 'HTTP 401')

    auditor = FailedAudit()
    policy = RepeatingPolicy('verify_answer', {'answer': 'A', 'refs': []})
    h = Harness('Q', MemoryRetriever(DOCS), auditor=auditor, config=Config(max_model_calls=8))
    try:
        terminal = run_episode(h, policy)
        assert auditor.calls == policy.calls == 1
        assert terminal['outcome'] == 'audit_service_error' and terminal['answer'] == ''
        assert h.state['usage']['unknown_calls'] == 1
    finally:
        h.close()


def test_backend_failure_stops_related_online_episode():
    class FailedRetriever(MemoryRetriever):
        def search(self, query, top_k):
            raise ContractError('service_error', 'HTTP 403')

    policy = RepeatingPolicy('search', {'query': 'test'})
    h = Harness('Q', FailedRetriever(DOCS), config=Config(max_model_calls=3))
    try:
        terminal = run_episode(h, policy)
        assert policy.calls == h.state['backend_calls'] == 1
        assert terminal['outcome'] == 'service_error'
    finally:
        h.close()


@pytest.mark.parametrize('reason', ['length', 'content_filter'])
def test_incomplete_provider_response_cannot_submit(reason):
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(max_model_calls=1))
    try:
        terminal = run_episode(h, RepeatingPolicy('submit_answer', {'answer': 'A'}, reason))
        assert terminal['answer'] == '' and terminal['outcome'] == 'incomplete_response'
        assert h.state['actions'] == 0 and h.state['usage']['output_tokens'] == 3
    finally:
        h.close()


def test_empty_action_spans_do_not_make_protocol_failure_rl_ready():
    h = Harness('Q', MemoryRetriever(DOCS))
    try:
        decision = h.begin()
        h.respond(decision, {'role': 'assistant', 'content': 'No action'}, sampling={
            'token_ids': [1], 'old_logprobs': [-1.0], 'action_spans': [], 'tokenizer_identity': 'fixture'})
        assert training_export(h.ledger)['rl_ready'] is False
        with pytest.raises(ContractError, match='Exact sampler'):
            training_export(h.ledger, require_rl=True)
    finally:
        h.close()


def test_resume_rejects_changed_auditor_identity(tmp_path):
    path = tmp_path / 'resume.sqlite'
    first = AuditFixture()
    h = Harness('Q', MemoryRetriever(DOCS), ledger=path, auditor=first)
    h.close()
    other = AuditFixture()
    other.identity = {'kind': 'different-provider'}
    with pytest.raises(ContractError, match='must match'):
        h = Harness('Q', MemoryRetriever(DOCS), ledger=path, auditor=other, resume=True)
        h.close()
