"""Offline analysis preserves raw argument errors and accepts supported reply forms."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from analyze_repair_surface_study import proposed_report
from esr_harness.protocol import HarnessError


@pytest.mark.parametrize('form', ['native', 'text_then_native', 'text', 'text_suffix'])
def test_report_decoding_preserves_quotes_and_verdict(form):
    report = {'target': {'status': 'contradicted', 'need': 'Return "Nera".'}}
    native = {'type': 'tool_use', 'name': 'audit_report', 'input': report}
    if form in {'native', 'text_then_native'}:
        blocks = ([{'type': 'text', 'text': 'Checking the report.'}]
                  if form == 'text_then_native' else []) + [native]
        response = {'stop_reason': 'tool_use', 'content': blocks}
    else:
        text = json.dumps(report) + ('</tool_call>' if form == 'text_suffix' else '')
        response = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': text}]}
    original = deepcopy(response)
    assert proposed_report(response) == report
    assert response == original


def test_decoder_does_not_select_first_of_multiple_audit_calls():
    call = {'type': 'tool_use', 'name': 'audit_report', 'input': {}}
    with pytest.raises(AssertionError):
        proposed_report({'stop_reason': 'tool_use', 'content': [call, deepcopy(call)]})


def test_decoder_preserves_corrupted_parameter_name_for_validation():
    bad = {'target<arg_key>coverage': {'status': 'supported', 'need': ''}, 'claims': []}
    response = {'stop_reason': 'tool_use', 'content': [
        {'type': 'tool_use', 'name': 'audit_report', 'input': bad}]}
    assert proposed_report(response) == bad
    assert 'target' not in proposed_report(response)


def test_decoder_does_not_repair_malformed_text_json():
    with pytest.raises(HarnessError):
        proposed_report({'stop_reason': 'end_turn', 'content': [
            {'type': 'text', 'text': '{"target":'}]})
