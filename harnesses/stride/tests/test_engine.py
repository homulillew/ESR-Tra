from copy import deepcopy
from dataclasses import replace
import pytest
from stride_search import Config,Harness
from stride_search.contract import ContractError,canonical
from stride_search.fixtures import ScriptedModel,native,smoke_corpus,smoke_model
from stride_search.providers import LocalCorpus

S=native(('search',{'queries':['Lumen Observatory first director'],'top_k':1}))
R=native(('read',{'ref':'d1'}))
F=native(('finish',{'answer':'Ada Rowan','refs':['e1']}))
A=native(('finish',{'abstain':True,'reason':'not established'}))

def run(responses,config=None,corpus=None):
    h=Harness('Original question?',corpus or smoke_corpus(),config=config or Config(max_model_calls=len(responses)))
    m=ScriptedModel(responses)
    h.run(m)
    return h,m

def results(h):
    return [e['payload'] for e in h.archive.events() if e['kind']=='action_result']

def test_shortest_path_no_note_or_audit():
    h,m=run([S,R,F])
    assert h.terminal['outcome']=='submitted'
    assert h.model_calls==3 and h.backend_calls==2 and h.action_slots==3
    assert not h.notes
    assert [r['tool'] for r in results(h)]==['search','read','finish']
    assert [t['function']['name'] for t in m.requests[-1]['tools']]==['finish']
    assert 'claim' not in h.terminal

def test_exact_answer_and_sources():
    answer='  "Ada Rowan"\n'
    h,m=run([S,R,native(('finish',{'answer':answer,'refs':['e1']}))])
    assert h.terminal['answer']==answer
    assert h.terminal['semantic_status']=='not_automatically_verified'

@pytest.mark.parametrize('bad',[
    native(('search',{'queries':['Lumen'],'top_k':1}),('read',{'ref':'d1'})),
    native(('read',{'ref':'d1'}),('finish',{'answer':'guess','refs':['e1']})),
])
def test_future_handles_rejected(bad):
    pre=[] if bad['choices'][0]['message']['tool_calls'][0]['function']['name']=='search' else [S]
    h,m=run(pre+[bad,A],Config(max_model_calls=len(pre)+2))
    assert any(r['result'].get('code')=='unreceived_reference' for r in results(h))
    assert h.terminal['outcome']=='abstained'

def test_navigation_is_not_source():
    h,m=run([S,native(('finish',{'answer':'Ada','refs':['d1']})),A])
    assert results(h)[1]['result']['code']=='arguments_invalid'
    assert not h.exposed

def test_no_pending_cleanup_even_with_unused_page():
    h,m=run([native(('search',{'queries':['Lumen'],'top_k':2})),
             native(('read',{'ref':'d1'}),('read',{'ref':'d2'})),F])
    assert h.terminal['outcome']=='submitted' and len(h.exposed)==2

def test_optional_notes_anchor_then_finish():
    h,m=run([S,R,native(('notes',{'op':'put','key':'bridge','text':'A possible bridge, not proof','anchors':['e1']}),
                              ('finish',{'answer':'Ada Rowan','refs':['e1']}))],Config(max_model_calls=4))
    assert h.terminal['outcome']=='submitted' and h.model_calls==3

def test_note_only_hypothesis_allowed():
    h,m=run([native(('notes',{'op':'put','key':'hypothesis','text':'Maybe X','anchors':[]})),A])
    assert h.notes['hypothesis']['anchors']==[]

def test_note_not_a_finish_source():
    h,m=run([S,R,native(('notes',{'op':'put','key':'n','text':'Guess','anchors':['e1']})),
        native(('finish',{'answer':'Guess','refs':['n']})),A])
    assert h.terminal['outcome']=='abstained'
    assert any(r['result'].get('code')=='arguments_invalid' for r in results(h))

def test_note_noop_delete_history_retained():
    n=native(('notes',{'op':'put','key':'n','text':'Bridge clue','anchors':[]}))
    h,m=run([n,n,native(('notes',{'op':'delete','key':'n'})),native(('recall',{'query':'Bridge'})),A])
    assert len(h.note_history)==1 and not h.notes
    assert results(h)[1]['result']['changed'] is False
    assert results(h)[3]['result']['matches'][0]['active'] is False

