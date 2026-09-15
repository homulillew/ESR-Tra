"""Offline baseline diagnostics. Raw error trees stay in a new private directory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from stride_search.archive import Archive
from stride_search.contract import SCHEMAS, ContractError, loads, validate

DATA_COMMIT = '749c505110741d828c7f54fdfb865c37b19627b3'
RELEASE = '5d7752be94a9d40aa757383d8899504bc0f81e81'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def error_tree(error):
    return {'message': error.message, 'validator': error.validator,
            'path': list(error.path), 'absolute_path': list(error.absolute_path),
            'schema_path': list(error.schema_path), 'absolute_schema_path': list(error.absolute_schema_path),
            'context': [error_tree(child) for child in error.context]}


def reproduce(repo, output):
    repo = Path(repo).resolve(); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    root = repo / 'harnesses/stride/artifacts/20260914-hard12-a3'; case = root / 'q778'
    manifest = read(case / 'manifest.json'); checks = {}
    for name, expected in manifest['source_hashes'].items():
        relative = 'harnesses/stride/src/stride_search/' + name
        blob = subprocess.check_output(['git', 'show', RELEASE + ':' + relative], cwd=repo)
        checks[name] = {'sha256': hashlib.sha256(blob).hexdigest(),
                        'release_matches': hashlib.sha256(blob).hexdigest() == expected,
                        'worktree_matches': (repo / relative).read_bytes() == blob}
    assert len(checks) == 14 and all(v['release_matches'] and v['worktree_matches'] for v in checks.values())
    public = read(root / 'MANIFEST.sha256.json')
    for name, expected in public.items():
        assert sha(root / name) == expected, name
    archive = Archive(case / 'episode.sqlite', readonly=True)
    try:
        verification = archive.verify()
        assert verification['head'] == read(root / 'ARCHIVE_HEAD_MAP.json')['q778']['published_head']
        trajectory = [json.loads(line) for line in (case / 'trajectory.jsonl').read_text(encoding='utf-8').splitlines()]
        assert list(archive.events()) == [{k: v for k, v in row.items() if k != 'utc'} for row in trajectory]
    finally:
        archive.close()
    call = read(case / 'http/004/response.body')['choices'][0]['message']['tool_calls'][0]
    args = loads(call['function']['arguments'])
    samples = {'actual_numeric': ('finish', args),
        'schema_string_only': ('finish', {**args, 'answer': str(args['answer'])}),
        'refs_type': ('finish', {'answer': 'synthetic', 'refs': 'synthetic'}),
        'blank': ('finish', {'answer': '   ', 'refs': []}),
        'mixed': ('finish', {'answer': 'synthetic', 'refs': [], 'abstain': True, 'reason': 'synthetic'}),
        'search_shape': ('search', {'queries': 'synthetic'})}
    results = {}
    for name, (tool, value) in samples.items():
        errors = list(Draft202012Validator(SCHEMAS[tool]).iter_errors(value))
        try:
            validate(tool, value); accepted = True; message = None
        except ContractError as exc:
            accepted = False; message = str(exc)
        results[name] = {'accepted': accepted, 'legacy_message': message,
                         'error_tree': [error_tree(e) for e in errors]}
    # Persist the first actual result before asserting agreement with the supplied diagnosis.
    write(output / 'RAW_ERROR_TREES.json', results)
    actual = results['actual_numeric']
    assert not actual['accepted'] and actual['error_tree'][0]['absolute_path'] == []
    assert actual['legacy_message'] == 'finish: invalid fields near []; follow the supplied schema'
    assert results['schema_string_only']['accepted']
    assert any(e['absolute_path'] == ['answer'] and e['validator'] == 'type' for e in actual['error_tree'][0]['context'])
    for name in ('refs_type', 'blank', 'mixed'):
        assert results[name]['error_tree'][0]['validator'] == 'oneOf'
        assert results[name]['error_tree'][0]['absolute_path'] == []
    wire = read(case / 'http/005/request.body')
    receipt = next(loads(m['content']) for m in wire['messages']
                   if m.get('role') == 'tool' and m.get('tool_call_id') == call['id'])
    control = loads(wire['messages'][-1]['content'].split('\n', 1)[1])
    assert receipt['message'] == control['feedback']['message'] == actual['legacy_message']
    assert receipt['code'] == 'arguments_invalid' and receipt['executed'] is False
    assert receipt['action_slot_charged'] and receipt['blocks_finish']
    assert control['feedback']['no_automatic_parameter_repair']
    assert control['uncommitted_response_not_evidence'] is None
    write(output / 'SOURCE_IDENTITY.json', {'data_commit': DATA_COMMIT, 'release': RELEASE,
        'core': checks, 'public_files_verified': len(public), 'public_archive': verification,
        'trajectory_matches_archive_ignoring_derived_utc': True, 'baseline_reproduction_matches': True,
        'receipt_feedback_message_equal': True, 'repair_view_is_none': True, 'real_model_calls': 0})
    print(json.dumps({'core_files': len(checks), 'public_files': len(public), 'baseline_reproduction_matches': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); reproduce(args.repo, args.output)
