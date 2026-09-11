"""The harness must preserve the answer string supplied by the policy."""
import pytest
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config
from esr_harness.runner import replay
from .helpers import env, opened, update


@pytest.mark.parametrize('mode', ['baseline', 'esr'])
def test_answer_whitespace_survives_submission_and_replay(tmp_path, mode):
    path = tmp_path / 'literal.sqlite'
    h = env(config=Config(mode=mode, audit_mode='off'), ledger=Ledger(path))
    answer = ' Taylor\n'
    if mode == 'baseline':
        assert h.execute('finish', {'answer': answer})['ok']
    else:
        assert update(h, opened(h), answer=answer)['ok']
        assert h.state['answer'] == answer
        assert h.execute('submit_answer')['ok']
    assert h.terminal['answer'] == answer
    h.ledger.close()
    restored = replay(path)
    assert restored.terminal['answer'] == answer
    restored.ledger.close()


def test_literal_change_invalidates_audit_without_editing_evidence():
    h = env()
    update(h, opened(h), answer='Taylor')
    h.execute('verify_answer')
    before = h.audit_packet()['claims']
    changed = h.execute('update_state', {'answer': ' Taylor '})
    assert changed['ok'] and changed['changes']['candidate_revision']
    assert h.current_audit is None
    assert h.audit_packet()['claims'] == before


@pytest.mark.parametrize('mode', ['baseline', 'esr'])
def test_blank_answer_remains_invalid(mode):
    h = env(config=Config(mode=mode, audit_mode='off'))
    action = 'finish' if mode == 'baseline' else 'update_state'
    assert not h.execute(action, {'answer': ' \n\t '})['ok']
    assert h.terminal is None
