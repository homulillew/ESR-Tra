"""Reference selection preserves raw evidence, scope and model verdicts."""
from copy import deepcopy
import json
import pytest
from esr_harness.audit import ModelAuditor, status
from esr_harness.audit_spans import source_span_packet, expand_references
from esr_harness.client import UsageBudget
from esr_harness.protocol import HarnessError
from .helpers import env, opened, update
from .test_strong_api_recovery import client, response


def test_source_passages_partition_every_raw_character_without_mutation():
    views=[{'observation_id':'o1','docid':'synthetic','raw_parts':['First sentence.\n'+'A long line with spaces '*50+'end.','A separate raw window.'],
            'spans':[[0,1170],[2000,2022]]}]
    before=deepcopy(views)
    observations,refs=source_span_packet(views,100)
    assert source_span_packet(views,100)==(observations,refs)
    for i,part in enumerate(views[0]['raw_parts']):
        pieces=[r for r in refs.values() if r['raw_part_index']==i]
        assert ''.join(r['quote'] for r in pieces)==part
        assert all(r['quote']==part[r['start']:r['end']] and len(r['quote'])<=100 for r in pieces)
    assert views==before
    assert [p['text'] for p in observations[0]['passages']]==[r['quote'] for r in refs.values()]


def fixture_report(h):
    return h.auditor.audit(h.question,h.audit_packet(),list(h.observations.values()))


def test_native_audit_references_expand_to_exact_source_and_keep_wire_receipt(tmp_path):
    h=env();update(h,opened(h));views=list(h.observations.values())
    _,refs=source_span_packet(views)
    report=fixture_report(h);wire=deepcopy(report)
    wire['claims'][0]['quotes']=[{'span_id':next(iter(refs))}]
    r=response();r['stop_reason']='tool_use';r['content']=[{'type':'tool_use','id':'a','name':'audit_report','input':wire}]
    c=client(tmp_path,[r]);c.budget=UsageBudget(2000)
    actual=ModelAuditor(c,citation_mode='source_spans').audit(h.question,h.audit_packet(),views)
    assert actual==report and set(wire['claims'][0]['quotes'][0])=={'span_id'}
    body=c.transport.requests[0];payload=json.loads(body['messages'][0]['content'])
    assert 'text' not in payload['observations'][0]  # each raw passage is sent once
    assert payload['observations'][0]['passages'][0]['text']==views[0]['raw_parts'][0]
    schema=body['tools'][0]['input_schema']
    assert schema['properties']['claims']['items']['properties']['quotes']['items']['properties']['span_id']['enum']==list(refs)
    events=[e for e in c.ledger.events() if e['type']=='audit_citation_resolution']
    assert len(events)==1 and events[0]['proposed_report']==wire and events[0]['expanded_report']==report
    assert events[0]['verdict_modified'] is False


class ReplyClient:
    identity={'fixture':True}
    def __init__(self,replies):self.replies=iter(replies);self.messages=[]
    def complete(self,messages,**kwargs):
        self.messages.append(deepcopy(messages));return json.dumps(next(self.replies))


def test_unknown_reference_gets_one_repair_with_original_evidence():
    h=env();update(h,opened(h));views=list(h.observations.values())
    _,refs=source_span_packet(views);good=fixture_report(h)
    good['claims'][0]['quotes']=[{'span_id':next(iter(refs))}]
    bad=deepcopy(good);bad['claims'][0]['quotes']=[{'span_id':'invented'}]
    with pytest.raises(HarnessError,match='Unknown source span'):expand_references(bad,refs)
    c=ReplyClient([bad,good]);ModelAuditor(c,citation_mode='source_spans').audit(h.question,h.audit_packet(),views)
    assert len(c.messages)==2 and c.messages[1][:2]==c.messages[0]
    assert 'invented' in c.messages[1][-1]['content']


def test_valid_reference_from_another_claim_scope_still_fails():
    h=env();update(h,opened(h));opened(h,'d2');views=list(h.observations.values())
    _,refs=source_span_packet(views);wire=fixture_report(h)
    wrong=next(sid for sid,ref in refs.items() if ref['observation_id']=='o2')
    wire['claims'][0]['quotes']=[{'span_id':wrong}]
    c=ReplyClient([wire,wire])
    with pytest.raises(HarnessError,match='outside this claim'):
        ModelAuditor(c,citation_mode='source_spans').audit(h.question,h.audit_packet(),views)
    assert len(c.messages)==2


def test_reference_resolution_never_promotes_unknown_verdict():
    h=env();update(h,opened(h));wire=fixture_report(h)
    for row in [wire['target'],wire['coverage'],*wire['claims']]:
        row.update(status='unknown',need='An additional relation remains unsupported')
    wire['claims'][0]['quotes']=[]
    c=ReplyClient([wire]);report=ModelAuditor(c,citation_mode='source_spans').audit(h.question,h.audit_packet(),list(h.observations.values()))
    assert report==wire and status(report)=='unknown'
