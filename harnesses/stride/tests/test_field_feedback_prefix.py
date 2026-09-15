from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from stride_search.contract import canonical

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/field_feedback'))
from prefix_replay import (PrefixMismatch, load_prefix, next_payload, prefix_event_diff,
                           replay, request_diff, timing_check)
from pilot_gate import gate
from reproduce import sha

CASE = Path(__file__).resolve().parents[1] / 'artifacts/20260914-hard12-a3/q778'


def test_prefix_and_exact_r5_only_error_messages_differ(tmp_path):
    tape = load_prefix(CASE)
    a, ma = replay(tape, tmp_path / 'a.sqlite')
    b, mb = replay(tape, tmp_path / 'b.sqlite', 'field')
    try:
        wire_a, wire_b = next_payload(a, ma), next_payload(b, mb)
        assert canonical(wire_a).encode() == (CASE / 'http/005/request.body').read_bytes()
        assert not prefix_event_diff(tape['events'], list(a.archive.events()))
        cid = tape['responses'][-1]['choices'][0]['message']['tool_calls'][0]['id']
        assert request_diff(wire_a, wire_b, cid)['decoded_difference_count'] == 2
        assert a.model_calls == b.model_calls == 4 and a.terminal is b.terminal is None
        assert a.remaining() == b.remaining() and a.config.max_model_calls == 64
        assert not a.final_phase() and not b.final_phase()
        assert a.search_cache == b.search_cache and a.exposed == b.exposed
        assert timing_check(CASE, tape['events'])['exact_time_balance_reconstructible'] is False
    finally:
        a.close(); b.close()


def test_replay_cannot_use_suffix_or_unknown_backend(tmp_path):
    tape = load_prefix(CASE); h, model = replay(tape, tmp_path / 'prefix.sqlite')
    try:
        with pytest.raises(PrefixMismatch):
            model.send(next_payload(h, model))
        with pytest.raises(PrefixMismatch):
            h.retriever.search('not in prefix', 3)
        with pytest.raises(PrefixMismatch):
            h.retriever.compile_query('not in prefix')
    finally:
        h.close()


def test_difference_whitelist_rejects_extra_instruction(tmp_path):
    tape = load_prefix(CASE); a, ma = replay(tape, tmp_path / 'a.sqlite'); b, mb = replay(tape, tmp_path / 'b.sqlite', 'field')
    try:
        wa, wb = next_payload(a, ma), next_payload(b, mb)
        cid = tape['responses'][-1]['choices'][0]['message']['tool_calls'][0]['id']
        wb['messages'][0]['content'] += 'synthetic additional instruction'
        with pytest.raises(AssertionError):
            request_diff(wa, wb, cid)
    finally:
        a.close(); b.close()


def test_gate_never_treats_cli_flag_as_readiness(tmp_path):
    plan = tmp_path / 'plan.json'; plan.write_text(json.dumps({'readiness': 'BLOCKED_PREFIX_RECONSTRUCTION'}))
    plan.with_suffix('.sha256').write_text(sha(plan))
    assert gate(plan)['status'] == 'LIVE_NOT_RUN'
    with pytest.raises(ValueError, match='BLOCKED_PREFIX_RECONSTRUCTION'):
        gate(plan, execute_approved_pilot=True)
    plan.write_text('{}')
    with pytest.raises(ValueError, match='plan changed'):
        gate(plan)
