"""Frozen fresh CLI episodes, then separate project judging; no retries or gold in policy."""
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
from stride_search.cpu_index import SQLiteFTS5
from stride_search.providers import HTTP
from stride_search.workflow_contract import WorkflowConfig

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'harnesses/stride/examples'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'field_feedback'))
from trace_question_a3 import Budget, CaptureOpener, export, save, sha, utc
from live_pilot import original_manifest, require
from judge_frozen_a3 import validate_response

BASE = '266772cebd296c4f9a7cb861c562f639ed3b0190'
CASES = ROOT / 'harnesses/stride/artifacts/20260914-hard12-a3'
SLOTS = [('q775-legacy', 775, 'legacy', 16), ('q775-full', 775, 'full', 16),
         ('q774-full', 774, 'full', 16), ('q774-legacy', 774, 'legacy', 16),
         ('q771-full', 771, 'full', 4), ('q778-full', 778, 'full', 4)]
GOLD_SHA = 'f1958aa81bbaca21cb14a58ba009f53c070fa047f0107414226dbec76a242807'
NORMAL = {'submitted', 'abstained', 'model_budget', 'action_budget', 'backend_budget',
          'output_budget', 'time_budget', 'stalled_no_submission', 'context_capacity'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sources():
    paths = list((ROOT / 'harnesses/stride/src/stride_search').glob('*.py'))
    paths += [Path(__file__), ROOT / 'src/esr_grpo/judge.py',
              ROOT / 'harnesses/stride/examples/trace_question_a3.py',
              ROOT / 'harnesses/stride/examples/judge_frozen_a3.py',
              Path(__file__).parent.parent / 'field_feedback/live_pilot.py']
    paths += list((ROOT / 'harnesses/stride/tests').glob('test_workflow*.py'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def question_path(qid):
    return CASES / f'q{qid}/question.txt'


def prepare(manifest, target, tests_xml):
    m = original_manifest(manifest)
    inventory = read(CASES / 'MANIFEST.sha256.json')
    slots = []
    for slot, qid, profile, limit in SLOTS:
        path = question_path(qid)
        require(sha(path) == inventory[path.relative_to(CASES).as_posix()], 'Question integrity')
        config = {**m['config'], 'max_model_calls': limit, 'max_seconds': 600}
        Config(**config)
        slots.append(dict(slot=slot, qid=qid, profile=profile, config=config,
            question_sha256=sha(path), workflow=WorkflowConfig.profile(profile).identity()))
    backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'],
                        timeout_seconds=m['index_identity']['query_timeout_seconds'])
    try: require(backend.identity == m['index_identity'], 'Index identity')
    finally: backend.close()
    plan = dict(base=BASE, package_version='0.1.0a3', answer_contract=INTEGER_ANSWER,
        slots=slots, source_sha256=sources(), private_manifest_sha256=sha(manifest),
        index_identity=m['index_identity'],
        model={k: v for k, v in m['model_identity'].items() if k != 'endpoint'},
        policy_cap=72, judge_cap=6, hard_http_cap=80, planned_http_cap=78,
        time='Fresh monotonic clock per episode; max_seconds=600; HTTP timeout min(180, remaining seconds).',
        capacity_units={'context_limit': 'UTF-8 bytes', 'response_reserve': 'UTF-8 bytes'},
        budget='Existing shared ledger, atomic reservation before send, failed/unknown attempts charged.',
        entry='cli.execute(run), explicit answer contract and workflow profile; Harness.run unchanged.',
        judge='Unmodified project judge after all policy slots sealed; submitted full answers only; same deployment, separate calls.',
        gold_sha256=GOLD_SHA, normal_outcomes=sorted(NORMAL), automatic_retries=0,
        offline_tests_xml_sha256=sha(tests_xml), utc_prepared=utc())
    target = Path(target); target.mkdir(parents=True, exist_ok=False)
    save(target / 'PLAN.json', plan)
    (target / 'PLAN.sha256').write_bytes((sha(target / 'PLAN.json') + '\n').encode())


def verify(path):
    path = Path(path); plan = read(path)
    require(sha(path) == path.with_suffix('.sha256').read_text().strip(), 'Plan changed')
    require(plan['source_sha256'] == sources(), 'Frozen sources changed')
    for s in plan['slots']:
        require(sha(question_path(s['qid'])) == s['question_sha256'], 'Question changed')
    return plan


class RoleBudget(Budget):
    role = 'policy'
    policy_sealed = False

    def take(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            require(self.role in ('policy', 'judge'), 'Unknown budget role')
            require(self.role != 'judge' or self.policy_sealed, 'Policy must be sealed before judge')
            require(self.role != 'policy' or not self.policy_sealed, 'Policy cannot restart after sealing')
            count = self.db.execute('SELECT count(*) FROM requests WHERE run=? AND role=?',
                                    (self.run, self.role)).fetchone()[0]
            s = self.snapshot()
            require(s['remaining'] > 0 and s['this_run'] < min(self.limit, 80)
                    and count < {'policy': 72, 'judge': 6}[self.role], 'Request budget exhausted')
            n = self.db.execute('INSERT INTO requests(run,role,status) VALUES (?,?,?)',
                                (self.run, self.role, 'unknown')).lastrowid
            self.db.execute('COMMIT'); return n
        except Exception:
            self.db.execute('ROLLBACK'); raise


class LimitedCapture(CaptureOpener):
    def __init__(self, *args, limit, check, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit, self.check, self.deadline = limit, check, None

    def open(self, request, timeout):
        self.check()
        require(len(self.rows) < self.limit, 'Slot attempt cap')
        if self.deadline is not None:
            timeout = min(180, self.deadline - time.monotonic())
            require(timeout > 0, 'Local HTTP time exhausted')
        return super().open(request, timeout)


def policy_slot(s, m, folder, cap):
    folder.mkdir()
    identity = m['model_identity']

    class ObservedHarness(Harness):
        def run(self, model):
            require(self.config.to_dict() == s['config'], 'CLI config mismatch')
            require(self.answer_contract == INTEGER_ANSWER and self.workflow.options.identity() == s['workflow'], 'CLI contract mismatch')
            require(not self.groups and not self.exposed and self.model_calls == self.backend_calls == 0, 'Not fresh')
            require(self.retriever.identity == m['index_identity'] and model.identity == identity, 'Identity mismatch')
            append = self.archive.append
            def timed(kind, payload):
                event = append(kind, payload)
                with (folder / 'events-timed.jsonl').open('a', encoding='utf-8') as f:
                    f.write(canonical({**event, 'utc': utc()}) + '\n')
                return event
            self.archive.append = timed
            cap.deadline = self.started + self.config.max_seconds
            return super().run(model)

    flags = ['run', '--allow-network', '--accept-counter-estimate', '--base-url', m['base_url'],
        '--model', identity['model'], '--model-revision', identity['revision_label'],
        '--expected-response-model', identity['expected_response_model'], '--temperature', '0',
        '--output-parameter', identity['output_parameter'], '--api-key-env', 'ESR_API_KEY',
        '--sqlite-index', m['index_path'], '--index-id', m['index_id'],
        '--timeout', str(m['index_identity']['query_timeout_seconds']), '--counter', 'utf8_bytes',
        '--question-file', str(question_path(s['qid'])), '--db', str(folder / 'episode.sqlite'),
        '--answer-contract', INTEGER_ANSWER, '--workflow-profile', s['profile']]
    for key in ['max_model_calls', 'max_backend_calls', 'max_actions', 'max_output_tokens',
                'max_total_output_tokens', 'max_seconds', 'context_limit', 'response_reserve',
                'max_batch', 'max_queries_per_search', 'context_mode', 'answer_prefix', 'answer_suffix']:
        flags += ['--' + key.replace('_', '-'), str(s['config'][key])]
    started = time.monotonic()
    with patch.object(cli, 'HTTP', lambda **kw: HTTP(**{**kw, 'timeout': 180}, opener=cap)), patch.object(cli, 'Harness', ObservedHarness):
        report = cli.execute(cli.parser().parse_args(flags))
    elapsed = time.monotonic() - started
    save(folder / 'report.json', report)
    export(folder)
    a = Archive(folder / 'episode.sqlite', readonly=True)
    try:
        save(folder / 'all-objects.json', dict(a.db.execute('SELECT sha,text FROM objects')))
        head = a.verify()['head']
    finally: a.close()
    save(folder / 'SEALED.json', {'utc': utc(), 'head': head,
        'files': {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}})
    return dict(slot=s['slot'], qid=s['qid'], status=report['terminal']['outcome'],
                terminal=report['terminal'], attempts=len(cap.rows), elapsed_seconds=elapsed,
                head=head, seal_sha256=sha(folder / 'SEALED.json'))


def judge_cases(output, rows, gold):
    require((output / 'POLICY_SEALED.json').is_file(), 'Policy seal missing')
    save(output / 'gold-access.json', {'utc': utc(), 'policy_seal_sha256': sha(output / 'POLICY_SEALED.json')})
    digest = hashlib.sha256(); answers = {}
    with Path(gold).open('rb') as f:
        for line in f:
            digest.update(line)
            row = json.loads(line)
            if int(row['query_id']) in {s[1] for s in SLOTS}:
                require(int(row['query_id']) not in answers, 'Duplicate gold')
                answers[int(row['query_id'])] = row
    require(digest.hexdigest() == GOLD_SHA, 'Gold identity changed')
    cases = []
    for row in rows:
        if row['status'] != 'submitted': continue
        folder = output / row['slot']; seal = read(folder / 'SEALED.json')
        require(sha(folder / 'SEALED.json') == row['seal_sha256'], 'Policy seal changed')
        require(all(sha(folder / name) == value for name, value in seal['files'].items()), 'Sealed file changed')
        a = Archive(folder / 'episode.sqlite', readonly=True)
        try:
            r = a.report(); require(a.verify()['head'] == row['head'], 'Policy head changed')
            q = r['header']['question']; response = r['terminal']['answer']
            require(q == answers[row['qid']]['query'], 'Gold question mismatch')
            require(response == row['terminal']['answer'], 'Submission changed')
            cases.append(dict(slot=row['slot'], qid=row['qid'], head=row['head'], question=q,
                              response=response, correct_answer=answers[row['qid']]['answer']))
        finally: a.close()
    save(output / 'judge-cases.json', cases)
    return cases


def run(plan_path, manifest, output, gold):
    plan = verify(plan_path); m = original_manifest(manifest)
    require(sha(manifest) == plan['private_manifest_sha256'], 'Private manifest changed')
    require(bool(os.environ.get('ESR_API_KEY')), 'Credential unavailable')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT), 'Tracked changes not frozen')
    require(Path(gold).is_file(), 'Gold unavailable')  # Contents opened only after policy seal.
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    budget = RoleBudget(m['budget_path'], str(output), limit=80)
    rows = [dict(slot=s['slot'], qid=s['qid'], status='NOT_RUN', attempts=0) for s in plan['slots']]
    judgments = []; active = None; queue_ok = True
    save(output / 'manifest.json', dict(plan=plan, plan_sha256=sha(plan_path),
        frozen_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        utc_started=utc(), budget_before=budget.before))
    def capture(folder, limit):
        return LimitedCapture(folder, budget, os.environ['ESR_API_KEY'],
            m['base_url'].rstrip('/') + '/chat/completions', limit=limit, check=lambda: verify(plan_path))
    try:
        for i, s in enumerate(plan['slots']):
            active = s['slot']; cap = capture(output / active, s['config']['max_model_calls'])
            print(canonical({'starting': active, 'budget': budget.snapshot()}), flush=True)
            rows[i] = policy_slot(s, m, output / active, cap)
            rows[i]['budget_after'] = budget.snapshot()
            save(output / f'{active}.summary.json', rows[i]); print(canonical(rows[i]), flush=True)
            if rows[i]['status'] not in NORMAL:
                queue_ok = False; break
        save(output / 'POLICY_SEALED.json', dict(utc=utc(), rows=rows, queue_ok=queue_ok))
        if not queue_ok: return
        budget.policy_sealed = True; budget.role = 'judge'; active = 'judge'
        cases = judge_cases(output, rows, gold)
        folder = output / 'judge'; folder.mkdir(); cap = capture(folder, 6)
        spec = importlib.util.spec_from_file_location('workflow_project_judge', ROOT / 'src/esr_grpo/judge.py')
        module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        judge = module.OpenAICompatibleJudge(m['base_url'], m['model_identity']['model'], api_key_env='ESR_API_KEY')
        for i, c in enumerate(cases, 1):
            with patch.object(module.urllib.request, 'urlopen', cap.open):
                result = judge.judge(c['question'], c['response'], c['correct_answer'])
            raw = read(folder / 'http' / f'{i:03d}' / 'response.body')
            parsed = module._parse_json_object(raw['choices'][0]['message']['content'])
            validate_response(raw, parsed)
            require(not result.parse_error and result.correct == parsed['correct'], 'Judge parse mismatch')
            row = dict(slot=c['slot'], head=c['head'], http_sequence=i, **asdict(result))
            judgments.append(row); save(folder / f'{i:03d}.judgment.json', row)
            print(canonical({'judged': c['slot'], 'correct': result.correct}), flush=True)
    except Exception as exc:
        if active in {s['slot'] for s in plan['slots']}:
            i = next(i for i, s in enumerate(plan['slots']) if s['slot'] == active)
            rows[i] = dict(slot=active, qid=plan['slots'][i]['qid'], status='stopped_error',
                           attempts=len(cap.rows), exception_type=type(exc).__name__)
            # CLI closes SQLite even on exceptions; preserve any terminal and its head.
            path = output / active / 'episode.sqlite'
            if path.exists():
                try:
                    a = Archive(path, readonly=True)
                    try:
                        rows[i].update(terminal=a.report()['terminal'], head=a.verify()['head'])
                    finally: a.close()
                except Exception:
                    rows[i]['archive_check'] = 'FAILED'
        save(output / 'STOPPED.json', dict(active=active, type=type(exc).__name__,
             code=getattr(exc, 'code', None), utc=utc(), attempts=budget.snapshot()['this_run']))
        print(canonical({'stopped': active, 'type': type(exc).__name__}), flush=True)
    finally:
        save(output / 'RESULTS.json', dict(rows=rows, judgments=judgments,
             budget_before=budget.before, budget_after=budget.snapshot(), utc_finished=utc()))
        budget.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'run']); p.add_argument('--private-manifest', required=True)
    p.add_argument('--output', required=True); p.add_argument('--tests-xml'); p.add_argument('--plan'); p.add_argument('--gold')
    a = p.parse_args()
    if a.command == 'prepare': prepare(a.private_manifest, a.output, a.tests_xml)
    else: run(a.plan, a.private_manifest, a.output, a.gold)
