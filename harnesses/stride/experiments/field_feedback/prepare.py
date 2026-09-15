"""OFFLINE_ONLY: replay, compare and freeze a non-executed continuation plan."""
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path

from stride_search.contract import canonical, digest
from matrix import acceptance_matrix
from prefix_replay import (differences, load_prefix, next_payload, prefix_event_diff,
                           read_bytes, replay, request_diff, state, timing_check)
from reproduce import DATA_COMMIT, RELEASE, read, sha, write


def prepare(artifacts, private_output, report_output):
    artifacts = Path(artifacts).resolve(); private_output = Path(private_output).resolve()
    report_output = Path(report_output).resolve(); case = artifacts / 'q778'
    inventory = read(artifacts / 'MANIFEST.sha256.json')
    # Verify the public chain against the public inventory, never the private head.
    for name, expected in inventory.items():
        if name.startswith('q778/') or name == 'ARCHIVE_HEAD_MAP.json':
            assert sha(artifacts / name) == expected, name
    tape = load_prefix(case)
    private_output.mkdir(parents=True, exist_ok=False)
    report_output.mkdir(parents=True, exist_ok=False)
    h_a, m_a = replay(tape, private_output / 'A-prefix.sqlite')
    h_b, m_b = replay(tape, private_output / 'B-prefix.sqlite', mode='field')
    try:
        a = next_payload(h_a, m_a); b = next_payload(h_b, m_b)
        original = (case / 'http/005/request.body').read_bytes()
        same_json = read_bytes(original) == a
        same_bytes = canonical(a).encode('utf-8') == original
        event_diff = prefix_event_diff(tape['events'], list(h_a.archive.events()))
        if not same_json or not same_bytes or event_diff:
            write(report_output / 'PREFIX_REPLAY_CHECK.json', {'status': 'BLOCKED_PREFIX_RECONSTRUCTION',
                'r5_json_equal': same_json, 'r5_serializer_bytes_equal': same_bytes,
                'event_differences': event_diff, 'real_model_calls': 0})
            raise ValueError('BLOCKED_PREFIX_RECONSTRUCTION: discrete state/request mismatch')
        failed = tape['responses'][-1]['choices'][0]['message']['tool_calls']
        assert len(failed) == 1
        diff = request_diff(a, b, failed[0]['id'])
        sa, sb = state(h_a), state(h_b)
        state_diff = differences(sa, sb)
        allowed_state = {f'/groups/{tape["boundary"] - 1}/messages/1/content',
                         f'/group_refs/{tape["boundary"] - 1}', '/feedback/message'}
        assert {d['path'] for d in state_diff} == allowed_state
        # Raw replay states and prepared requests stay private, including their original source text.
        for label, value in [('A', a), ('B', b)]:
            (private_output / f'{label}-first-request.body').write_bytes(canonical(value).encode('utf-8'))
        write(private_output / 'A-state.json', sa); write(private_output / 'B-state.json', sb)
        timing = timing_check(case, tape['events'])
        status = 'BLOCKED_PREFIX_RECONSTRUCTION' if not timing['exact_time_balance_reconstructible'] else 'READY'
        source_identity = read(artifacts / 'ARCHIVE_HEAD_MAP.json')['q778']
        check = {'status': status, 'discrete_state_reconstructed': True, 'boundary_round': tape['boundary'],
            'source_data_commit': DATA_COMMIT, 'source_core_release': RELEASE,
            'source_public_head': source_identity['published_head'], 'source_prefix_head': tape['events'][-1]['hash'],
            'source_prefix_end_seq': tape['events'][-1]['seq'], 'prefix_event_count': len(tape['events']),
            'prefix_request_checks_A': m_a.comparisons, 'prefix_request_checks_B': m_b.comparisons,
            'a_prefix_event_payloads_equal_except_elapsed': not event_diff,
            'r5_json_equal': same_json, 'r5_serializer_bytes_equal': same_bytes,
            'original_r5_body_sha256': hashlib.sha256(original).hexdigest(),
            'a_first_body_sha256': hashlib.sha256(canonical(a).encode()).hexdigest(),
            'b_first_body_sha256': hashlib.sha256(canonical(b).encode()).hexdigest(),
            'remaining': h_a.remaining(), 'phase': sa['phase'], 'state_fields_hashed': {k: digest(v) for k, v in sa.items()},
            'a_b_state_differences': sorted(allowed_state), 'all_other_state_fields_equal': True,
            'documents': len(sa['docs']), 'evidence_windows': len(sa['evidence']),
            'delivered_documents': len(sa['published_docs']), 'delivered_evidence': len(sa['exposed']),
            'query_cache_entries': len(sa['search_cache']), 'timing': timing,
            'historical_model_responses_replayed_per_arm': 4, 'historical_backend_responses_replayed_per_arm': 7,
            'prefix_cost_recharged': False, 'real_model_calls': 0, 'production_index_queries': 0,
            'historical_suffix_model_responses_loaded': 0, 'gold_in_replay_inputs': False,
            'request_oracle_is_only_compared_after_reconstruction': True,
            'original_raw_model_arguments_unchanged': True}
        write(report_output / 'PREFIX_REPLAY_CHECK.json', check)
        write(report_output / 'REQUEST_DIFF_A_B.json', diff)
        acceptance = acceptance_matrix()
        assert acceptance['same_acceptance_set']
        write(report_output / 'ACCEPTANCE_DIFF.json', acceptance)
        repo = Path(__file__).resolve().parents[4]
        paths = ['harnesses/stride/src/stride_search/contract.py', 'harnesses/stride/src/stride_search/engine.py',
                 'harnesses/stride/src/stride_search/validation_feedback.py',
                 'harnesses/stride/tests/test_field_feedback.py', 'harnesses/stride/tests/test_field_feedback_prefix.py']
        paths += [p.relative_to(repo).as_posix() for p in Path(__file__).parent.glob('*.py')]
        source_hashes = {p: sha(repo / p) for p in sorted(paths)}
        manifest = read(case / 'manifest.json')
        plan = {'status': 'LIVE_NOT_RUN', 'mode': 'OFFLINE_ONLY', 'approval_granted': False,
            'readiness': status, 'blocking_items': ['Original R4 monotonic elapsed-time balance is not recorded'],
            'data_commit': DATA_COMMIT, 'core_release': RELEASE, 'source_public_head': source_identity['published_head'],
            'source_prefix_head': tape['events'][-1]['hash'], 'source_prefix_end_round': 4,
            'source_manifest_original_sha256': read(case / 'SOURCE_FILE_HASHES.json')['manifest.json'],
            'prefix_check_sha256': sha(report_output / 'PREFIX_REPLAY_CHECK.json'),
            'request_diff_sha256': sha(report_output / 'REQUEST_DIFF_A_B.json'),
            'source_sha256': source_hashes, 'order': ['A1', 'B1', 'B2', 'A2'],
            'slots': [{'slot': label, 'feedback': 'legacy' if label[0] == 'A' else 'field',
                       'status': 'LIVE_NOT_RUN', 'max_new_attempts': 4, 'attempts_used': 0,
                       'independent_same_prefix': True} for label in ['A1', 'B1', 'B2', 'A2']],
            'max_total_new_attempts': 16, 'config': manifest['config'],
            'remaining_after_prefix': h_a.remaining(), 'remaining_time_seconds': None,
            'model_identity_public': manifest['model_identity'], 'http_timeout_seconds': 180,
            'index_identity': manifest['index_identity'], 'new_queries_backend': 'original read-only CPU SQLite FTS5',
            'local_cap_is_external_to_harness': True, 'local_cap_status': 'local_continuation_cap',
            'cap_does_not_change_phase_or_config': True, 'cap_does_not_create_terminal': True,
            'stop_on_success': True, 'fill_unused_attempts': False, 'automatic_retries': 0,
            'auditor_attempts': 0, 'judge_attempts': 0, 'historical_prefix_cost_is_new_charge': False,
            'budget_policy': {'existing_ledger_required': True, 'create_or_reset_ledger': False,
                'atomic_charge_before_send': True, 'attempted_unknowns_charged': True,
                'last_reported_remaining': 449, 'current_balance_verified': False,
                'balance_checked_at_send': True, 'shared_and_local_limits_both_enforced': True},
            'pre_send_gates': ['separate explicit authorization', 'exact prefix including time balance',
                'frozen code and source files match', 'private original manifest hash and deployment match',
                'existing global ledger balance covers the registered remaining plan', 'production index identity matches'],
            'stop_entire_queue_on': ['401', '403', '429', 'timeout', 'any transport/HTTP failure',
                'model identity change', 'truncated/incomplete response', 'unknown completion', 'integrity failure',
                'production backend failure', 'insufficient shared budget'],
            'unstarted_slots_after_stop': 'NOT_RUN', 'within_run_caps': 'all original Config and remaining limits',
            'time_policy': 'exact historical prefix elapsed + new continuation monotonic elapsed; copying and offline preparation excluded',
            'suffix_policy': 'new model responses and real backend results only; no historical suffix or simulated new retrieval',
            'metrics': ['self-generated string answer', 'legal submitted finish', 'answer information preserved',
                'delivered refs valid', 'first correction decision', 'first legal submission decision',
                'wrong answer or abstention', 'unrelated search or continued loop',
                'all new HTTP/actions/backend calls/provider token-cache usage/latencies'],
            'original_batch_labels_mutable': False, 'new_official_judge_labels': False,
            'scope': 'paired local development-prefix experiment, not a new 12-case evaluation',
            'temperature_zero_is_determinism_guarantee': False}
        write(report_output / 'EXPERIMENT_PLAN.json', plan)
        (report_output / 'EXPERIMENT_PLAN.sha256').write_text(sha(report_output / 'EXPERIMENT_PLAN.json') + '\n', encoding='ascii')
        print(canonical({'status': status, 'r5_exact': same_bytes, 'whitelist_passed': True,
                         'acceptance_matrix_cases': acceptance['cases'], 'real_model_calls': 0}))
    finally:
        h_a.close(); h_b.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts', required=True); p.add_argument('--private-output', required=True)
    p.add_argument('--report-output', required=True)
    a = p.parse_args(); prepare(a.artifacts, a.private_output, a.report_output)