def test_no_notes_arm_rejects_actual_call():
    h,m=run([native(('notes',{'op':'put','key':'n','text':'x','anchors':[]})),A],Config(max_model_calls=2,notes_enabled=False))
    assert results(h)[0]['result']['code']=='notes_disabled'

def test_capacity_for_notes_does_not_prevent_finish():
    n=lambda k:native(('notes',{'op':'put','key':k,'text':'x','anchors':[]}))
    h,m=run([S,R,n('a'),n('b'),F],Config(max_model_calls=5,max_notes=1))
    assert h.terminal['outcome']=='submitted'
    assert any(r['result'].get('code')=='notes_capacity' for r in results(h))

def test_find_unicode_offsets_and_read_range():
    text='🙂前置\nTarget: Delta\nend'
    corpus=LocalCorpus([{'docid':'x','title':'Target','content':text}])
    pos=text.index('Target')
    h,m=run([native(('search',{'queries':['Target']})),native(('find',{'ref':'d1','text':'Target'})),
       native(('read',{'ref':'d1','start':pos,'length':13})),native(('finish',{'answer':'Delta','refs':['e1']}))],corpus=corpus)
    rr=results(h)
    assert rr[1]['result']['matches'][0]['start']==pos
    assert rr[2]['result']['evidence']['text']==text[pos:pos+13]
    assert h.backend_calls==2

def test_find_excerpts_not_exposure():
    h,m=run([S,native(('find',{'ref':'d1','text':'Ada'})),native(('finish',{'answer':'Ada','refs':['e1']})),A])
    assert not h.exposed and h.terminal['outcome']=='abstained'

def test_raw_replay_deduplicates_and_no_backend():
    h,m=run([S,R,native(('read',{'ref':'e1'})),F])
    assert h.backend_calls==2
    assert h.archive.db.execute('select count(*) from evidence').fetchone()[0]==1
    assert results(h)[2]['result']['replayed']

def test_search_cache_still_uses_policy_attempt():
    h,m=run([S,S,R,F])
    assert h.model_calls==4 and h.backend_calls==2
    assert results(h)[1]['result']['results'][0]['cached']

def test_frozen_snapshot_not_refetched():
    corpus=smoke_corpus()
    model=ScriptedModel([S,R,native(('read',{'ref':'d1','start':0,'length':20})),F])
    old=model.send
    def send(wire):
        if len(model.requests)==2: corpus.documents['archive-entry']['content']='REPLACED DOCUMENT'
        return old(wire)
    model.send=send
    h=Harness('Q',corpus,config=Config(max_model_calls=4)); h.run(model)
    assert 'REPLACED' not in h.archive.evidence('e2')['text'] and h.backend_calls==2

def test_final_disallows_unconsumable_read():
    h,m=run([S,R,R])
    assert h.terminal['outcome']=='model_budget' and h.backend_calls==2
    assert results(h)[-1]['result']['code']=='final_only'

def test_final_reserve_ablation():
    h,m=run([S,R,R],Config(max_model_calls=3,reserve_finish=False))
    assert results(h)[-1]['result']['ok']
    assert len(m.requests[-1]['tools'])>1

def test_action_reserve_keeps_finish_possible():
    h,m=run([S,R,F],Config(max_model_calls=10,max_actions=3))
    assert h.terminal['outcome']=='submitted' and h.action_slots==3
    assert len(m.requests[-1]['tools'])==1

def test_backend_budget_still_allows_abstention():
    h,m=run([S,R,A],Config(max_model_calls=3,max_backend_calls=1))
    assert h.backend_calls==1 and h.terminal['outcome']=='abstained'

def test_failure_does_not_kill_independent_sibling():
    h,m=run([S,native(('read',{'ref':'d99'}),('read',{'ref':'d1'})),F])
    assert h.terminal['outcome']=='submitted'
    assert results(h)[1]['result']['code']=='unreceived_reference'
    assert results(h)[2]['result']['ok']

