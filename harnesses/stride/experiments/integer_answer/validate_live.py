"""Bounded acceptance: recorded R4 offline, new R4 continuation, then fresh CLI run."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import patch

from stride_search import Harness, cli
from stride_search.contract import INTEGER_ANSWER, canonical
from stride_search.providers import HTTP, OpenAIModel
from stride_search.cpu_index import SQLiteFTS5

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).parent.parent / 'field_feedback'))
from live_pilot import (Budget, CaptureOpener, CASE, attach_live, original_manifest,
                        require, utc, verify_public)
from prefix_replay import differences, load_prefix, next_payload, replay, state
from reproduce import read, sha


def save(path, value):
    with Path(path).open('xb') as f:
        f.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def sources():
    paths = list((ROOT / 'harnesses/stride/src/stride_search').glob('*.py'))
    paths += list((Path(__file__).parent.parent / 'field_feedback').glob('*.py'))
    paths += [Path(__file__), ROOT / 'harnesses/stride/examples/trace_question_a3.py',
              ROOT / 'harnesses/stride/tests/test_integer_answer.py',
              ROOT / 'harnesses/stride/tests/test_integer_live.py']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def evidence_gate(h):
    """Offline q778 acceptance only; never changes policy inputs or answer values.

    Conservative match against actually delivered source text. This is not gold
    or an official judge. An unrecognized wording stops automatic phase 2.
    """
    t = h.terminal
    if not t or t['outcome'] != 'submitted' or not t.get('refs'):
        return False
    for ref in t['refs']:
        if ref not in h.exposed:
            return False
        text = h.archive.evidence(ref)['text']
        match = re.search(r'\bmother was (\d+) when she gave birth\b', text, re.I)
        if match and t['answer'].strip() in (match[1], match[1] + ' years', match[1] + ' years old'):
            return True
    return False


def prepare(private_manifest, output, report):
    verify_public(); m = original_manifest(private_manifest)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    report = Path(report); report.mkdir(parents=True, exist_ok=False)
    tape = load_prefix(CASE, boundary=3)
    h, model = replay(tape, output / 'recorded-action.sqlite')
    try:
        old = next_payload(h, model)
        require(canonical(old).encode() == (CASE / 'http/004/request.body').read_bytes(), 'Original R4 mismatch')
        before = state(h); h.set_answer_contract(INTEGER_ANSWER)
        new = next_payload(h, model)
        diff = differences(old, new)
        require({d['path'] for d in diff} == {'/messages/0/content', '/tools/5/function/description',
            '/tools/5/function/parameters/oneOf/0/properties/answer/type'}, 'Unexpected request changes')
        require(state(h) == before, 'Discrete prefix state changed')
        raw = read(CASE / 'http/004/response.body')
        model.send = lambda wire: deepcopy(raw)  # Offline recorded action, never used live.
        h._step(model)
        require(evidence_gate(h), 'Recorded action not submitted with supported source')
        save(output / 'recorded-result.json', h.archive.report())
        save(report / 'OFFLINE_RECORDED_ACTION.json', {'kind': 'recorded_action_not_new_model_success',
            'source_response_sha256': sha(CASE / 'http/004/response.body'),
            'raw_arguments': raw['choices'][0]['message']['tool_calls'][0]['function']['arguments'],
            'terminal': {k: h.terminal[k] for k in ['outcome', 'answer', 'refs', 'answer_representation']},
            'archive_head': h.archive.verify()['head'], 'source_and_content_check': True, 'real_requests': 0})
        save(report / 'PREFIX_CHECK.json', {'boundary': 3, 'legacy_r4_bytes_exact': True,
            'first_three_requests': model.comparisons, 'remaining': before['remaining'],
            'source_prefix_head': tape['events'][-1]['hash'], 'discrete_state_unchanged': True,
            'new_request_differences': diff})
        backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'],
                             timeout_seconds=m['index_identity']['query_timeout_seconds'])
        try: require(backend.identity == m['index_identity'] == h.retriever.identity, 'Index mismatch')
        finally: backend.close()
        plan = {'feature': INTEGER_ANSWER, 'parent': '8238a19a98db143212ac22e85f4b5a6c529a202f',
            'authorization': 'Explicit user instruction to execute after offline acceptance',
            'phases': [{'name': 'prefix', 'max_new_requests': 4}, {'name': 'natural', 'max_new_requests': 12}],
            'max_total_new_requests': 16, 'local_seconds_per_phase': 300, 'http_timeout_ceiling': 180,
            'config': m['config'], 'model': {k: v for k, v in m['model_identity'].items() if k != 'endpoint'},
            'index_identity': m['index_identity'], 'private_manifest_sha256': sha(private_manifest),
            'source_sha256': sources(), 'prefix_first_sha256': hashlib.sha256(canonical(new).encode()).hexdigest(),
            'prefix_check_sha256': sha(report / 'PREFIX_CHECK.json'),
            'recorded_action_sha256': sha(report / 'OFFLINE_RECORDED_ACTION.json'),
            'time': 'New real local monotonic clock; historical elapsed unknown; check between complete steps; bound HTTP timeout by local remaining time. Original bounded CPU work may finish after window; no next step.',
            'phase2_gate': 'Phase1 submitted and evidence_gate passes; conservative offline delivered-source check, no policy injection.',
            'natural_entry': 'cli.execute(run), default new contract; external observer only replaces run loop for cap/capture.',
            'budget': 'Existing ledger, atomically reserve before actual send, including failures/unknowns; no reset.',
            'stop_queue_on': 'HTTP/auth/429/timeout/truncation/identity/integrity/backend/budget error or phase1 not accepted',
            'automatic_retries': 0, 'paid_judges': 0, 'official_labels_unchanged': True}
        save(report / 'PLAN.json', plan)
        (report / 'PLAN.sha256').write_bytes((sha(report / 'PLAN.json') + '\n').encode())
    finally: h.close()


def verify(plan_path):
    path = Path(plan_path); plan = read(path)
    require(sha(path) == path.with_suffix('.sha256').read_text().strip(), 'Plan changed')
    require(plan['source_sha256'] == sources(), 'Frozen code changed')
    require(plan['max_total_new_requests'] == 16 and plan['phases'] == [
        {'name': 'prefix', 'max_new_requests': 4}, {'name': 'natural', 'max_new_requests': 12}], 'Limits changed')
    return plan


class LimitedCapture(CaptureOpener):
    def __init__(self, *args, limit, check, first_sha256=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit, self.check, self.first_sha256 = limit, check, first_sha256

    def open(self, request, timeout):
        self.check()
        require(len(self.rows) < self.limit, 'External HTTP attempt cap')
        if not self.rows and self.first_sha256:
            require(hashlib.sha256(request.data).hexdigest() == self.first_sha256, 'First outgoing request changed')
        return super().open(request, timeout)


def observe(h, model, capture, seconds=300):
    status = None
    while h.terminal is None and len(capture.rows) < capture.limit:
        remaining = seconds - (time.monotonic() - h.started)
        if remaining <= 0:
            status = 'local_time_cap'; break
        model.http.timeout = min(180, remaining)
        try: h._step(model)
        except Exception as exc:
            status = getattr(exc, 'code', 'implementation_error'); break
        if h.terminal is not None: status = h.terminal['outcome']
    return {'status': status or 'local_continuation_cap', 'attempts': len(capture.rows),
            'elapsed_seconds': time.monotonic() - h.started}


def seal(h, capture, outcome, folder, start_round, budget):
    report = h.archive.report()
    actions = [e['payload'] for e in h.archive.events()
               if e['kind'] == 'action_result' and e['payload']['round'] > start_round]
    result = {**outcome, 'terminal': h.terminal, 'new_actions': actions, 'http': capture.rows,
              'content_source_gate': evidence_gate(h), 'remaining': h.remaining(),
              'budget_after': budget.snapshot(), 'archive_integrity': h.archive.verify()}
    save(folder / 'result.json', result); save(folder / 'report.json', report)
    save(folder / 'state.json', {**state(h), 'answer_contract': h.answer_contract})
    with (folder / 'trajectory.jsonl').open('x', encoding='utf-8') as f:
        for event in h.archive.events(): f.write(canonical(event) + '\n')
    return result


def run(plan_path, private_manifest, output):
    plan = verify(plan_path); verify_public(); m = original_manifest(private_manifest)
    require(sha(private_manifest) == plan['private_manifest_sha256'], 'Manifest changed')
    require(bool(os.environ.get('ESR_API_KEY')), 'Missing credential')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT), 'Unfrozen tracked changes')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    budget = Budget(m['budget_path'], output.name, limit=16)
    results = {'prefix': {'status': 'NOT_RUN', 'attempts': 0}, 'natural': {'status': 'NOT_RUN', 'attempts': 0}}
    save(output / 'manifest.json', {'plan': plan, 'plan_sha256': sha(plan_path), 'utc_started': utc(),
        'frozen_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'private_original_manifest': str(Path(private_manifest).resolve()), 'budget_before': budget.before})
    tape = load_prefix(CASE, boundary=3)

    def check():
        verify(plan_path)
        balance = budget.snapshot()
        require(balance['remaining'] >= 16 - balance['this_run'], 'Insufficient shared balance')

    def capture_for(folder, limit, first=None):
        return LimitedCapture(folder, budget, os.environ['ESR_API_KEY'], m['base_url'].rstrip('/') + '/chat/completions',
                              limit=limit, check=check, first_sha256=first)

    active = 'prefix'; h = backend = None
    try:
        folder = output / 'prefix'; folder.mkdir()
        h, _ = replay(tape, folder / 'episode.sqlite'); h.set_answer_contract(INTEGER_ANSWER)
        backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'], timeout_seconds=m['index_identity']['query_timeout_seconds'])
        cap = capture_for(folder, 4, plan['prefix_first_sha256'])
        identity = m['model_identity']
        model = OpenAIModel(identity['endpoint'], identity['model'], revision=identity['revision_label'],
            http=HTTP(allow_network=True, timeout=180, opener=cap), api_key=os.environ['ESR_API_KEY'],
            temperature=identity['temperature'], expected_response_model=identity['expected_response_model'],
            output_parameter=identity['output_parameter'])
        attach_live(h, model, backend)
        outcome = observe(h, model, cap, plan['local_seconds_per_phase'])
        results['prefix'] = seal(h, cap, outcome, folder, 3, budget)
        h.close(); h = None; backend.close(); backend = None
        print(canonical({'phase': 'prefix', **outcome, 'gate': results['prefix']['content_source_gate']}), flush=True)
        if outcome['status'] != 'submitted' or not results['prefix']['content_source_gate']:
            return
        active = 'natural'; folder = output / 'natural'; folder.mkdir()
        question = folder / 'question.txt'; question.write_bytes(tape['header']['question'].encode())
        cap = capture_for(folder, 12)
        outer_result = {}

        class ObservedHarness(Harness):
            def run(self, live_model):
                require(self.config.to_dict() == plan['config'], 'CLI configuration differs from original')
                require(self.answer_contract == INTEGER_ANSWER and self.model_calls == self.backend_calls == 0
                        and not self.groups and not self.exposed, 'CLI did not start fresh with new contract')
                require(self.retriever.identity == plan['index_identity'], 'CLI index identity mismatch')
                require(live_model.identity == identity, 'CLI model identity mismatch')
                self.model_identity = deepcopy(live_model.identity)
                self.archive.append('model_identity', self.model_identity)
                self.clock = time.monotonic; self.started = self.clock()
                outcome = observe(self, live_model, cap, plan['local_seconds_per_phase'])
                outer_result.update(seal(self, cap, outcome, folder, 0, budget))
                return self.terminal

        flags = ['run', '--allow-network', '--accept-counter-estimate', '--base-url', m['base_url'],
            '--model', identity['model'], '--model-revision', identity['revision_label'],
            '--expected-response-model', identity['expected_response_model'], '--temperature', '0',
            '--output-parameter', identity['output_parameter'], '--api-key-env', 'ESR_API_KEY',
            '--sqlite-index', m['index_path'], '--index-id', m['index_id'], '--timeout', str(m['index_identity']['query_timeout_seconds']),
            '--counter', 'utf8_bytes', '--question-file', str(question), '--db', str(folder / 'episode.sqlite')]
        for key in ['max_model_calls', 'max_backend_calls', 'max_actions', 'max_output_tokens',
                    'max_total_output_tokens', 'max_seconds', 'context_limit', 'response_reserve',
                    'max_batch', 'max_queries_per_search', 'context_mode', 'answer_prefix', 'answer_suffix']:
            flags += ['--' + key.replace('_', '-'), str(plan['config'][key])]
        # Official parser/execute/model/retriever/config/schema path. Only transport
        # capture and the external stopping loop are attached by the observer.
        with patch.object(cli, 'HTTP', lambda **kw: HTTP(**kw, opener=cap)), patch.object(cli, 'Harness', ObservedHarness):
            product_report = cli.execute(cli.parser().parse_args(flags))
        save(folder / 'cli-output.json', product_report)
        results['natural'] = outer_result
        print(canonical({'phase': 'natural', 'status': outer_result['status'], 'attempts': outer_result['attempts']}), flush=True)
    except Exception as exc:
        results[active] = {'status': 'stopped_error', 'exception_type': type(exc).__name__,
                          'attempts': len(list((output / active).glob('http/*/attempt-start.json')))}
        save(output / 'exception.json', {'phase': active, 'type': type(exc).__name__})
    finally:
        if h is not None: h.close()
        if backend is not None: backend.close()
        save(output / 'RESULTS.json', {'phases': results, 'budget_before': budget.before,
             'budget_after': budget.snapshot(), 'utc_finished': utc()})
        budget.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('command', choices=['prepare', 'run'])
    p.add_argument('--private-manifest', required=True); p.add_argument('--output', required=True)
    p.add_argument('--report'); p.add_argument('--plan'); a = p.parse_args()
    if a.command == 'prepare': prepare(a.private_manifest, a.output, a.report)
    else: run(a.plan, a.private_manifest, a.output)
