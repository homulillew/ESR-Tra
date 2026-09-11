"""Independent CLI/adapter/artifact checks, without any external endpoint."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import EchoRetriever, MemoryRetriever, OpenAICompatible, run_episode
from esr_harness_v3.cli import main
from .conftest import DOCS


def test_partial_usage_preserves_known_tokens_without_marking_request_fully_known():
    h = Harness('Q', MemoryRetriever(DOCS))
    try:
        d = h.begin()
        h.respond(d, {'role': 'assistant', 'content': 'No action'}, usage={'prompt_tokens': 17})
        assert h.state['usage'] == {'input_tokens': 17, 'output_tokens': 0, 'unknown_calls': 1}
    finally:
        h.close()


def test_live_cli_requires_an_explicit_request_cap_before_reading_files(tmp_path):
    args = ['run', '--allow-network', '--question-file', 'does-not-exist', '--db', str(tmp_path/'no-db'),
            '--base-url', 'http://127.0.0.1:1/v1', '--model', 'fixture', '--retrieval-url', 'http://127.0.0.1:1',
            '--index-fingerprint', 'fixture', '--tokenizer', 'absent']
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2 and not (tmp_path/'no-db').exists()


@pytest.mark.parametrize('url', ['http:/missing-host', 'https://example.com/v1#private-fragment'])
@pytest.mark.parametrize('kind', ['policy', 'retriever'])
def test_invalid_endpoint_is_rejected_before_identity_logging(url, kind):
    with pytest.raises(ValueError):
        if kind == 'policy':
            OpenAICompatible(url, 'fixture')
        else:
            EchoRetriever(url, index_fingerprint='fixture')


@pytest.mark.parametrize('raw', [None, [], {'choices': None}])
def test_malformed_policy_envelope_is_accounted_without_python_crash(raw):
    class Policy:
        identity = {'kind': 'fixture-malformed-policy'}
        def complete(self, request):
            return raw
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(max_model_calls=1))
    try:
        terminal = run_episode(h, Policy())
        assert not terminal['answer'] and h.state['model_calls'] == 1
        assert h.state['usage']['unknown_calls'] == 1
        assert any(e['kind'] == 'policy_response' for e in h.ledger.verify())
    finally:
        h.close()


def test_validation_keeps_replay_and_export_inputs_after_return(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'validate_v3.py'
    spec = importlib.util.spec_from_file_location('validation_script', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / 'acceptance'
    def fake_run(command, **kwargs):
        # This checks artifact lifetime, not the smoke implementation or its result.
        if 'smoke' in command:
            Path(command[command.index('--db') + 1]).write_bytes(b'fixture database marker')
        if 'export' in command:
            Path(command[command.index('--output') + 1]).write_text('{}', encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='fixture command\n', stderr='')
    monkeypatch.setattr(module.subprocess, 'run', fake_run)
    monkeypatch.setattr(module.sys, 'argv', ['validate_v3.py', '--output', str(output)])
    assert module.main() == 0
    report = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    commands = [row['command'] for row in report['commands']]
    dbs = [Path(c[c.index('--db') + 1]) for c in commands if '--db' in c]
    exports = [Path(c[c.index('--output') + 1]) for c in commands if '--output' in c]
    assert dbs and exports and all(p.is_file() for p in dbs + exports)
    assert all(p.is_relative_to(output) for p in dbs + exports)
    assert 'src/esr_harness/engine.py' in report['source_sha256']
