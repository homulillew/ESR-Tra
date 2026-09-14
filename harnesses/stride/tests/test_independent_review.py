"""Adversarial review tests, added after the initial green suite."""
import sqlite3
from pathlib import Path
import pytest
from stride_search import Harness,Config,ContractError
from stride_search.archive import Archive
from stride_search.fixtures import smoke_corpus,smoke_model


def finished(tmp_path):
    path=tmp_path/'episode.sqlite'
    h=Harness('Q',smoke_corpus(),path=path,config=Config(max_model_calls=3))
    h.run(smoke_model());h.close()
    return path

def test_document_identity_corruption_is_not_silent(tmp_path):
    path=finished(tmp_path)
    c=sqlite3.connect(path);c.execute("UPDATE docs SET backend='wrong document' WHERE n=1");c.commit();c.close()
    with pytest.raises(ContractError):Archive(path,readonly=True)

def test_missing_recorded_backend_object_is_not_silent(tmp_path):
    path=finished(tmp_path)
    a=Archive(path,readonly=True)
    ref=next(e['payload']['object'] for e in a.events() if e['kind']=='backend_response')
    a.close()
    c=sqlite3.connect(path);c.execute('DELETE FROM objects WHERE sha=?',(ref,));c.commit();c.close()
    with pytest.raises(ContractError):Archive(path,readonly=True)

def test_notes_read_only_objects_cannot_be_deleted_without_detection(tmp_path):
    path=finished(tmp_path)
    a=Archive(path,readonly=True)
    ref=next(e['payload']['notes'] for e in a.events() if e['kind']=='round_end');a.close()
    c=sqlite3.connect(path);c.execute('DELETE FROM objects WHERE sha=?',(ref,));c.commit();c.close()
    with pytest.raises(ContractError):Archive(path,readonly=True)

def test_repeated_text_range_tampering_still_detected(tmp_path):
    a=Archive(tmp_path/'ranges.sqlite')
    a.append('episode',{'protocol':'stride-search-1'})
    d=a.register_doc('x','x');a.snapshot(d,'abcabc')
    a.window(d,0,3)
    # Same substring hash, wrong original offset: journal must bind the range too.
    a.db.execute('UPDATE evidence SET start=3,end=6')
    with pytest.raises(ContractError):a.verify()
    a.close()

def test_vector_query_width_is_not_hidden_in_single_tool():
    from stride_search.fixtures import ScriptedModel,native
    h=Harness('Q',smoke_corpus(),config=Config(max_model_calls=2,max_queries_per_search=1))
    m=ScriptedModel([native(('search',{'queries':['a','b']})),native(('finish',{'abstain':True,'reason':'x'}))])
    h.run(m)
    schema=next(t for t in m.requests[0]['tools'] if t['function']['name']=='search')
    assert schema['function']['parameters']['properties']['queries']['maxItems']==1
    assert h.backend_calls==0
    h.close()

def test_backend_batch_budget_is_checked_before_partial_search():
    from stride_search.fixtures import ScriptedModel,native
    h=Harness('Q',smoke_corpus(),config=Config(max_model_calls=2,max_backend_calls=1))
    m=ScriptedModel([native(('search',{'queries':['Lumen','archive']})),native(('finish',{'abstain':True,'reason':'x'}))])
    h.run(m);assert h.backend_calls==0;h.close()
