"""Frozen question-only paired stages; post-seal judging; one shared allowance epoch."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from stride_search import Harness, cli
from stride_search.archive import Archive
from stride_search.contract import Config, INTEGER_ANSWER, canonical
from stride_search.decision_protocol import identity as decision_identity
from stride_search.cpu_index import SQLiteFTS5
from stride_search.providers import HTTP
from stride_search.workflow_contract import WorkflowConfig

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'harnesses/stride/examples'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'field_feedback'))
from trace_question_a3 import CaptureOpener, export, save, sha, utc
from live_pilot import original_manifest, require
from judge_frozen_a3 import validate_response
from budget import EpochBudget

EPOCH = 'autonomous-search-20260915'
CASES = ROOT / 'harnesses/stride/artifacts/20260914-hard12-a3'
GOLD_SHA = 'f1958aa81bbaca21cb14a58ba009f53c070fa047f0107414226dbec76a242807'
NORMAL = {'submitted','abstained','model_budget','action_budget','backend_budget',
          'output_budget','time_budget','stalled_no_submission','context_capacity'}


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def sources():
    paths = list((ROOT / 'harnesses/stride/src/stride_search').glob('*.py'))
    paths += list(Path(__file__).parent.glob('*.py'))
    paths += [ROOT / 'src/esr_grpo/judge.py', ROOT / 'harnesses/stride/examples/trace_question_a3.py',
              ROOT / 'harnesses/stride/examples/judge_frozen_a3.py',
              Path(__file__).parent.parent / 'field_feedback/live_pilot.py']
    paths += list((ROOT / 'harnesses/stride/tests').glob('test_decision*.py'))
    paths += [ROOT / 'harnesses/stride/tests/test_search_pivot.py',
              ROOT / 'harnesses/stride/tests/test_middle_history.py',
              ROOT / 'harnesses/stride/tests/test_once_prose_reset.py',
              ROOT / 'harnesses/stride/tests/test_relation_review.py',
              ROOT / 'harnesses/stride/tests/test_review_memory.py',
              ROOT / 'harnesses/stride/tests/test_read_only.py',
              ROOT / 'harnesses/stride/tests/test_stage_publication.py']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def prepare(manifest, target, qids, protocol, repeats=1, reverse=False):
    m = original_manifest(manifest); inventory = read(CASES / 'MANIFEST.sha256.json')
    slots = []
    for rep in range(repeats):
        for i, qid in enumerate(qids):
            path = CASES / f'q{qid}/question.txt'
            require(sha(path) == inventory[path.relative_to(CASES).as_posix()], 'Question integrity')
            config = {**m['config'], 'max_model_calls': 4 if qid in (771,778) else 16, 'max_seconds': 600}
            Config(**config)
            order = ['baseline', protocol]
            if (i + rep + reverse) % 2: order.reverse()
            for arm in order:
                slots.append(dict(slot=f'q{qid}-{arm}-r{rep+1}', qid=qid, protocol=arm,
                    config=config, question_sha256=sha(path), workflow=WorkflowConfig.profile('full').identity()))
    backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'], timeout_seconds=m['index_identity']['query_timeout_seconds'])
    try: require(backend.identity == m['index_identity'], 'CPU index identity')
    finally: backend.close()
    target = Path(target); target.mkdir(parents=True, exist_ok=False)
    plan = dict(epoch=EPOCH, stage=target.name, source_sha256=sources(), slots=slots,
        private_manifest_sha256=sha(manifest), index_identity=m['index_identity'],
        model={k:v for k,v in m['model_identity'].items() if k != 'endpoint'},
        policy_cap=sum(s['config']['max_model_calls'] for s in slots), judge_cap=len(slots),
        answer_contract=INTEGER_ANSWER, gold_sha256=GOLD_SHA, utc_prepared=utc(),
        time='Fresh monotonic per slot; 600 seconds; HTTP min(180, remaining seconds).',
        budget='Existing ledger, authorized 1000-call epoch; failed/unknown charged before send; no retries.',
        judge='Project judge, full submitted terminal answers only, after all policy slots sealed.',
        decision_protocols={name:decision_identity(name) for name in ['baseline',protocol]},
        unique_variable='Named decision_protocol as declared by its identity; same full workflow and all other settings within each pair')
    save(target / 'PLAN.json', plan)
    (target / 'PLAN.sha256').write_bytes((sha(target / 'PLAN.json') + '\n').encode())


def verify(path):
    path = Path(path); plan = read(path)
    require(sha(path) == path.with_suffix('.sha256').read_text().strip(), 'Frozen plan changed')
    require(plan['source_sha256'] == sources(), 'Frozen sources changed')
    for s in plan['slots']:
        require(sha(CASES / f"q{s['qid']}/question.txt") == s['question_sha256'], 'Question changed')
    return plan


class LimitedCapture(CaptureOpener):
    def __init__(self, *args, limit, check, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit, self.check, self.deadline = limit, check, None

    def open(self, request, timeout):
        self.check(); require(len(self.rows) < self.limit, 'Slot HTTP cap')
        if self.deadline is not None:
            timeout = min(180, self.deadline - time.monotonic())
            require(timeout > 0, 'Local HTTP time exhausted')
        return super().open(request, timeout)


def policy_slot(s, m, folder, cap):
    folder.mkdir(); identity = m['model_identity']
    class ObservedHarness(Harness):
        def run(self, model):
            require(self.config.to_dict() == s['config'], 'CLI config mismatch')
            require(self.answer_contract == INTEGER_ANSWER and self.workflow.options.identity() == s['workflow']
                    and self.decision_protocol == s['protocol'], 'CLI protocol mismatch')
            require(not self.groups and not self.exposed and self.model_calls == self.backend_calls == 0, 'Not fresh')
            require(self.retriever.identity == m['index_identity'] and model.identity == identity, 'Identity mismatch')
            append = self.archive.append
            def timed(kind, payload):
                event = append(kind, payload)
                with (folder / 'events-timed.jsonl').open('a', encoding='utf-8') as f:
                    f.write(canonical({**event, 'utc':utc()}) + '\n')
                return event
            self.archive.append = timed; cap.deadline = self.started + self.config.max_seconds
            return super().run(model)
    flags = ['run','--allow-network','--accept-counter-estimate','--base-url',m['base_url'],
        '--model',identity['model'],'--model-revision',identity['revision_label'],
        '--expected-response-model',identity['expected_response_model'],'--temperature','0',
        '--output-parameter',identity['output_parameter'],'--api-key-env','ESR_API_KEY',
        '--sqlite-index',m['index_path'],'--index-id',m['index_id'],
        '--timeout',str(m['index_identity']['query_timeout_seconds']),'--counter','utf8_bytes',
        '--question-file',str(CASES / f"q{s['qid']}/question.txt"),'--db',str(folder/'episode.sqlite'),
        '--answer-contract',INTEGER_ANSWER,'--workflow-profile','full','--decision-protocol',s['protocol']]
    for k in ['max_model_calls','max_backend_calls','max_actions','max_output_tokens','max_total_output_tokens',
              'max_seconds','context_limit','response_reserve','max_batch','max_queries_per_search',
              'context_mode','answer_prefix','answer_suffix']:
        flags += ['--'+k.replace('_','-'),str(s['config'][k])]
    started = time.monotonic()
    with patch.object(cli,'HTTP',lambda **kw: HTTP(**{**kw,'timeout':180},opener=cap)), patch.object(cli,'Harness',ObservedHarness):
        report = cli.execute(cli.parser().parse_args(flags))
    elapsed = time.monotonic()-started
    save(folder/'report.json',report); export(folder)
    a=Archive(folder/'episode.sqlite',readonly=True)
    try:
        save(folder/'all-objects.json',dict(a.db.execute('SELECT sha,text FROM objects')))
        head=a.verify()['head']
    finally:a.close()
    save(folder/'SEALED.json',dict(utc=utc(),head=head,files={p.relative_to(folder).as_posix():sha(p)
        for p in sorted(folder.rglob('*')) if p.is_file() and not p.name.endswith(('-shm','-wal'))}))
    return dict(slot=s['slot'],qid=s['qid'],protocol=s['protocol'],status=report['terminal']['outcome'],
        terminal=report['terminal'],attempts=len(cap.rows),elapsed_seconds=elapsed,head=head,
        seal_sha256=sha(folder/'SEALED.json'))


def judge_cases(output, rows, gold):
    require((output/'POLICY_SEALED.json').is_file(),'Policy seal missing')
    save(output/'gold-access.json',dict(utc=utc(),policy_seal_sha256=sha(output/'POLICY_SEALED.json')))
    needed={r['qid'] for r in rows if r['status']=='submitted'}; answers={}; digest=hashlib.sha256()
    with Path(gold).open('rb') as f:
        for line in f:
            digest.update(line); row=json.loads(line)
            if int(row['query_id']) in needed:
                require(int(row['query_id']) not in answers,'Duplicate gold')
                answers[int(row['query_id'])]=row
    require(digest.hexdigest()==GOLD_SHA,'Gold identity changed')
    cases=[]
    for row in rows:
        if row['status']!='submitted':continue
        folder=output/row['slot'];seal=read(folder/'SEALED.json')
        require(sha(folder/'SEALED.json')==row['seal_sha256'],'Seal changed')
        require(all(sha(folder/name)==v for name,v in seal['files'].items()),'Sealed file changed')
        a=Archive(folder/'episode.sqlite',readonly=True)
        try:
            r=a.report(); require(a.verify()['head']==row['head'],'Policy head changed')
            q=r['header']['question']; answer=r['terminal']['answer']
            require(q==answers[row['qid']]['query'] and answer==row['terminal']['answer'],'Judge binding changed')
            cases.append(dict(slot=row['slot'],qid=row['qid'],head=row['head'],question=q,
                response=answer,correct_answer=answers[row['qid']]['answer']))
        finally:a.close()
    save(output/'judge-cases.json',cases);return cases


def run(plan_path, manifest, output, gold):
    plan=verify(plan_path);m=original_manifest(manifest)
    require(sha(manifest)==plan['private_manifest_sha256'],'Manifest changed')
    require(bool(os.environ.get('ESR_API_KEY')),'Credential unavailable')
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT),'Tracked changes not frozen')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    budget=EpochBudget(m['budget_path'],str(output),plan['epoch'],plan['policy_cap'],plan['judge_cap'])
    rows=[dict(slot=s['slot'],qid=s['qid'],protocol=s['protocol'],status='NOT_RUN',attempts=0) for s in plan['slots']]
    judgments=[];active=None;cap=None
    save(output/'manifest.json',dict(plan=plan,plan_sha256=sha(plan_path),utc_started=utc(),
        frozen_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),budget_before=budget.window()))
    def capture(folder,limit):
        return LimitedCapture(folder,budget,os.environ['ESR_API_KEY'],m['base_url'].rstrip('/')+'/chat/completions',
            limit=limit,check=lambda:verify(plan_path))
    try:
        for i,s in enumerate(plan['slots']):
            active=s['slot'];cap=capture(output/active,s['config']['max_model_calls'])
            print(canonical({'starting':active,'budget':budget.window()}),flush=True)
            rows[i]=policy_slot(s,m,output/active,cap);rows[i]['budget_after']=budget.window()
            save(output/f'{active}.summary.json',rows[i]);print(canonical(rows[i]),flush=True)
            if rows[i]['status'] not in NORMAL:raise RuntimeError('Infrastructure outcome; queue stopped')
        save(output/'POLICY_SEALED.json',dict(utc=utc(),rows=rows))
        budget.policy_sealed=True;budget.role='judge';active='judge'
        cases=judge_cases(output,rows,gold);folder=output/'judge';folder.mkdir();cap=capture(folder,plan['judge_cap'])
        spec=importlib.util.spec_from_file_location('stage_project_judge',ROOT/'src/esr_grpo/judge.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        judge=module.OpenAICompatibleJudge(m['base_url'],m['model_identity']['model'],api_key_env='ESR_API_KEY')
        for i,c in enumerate(cases,1):
            with patch.object(module.urllib.request,'urlopen',cap.open):result=judge.judge(c['question'],c['response'],c['correct_answer'])
            raw=read(folder/'http'/f'{i:03d}'/'response.body');parsed=module._parse_json_object(raw['choices'][0]['message']['content'])
            validate_response(raw,parsed);require(not result.parse_error and result.correct==parsed['correct'],'Judge parse mismatch')
            row=dict(slot=c['slot'],head=c['head'],http_sequence=i,**asdict(result))
            judgments.append(row);save(folder/f'{i:03d}.judgment.json',row)
            print(canonical({'judged':c['slot'],'correct':result.correct}),flush=True)
    except Exception as exc:
        if active is not None and active!='judge':
            i=next(i for i,s in enumerate(plan['slots']) if s['slot']==active)
            if rows[i]['status']=='NOT_RUN':rows[i].update(status='stopped_error',attempts=len(cap.rows) if cap else 0)
        save(output/'STOPPED.json',dict(active=active,type=type(exc).__name__,code=getattr(exc,'code',None),utc=utc()))
        print(canonical({'stopped':active,'type':type(exc).__name__}),flush=True)
    finally:
        save(output/'RESULTS.json',dict(rows=rows,judgments=judgments,budget_after=budget.window(),utc_finished=utc()))
        budget.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--private-manifest',required=True);p.add_argument('--output',required=True)
    p.add_argument('--plan');p.add_argument('--gold');p.add_argument('--qids',type=int,nargs='+')
    p.add_argument('--protocol',default='constraint-review-v1');p.add_argument('--repeats',type=int,default=1)
    p.add_argument('--reverse',action='store_true');a=p.parse_args()
    if a.command=='prepare':prepare(a.private_manifest,a.output,a.qids,a.protocol,a.repeats,a.reverse)
    else:run(a.plan,a.private_manifest,a.output,a.gold)
