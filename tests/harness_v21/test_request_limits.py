import json
from types import SimpleNamespace

import httpx
import pytest

from esr_harness.client import UsageBudget
from esr_harness.engine import Harness
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config, HarnessError
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from esr_harness.runner import run
from esr_harness.views import MemoryRetriever
from .test_strong_api_recovery import Transport, response
from .helpers import env, opened, update


def test_global_checkpoint_counts_unknown_and_all_purposes_after_restart(tmp_path):
    path=tmp_path/'budget.sqlite'
    budget=GlobalBudget(path)
    budget.reserve('policy',10,5)  # Historic unknown request is not reset.
    budget.configure_request_limits(4,3,'First bounded stage')
    budget.reserve('audit',10,5)
    budget.db.close()
    restarted=GlobalBudget(path)
    restarted.reserve('judge',10,5)
    with pytest.raises(HarnessError,match='checkpoint'):
        restarted.reserve('probe',10,5)
    assert restarted.request_status()['used']==3
    restarted.configure_request_limits(4,4,'Reviewed first stage; complete remaining work')
    restarted.reserve('probe',10,5)
    with pytest.raises(HarnessError): restarted.reserve('diagnostic',10,5)
    with pytest.raises(ValueError,match='expand'): restarted.configure_request_limits(5,5,'Disallowed expansion')
    assert restarted.db.execute('SELECT count(*) FROM request_limit_events').fetchone()[0]==2


def test_episode_request_limit_includes_audit_and_unknown_transport_retry(tmp_path):
    ledger=Ledger();ledger.initialize({'fixture':True})
    t=Transport([response(),httpx.ReadTimeout('fixture'),response()])
    b=GlobalBudget(tmp_path/'budget.sqlite')
    c=AnthropicClient(t,UsageBudget(2000),ledger,b,
                      config=RemoteConfig(max_output_tokens=32,max_requests=2,transport_attempts=2))
    c.complete([{'role':'user','content':'fixture'}],purpose='policy')
    with pytest.raises(HarnessError) as error:
        c.complete([{'role':'user','content':'fixture'}],purpose='audit')
    assert error.value.code=='request_budget_exhausted'
    assert len(t.requests)==2 and b.request_status()['used']==2
    assert c.budget.unknown_usage_requests==1
    assert c.request_status()['remaining']==0


@pytest.mark.parametrize('mode',['baseline','esr'])
def test_three_distinct_parse_errors_stop_inside_episode_without_fourth_call(mode):
    h=Harness('Synthetic task',MemoryRetriever([]),config=Config(
        mode=mode,audit_mode='off',max_execution_errors=6,max_consecutive_errors=3))
    replies=iter(['not json A','not json B','not json C'])
    calls=[]
    def complete(*args,**kwargs):
        calls.append(1)
        return next(replies)
    result=run(h,SimpleNamespace(fits=lambda _:True,complete=complete))
    assert len(calls)==3 and result['terminal']['outcome']=='execution_error_limit'
    assert result['terminal']['answer']==''
    stop=[e for e in h.ledger.events() if e['type']=='execution_stop']
    assert stop[0]['reason']=='consecutive_execution_errors'


def test_valid_action_between_errors_allows_recovery_without_forced_answer():
    h=Harness('Synthetic task',MemoryRetriever([]),config=Config(
        mode='baseline',audit_mode='off',max_execution_errors=6,max_consecutive_errors=3))
    replies=iter(['bad','bad',json.dumps({'action':'search','arguments':{'query':'fixture'}}),
                  'bad',json.dumps({'action':'finish','arguments':{'answer':'fixture answer'}})])
    result=run(h,SimpleNamespace(fits=lambda _:True,complete=lambda *a,**kw:next(replies)))
    assert result['terminal']['outcome']=='submitted' and result['invalid_actions']==3


def test_six_separated_execution_errors_stop_inside_episode():
    h=Harness('Synthetic task',MemoryRetriever([]),config=Config(
        mode='baseline',audit_mode='off',max_execution_errors=6,max_consecutive_errors=3))
    replies=iter(sum(([json.dumps({'action':'search','arguments':{'query':f'fixture {i}'}}),'bad'] for i in range(6)),[]))
    result=run(h,SimpleNamespace(fits=lambda _:True,complete=lambda *a,**kw:next(replies)))
    assert result['terminal']['outcome']=='execution_error_limit'
    assert result['invalid_actions']==6 and result['attempts']==12


@pytest.mark.parametrize('code',['request_budget_exhausted','service_error'])
def test_auditor_resource_failure_ends_episode_without_another_policy_call(code):
    h=env(config=Config(audit_mode='soft',max_execution_errors=6,max_consecutive_errors=3))
    opened(h); assert update(h)['ok']
    def audit(*args,**kwargs):raise HarnessError(code,'fixture resource stop')
    h.auditor=SimpleNamespace(audit=audit,identity=h.auditor.identity)
    calls=[]
    def complete(*args,**kwargs):
        calls.append(1)
        return json.dumps({'action':'verify_answer','arguments':{}})
    result=run(h,SimpleNamespace(fits=lambda _:True,complete=complete))
    assert result['terminal']['outcome']==code and len(calls)==1
    assert result['terminal']['answer']==''


def test_two_failed_audits_stop_before_third_verification():
    h=env(config=Config(audit_mode='soft',max_execution_errors=6,max_consecutive_errors=3))
    opened(h); assert update(h)['ok']
    def audit(*args,**kwargs):raise HarnessError('audit_protocol_error','fixture bad quotes')
    h.auditor=SimpleNamespace(audit=audit,identity=h.auditor.identity)
    calls=[]
    def complete(*args,**kwargs):
        calls.append(1)
        return json.dumps({'action':'verify_answer','arguments':{}})
    result=run(h,SimpleNamespace(fits=lambda _:True,complete=complete))
    assert result['terminal']['outcome']=='execution_error_limit' and len(calls)==2
