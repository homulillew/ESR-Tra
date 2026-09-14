from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
import urllib.request
import pytest
from stride_search import Config,Harness,ContractError
from stride_search.providers import HTTP,OpenAIModel,AnthropicModel,EchoRetriever,endpoint,usage_of
from stride_search.fixtures import native,smoke_corpus
from test_engine import S,R,F,A

@pytest.mark.parametrize('url',['https://user:key@example.com/v1','http://','http://:80','https://x?key=foo',
    'https://x#frag','ftp://example.com','https://x:bad','https://x\n/v1'])
def test_endpoint_rejects(url):
    with pytest.raises(ValueError): endpoint(url)

def test_network_disabled_by_default():
    with pytest.raises(ContractError,match='allow-network'): HTTP().post('http://127.0.0.1:1',{})

def test_openai_strict_envelope_and_returned_identity():
    model=OpenAIModel('http://example.invalid/v1','route',revision='frozen',http=HTTP(),expected_response_model='expected')
    with pytest.raises(ContractError): model.parse({'choices':[]})
    with pytest.raises(ContractError,match='Unexpected'): model.parse(A)

def test_anthropic_blocks_ids_and_results_roundtrip():
    model=AnthropicModel('http://example.invalid/v1','m',revision='r',http=HTTP())
    raw={'role':'assistant','model':'m','stop_reason':'tool_use','content':[
        {'type':'thinking','thinking':'synthetic thought','signature':'synthetic_signature'},
        {'type':'text','text':'read both'},
        {'type':'tool_use','id':'u1','name':'read','input':{'ref':'d1'}},
        {'type':'tool_use','id':'u2','name':'read','input':{'ref':'d2'}}],
        'usage':{'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':100}}
    reply=model.parse(raw)
    wire=model.prepare([{'role':'system','content':'s'},reply.message,
        {'role':'tool','tool_call_id':'u1','content':'first'},
        {'role':'tool','tool_call_id':'u2','content':'second'},
        {'role':'user','content':'continue'}],[],100)
    assert wire['messages'][0]['content']==raw['content']
    results=[b for b in wire['messages'][1]['content'] if b['type']=='tool_result']
    assert [r['tool_use_id'] for r in results]==['u1','u2']
    assert reply.usage=={'input_tokens':10,'output_tokens':5,'cache_read_tokens':100}
    assert raw['content'][0]['signature']=='synthetic_signature'

@pytest.mark.parametrize('reason',['max_tokens','refusal','pause_turn',None])
def test_anthropic_incomplete(reason):
    model=AnthropicModel('http://example.invalid/v1','m',revision='r',http=HTTP())
    with pytest.raises(ContractError): model.parse({'role':'assistant','stop_reason':reason,'content':[]})

def test_anthropic_duplicate_ids_and_unknown_block():
    model=AnthropicModel('http://example.invalid/v1','m',revision='r',http=HTTP())
    block={'type':'tool_use','id':'same','name':'read','input':{'ref':'d1'}}
    with pytest.raises(ContractError): model.parse({'role':'assistant','stop_reason':'tool_use','content':[block,block]})
    with pytest.raises(ContractError): model.parse({'role':'assistant','stop_reason':'tool_use','content':[{'type':'image'}]})

@pytest.mark.parametrize('rows',[None,{},[None],[{'docid':'x','document':[]}],[{'docid':None}],
    [{'docid':'x','title':42}], [{'docid':'x','snippet':None}]])
def test_retriever_bad_rows(rows):
    class Fake:
        def post(self,*a,**kw):return {'result':rows}
    r=EchoRetriever('http://example.invalid',index_id='frozen',http=Fake())
    with pytest.raises(ContractError): r.search('query',3)

def test_retriever_document_identity_mismatch():
    class Fake:
        def post(self,*a,**kw): return {'docid':'other','content':'text'}
    r=EchoRetriever('http://example.invalid',index_id='frozen',http=Fake())
    with pytest.raises(ContractError): r.get_document('requested')

def test_partial_usage_and_boolean_not_counted():
    assert usage_of({'usage':{'prompt_tokens':True,'completion_tokens':-1}},'openai')=={}
    assert usage_of({'usage':{'prompt_tokens':12}},'openai')=={'input_tokens':12}

@pytest.fixture
def server():
    received=[]; replies=[S,R,F]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((self.path,body,dict(self.headers)))
            if self.path=='/v1/chat/completions':
                payload=replies.pop(0); status=200
            elif self.path=='/limited':
                payload={'error':'private provider body MUST NOT BE LOGGED'}; status=429
            elif self.path=='/redirect':
                self.send_response(302); self.send_header('Location','http://example.invalid'); self.end_headers();return
            else: payload={}; status=404
            self.send_response(status); self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
    srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{srv.server_port}',received
    finally:srv.shutdown();srv.server_close();thread.join(timeout=2)

