from copy import deepcopy
import pytest

from esr_harness.audit import AUDIT_SYSTEM, status, validate_report
from esr_harness.protocol import AUDIT_SCHEMA, Config, HarnessError, SCHEMAS, parse_object, validate
from esr_harness.views import MemoryRetriever, document, make_view, merge_spans
from conftest import opened, report_for, update


@pytest.mark.parametrize("text", ['[]', '1', 'null', '{"x": NaN}', '{"x":1,"x":2}',
                                  'example {"x":1} final {"x":2}', '<think>unclosed'])
def test_strict_parser_rejects_ambiguous_output(text):
    with pytest.raises(HarnessError):
        parse_object(text)


@pytest.mark.parametrize("text", ['{"x":1}', '```json\n{"x":1}\n```',
                                  '<think>an example {"x":0}</think>\n{"x":1}'])
def test_parser_handles_complete_platform_wrappers(text):
    assert parse_object(text) == {"x": 1}


@pytest.mark.parametrize("mode", ["esr", "baseline"])
@pytest.mark.parametrize("audit_mode", ["hard", "soft", "off"])
def test_exposed_schemas_are_single_source(mode, audit_mode):
    for tool in Config(mode=mode, audit_mode=audit_mode).tools:
        assert tool["parameters"] is SCHEMAS[tool["name"]]


def test_runtime_matches_jsonschema_for_nested_claims():
    import jsonschema
    valid = {"answer": "Taylor", "answer_kind": "answer", "target": "winner",
             "claims": [{"claim_id": "c1", "requirement": "two years before", "observation_ids": ["o1"]}]}
    for data in [valid, {**valid, "claims": []}]:
        validate(data, SCHEMAS["update_state"])
        jsonschema.validate(data, SCHEMAS["update_state"])
    for data in [{**valid, "extra": 1}, {**valid, "claims": [{"claim_id": "c1"}]},
                 {**valid, "claims": [{**valid["claims"][0], "observation_ids": ["o1", "o1"]}]}]:
        with pytest.raises(HarnessError):
            validate(data, SCHEMAS["update_state"])
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, SCHEMAS["update_state"])


@pytest.mark.parametrize("change", ["fabricated_quote", "unreferenced_id", "missing_claim", "duplicate_claim", "empty_quotes", "extra_overall_flag"])
def test_audit_cannot_bypass_quote_and_coverage_invariants(env, change):
    update(env, opened(env))
    report = report_for(env.state, list(env.observations.values()))
    if change == "fabricated_quote":
        report["claims"][0]["quotes"][0]["quote"] = "Never observed"
    elif change == "unreferenced_id":
        report["claims"][0]["quotes"][0]["observation_id"] = "o999"
    elif change == "missing_claim":
        report["claims"] = []
    elif change == "duplicate_claim":
        report["claims"] *= 2
    elif change == "empty_quotes":
        report["claims"][0]["quotes"] = []
    else:
        report["supported"] = True
    with pytest.raises(HarnessError):
        validate_report(report, env.state, env.observations)


def test_headers_are_not_evidence_quotes(env):
    update(env, opened(env))
    report = report_for(env.state, list(env.observations.values()))
    report["claims"][0]["quotes"][0]["quote"] = "[chars 0:63]"
    with pytest.raises(HarnessError):
        validate_report(report, env.state, env.observations)


def test_missing_target_or_coverage_support_blocks_overall(env):
    update(env, opened(env))
    report = report_for(env.state, list(env.observations.values()))
    report["target"]["status"] = "unknown"
    assert status(report) == "unknown"
    report["coverage"]["status"] = "contradicted"
    assert status(report) == "contradicted"


def test_audit_prompt_covers_badcase_relations_without_gold_rules():
    for term in ["not found", "before/after", "fewer than", "rounding", "multi-hop", "intermediate", "world knowledge"]:
        assert term in AUDIT_SYSTEM
    assert "Gold/answer names" not in AUDIT_SYSTEM


def test_explicit_tail_window_beyond_old_16k_prefix():
    raw = "A" * 19000 + " crucial tail evidence " + "B" * 1000
    r = MemoryRetriever([{"docid": "tail", "content": raw}])
    doc = r.get_document("tail")
    view = make_view(doc, r, "tail", limit=100, top_k=3, offset=19000)
    assert "crucial tail evidence" in view["text"]
    assert view["spans"] == [[19000, 19100]] and view["source"] == "raw_window"


def test_local_chunk_fallback_can_find_tail():
    r = MemoryRetriever([{"docid": "tail", "content": ("noise " * 4000) + "target_unique"}])
    view = make_view(r.get_document("tail"), r, "target_unique", limit=4000, top_k=1)
    assert "target_unique" in view["text"]
    assert view["fallback"] == "chunks_unavailable"


def test_nonverbatim_remote_chunks_are_not_trusted():
    class BadChunks(MemoryRetriever):
        def get_doc_chunks(self, *args, **kwargs):
            return {"chunks": [{"text": "hallucinated replacement"}]}
    r = BadChunks([{"docid": "d", "content": "only actual evidence"}])
    view = make_view(r.get_document("d"), r, "evidence", limit=1000, top_k=3)
    assert view["fallback"] == "chunks_not_verbatim"
    assert "hallucinated" not in view["text"]


def test_overlapping_chunks_merge_and_keep_exact_offsets():
    class Chunks(MemoryRetriever):
        def get_doc_chunks(self, *args, **kwargs):
            return {"chunks": [{"text": "abcdef"}, {"text": "defghi"}]}
    r = Chunks([{"docid": "d", "content": "abcdefghijk"}])
    view = make_view(r.get_document("d"), r, "abc", limit=100, top_k=3)
    assert view["raw_parts"] == ["abcdefghi"] and view["spans"] == [[0, 9]]


def test_document_identity_mismatch_is_error():
    with pytest.raises(HarnessError):
        document({"docid": "wrong", "content": "text"}, "requested")


def test_invalid_window_is_error():
    r = MemoryRetriever([{"docid": "d", "content": "text"}])
    with pytest.raises(HarnessError):
        make_view(r.get_document("d"), r, "x", limit=10, top_k=1, offset=100)


@pytest.mark.parametrize("kwargs", [{"max_actions": 0}, {"view_chars": -1}, {"search_top_k": 51},
                                    {"mode": "other"}, {"audit_mode": "force_supported"}, {"max_actions": True}])
def test_invalid_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)
