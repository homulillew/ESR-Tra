"""Self-contained local publication fixtures; no private runs or network."""
import importlib.util
from pathlib import Path
import pytest
from stride_search import Config, Harness
from stride_search.archive import Archive
from stride_search.fixtures import ScriptedModel, native, smoke_corpus

PATH = Path(__file__).resolve().parents[1] / "experiments/autonomous_search/publish_stage.py"
spec = importlib.util.spec_from_file_location("stage_publication_fixture", PATH)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
HOST = "private-deployment.example"
USER = "PRIVATE_LOCAL_USER"


def make_stage(tmp_path, stopped=False):
    source = tmp_path / "source"; source.mkdir()
    folder = source / "fixture"; folder.mkdir()
    replies = [native(("search", {"queries": ["Lumen"]})),
               native(("read", {"ref": "d1"})),
               native(("finish", {"answer": "Ada Rowan", "refs": ["e1"]}))]
    model = ScriptedModel(replies)
    model.identity["endpoint"] = "http://" + HOST
    h = Harness("Who first directed Lumen?", smoke_corpus(), path=folder / "episode.sqlite",
                config=Config(max_model_calls=4))
    try:
        terminal = h.run(model)
        head = h.archive.verify()["head"]
    finally: h.close()
    for number, (request, response) in enumerate(zip(model.requests, replies), 1):
        http = folder / "http" / f"{number:03d}"; http.mkdir(parents=True)
        # Deliberate whitespace ensures publication preserves bytes, not just JSON.
        for name, data in [("request.body", request), ("response.body", response)]:
            publisher.write(http / name, data)
        publisher.write(http / "attempt-start.json", {"sequence": number})
        publisher.write(http / "metadata.json", {"sequence": number, "http_status": 200})
    seal = dict(head=head, files={p.relative_to(folder).as_posix():publisher.sha(p)
        for p in folder.rglob("*") if p.is_file() and not p.name.endswith(("-wal", "-shm"))})
    publisher.write(folder / "SEALED.json", seal)
    row = dict(slot="fixture", qid=0, protocol="baseline", status="submitted", attempts=3,
               head=head, seal_sha256=publisher.sha(folder / "SEALED.json"), terminal=terminal)
    rows = [row]
    if stopped:
        rows.append(dict(slot="not-run", qid=0, protocol="baseline", status="NOT_RUN", attempts=0))
        publisher.write(source / "STOPPED.json", {"active": "fixture", "type": "SyntheticStop"})
    else:
        publisher.write(source / "POLICY_SEALED.json", {"rows": rows})
    publisher.write(source / "RESULTS.json", {"rows": rows, "judgments": [], "budget_after": {"this_run": 3}})
    # These intentionally invalid/private files must never be copied.
    (source / "budget.sqlite").write_bytes(b"private budget")
    publisher.write(source / "manifest.json", {"credential": "DO_NOT_COPY"})
    return source


@pytest.mark.parametrize("stopped", [False, True])
def test_publication_preserves_bytes_chain_and_stage_status(tmp_path, stopped):
    source = make_stage(tmp_path, stopped)
    before = publisher.sha(source / "fixture/SEALED.json")
    output = tmp_path / "output"
    checks = publisher.publish(source, tmp_path / "staging", output, HOST, USER)
    assert checks["http_attempts"] == checks["charged_this_run"] == 3
    assert checks["http_bodies_byte_exact"] == 6
    assert checks["global_policy_sealed"] is not stopped
    assert checks["planned_slots"] == (2 if stopped else 1)
    assert checks["not_run_slots"] == int(stopped)
    assert publisher.sha(source / "fixture/SEALED.json") == before
    for original in (source / "fixture").glob("http/*/*.body"):
        assert original.read_bytes() == (output / "fixture" / original.relative_to(source / "fixture")).read_bytes()
    identities = publisher.read(output / "ARCHIVE_HEAD_MAP.json")["fixture"]
    assert identities["original_head"] != identities["published_head"]
    private = Archive(source / "fixture/episode.sqlite", readonly=True)
    public = Archive(output / "fixture/episode.sqlite", readonly=True)
    try:
        assert private.verify()["head"] == identities["original_head"]
        assert public.verify()["head"] == identities["published_head"]
        assert dict(private.db.execute("SELECT sha,text FROM objects")) == dict(public.db.execute("SELECT sha,text FROM objects"))
    finally: private.close(); public.close()
    assert (output / "fixture/rounds/round-01.md").is_file()
    assert not (output / "cohort/manifest.json").exists()
    assert not list(output.rglob("budget.sqlite"))
    assert not (output / "judge").exists()
    if stopped:
        assert (output / "cohort/STOPPED.json").is_file()
        assert not (output / "cohort/POLICY_SEALED.json").exists()
        assert publisher.read(output / "cohort/RESULTS.json")["rows"][1]["status"] == "NOT_RUN"


def test_metering_mismatch_rejects_before_copy(tmp_path):
    source = make_stage(tmp_path)
    results = publisher.read(source / "RESULTS.json")
    results["budget_after"]["this_run"] = 4
    publisher.write(source / "RESULTS.json", results)
    with pytest.raises(ValueError, match="charged"):
        publisher.publish(source, tmp_path / "staging", tmp_path / "output", HOST, USER)
    assert not (tmp_path / "staging").exists()
    assert not (tmp_path / "output").exists()


def test_tampered_private_body_rejects_before_copy(tmp_path):
    source = make_stage(tmp_path, stopped=True)
    with (source / "fixture/http/001/response.body").open("ab") as f: f.write(b" ")
    with pytest.raises(ValueError, match="Sealed file changed"):
        publisher.publish(source, tmp_path / "staging", tmp_path / "output", HOST, USER)
    assert not (tmp_path / "output").exists()
