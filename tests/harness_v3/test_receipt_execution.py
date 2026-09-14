import json

from .conftest import send


def test_invalid_cursor_query_is_not_executed_and_receipts_reach_next_turn(h):
    before = h.state['backend_calls']
    rows = send(h, [
        ('open_page', {'cursor': 'k4', 'query': 'a magazine sale'}),
        ('search', {'query': 'tournament'}),
    ])
    assert rows[0]['code'] == 'arguments_invalid'
    assert rows[0]['committed'] is False
    assert rows[0]['executed'] is False
    assert rows[1]['code'] == 'not_executed'
    assert rows[1]['executed'] is False
    assert h.state['backend_calls'] == before
    decision = h.begin()
    receipts = [json.loads(m['content']) for m in decision.payload['messages'] if m['role'] == 'tool']
    assert receipts[-2:] == rows


def test_dispatch_failure_remains_an_execution_attempt(h):
    rows = send(h, ('open_page', {'ref': 'd999'}))
    assert rows[0]['code'] == 'unpublished_document'
    assert rows[0]['executed'] is True
    assert rows[0]['committed'] is False
    assert h.state['backend_calls'] == 0
