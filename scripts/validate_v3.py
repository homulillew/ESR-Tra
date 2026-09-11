"""Offline acceptance with reproducible artifacts. Never calls model endpoints."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timezone


def source_hashes(root):
    paths = [root / 'scripts/validate_v3.py', root / 'pyproject.toml']
    for folder in ('src/esr_harness_v3', 'tests/harness_v3', 'src/esr_harness', 'tests/harness_v2'):
        paths.extend((root / folder).rglob('*.py'))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New output directory; never overwrite a previous run')
    parser.add_argument('--include-legacy', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    initial_hashes = source_hashes(root)
    env = dict(os.environ, PYTHONUTF8='1')
    env['PYTHONPATH'] = str(root / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    temp = out / 'pytest-temp'
    temp.mkdir()
    env['PYTEST_DEBUG_TEMPROOT'] = str(temp)
    bypass = env.get('NO_PROXY', env.get('no_proxy', ''))
    env['NO_PROXY'] = env['no_proxy'] = ','.join(filter(None, [bypass, 'localhost', '127.0.0.1', '::1']))
    tests = ['tests/harness_v3']
    legacy = 'NOT_RUN'
    if args.include_legacy:
        if not (root / 'tests/harness_v2').is_dir():
            raise SystemExit('Legacy tree absent; do not report a combined regression')
        tests.insert(0, 'tests/harness_v2')
        legacy = 'EXECUTED_SEE_LOG'
    commands = [[sys.executable, '-m', 'pytest', *tests, '-q', '--junitxml=' + str(out / 'junit.xml')],
                [sys.executable, '-m', 'compileall', '-q', 'src/esr_harness_v3'],
                [sys.executable, '-m', 'esr_harness_v3', 'schema']]
    db = str(out / 'smoke.sqlite')
    commands += [[sys.executable, '-m', 'esr_harness_v3', 'smoke', '--db', db],
                 [sys.executable, '-m', 'esr_harness_v3', 'replay', '--db', db],
                 [sys.executable, '-m', 'esr_harness_v3', 'export', '--db', db,
                  '--output', str(out / 'trace.json')]]
    records = [{'command': c, 'status': 'NOT_RUN', 'returncode': None} for c in commands]
    for i, row in enumerate(records, 1):
        started = time.monotonic()
        try:
            proc = subprocess.run(row['command'], cwd=root, env=env, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=600)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            stdout, stderr, code = '', f'{type(exc).__name__}: {exc}', -1
            if isinstance(exc, subprocess.TimeoutExpired):
                stdout = exc.stdout.decode('utf-8', errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
                stderr += '\n' + (exc.stderr.decode('utf-8', errors='replace') if isinstance(exc.stderr, bytes) else (exc.stderr or ''))
        for label, body in [('stdout', stdout), ('stderr', stderr)]:
            path = out / f'{i:02d}.{label}.txt'
            path.write_text(body, encoding='utf-8')
            row[label] = path.name
        row.update(returncode=code, elapsed_seconds=time.monotonic() - started, status='PASS' if code == 0 else 'FAIL')
        if code:
            break
    packages = {}
    for name in ('pytest', 'jsonschema', 'transformers', 'torch'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
    artifacts = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in out.iterdir() if p.is_file()}
    stable = initial_hashes == source_hashes(root)
    result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'platform': platform.platform(), 'dependencies': packages,
              'git_sha': git.stdout.strip() if git.returncode == 0 else None,
              'status': 'PASS' if stable and all(r['status'] == 'PASS' for r in records) else 'FAIL',
              'sources_unchanged_during_run': stable,
              'legacy_regression': legacy, 'real_model_calls': 0, 'benchmark_accuracy': None,
              'commands': records, 'source_sha256': initial_hashes, 'artifact_sha256': artifacts}
    (out / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'manifest': str(out/'manifest.json'), 'real_model_calls': 0}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
