"""Explicit temporary stage changes one SYSTEM field, without action rewriting."""
from copy import deepcopy
from dataclasses import replace
import pytest
from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.contract import digest, text_hash
from stride_search.fixtures import ScriptedModel, smoke_corpus, native
from stride_search.providers import AnthropicModel, HTTP
from stride_search.read_only import EXPLICIT_INSTRUCTION, explicit_identity
from test_middle_history import step, preview, READ, STOP
from test_relation_review import seed
from test_read_only import names


def make(protocol='read-only-explicit-v1'):
    return Harness('Who directed Lumen?',smoke_corpus(),decision_protocol=protocol,config=Config(max_model_calls=12))


def test_only_one_system_field_differs_and_next_request_restores():
    old,new=make('read-only-once-v1'),make()
    try:
        for q in ['Lumen','director','Observatory']:
            assert preview(old)['wire']==preview(new)['wire']
            for h in [old,new]:step(h,('search',{'queries':[q]}))
        a,b=preview(old),preview(new);original=deepcopy(new.groups);seq=new.archive.seq
        assert b==preview(new) and new.archive.seq==seq and new.read_only.used==0
        changed=deepcopy(a['wire']);changed['messages'][0]['content']+=EXPLICIT_INSTRUCTION
        assert changed==b['wire'] and names(b['wire'])=={'read'}
        assert b['read_only_audit']['system_sha256']==text_hash(b['wire']['messages'][0]['content'])
        assert b['capacity']==new.counter(b['wire'])
        for h in [old,new]:step(h,READ)
        assert preview(old)['wire']==preview(new)['wire'] and new.groups[:-1]==original
        assert EXPLICIT_INSTRUCTION not in str(preview(new,final=True)['wire'])
    finally:old.close();new.close()


def test_capacity_cancellation_removes_instruction_and_filter():
    h=make()
    try:
        seed(h);h.groups=[];seq=h.archive.seq
        def counter(w):return h.config.context_limit if EXPLICIT_INSTRUCTION in w['messages'][0]['content'] else 1
        p=preview(h,counter=counter)
        assert p['compacted'] and p['read_only_audit'] is None and names(p['wire'])!={'read'}
        assert EXPLICIT_INSTRUCTION not in str(p['wire']) and h.read_only.used==0 and h.archive.seq==seq
    finally:h.close()


def test_real_capacity_includes_explicit_system():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups);p=preview(h)
        h.config=replace(h.config,context_limit=p['capacity']+h.config.response_reserve)
        assert preview(h)['wire']==p['wire'] and h.groups==before
    finally:h.close()


def test_anthropic_actual_system_and_tools():
    old,new=make('read-only-once-v1'),make()
    model=AnthropicModel('http://fixture.invalid','fixture',revision='fixture',http=HTTP())
    try:
        for h in [old,new]:seed(h)
        a,b=preview(old,model=model)['wire'],preview(new,model=model)['wire']
        a['system']+=EXPLICIT_INSTRUCTION
        assert a==b and names(b)=={'read'}
    finally:old.close();new.close()


def test_failed_send_consumes_with_system_audit():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups)
        class Fail(ScriptedModel):
            def send(self,wire):
                e=list(h.archive.events())[-1]['payload']
                assert h.read_only.used==1 and e['system_sha256']==text_hash(wire['messages'][0]['content'])
                assert e['identity']==explicit_identity()
                raise TimeoutError('fixture')
        h._step(Fail([]))
        assert h.groups==before and h.model_calls==4 and h.terminal['outcome']=='model_transport'
        events=list(h.archive.events())
        failure=[e['payload'] for e in events if e['kind']=='model_failure'][-1]
        assert failure['exception_type']=='TimeoutError'
        audit=[e['payload'] for e in events if e['kind']=='read_only_once'][-1]
        assert audit['identity']==explicit_identity() and audit['system_sha256']
    finally:h.close()


def test_cli_full_sqlite_and_restricted_error(tmp_path,monkeypatch):
    q=tmp_path/'q.txt';q.write_text('Who directed Lumen?',encoding='utf8');db=tmp_path/'explicit.sqlite'
    replies=[native(('search',{'queries':[s]})) for s in ['Lumen','director','Observatory']]
    replies += [native(('search',{'queries':['new']})),native(READ),native(('finish',{'answer':'Ada Rowan','refs':['e1']}))]
    model=ScriptedModel(replies);monkeypatch.setattr(cli,'_model',lambda args,http:model)
    monkeypatch.setattr(cli,'_retriever',lambda args,http:smoke_corpus())
    flags=['run','--allow-network','--accept-counter-estimate','--base-url','http://fixture.invalid','--model','fixture',
           '--model-revision','fixture','--retrieval-url','http://fixture.invalid','--index-id','fixture','--counter','utf8_bytes',
           '--question-file',str(q),'--db',str(db),'--max-model-calls','8','--context-limit','96000','--response-reserve','4096',
           '--workflow-profile','full','--decision-protocol','read-only-explicit-v1']
    result=cli.execute(cli.parser().parse_args(flags))
    assert result['terminal']['outcome']=='submitted' and len(model.requests)==6
    assert names(model.requests[3])=={'read'} and EXPLICIT_INSTRUCTION not in str(model.requests[4])
    a=Archive(db,readonly=True)
    try:
        events=list(a.events());e=[e['payload'] for e in events if e['kind']=='read_only_once']
        assert len(e)==1 and e[0]['identity']==explicit_identity()
        assert e[0]['wire_sha256']==digest(model.requests[3])
        r=next(e['payload'] for e in events if e['kind']=='action_result' and e['payload']['round']==4)
        assert r['tool']=='search' and r['result']['code']=='read_only_tool_only' and not r['executed']
        request=next(e['payload'] for e in events if e['kind']=='model_request' and e['payload']['round']==4)
        assert a.load_request(request['request'])==model.requests[3] and a.verify()
    finally:a.db.close()