def test_local_http_end_to_end_no_secret_in_archive(server,tmp_path):
    url,received=server
    http=HTTP(allow_network=True,opener=urllib.request.build_opener(urllib.request.ProxyHandler({})))
    m=OpenAIModel(url+'/v1','fixture',revision='fixture',http=http,api_key='TEST_ONLY_NOT_A_SECRET')
    h=Harness('Q',smoke_corpus(),path=tmp_path/'episode.sqlite',config=Config(max_model_calls=3));h.run(m)
    assert h.terminal['outcome']=='submitted' and len(received)==3
    assert all(r[2].get('Authorization')=='Bearer TEST_ONLY_NOT_A_SECRET' for r in received)
    all_text=' '.join(t[0] for t in h.archive.db.execute('select text from objects'))
    assert 'TEST_ONLY_NOT_A_SECRET' not in all_text
    assert [h.archive.load_request(e['payload']['request']) for e in h.archive.events() if e['kind']=='model_request']==[r[1] for r in received]
    h.close()

def test_http_429_has_no_retry_or_error_body(server):
    url,received=server
    http=HTTP(allow_network=True,opener=urllib.request.build_opener(urllib.request.ProxyHandler({})))
    with pytest.raises(ContractError) as e:http.post(url+'/limited',{})
    assert len(received)==1 and '429' in str(e.value) and 'private provider' not in str(e.value)

def test_redirect_is_not_followed(server):
    url,received=server
    # Default safe redirect handler, explicit loopback proxy bypass only in this test.
    from stride_search.providers import _NoRedirect
    http=HTTP(allow_network=True,opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect()))
    with pytest.raises(ContractError):http.post(url+'/redirect',{})
    assert len(received)==1

def test_anthropic_and_echo_http_full_episode(tmp_path):
    from stride_search.providers import _NoRedirect
    received=[]
    decisions=[('search',{'queries':['Lumen first director'],'top_k':1}),
               ('read',{'ref':'d1'}),('finish',{'answer':'Ada Rowan','refs':['e1']})]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((self.path,body))
            if self.path=='/v1/messages':
                name,args=decisions.pop(0)
                payload={'role':'assistant','model':'fixture-anthropic','stop_reason':'tool_use',
                    'content':[{'type':'text','text':'fixture decision'},
                       {'type':'tool_use','id':'native-id-'+str(len(decisions)),'name':name,'input':args}],
                    'usage':{'input_tokens':100,'output_tokens':20,'cache_read_input_tokens':10}}
            elif self.path=='/retrieve':
                payload={'result':[[{'docid':'x','document':{'title':'Lumen','contents':'Lumen first director'}}]]}
            elif self.path=='/get_doc':
                payload={'docid':'x','document':{'contents':'Lumen first director: Ada Rowan.'}}
            else:raise AssertionError(self.path)
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
    srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{srv.server_port}'
    try:
        http=HTTP(allow_network=True,opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect()))
        m=AnthropicModel(url+'/v1','fixture',revision='local',http=http)
        r=EchoRetriever(url,index_id='local-fixed',http=http)
        h=Harness('Who was the first director?',r,path=tmp_path/'anthropic.sqlite',config=Config(max_model_calls=3))
        h.run(m);report=h.archive.report()
        assert report['terminal']['answer']=='Ada Rowan'
        assert report['model_attempts']==3 and report['backend_attempts']==2 and len(received)==5
        assert report['usage_known']['input_tokens']==300 and report['usage_known']['cache_read_tokens']==30
        backends=[e['payload'] for e in h.archive.events() if e['kind']=='backend_response']
        assert all(p['raw_wire'] for p in backends)
        assert h.archive.json(backends[-1]['object'])['identity_echoed'] is True
        wires=[body for path,body in received if path=='/v1/messages']
        assert wires[-1]['messages'][-1]['content'][0]['type']=='tool_result'
        assert [t['name'] for t in wires[-1]['tools']]==['finish']
        h.close()
    finally:srv.shutdown();srv.server_close();thread.join(timeout=2)

def test_missing_document_identity_echo_is_explicit():
    class Fake:
        def post(self,*a,**kw):return {'content':'A body without returned ID'}
    r=EchoRetriever('http://example.invalid',index_id='fixed',http=Fake())
    assert r.get_document('request-bound')['identity_echoed'] is False
