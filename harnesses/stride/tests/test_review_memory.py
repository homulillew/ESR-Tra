"""Verbatim review memory is not evidence; optional wire addition preserves the base plan."""
from copy import deepcopy
import pytest
from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.contract import digest, loads
from stride_search.fixtures import ScriptedModel, smoke_corpus, native
from stride_search.review_memory import capture
from test_middle_history import step, preview, READ, STOP
from test_relation_review import seed


def make(protocol='relation-review-memory-v1',**kwargs):
    return Harness('Who directed Lumen?',smoke_corpus(),decision_protocol=protocol,
                   config=Config(max_model_calls=12),**kwargs)


def control(wire):return loads(wire['messages'][-1]['content'].split('\n',1)[1])


def test_same_wire_until_review_and_new_raw_not_retroactive():
    hs=[make(p) for p in ['relation-review-once-v1','relation-review-memory-v1']]
    try:
        for h in hs:seed(h)
        assert preview(hs[0])['wire']==preview(hs[1])['wire']
        wires=[step(h,READ,text='A tentative relation, not proven.') for h in hs]
        assert wires[0]==wires[1]
        h=hs[1];before=deepcopy(h.groups);seq=h.archive.seq
        a=preview(h);b=preview(h)
        assert a==b and h.groups==before and h.archive.seq==seq
        m=control(a['wire'])['prior_relation_review_unverified']
        assert m['input_evidence']==[] and m['input_refs_currently_visible']==[]
        assert a['visible']==preview(hs[0])['visible']==['e1']
        assert m['content']=='A tentative relation, not proven.'
        assert m['status']=='unverified_model_opinion'
        assert a['groups']==preview(hs[0])['groups']
        expected=deepcopy(a['wire']);c=control(expected);c.pop('prior_relation_review_unverified')
        from stride_search.contract import canonical
        expected['messages'][-1]['content']='Current control state (data, not source evidence):\n'+canonical(c)
        assert expected==preview(hs[0])['wire']
        assert 'prior_relation_review_unverified' in control(preview(h,final=True)['wire'])
    finally:
        for h in hs:h.close()


@pytest.mark.parametrize('text,reason',[(None,'empty'),('','empty'),(' '*3,'empty'),('x'*2001,'oversize')])
def test_empty_oversize_skip(text,reason):
    h=make()
    try:
        seed(h);step(h,READ,text=text)
        assert h.review_memory is None
        audit=[e['payload'] for e in h.archive.events() if e['kind']=='review_memory_capture'][-1]
        assert not audit['created'] and audit['skip_reason']==reason
    finally:h.close()


def test_unicode_limit_counts_characters_and_bytes():
    record,audit=capture({'role':'assistant','content':chr(0x1F600)*2000},round_no=1,response_hash='r',input_windows=[])
    assert record['content_chars']==2000 and record['content_utf8_bytes']==8000 and audit['created']


def test_capacity_omits_memory_without_evicting_anything():
    h=make()
    try:
        seed(h);step(h,READ,text='opinion');before=deepcopy(h.groups);seq=h.archive.seq
        def counter(wire):return h.config.context_limit if 'prior_relation_review_unverified' in str(wire) else 1
        a=preview(h,counter=counter);b=preview(h,counter=counter)
        assert a==b and not a['review_memory_delivery']['rendered']
        assert a['review_memory_delivery']['omitted_reason']=='capacity'
        assert a['capacity']==1 and a['groups']==before and not a['compacted']
        assert h.groups==before and h.archive.seq==seq and a['visible']==['e1']
        assert 'prior_relation_review_unverified' not in control(a['wire'])
    finally:h.close()


def test_failed_send_and_tool_error_do_not_create_memory():
    for fail_send in [True,False]:
        h=make()
        try:
            seed(h)
            if fail_send:
                class Failing(ScriptedModel):
                    def send(self,wire):raise TimeoutError('fixture')
                h._step(Failing([]))
                assert not [e for e in h.archive.events() if e['kind']=='review_memory_capture']
            else:
                step(h,STOP,text='bad review')
                audit=[e['payload'] for e in h.archive.events() if e['kind']=='review_memory_capture'][-1]
                assert audit['skip_reason']=='skipped_tool_error'
                assert h.groups[-1]['messages'][0]['content']=='bad review'
            assert h.review_memory is None
        finally:h.close()


