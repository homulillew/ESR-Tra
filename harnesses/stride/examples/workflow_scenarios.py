"""Offline SCRIPTED workflow scenarios; no real model calls."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from stride_search import Config,Harness
from stride_search.contract import INTEGER_ANSWER
from stride_search.fixtures import ScriptedModel,native,smoke_corpus
from stride_search.workflow_contract import WorkflowConfig


def run(root,name,workflow,responses):
    d=root/name;d.mkdir();h=Harness('Who was the first director of Lumen Observatory?',smoke_corpus(),
        path=d/'episode.sqlite',config=Config(max_model_calls=12),answer_contract=INTEGER_ANSWER,workflow=workflow)
    try:
        terminal=h.run(ScriptedModel(responses));out={'kind':'SCRIPTED_NOT_MODEL_QUALITY','outcome':terminal['outcome'],
            'answer':terminal['answer'],'model_decisions':h.model_calls,'backend_calls':h.backend_calls,
            'workflow':workflow.identity()};(d/'report.json').write_text(json.dumps(out,indent=2));return out
    finally:h.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);root=Path(p.parse_args().output);root.mkdir(parents=True)
    s=('search',{'queries':['Lumen']});r=('read',{'ref':'d1'});f=('finish',{'answer':'Ada Rowan','refs':['e1']});full=WorkflowConfig.profile('full')
    result={
      'short_legacy':run(root,'short_legacy',WorkflowConfig(),[native(s),native(r),native(f)]),
      'short_full':run(root,'short_full',full,[native(s),native(r),native(f)]),
      'loop_legacy':run(root,'loop_legacy',WorkflowConfig(),[native(s) for _ in range(12)]),
      'loop_full':run(root,'loop_full',full,[native(s) for _ in range(12)]),
      'recover_read':run(root,'recover_read',full,[native(s),native(s),native(s),native(r),native(f)])}
    (root/'RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
