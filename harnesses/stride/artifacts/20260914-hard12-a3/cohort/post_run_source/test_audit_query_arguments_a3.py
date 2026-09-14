import json
import pytest
from audit_query_arguments_a3 import audit


def test_string_queries_does_not_count_characters_and_preserves_sources(tmp_path):
    raw_dir = tmp_path / 'http/001'; raw_dir.mkdir(parents=True)
    body = json.dumps({'choices': [{'message': {'tool_calls': [
        {'id': 'a', 'function': {'name': 'search', 'arguments': json.dumps({'queries': ['alpha', 'beta']})}},
        {'id': 'b', 'function': {'name': 'search', 'arguments': json.dumps({'queries': 'alpha,beta'})}},
    ]}}]}).encode()
    (raw_dir / 'response.body').write_bytes(body)
    (tmp_path / 'episode.sqlite').write_bytes(b'synthetic opaque archive sentinel')
    original = json.dumps({'metrics': {'declared_search_queries': 12}}).encode()
    for name in ('POSTHOC_CHECKS', 'REVIEW_DIGEST'):
        (tmp_path / (name + '.json')).write_bytes(original)
    audit(tmp_path)
    result = json.loads((tmp_path / 'QUERY_ARGUMENTS_AUDIT.json').read_text())
    assert result['declared_array_query_items'] == 2 and result['invalid_shape_calls'] == 1
    assert (raw_dir / 'response.body').read_bytes() == body
    assert (tmp_path / 'episode.sqlite').read_bytes() == b'synthetic opaque archive sentinel'
    for name in ('POSTHOC_CHECKS', 'REVIEW_DIGEST'):
        assert (tmp_path / (name + '.before-query-count-correction.json')).read_bytes() == original
        assert json.loads((tmp_path / (name + '.json')).read_text())['metrics']['declared_search_queries'] == 2


def test_rejects_sealed_case_before_any_mutation(tmp_path):
    (tmp_path / 'MANIFEST.sha256.json').write_text('{}')
    with pytest.raises(ValueError, match='sealed'):
        audit(tmp_path)
    assert len(list(tmp_path.iterdir())) == 1
