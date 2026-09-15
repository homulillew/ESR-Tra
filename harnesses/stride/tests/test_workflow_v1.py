"""Gap workflow mechanism tests; scripted policies are not model-quality evidence."""
import json
import pytest

from stride_search import Config, Harness
from stride_search.context import build
from stride_search.contract import INTEGER_ANSWER, ContractError
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.goal_read import select_window
from stride_search.providers import ByteCounter
from stride_search.workflow_contract import WorkflowConfig, SECTIONS, TOOL_PARTS, toolset, validate_call

FULL = WorkflowConfig.profile('full')
SEARCH = ('search', {'queries':['Lumen']})
READ = ('read', {'ref':'d1'})
FINISH = ('finish', {'answer':'Ada Rowan','refs':['e1']})


def make(workflow=FULL, config=None):
    return Harness('Who was the first director of Lumen Observatory?', smoke_corpus(),
                   config=config or Config(max_model_calls=12), workflow=workflow,
                   answer_contract=INTEGER_ANSWER)


def step(h, *calls):
    before = [e for e in h.archive.events() if e['kind']=='action_result']
    h._step(ScriptedModel([native(*calls)]))
    after = [e['payload'] for e in h.archive.events() if e['kind']=='action_result']
    return after[len(before):]


def test_six_part_descriptions_and_full_tools():
    items = toolset(FULL, notes_enabled=True, final=False, query_limit=3, answer_contract=INTEGER_ANSWER)
    assert [x['function']['name'] for x in items][-1] == 'update_gap'
    for item in items:
        desc=item['function']['description']
        assert all(desc.count(section+':') == 1 for section in SECTIONS)


def test_legacy_toolset_has_no_gap():
    items = toolset(WorkflowConfig(), notes_enabled=True, final=False, query_limit=3, answer_contract='legacy')
    assert 'update_gap' not in [x['function']['name'] for x in items]


def test_short_path_still_three_decisions():
    h=make()
    try:
        result=h.run(ScriptedModel([native(SEARCH),native(READ),native(FINISH)]))
        assert result['outcome']=='submitted' and h.model_calls==3 and h.backend_calls==2
    finally:h.close()


def test_search_card_distinguishes_navigation_from_read():
    h=make()
    try:
        row=step(h,SEARCH)[0]['result']['results'][0]['hits'][0]
        assert row['navigation_seen'] is False and row['raw_ranges_delivered']==[]
        assert row['read_action']=={'ref':'d1'} and not h.exposed
    finally:h.close()


def test_exact_repeat_compacts_and_replay_restores():
    h=make()
    try:
        a=step(h,SEARCH)[0]['result']['results'][0]
        b=step(h,SEARCH)[0]['result']['results'][0]
        assert b['view']=='reuse' and b['hits'][0]['snippet']==''
        c=step(h,('search',{'queries':['Lumen'],'replay':True}))[0]['result']['results'][0]
        assert c['view']=='full' and c['hits'][0]['snippet']==a['hits'][0]['snippet']
        assert h.backend_calls==1
    finally:h.close()


def test_same_response_repeat_not_treated_as_received():
    h=make()
    try:
        out=step(h,SEARCH,SEARCH,FINISH)
        assert out[0]['result']['results'][0]['view']=='full'
        assert out[1]['result']['results'][0]['view']=='full'
        assert out[-1]['result']['code']=='unreceived_reference'
    finally:h.close()


def test_bounded_repeat_ends_honestly():
    h=make()
    try:
        result=h.run(ScriptedModel([native(SEARCH) for _ in range(10)]))
        assert result['outcome']=='stalled_no_submission' and result['answer']==''
        assert h.model_calls==6 and h.backend_calls==1
    finally:h.close()


def test_recovery_can_switch_to_read_and_finish():
    h=make()
    try:
        result=h.run(ScriptedModel([native(SEARCH),native(SEARCH),native(SEARCH),native(READ),native(FINISH)]))
        assert result['outcome']=='submitted' and h.model_calls==5
    finally:h.close()


def test_observe_mode_never_blocks_search():
    h=make(WorkflowConfig(enabled=True,repetition='observe'))
    try:
        for _ in range(7):step(h,SEARCH)
        assert h.terminal is None and h.workflow.stage()=='warning'
    finally:h.close()


def test_gap_is_fallible_and_source_scoped():
    h=make()
    gap={'subject':'Lumen','question':'Who directed it first?','kind':'relation','status':'open',
         'evidence_refs':[],'navigation_refs':['d1'],'next_action':'read','basis':'Candidate page found; raw text needed.'}
    try:
        step(h,SEARCH)
        row=step(h,('update_gap',gap))[0]['result']['current']
        assert row['kind_of_record']=='agent_judgment_not_verified'
        bad={**gap,'status':'supported','evidence_refs':[]}
        assert step(h,('update_gap',bad))[0]['result']['code']=='gap_basis'
    finally:h.close()


@pytest.mark.parametrize('args,ok', [({'ref':'d1'},True),({'ref':'d1','goal':'director'},True),
    ({'ref':'d1','goal':'director','start':0},False),({'ref':'e1','goal':'director'},False)])
def test_read_modes(args,ok):
    if ok: validate_call(FULL,'read',args,feedback='field',answer_contract=INTEGER_ANSWER)
    else:
        with pytest.raises(ContractError): validate_call(FULL,'read',args,feedback='field',answer_contract=INTEGER_ANSWER)


def test_goal_read_is_contiguous_original_text():
    text='Intro.\n\n'+('Filler. '*400)+'\n\nDR NERA QUILL\n\nNera founded the Meridian lab in 1987.'
    s=select_window(text,'Meridian founded',900)
    assert s['matched'] and 'Meridian' in text[s['start']:s['end']]
    assert s['selection_is_semantic_support'] is False


def test_goal_no_match_returns_no_evidence():
    h=make()
    try:
        step(h,SEARCH)
        row=step(h,('read',{'ref':'d1','goal':'absentzzz'}))[0]['result']
        assert row['ok'] and row['matched'] is False and 'evidence' not in row
    finally:h.close()


@pytest.mark.parametrize('text,goal,needle', [('İstanbul is the location.','İstanbul','İstanbul'),('Die Straße hat einen Namen.','STRASSE','Straße')])
def test_goal_unicode_offsets(text,goal,needle):
    s=select_window(text,goal,100)
    assert s['matched'] and needle in text[s['start']:s['end']]


def test_gap_archive_object_is_verified(tmp_path):
    path=tmp_path/'episode.sqlite'; h=Harness('Q',smoke_corpus(),path=path,workflow=FULL)
    gap={'subject':'Lumen','question':'Who?','kind':'locate','status':'open','evidence_refs':[],
         'navigation_refs':[],'next_action':'search','basis':'Need source.'}
    try:
        step(h,('update_gap',gap)); h.archive.verify()
    finally:h.close()


def test_integer_answer_contract_survives_workflow():
    h=make()
    try:
        step(h,SEARCH);step(h,READ);step(h,('finish',{'answer':21,'refs':['e1']}))
        assert h.terminal['answer']=='21'
    finally:h.close()


def test_full_schema_is_larger_but_no_extra_short_path_round():
    legacy=make(WorkflowConfig()); full=make(FULL)
    try:
        a=build(legacy,ScriptedModel([]),ByteCounter(),final=False,output_limit=100)['wire']
        b=build(full,ScriptedModel([]),ByteCounter(),final=False,output_limit=100)['wire']
        assert len(json.dumps(b)) > len(json.dumps(a))
    finally:legacy.close();full.close()
