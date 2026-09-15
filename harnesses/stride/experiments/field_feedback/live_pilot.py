"""Fixed-prefix real continuations; external observation limits, unchanged policy.

The historical OFFLINE_ONLY plan is immutable. This separate entry point requires
a new frozen plan and an existing shared ledger. No retries or historical suffixes.
"""
import argparse
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

from stride_search.contract import ContractError, canonical
from stride_search.cpu_index import SQLiteFTS5
from stride_search.providers import HTTP, OpenAIModel

from prefix_replay import (differences, load_prefix, next_payload, prefix_event_diff,
                           replay, request_diff, state)
from reproduce import read, sha, write

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'harnesses/stride/examples'))
from trace_question_a3 import Budget, CaptureOpener, utc

ORDER = ('A1', 'B1', 'B2', 'A2')
CASE = ROOT / 'harnesses/stride/artifacts/20260914-hard12-a3/q778'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inventory():
    paths = list((ROOT / 'harnesses/stride/src/stride_search').glob('*.py'))
    paths += list(Path(__file__).parent.glob('*.py'))
    paths += [ROOT / 'harnesses/stride/examples/trace_question_a3.py']
    paths += list((ROOT / 'harnesses/stride/tests').glob('test*field_feedback*.py'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def original_manifest(path):
    expected = read(CASE / 'SOURCE_FILE_HASHES.json')['manifest.json']
    require(sha(path) == expected, 'Original private manifest hash mismatch')
    m = read(path)
    require(m['config'] == read(CASE / 'manifest.json')['config'], 'Original config mismatch')
    require(m['model_identity']['temperature'] == 0, 'Unexpected temperature')
    require(m['model_identity']['expected_response_model'], 'Missing returned model identity')
    require(m['base_url'] == m['model_identity']['endpoint'], 'Deployment mismatch')
    return m


def verify_public():
    for name, expected in read(CASE.parent / 'MANIFEST.sha256.json').items():
        if name.startswith('q778/') or name == 'ARCHIVE_HEAD_MAP.json':
            require(sha(CASE.parent / name) == expected, 'Published source integrity mismatch')


def attach_live(h, model, backend, clock=time.monotonic):
    """Switch adapters without touching discrete state, cache keys or policy inputs."""
    require(backend.identity == h.retriever.identity, 'Backend identity changed')
    require(backend.capabilities == h.search_capabilities, 'Backend capabilities changed')
    require(not [d for d in differences(h.model_identity, model.identity)
                 if d['path'] != '/endpoint'], 'Model configuration changed')
    h.retriever = backend
    h.model_identity = deepcopy(model.identity)
    h.clock = clock
    h.started = clock()  # New continuation origin; NOT historical elapsed time.
    return h.started


class GuardedCapture(CaptureOpener):
    def __init__(self, *args, check=lambda: None, first_sha256=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.check = check
        self.first_sha256 = first_sha256

    def open(self, request, timeout):
        self.check()
        if len(self.rows) >= 4:
            raise ContractError('pilot_attempt_cap', 'External attempt cap', fatal=True)
        if not self.rows and self.first_sha256:
            require(hashlib.sha256(request.data).hexdigest() == self.first_sha256,
                    'First outgoing body differs from frozen request')
        return super().open(request, timeout)


def continue_slot(h, model, capture, *, seconds=300, clock=time.monotonic):
    """Observe up to four sends. Never manufacture a Harness terminal at the cap.

    Check time between complete steps; bound every send by the remaining local
    time. A transport timeout stops the queue. A completed step may include the
    original bounded CPU work; no additional step starts after the deadline.
    """
    started = h.started
    status = None
    while h.terminal is None and len(capture.rows) < 4:
        remaining = seconds - (clock() - started)
        if remaining <= 0:
            status = 'local_time_cap'
            break
        model.http.timeout = min(180, remaining)
        try:
            h._step(model)
        except ContractError as exc:
            status = exc.code
            break
        except Exception:
            status = 'implementation_error'
            break
        if h.terminal is not None:
            status = h.terminal['outcome']
    status = status or 'local_continuation_cap'
    return {'status': status, 'attempts': len(capture.rows),
            'seconds': clock() - started,
            'stop_queue': status not in ('submitted', 'abstained', 'local_continuation_cap', 'local_time_cap')}


def prepare(private_manifest, private_output, report):
    verify_public()
    m = original_manifest(private_manifest)
    private_output = Path(private_output); private_output.mkdir(parents=True, exist_ok=False)
    report = Path(report); report.mkdir(parents=True, exist_ok=False)
    tape = load_prefix(CASE)
    a, ma = replay(tape, private_output / 'A.sqlite')
    b, mb = replay(tape, private_output / 'B.sqlite', 'field')
    try:
        wa, wb = next_payload(a, ma), next_payload(b, mb)
        require(canonical(wa).encode() == (CASE / 'http/005/request.body').read_bytes(), 'R5 mismatch')
        require(not prefix_event_diff(tape['events'], list(a.archive.events())), 'Prefix event mismatch')
        cid = tape['responses'][-1]['choices'][0]['message']['tool_calls'][0]['id']
        diff = request_diff(wa, wb, cid)
        sa, sb = state(a), state(b)
        require({d['path'] for d in differences(sa, sb)} == {
            '/groups/3/messages/1/content', '/group_refs/3', '/feedback/message'}, 'Unexpected state difference')
        backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'],
                             timeout_seconds=m['index_identity']['query_timeout_seconds'])
        try:
            require(backend.identity == m['index_identity'] == a.retriever.identity, 'Index mismatch')
        finally:
            backend.close()
        check = {'r5_bytes_exact': True, 'first_four_requests_exact': ma.comparisons,
                 'discrete_state_equal_except_feedback': True, 'real_index_identity_matches': True,
                 'index_queries': 0, 'real_model_requests': 0,
                 'source_prefix_head': tape['events'][-1]['hash'], 'source_prefix_seq': 79}
        write(report / 'PREFIX_CHECK.json', check)
        write(report / 'REQUEST_DIFF.json', diff)
        identity = {k: v for k, v in m['model_identity'].items() if k != 'endpoint'}
        plan = {'kind': 'q778_fixed_prefix_continuation', 'authorization': 'explicit user approval before preparation',
                'reviewed_parent': '80c0868c0987bb83f07f6290a4ae33219c274e9a',
                'order': list(ORDER), 'max_attempts_per_slot': 4, 'max_total_attempts': 16,
                'feedback': {'A': 'legacy', 'B': 'field'}, 'config': m['config'],
                'remaining_after_prefix': a.remaining(), 'phase': 'RESEARCH',
                'local_seconds': 300, 'http_timeout_ceiling': 180,
                'time_semantics': 'New real monotonic origin after replay, same 300s observation window per slot. Check between complete steps; HTTP timeout <= remaining window. Original bounded CPU step may finish after window; no next step. Historical elapsed unknown, no UTC substitution.',
                'historical_monotonic_elapsed': None, 'outer_caps_visible_to_model': False,
                'model_identity': identity, 'index_identity': m['index_identity'],
                'private_manifest_sha256': sha(private_manifest), 'source_sha256': inventory(),
                'first_request_sha256': {k: hashlib.sha256(canonical(w).encode()).hexdigest()
                                         for k, w in [('A', wa), ('B', wb)]},
                'prefix_check_sha256': sha(report / 'PREFIX_CHECK.json'),
                'request_diff_sha256': sha(report / 'REQUEST_DIFF.json'),
                'budget': 'Existing original ledger only; atomic charge before send including failures/unknowns; no reset.',
                'stop_queue_on': ['HTTP/transport/auth/rate-limit/timeout', 'truncation', 'identity mismatch',
                                  'integrity failure', 'backend failure', 'insufficient budget'],
                'automatic_retries': 0, 'judge_requests': 0, 'fill_unused_attempts': False,
                'temperature_zero_deterministic': False, 'original_batch_labels_unchanged': True}
        write(report / 'PLAN.json', plan)
        (report / 'PLAN.sha256').write_bytes((sha(report / 'PLAN.json') + '\n').encode())
    finally:
        a.close(); b.close()


def verify_plan(path):
    path = Path(path)
    require(sha(path) == path.with_suffix('.sha256').read_text().strip(), 'Frozen plan changed')
    plan = read(path)
    require(plan['source_sha256'] == inventory(), 'Frozen implementation changed')
    require(plan['order'] == list(ORDER) and plan['max_total_attempts'] == 16
            and plan['max_attempts_per_slot'] == 4 and plan['local_seconds'] == 300, 'Plan limits changed')
    for filename, key in [('PREFIX_CHECK.json', 'prefix_check_sha256'), ('REQUEST_DIFF.json', 'request_diff_sha256')]:
        require(sha(path.parent / filename) == plan[key], 'Frozen acceptance changed')
    return plan


def slot_result(h, capture, outcome, before, prefix_seq):
    events = [e for e in h.archive.events() if e['seq'] > prefix_seq]
    actions = [e['payload'] for e in events if e['kind'] == 'action_result']
    return {**outcome, 'terminal': deepcopy(h.terminal), 'remaining': h.remaining(),
            'new_tools': actions, 'new_action_slots': h.action_slots - before['action_slots'],
            'new_declared_calls': h.declared_calls - before['declared_calls'],
            'new_backend_calls': h.backend_calls - before['backend_calls'],
            'new_output_charged': h.output_charged - before['output_charged'],
            'http': deepcopy(capture.rows), 'archive_integrity': h.archive.verify()}


def run(plan_path, private_manifest, output):
    plan = verify_plan(plan_path)
    verify_public()
    m = original_manifest(private_manifest)
    require(sha(private_manifest) == plan['private_manifest_sha256'], 'Manifest changed')
    require(m['config'] == plan['config'], 'Plan config changed')
    key = os.environ.get('ESR_API_KEY')
    require(bool(key), 'Missing local credential')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT),
            'Tracked changes after freeze')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    budget = Budget(m['budget_path'], output.name, limit=16)
    results = {label: {'status': 'NOT_RUN', 'attempts': 0} for label in ORDER}
    write(output / 'manifest.json', {'utc_started': utc(), 'plan': plan, 'plan_sha256': sha(plan_path),
          'frozen_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'private_original_manifest': str(Path(private_manifest).resolve()), 'model_identity': m['model_identity'],
          'budget_before': budget.before})
    tape = load_prefix(CASE)
    queue_error = None
    try:
        for label in ORDER:
            h = backend = None
            folder = output / label; folder.mkdir()
            try:
                verify_plan(plan_path)
                mode = plan['feedback'][label[0]]
                h, captured = replay(tape, folder / 'episode.sqlite', mode)
                expected = plan['first_request_sha256'][label[0]]
                require(hashlib.sha256(canonical(next_payload(h, captured)).encode()).hexdigest() == expected,
                        'Independent prefix request mismatch')
                before = state(h); prefix_seq = h.archive.seq
                backend = SQLiteFTS5(m['index_path'], index_id=m['index_id'],
                                     timeout_seconds=m['index_identity']['query_timeout_seconds'])
                require(backend.identity == plan['index_identity'], 'Live index identity mismatch')

                def before_send():
                    verify_plan(plan_path)
                    s = budget.snapshot()
                    require(s['remaining'] >= 16 - s['this_run'], 'Insufficient shared budget')

                capture = GuardedCapture(folder, budget, key, m['base_url'].rstrip('/') + '/chat/completions',
                                         check=before_send, first_sha256=expected)
                identity = m['model_identity']
                model = OpenAIModel(identity['endpoint'], identity['model'], revision=identity['revision_label'],
                    http=HTTP(allow_network=True, timeout=180, opener=capture), api_key=key,
                    temperature=identity['temperature'], expected_response_model=identity['expected_response_model'],
                    output_parameter=identity['output_parameter'])
                # Compare with the real adapter before enabling the real clock/sends.
                require(canonical(next_payload(h, model)) == canonical(next_payload(h, captured)), 'Live wire changed')
                attach_live(h, model, backend)
                write(folder / 'manifest.json', {'slot': label, 'feedback': mode, 'prefix_end_seq': prefix_seq,
                      'time_semantics': plan['time_semantics'], 'local_monotonic_start': h.started,
                      'model_identity': model.identity, 'config': h.config.to_dict(), 'remaining': h.remaining()})
                outcome = continue_slot(h, model, capture, seconds=plan['local_seconds'])
                result = slot_result(h, capture, outcome, before, prefix_seq)
                result['budget_after'] = budget.snapshot()
                # The first actual send is checked against the frozen offline request.
                if capture.rows:
                    require(sha(folder / 'http/001/request.body') == expected, 'First actual HTTP body mismatch')
                write(folder / 'result.json', result)
                write(folder / 'state.json', state(h))
                with (folder / 'trajectory.jsonl').open('x', encoding='utf-8') as f:
                    for event in h.archive.events():
                        f.write(canonical(event) + '\n')
                write(folder / 'FILE_SHA256.json', {p.relative_to(folder).as_posix(): sha(p)
                      for p in sorted(folder.rglob('*')) if p.is_file() and 'sqlite' not in p.name})
                results[label] = result
                print(canonical({'slot': label, 'status': outcome['status'], 'attempts': outcome['attempts'],
                                 'remaining': result['budget_after']['remaining']}), flush=True)
                if outcome['stop_queue']:
                    break
            except Exception as exc:
                queue_error = type(exc).__name__  # Never publish private exception text.
                results[label] = {'status': 'queue_integrity_or_setup_error', 'exception_type': queue_error,
                                  'attempts': len(list(folder.glob('http/*/attempt-start.json')))}
                write(folder / 'exception.json', results[label])
                break
            finally:
                if h is not None:
                    h.close()
                if backend is not None:
                    backend.close()
    finally:
        write(output / 'RESULTS.json', {'slots': results, 'budget_before': budget.before,
              'budget_after': budget.snapshot(), 'queue_error': queue_error, 'utc_finished': utc()})
        budget.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare')
    a.add_argument('--private-manifest', required=True); a.add_argument('--private-output', required=True)
    a.add_argument('--report', required=True)
    a = sub.add_parser('run')
    a.add_argument('--plan', required=True); a.add_argument('--private-manifest', required=True)
    a.add_argument('--output', required=True)
    a = p.parse_args()
    if a.command == 'prepare':
        prepare(a.private_manifest, a.private_output, a.report)
    else:
        run(a.plan, a.private_manifest, a.output)