def test_failed_prefix_prevents_pregenerated_finish():
    h,m=run([S,R,native(('read',{'ref':'d99'}),('finish',{'answer':'Ada','refs':['e1']})),F])
    assert results(h)[3]['result']['code']=='not_executed'
    assert h.model_calls==4

def test_native_receipts_all_present_and_final_boundary():
    h,m=run([native(('search',{'queries':['Lumen']}),('search',{'queries':['archive']})),R,F])
    first=h.archive.json(h.group_refs[0])
    calls=first['messages'][0]['tool_calls']; receipts=first['messages'][1:]
    assert [c['id'] for c in calls]==[r['tool_call_id'] for r in receipts]
    assert h.terminal['outcome']=='submitted'

def test_large_group_all_rejected_no_truncation():
    h,m=run([native(*[('search',{'queries':[str(i)]}) for i in range(5)]),A])
    assert len(results(h))==6 and h.backend_calls==0
    assert all(r['result']['code']=='batch_limit' for r in results(h)[:5])

def test_duplicate_ids_no_execution():
    bad=native(('search',{'queries':['a']}),('search',{'queries':['b']}))
    bad['choices'][0]['message']['tool_calls'][1]['id']='call_0'
    h,m=run([bad,A]); assert h.backend_calls==0 and len(results(h))==1

@pytest.mark.parametrize('reason',['length','content_filter',None])
def test_incomplete_output_not_executed(reason):
    h,m=run([native(('finish',{'abstain':True,'reason':'x'}),finish_reason=reason)])
    assert h.terminal['outcome']=='incomplete_response' and not results(h)
    assert h.archive.report()['usage_known']['output_tokens']==20

def test_transport_failure_no_retry_no_exposure():
    h,m=run([S,R,ContractError('http_error','429',fatal=True)])
    assert h.terminal['outcome']=='http_error' and len(m.requests)==3 and not h.exposed
    assert h.archive.report()['unknown_usage_calls']==1

def test_partial_usage_preserved():
    h,m=run([native(('finish',{'abstain':True,'reason':'x'}),usage={'prompt_tokens':123})])
    report=h.archive.report()
    assert report['usage_known']['input_tokens']==123 and report['unknown_usage_calls']==1
    assert h.output_charged==h.config.max_output_tokens

def test_unknown_output_conservatively_reserved():
    bad=native(('search',{'queries':['Lumen']}),usage={})
    h,m=run([bad,A],Config(max_model_calls=2,max_total_output_tokens=2048,reserve_finish=False))
    assert h.terminal['outcome']=='output_budget' and h.model_calls==1

def test_configured_literal_guard_not_auto_repair():
    h,m=run([S,R,F,native(('finish',{'answer':'"Ada Rowan"','refs':['e1']}))],
             Config(max_model_calls=4,answer_prefix='"',answer_suffix='"'))
    assert h.terminal['answer']=='"Ada Rowan"'
    assert results(h)[2]['result']['code']=='literal_contract'

def test_default_does_not_infer_format_from_question():
    h,m=run([S,R,F]); assert h.terminal['answer']=='Ada Rowan'

def test_source_requirement_can_only_change_explicit_config():
    f=native(('finish',{'answer':'guess','refs':[]}))
    h,m=run([f],Config(max_model_calls=1)); assert h.terminal['outcome']=='model_budget'
    h,m=run([f],Config(max_model_calls=1,require_sources=False)); assert h.terminal['outcome']=='submitted'

def test_no_free_text_salvage():
    h,m=run([native(content='The answer is Ada')]); assert h.terminal['answer']==''

def test_cannot_run_twice():
    h,m=run([A])
    with pytest.raises(ContractError): h.run(m)

def test_delivery_metric_does_not_count_unacknowledged_request():
    h,m=run([S,R,ContractError('http_error','timeout',fatal=True)])
    assert h.archive.report()['rounds_receiving_new_raw']==0
    h,m=run([S,R,F])
    assert h.archive.report()['rounds_receiving_new_raw']==1
    assert h.archive.report()['final_phase_requests']==1
