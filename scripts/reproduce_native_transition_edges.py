"""Offline transition diagnostics with explicit fixed/defective expectations."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from esr_harness.engine import Harness
from esr_harness.protocol import Config, canonical
from esr_harness.runner import run
from esr_harness.tool_turn import NativeTurn, execute_turn
from esr_harness.views import MemoryRetriever


def environment(mode):
    return Harness('Compare the lake records', MemoryRetriever([
        {'docid':'d1','title':'Lake','content':'Lake record alpha.'}]),
        config=Config(mode=mode,audit_mode='off',max_tool_calls=4))


def turn(h, *calls):
    return NativeTurn('synthetic-request', [
        {'type':'tool_use','id':str(i),'name':name,'input':args}
        for i, (name,args) in enumerate(calls)], h.available_tools())


def reproduce(expected='fixed'):
    h = environment('baseline')
    class Policy:
        calls = 0
        fits = staticmethod(lambda _: True)
        def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return turn(h, ('search', {'query':'Lake'}))
            if self.calls == 2:
                return canonical({'action':'search','arguments':{'query':'record'}})
            if self.calls == 3:
                return canonical({'action':'finish','arguments':{'answer':'synthetic completion'}})
            raise AssertionError('Unexpected extra synthetic policy call')
    policy = Policy()
    exception = None
    try:
        run(h,policy)
    except Exception as exc:
        exception = type(exc).__name__
    first = {'exception':exception, 'stub_policy_calls':policy.calls,
             'committed_actions':len(h.actions), 'terminal':h.terminal}
    if expected == 'defects':
        assert exception == 'StopIteration' and len(h.actions)==1 and h.terminal is None
    else:
        assert exception is None and len(h.actions)==3 and h.terminal['outcome']=='submitted'
    h.ledger.close()

    h = environment('esr')
    new_focus = {'claim_id':'c0','need':'Find a different relation'}
    execute_turn(h,turn(h,
        ('search',{'query':'Lake','focus':new_focus,'anchor_refs':['o999']}),
        ('search',{'query':'record'})), 'd1')
    assert h.actions[0]['result']['error_code']=='unexposed_reference'
    result = h.native_turns['d1']['results']['1']
    actual = result.get('purpose', {}).get('need')
    if expected == 'defects':
        assert result['ok'] and actual != new_focus['need'] and actual == h.question
    else:
        assert result['error_code']=='dependency_failed' and result['execution']=='not_executed'
        assert len(h.actions)==1 and h.state['focus']['need']==h.question
    second = {'first_error':h.actions[0]['result']['error_code'],
              'first_focus_edit_applied':h.actions[0]['result']['focus_edit_applied'],
              'second_search_succeeded':result['ok'], 'second_receipt':result,
              'planned_focus_need':new_focus['need'], 'actual_focus_need':actual,
              'committed_actions':len(h.actions)}
    h.ledger.close()
    return {'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'api_calls':0, 'external_retrieval_calls':0, 'synthetic_only':True,
            'expected':expected,
            'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
            'baseline_native_then_text':first, 'failed_focus_then_implicit_search':second}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--expect',choices=['fixed','defects'],default='fixed')
    args=parser.parse_args()
    encoded=json.dumps(reproduce(args.expect),ensure_ascii=True,indent=2)
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            stream.write(encoded+'\n')
    print(encoded)
