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
import tempfile
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New output directory; never overwrite a previous run')
    parser.add_argument('--include-legacy', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(root / 'src') + os.pathsep + env.get('PYTHONPATH', '')
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
    records = []
    with tempfile.TemporaryDirectory(prefix='esr-v3-acceptance-') as temp:
        db = str(Path(temp) / 'smoke.sqlite')
        commands += [[sys.executable, '-m', 'esr_harness_v3', 'smoke', '--db', db],
                     [sys.executable, '-m', 'esr_harness_v3', 'replay', '--db', db],
                     [sys.executable, '-m', 'esr_harness_v3', 'export', '--db', db,
                      '--output', str(Path(temp) / 'trace.json')]]
        for i, command in enumerate(commands, 1):
            proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            log = out / f'{i:02d}.log'
            log.write_text(proc.stdout + '\nSTDERR:\n' + proc.stderr, encoding='utf-8')
            records.append({'command': command, 'returncode': proc.returncode, 'log': log.name})
            if proc.returncode:
                break
    files = {}
    for folder in ('src/esr_harness_v3', 'tests/harness_v3'):
        for p in sorted((root / folder).rglob('*.py')):
            files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'platform': platform.platform(), 'status': 'PASS' if all(r['returncode'] == 0 for r in records) else 'FAIL',
              'legacy_regression': legacy, 'real_model_calls': 0, 'benchmark_accuracy': None,
              'commands': records, 'sha256': files}
    (out / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
