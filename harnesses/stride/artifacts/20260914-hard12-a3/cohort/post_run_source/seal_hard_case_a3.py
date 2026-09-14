"""Verify completed trace correspondence and seal all review files, offline."""
import argparse
import json
from pathlib import Path
from trace_question_a3 import save, sha


def seal(root):
    root = Path(root)
    if (root / 'MANIFEST.sha256.json').exists():
        raise FileExistsError('Case is already sealed')
    for name in ('INTERACTION_ANALYSIS.md', 'EVIDENCE_AUDIT.md', 'ROUND_ANALYSIS.md'):
        if not (root / name).is_file():
            raise ValueError('Missing review: ' + name)
    read = lambda name: json.loads((root / name).read_text(encoding='utf-8'))
    integ = read('INTEGRITY_CHECKS.json'); supplement = read('SUPPLEMENTAL_CHECKS.json')
    post = read('POSTHOC_CHECKS.json'); data = read('analysis-data.json')
    checks = {
        'request_json_equivalence': integ['all_json_equivalent'],
        'response_json_equivalence': all(v['response_json_equivalent'] for v in supplement['response_correspondence']),
        'native_execution_order': all(v['ids_match_in_order'] for v in supplement['native_execution_order']),
        'native_arguments_and_results': all(all(v[k] for k in ('native_call_found','name_matches','arguments_exact','action_result_found')) for v in post['tool_checks']),
        'read_windows_match_snapshot': supplement['raw_windows_match_saved_snapshot'],
        'find_offsets_match_snapshot': all(v['offsets_match_original'] for v in post['find_checks']),
        'next_request_receipts_present': all(v['next_input_receipt'] for v in data['actions'] if v['next_request'] is not None),
        'http_request_hashes': True, 'http_response_hashes': True,
    }
    for path in root.glob('http/*/metadata.json'):
        metadata = json.loads(path.read_text(encoding='utf-8'))
        checks['http_request_hashes'] &= sha(path.parent / 'request.body') == metadata['request_body_sha256']
        checks['http_response_hashes'] &= sha(path.parent / 'response.body') == metadata['saved_response_body_sha256']
    if not all(checks.values()):
        raise ValueError('Trace audit failure: ' + json.dumps(checks))
    save(root / 'SEAL_VALIDATION.json', checks)
    inventory = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
                 if p.is_file() and not p.name.endswith(('-wal', '-shm'))}
    save(root / 'MANIFEST.sha256.json', inventory)
    print(json.dumps({'sealed': str(root), 'files': len(inventory)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root'); seal(p.parse_args().root)