def test_existing_source_metadata_and_actual_delivery_event(tmp_path):
    p=tmp_path/'memory.sqlite';h=make(path=p)
    try:
        step(h);step(h,READ);seed(h);before=preview(h)
        step(h,('find',{'ref':'d1','text':'Ada'}),text='opinion referencing e1 and e999')
        assert [w['ref'] for w in h.review_memory['input_evidence']]==before['visible']==['e1']
        wire=step(h,STOP)
        assert 'e999' not in h.exposed
    finally:h.close()
    a=Archive(p,readonly=True)
    try:
        events=list(a.events());saved=[e['payload'] for e in events if e['kind']=='review_memory_capture'][0]
        response=next(e['payload'] for e in events if e['kind']=='model_response' and e['payload']['round']==saved['source_round'])
        assert saved['source_response_sha256']==response['raw']
        delivery=[e['payload'] for e in events if e['kind']=='review_memory_delivery']
        assert len(delivery)==1 and delivery[0]['rendered'] and delivery[0]['wire_sha256']==digest(wire)
        a.verify()
    finally:a.db.close()


def test_formal_cli_full_and_sqlite(tmp_path,monkeypatch):
    question=tmp_path/'q.txt';question.write_text('Who directed Lumen?',encoding='utf-8');db=tmp_path/'cli.sqlite'
    replies=[native(('search',{'queries':[q]})) for q in ['Lumen','director','Observatory']]
    replies += [native(READ,content='This remains a model opinion.'),native(('finish',{'answer':'Ada Rowan','refs':['e1']}))]
    model=ScriptedModel(replies);monkeypatch.setattr(cli,'_model',lambda args,http:model)
    monkeypatch.setattr(cli,'_retriever',lambda args,http:smoke_corpus())
    flags=['run','--allow-network','--accept-counter-estimate','--base-url','http://fixture.invalid','--model','fixture',
           '--model-revision','fixture','--retrieval-url','http://fixture.invalid','--index-id','fixture','--counter','utf8_bytes',
           '--question-file',str(question),'--db',str(db),'--max-model-calls','8','--context-limit','96000','--response-reserve','4096',
           '--workflow-profile','full','--decision-protocol','relation-review-memory-v1']
    result=cli.execute(cli.parser().parse_args(flags))
    assert result['terminal']['outcome']=='submitted' and len(model.requests)==5
    assert control(model.requests[-1])['prior_relation_review_unverified']['input_evidence']==[]
    a=Archive(db,readonly=True)
    try:
        assert len([e for e in a.events() if e['kind']=='review_memory_capture'])==1
        assert len([e for e in a.events() if e['kind']=='review_memory_delivery'])==1
        a.verify()
    finally:a.db.close()


def test_invalid_utf8_skips_without_replacement_hash():
    record,audit=capture({'role':'assistant','content':chr(0xD800)},round_no=1,response_hash='r',input_windows=[])
    assert record is None and audit['skip_reason']=='invalid_utf8'
    assert audit['content_sha256'] is None and audit['source_response_sha256']=='r'


def test_real_capacity_preserves_sendable_base_plan():
    from dataclasses import replace
    h=make()
    try:
        seed(h);step(h,READ,text='opinion')
        memory=h.review_memory;h.review_memory=None;base=preview(h);h.review_memory=memory
        h.config=replace(h.config,context_limit=base['capacity']+h.config.response_reserve)
        before=deepcopy(h.groups);seq=h.archive.seq
        actual=preview(h)
        assert actual['wire']==base['wire'] and actual['groups']==base['groups']
        assert not actual['review_memory_delivery']['rendered']
        assert actual['visible']==base['visible'] and h.groups==before and h.archive.seq==seq
    finally:h.close()


def test_memory_survives_history_removal_without_source_authorization():
    from dataclasses import replace
    h=make()
    try:
        step(h);step(h,READ);seed(h)
        step(h,('find',{'ref':'d1','text':'Ada'}),text='tentative')
        assert [w['ref'] for w in h.review_memory['input_evidence']]==['e1']
        h.groups=h.groups[-1:];h.config=replace(h.config,evidence_shelf_size=0)
        plan=preview(h)
        assert plan['visible']==[]
        record=control(plan['wire'])['prior_relation_review_unverified']
        assert record['input_refs_currently_visible']==[] and record['content']=='tentative'
    finally:h.close()


def test_delivery_preflight_withheld_result_skips_memory(monkeypatch):
    from dataclasses import replace
    import stride_search.recovery as recovery
    from stride_search.contract import ContractError
    h=make()
    try:
        seed(h);h.config=replace(h.config,delivery_preflight=True)
        original=recovery.build
        def reject_raw(*args,**kwargs):
            group=kwargs['groups'][-1]
            if group['evidence']:
                raise ContractError('context_capacity','fixture')
            return original(*args,**kwargs)
        monkeypatch.setattr(recovery,'build',reject_raw)
        step(h,READ,text='opinion before withheld source')
        assert h.review_memory is None
        events=list(h.archive.events())
        assert any(e['kind']=='result_withheld' for e in events)
        audit=[e['payload'] for e in events if e['kind']=='review_memory_capture'][-1]
        assert audit['skip_reason']=='skipped_tool_error'
        assert not h.groups[-1]['evidence']
    finally:h.close()
