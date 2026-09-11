"""Single-use bounded study; policies and auditors run through the existing harness.

Requires the private historical study root. Never loads reference answers online.
See docs/research/strong_api_esr/FIELD_FEEDBACK_PREREG_20260911.md.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml
from strong_api import (ROOT as REPO, GlobalBudget, LanzClient, Ledger, AnthropicClient,
                        RemoteConfig, UsageBudget, snapshot, write_json, export, episode)
from task_coverage_cases import packets
from esr_harness.audit import ModelAuditor, status
from esr_harness.protocol import canonical, digest
from audit_native_tool_turns import audit as delivery_audit
from audit_strong_api_schemas import anomalies
from strong_api_freeze_guard import checked_index_fingerprint

LABEL = 'FIELD_FEEDBACK_20260911'
START = 1398
QIDS = ['149', '790', '26', '785', '301', '1012', '701', '1044', '718']
PREFIXES = [
    ('count-negative', 'atomic', '20260910T093856532205Z_audit-packet_atomic_count-negative'),
    ('time-negative', 'atomic', '20260910T094026444621Z_audit-packet_atomic_time-negative'),
    ('known-790-original-audit', 'task_first_literal',
     '20260910T094744752967Z_audit-packet_task_first_literal_known-790-original-audit'),
]


def events(directory):
    return [json.loads(line) for line in (directory / 'trajectory.jsonl').read_text(encoding='utf-8').splitlines()]


def check_events(directory):
    rows = events(directory)
    requests = [e for e in rows if e['type'] == 'generation_request']
    generations = [e for e in rows if e['type'] == 'generation']
    ids = [e['request_id'] for e in requests]
    paired = len(ids) == len(set(ids)) == len(generations) and set(ids) == {e['request_id'] for e in generations}
    models = sorted({e['response'].get('model') for e in generations if e.get('response')})
    unknown = sum(e.get('usage') is None for e in generations)
    malformed = [p for e in requests for p in anomalies(e['request'])]
    issue = ('receipt_pairing' if not paired else 'unknown_usage_or_service_error' if unknown
             else 'schema_error' if malformed else 'model_identity_change' if models != ['glm-5.2'] else None)
    return {'requests': len(requests), 'models': models, 'unknown': unknown,
            'schema_problems': malformed, 'issue': issue}


class FrozenInitialReply:
    """Diagnostic only: one archived generation, then exactly one live repair.

    Verify the entire reconstructed initial provider body before replaying it.
    This client is never used by natural policy episodes.
    """
    def __init__(self, client, source):
        self.client, self.source = client, source
        self.identity, self.ledger = client.identity, client.ledger
        self.calls = 0

    def complete(self, messages, purpose):
        self.calls += 1
        if self.calls == 1:
            assert purpose == 'audit'
            assert self.client.body(messages, 4096) == self.source['request'], 'Historical prefix differs'
            self.ledger.append({'type': 'diagnostic_frozen_initial_reply',
                                'source_run_id': self.source['run_id'],
                                'source_request_id': self.source['request_id'],
                                'request_hash': digest(self.source['request']),
                                'reply_hash': digest(self.source['reply']), 'new_remote_request': False})
            return self.source['reply']
        assert self.calls == 2, 'Exactly one repair continuation is allowed'
        assert messages[-2]['content'] == self.source['reply']
        actual = self.client.body(messages, 4096)
        comparable = deepcopy(actual)
        comparable['messages'][-1] = self.source['repair_request']['messages'][-1]
        assert comparable == self.source['repair_request'], 'Repair changed more than the last feedback message'
        return self.client.complete(messages, purpose=purpose)


def load_prefix(root, run_id):
    directory = root / run_id
    rows = events(directory)
    initial = next(e for e in rows if e['type'] == 'generation_request')
    response = next(e for e in rows if e['type'] == 'generation' and e['request_id'] == initial['request_id'])
    blocks = response['response']['content']
    assert len(blocks) == 1 and blocks[0]['name'] == 'audit_report'
    repair = [e['request'] for e in rows if e['type'] == 'generation_request'][1]
    return {'run_id': run_id, 'request_id': initial['request_id'], 'request': initial['request'], 'repair_request': repair,
            'reply': canonical(blocks[0]['input']), 'historical_usage': response['usage']}, json.loads(
                (directory / 'packet.json').read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true', help='Offline integrity checks, no files or API calls')
    args = parser.parse_args()
    root = args.root.resolve()
    settings = yaml.safe_load((REPO / 'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    conditions = snapshot()
    budget = GlobalBudget(root / 'global_budget.sqlite')
    assert budget.request_status()['used'] == START
    assert budget.db.execute("select count(*) from episodes where status='started'").fetchone()[0] == 0
    assert budget.db.execute('select count(*) from episodes').fetchone()[0] + 36 <= 186
    assert settings['provider']['model'] == 'EB-GLM-5.2' and settings['ordered_tool_calls']
    assert not (root / (LABEL + '_STARTED.json')).exists(), 'Single-use experiment; never overwrite a run'
    prefixes = [(*spec[:2], *load_prefix(root, spec[2])) for spec in PREFIXES]
    questions = [json.loads(s) for s in (root / 'dataset_splits/development.questions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(set(row) == {'qid', 'question'} for row in questions)
    assert {row['qid'] for row in questions} == set(QIDS)
    index = Path(settings['dataset_root']) / 'indexes/esr-sqlite-bm25-20260909.sqlite'
    checked_index_fingerprint(root, index, required=True)
    if args.prepare_only:
        print(json.dumps({'prepared': True, 'prefixes': len(prefixes), 'questions': len(questions),
                          'budget': budget.request_status(), 'dirty_status': conditions['dirty_status']}))
        budget.db.close()
        return 0
    assert not conditions['dirty_status'], 'Commit code before inference'
    variants = [('E-off', 'generic'), ('E-soft', 'generic'), ('E-soft', 'field_paths')]
    schedule = [{'qid': qid, 'arm': arm, 'feedback': feedback}
                for i, qid in enumerate(QIDS) for arm, feedback in variants[i % 3:] + variants[:i % 3]]
    plan = {'label': LABEL, 'snapshot': conditions, 'settings': settings, 'start_requests': START,
            'maximum_new_requests': 477, 'maximum_units': 36, 'total_limit': 2000,
            'baseline_paused': True, 'confirmation_sealed': True, 'schedule': schedule,
            'prefix_hashes': {name: digest(source) for name, _, source, _ in prefixes},
            'prereg_sha256': hashlib.sha256((REPO / 'docs/research/strong_api_esr/FIELD_FEEDBACK_PREREG_20260911.md').read_bytes()).hexdigest(),
            'question_file_sha256': hashlib.sha256((root / 'dataset_splits/development.questions.jsonl').read_bytes()).hexdigest(),
            'controller_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_json(root / (LABEL + '_PLAN.json'), plan)
    key = os.getenv('ANTHROPIC_AUTH_TOKEN') or getpass.getpass('ANTHROPIC_AUTH_TOKEN: ')
    assert key
    transport = LanzClient(base_url=os.getenv('ANTHROPIC_BASE_URL', settings['provider']['base_url']),
                           token=key, model=settings['provider']['model'])
    write_json(root / (LABEL + '_STARTED.json'), {'plan_hash': digest(plan), 'timestamp_utc': datetime.now(timezone.utc).isoformat()})
    pause = root / 'PAUSE_NEW_EPISODES.json'
    if pause.exists(): pause.rename(root / (LABEL + '_PRIOR_PAUSE.json'))
    budget.configure_request_limits(2000, START + 6, 'Three frozen failing audit prefixes, two one-request repair conditions')
    packet_results, runs, reviews, smoke_runs = [], [], [], []
    stopped = None

    def packet_run(packet, profile, feedback, source=None):
        assert snapshot()['source_hashes'] == conditions['source_hashes']
        directory = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_field-feedback_' + feedback + '_' + packet['name'])
        directory.mkdir()
        budget.episode(directory.name, 'diagnostic' if source else 'fixture')
        ledger = Ledger(directory / 'ledger.sqlite')
        client = AnthropicClient(transport, UsageBudget(8192), ledger, budget,
            config=RemoteConfig(model=transport.model, max_output_tokens=4096, temperature=0.6,
                                context_operating_cap=128000, max_requests=1 if source else 2, max_tool_calls=4),
            deadline=time.monotonic() + 180)
        auditor = ModelAuditor(FrozenInitialReply(client, source) if source else client,
                               citation_mode='source_spans', profile=profile, repair_feedback=feedback)
        ledger.initialize({'kind': 'frozen_audit_repair' if source else 'fixed_audit_packet',
                           'packet_hash': digest(packet), 'auditor': auditor.identity, 'snapshot': conditions})
        write_json(directory / 'packet.json', packet)
        if source: write_json(directory / 'frozen_prefix.json', source)
        result = {'name': packet['name'], 'profile': profile, 'feedback': feedback,
                  'run_id': directory.name, 'frozen_prefix': bool(source), 'error': None}
        started = time.monotonic()
        try:
            report = auditor.audit(packet['question'], packet['state'], packet['views'])
            result.update(report=report, status=status(report))
        except Exception as exc:
            result['error'] = {'type': type(exc).__name__, 'message': str(exc).replace(key, '[REDACTED]')}
        finally:
            result.update(elapsed_seconds=time.monotonic() - started, usage=client.budget.summary())
            ledger.verify(); export(ledger, directory); ledger.close()
            with budget.db: budget.db.execute("update episodes set status='finished' where id=?", (directory.name,))
        result['checks'] = check_events(directory)
        write_json(directory / 'result.json', result)
        packet_results.append(result)
        print(json.dumps({'event': 'packet', **{k: result[k] for k in ['name', 'feedback', 'status', 'error', 'checks'] if k in result}}), flush=True)
        if result['checks']['issue']: raise RuntimeError(result['checks']['issue'])
        return result

    def run_review(result, directory):
        checked, delivery = check_events(directory), delivery_audit(directory)
        issue = checked['issue'] or ('delivery_error' if delivery['problems'] else None)
        terminal = (result.get('terminal') or {}).get('outcome')
        if terminal in {None, 'service_error'}: issue = issue or 'infrastructure_or_unfinished'
        audit_errors = sum(e['type'] == 'tool' and e['result'].get('error_code') == 'audit_protocol_error' for e in events(directory))
        return {'run_id': directory.name, 'checks': checked, 'delivery': delivery, 'issue': issue,
                'terminal': terminal, 'audit_protocol_errors': audit_errors}

    try:
        for i, (name, profile, source, packet) in enumerate(prefixes):
            for feedback in (['generic', 'field_paths'] if i % 2 == 0 else ['field_paths', 'generic']):
                packet_run(packet, profile, feedback, source)
        valid_negative = lambda r: not r['error'] and r.get('status') in {'contradicted', 'unknown'}
        candidates = [r for r in packet_results if r['feedback'] == 'field_paths']
        gains = sum(valid_negative(r) and not valid_negative(next(c for c in packet_results if c['name'] == r['name'] and c['feedback'] == 'generic')) for r in candidates)
        passed = all(valid_negative(r) for r in candidates) and gains >= 1
        write_json(root / (LABEL + '_PREFIX_GATE.json'), {'passed': passed, 'gains': gains, 'results': packet_results})
        print(json.dumps({'event': 'prefix_gate', 'passed': passed, 'gains': gains}), flush=True)
        if not passed: stopped = 'prefix_gate_not_met'
        if passed:
            budget.configure_request_limits(2000, budget.request_status()['used'] + 12, 'Field-feedback prefix gate passed; two fresh packets and one eight-request synthetic episode')
            positive = next(p for p in packets() if p['name'] == 'quoting-positive')
            positive_result = packet_run(positive, 'task_first_literal', 'field_paths')
            known_result = packet_run(prefixes[-1][3], 'task_first_literal', 'field_paths')
            detected = any(row.get('status') in {'contradicted', 'unknown'} and 'quot' in row.get('need', '').lower()
                           for key, row in known_result.get('report', {}).items() if key in {'target', 'coverage'})
            passed = positive_result.get('status') == 'supported' and not positive_result['error'] and detected and not known_result['error']
            if passed:
                cfg = deepcopy(settings); cfg['max_remote_requests_per_episode'] = 8
                cfg['auditor'].update(profile='task_first_literal', repair_feedback='field_paths')
                result, directory = episode(root, budget, transport, cfg,
                    question='Who was the first director of the fictional Orin Observatory? Return the name enclosed in literal double quotation marks.',
                    qid='synthetic-field-feedback-orin', arm='E-soft', category='fixture')
                smoke_runs.append(directory.name)
                review = run_review(result, directory)
                write_json(directory / 'field_feedback_review.json', review)
                passed = review['terminal'] == 'submitted' and not review['issue'] and review['audit_protocol_errors'] == 0
                if review['issue']: raise RuntimeError(review['issue'])
            write_json(root / (LABEL + '_SMOKE_GATE.json'), {'passed': passed, 'smoke_runs': smoke_runs,
                                                           'positive': positive_result, 'known_prefix': known_result})
            print(json.dumps({'event': 'smoke_gate', 'passed': passed, 'smoke_runs': smoke_runs}), flush=True)
            if not passed: stopped = 'smoke_gate_not_met'
        if passed:
            budget.configure_request_limits(2000, budget.request_status()['used'] + 459, 'All gates passed; frozen nine-question three-condition development cohort including one judge per answer')
            candidate_error_streak = 0
            for item in schedule:
                if pause.exists(): stopped = 'cooperative_pause'; break
                assert snapshot()['source_hashes'] == conditions['source_hashes']
                budget.ensure_request_capacity(16 + len(runs) + 1)
                cfg = deepcopy(settings)
                cfg['auditor'].update(profile='task_first_literal', repair_feedback=item['feedback'])
                result, directory = episode(root, budget, transport, cfg,
                    question=next(row['question'] for row in questions if row['qid'] == item['qid']),
                    qid=item['qid'], arm=item['arm'], category='development', index=index)
                runs.append(directory.name)
                review = {**run_review(result, directory), **item}
                reviews.append(review); write_json(directory / 'field_feedback_review.json', review)
                print(json.dumps({'event': 'cohort_review', **review, 'budget': budget.request_status()}), flush=True)
                if review['issue']: stopped = review['issue']; break
                if item['feedback'] == 'field_paths':
                    candidate_error_streak = candidate_error_streak + 1 if review['audit_protocol_errors'] else 0
                    if candidate_error_streak >= 2: stopped = 'candidate_repeated_audit_protocol_failure'; break
    except Exception as exc:
        stopped = 'controller_' + type(exc).__name__
        write_json(root / (LABEL + '_ERROR.json'), {'type': type(exc).__name__, 'message': str(exc).replace(key, '[REDACTED]')})
    finally:
        record = {'runs': runs, 'reviews': reviews, 'packets': packet_results, 'smoke_runs': smoke_runs,
                  'stop_reason': stopped, 'budget': budget.request_status(), 'no_online_worker': True}
        write_json(root / (LABEL + '_ONLINE_FINISHED.json'), record)
        if not pause.exists(): write_json(pause, {'reason': stopped or 'Field feedback online cohort complete', 'runs': runs})
        print(json.dumps({'event': 'online_finished', 'runs': len(runs), 'stop_reason': stopped, 'budget': budget.request_status()}), flush=True)
    judge_exit = None
    if runs:
        child_env = os.environ.copy(); child_env['ANTHROPIC_AUTH_TOKEN'] = key
        with (root / (LABEL + '_judge.log')).open('x', encoding='utf-8') as out:
            child = subprocess.run([sys.executable, '-B', '-X', 'utf8', 'scripts/evaluate_strong_api.py',
                '--max-requests-per-answer', '1', '--run-dirs', *runs], cwd=REPO, env=child_env, stdout=out, stderr=subprocess.STDOUT)
        judge_exit = child.returncode
        del child_env
    write_json(root / (LABEL + '_FINISHED.json'), {**record, 'judge_exit': judge_exit,
               'budget': budget.request_status(), 'new_requests': budget.request_status()['used'] - START})
    print(json.dumps({'event': 'finished', 'stop_reason': stopped, 'judge_exit': judge_exit, 'budget': budget.request_status()}), flush=True)
    budget.db.close()
    return 1 if stopped or judge_exit else 0


if __name__ == '__main__':
    sys.exit(main())
