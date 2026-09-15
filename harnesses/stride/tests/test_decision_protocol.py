"""Synthetic protocol boundary checks, not evidence of research accuracy."""
from copy import deepcopy
from hashlib import sha256
import pytest
from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.contract import INTEGER_ANSWER
from stride_search.decision_protocol import CONSTRAINT_REVIEW
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.workflow_contract import WorkflowConfig

PROTOCOL = "constraint-review-v1"
SEARCH = ("search", {"queries": ["Lumen"]})
READ = ("read", {"ref": "d1"})


def make(protocol="baseline", **kwargs):
    return Harness("Who directed Lumen, and when did it open?", smoke_corpus(),
                   decision_protocol=protocol, answer_contract=INTEGER_ANSWER,
                   config=Config(max_model_calls=6), workflow=WorkflowConfig.profile("full"),
                   **kwargs)


@pytest.mark.parametrize("final", [False, True])
def test_wire_diff_is_system_instruction_only(final):
    requests = []
    for protocol in ("baseline", PROTOCOL):
        h = make(protocol)
        try:
            if final:
                h.model_calls = h.config.max_model_calls - 1
            model = ScriptedModel([native(("finish", {"abstain": True, "reason": "fixture"}))])
            before = h.remaining()
            h._step(model)
            requests.append(deepcopy(model.requests[0]))
            assert h.remaining()["model_calls"] == before["model_calls"] - 1
            assert h.backend_calls == 0
        finally:
            h.close()
    baseline, treatment = requests
    assert treatment["messages"][0]["content"] == baseline["messages"][0]["content"] + CONSTRAINT_REVIEW
    treatment["messages"][0] = baseline["messages"][0]
    assert treatment == baseline  # Includes tools, limits, runtime budget, and source scope.


@pytest.mark.parametrize("protocol", ["baseline", PROTOCOL])
@pytest.mark.parametrize("answer", ["Ada Rowan", 2012])
def test_supported_string_and_integer_finish(protocol, answer):
    h = make(protocol)
    try:
        result = h.run(ScriptedModel([native(SEARCH), native(READ),
            native(("finish", {"answer": answer, "refs": ["e1"]}))]))
        assert result["outcome"] == "submitted"
        assert str(result["answer"]) == str(answer)
        assert h.model_calls == 3 and h.backend_calls == 2
    finally:
        h.close()


@pytest.mark.parametrize("protocol", ["baseline", PROTOCOL])
@pytest.mark.parametrize("bad_ref", ["e999", "d1"])
def test_invalid_or_navigation_reference_cannot_finish(protocol, bad_ref):
    h = make(protocol)
    try:
        for response in [native(SEARCH), native(READ),
                         native(("finish", {"answer": "Ada Rowan", "refs": [bad_ref]}))]:
            h._step(ScriptedModel([response]))
        assert h.terminal is None
        errors = [e["payload"]["result"] for e in h.archive.events() if e["kind"] == "action_result"]
        assert errors[-1]["ok"] is False
        h._step(ScriptedModel([native(("finish", {"answer": "Ada Rowan", "refs": ["e1"]}))]))
        assert h.terminal["outcome"] == "submitted"
    finally:
        h.close()


def test_protocol_identity_and_request_survive_readonly_replay(tmp_path):
    path = tmp_path / "episode.sqlite"
    h = make(PROTOCOL, path=path)
    try:
        h.run(ScriptedModel([native(("finish", {"abstain": True, "reason": "fixture"}))]))
        events = list(h.archive.events())
        request = next(e["payload"]["request"] for e in events if e["kind"] == "model_request")
        expected = h.archive.load_request(request)
    finally:
        h.close()
    archive = Archive(path, readonly=True)
    try:
        header = next(archive.events())["payload"]["decision_protocol"]
        assert header["version"] == PROTOCOL
        assert header["instruction_sha256"] == sha256(CONSTRAINT_REVIEW.encode()).hexdigest()
        assert archive.load_request(request) == expected
        archive.verify()
    finally:
        archive.db.close()


def test_cli_defaults_to_baseline_and_accepts_explicit_protocol():
    flags = ["run", "--base-url", "http://fixture.invalid", "--model", "fixture",
             "--model-revision", "fixture", "--retrieval-url", "http://fixture.invalid",
             "--index-id", "fixture", "--counter", "utf8_bytes", "--question-file", "fixture",
             "--db", "fixture.sqlite", "--max-model-calls", "6", "--context-limit", "96000",
             "--response-reserve", "4096"]
    assert cli.parser().parse_args(flags).decision_protocol == "baseline"
    assert cli.parser().parse_args(flags + ["--decision-protocol", PROTOCOL]).decision_protocol == PROTOCOL
    with pytest.raises(SystemExit):
        cli.parser().parse_args(flags + ["--decision-protocol", "unknown"])
