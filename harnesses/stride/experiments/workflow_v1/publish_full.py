"""Publish user-authorized full traces; preserve HTTP bytes and private originals."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'harnesses/stride/examples'))
from publish_trace_bundle_a3 import build, reading_views, sha, write
from stride_search.archive import Archive


def publish(source, staging, output, private_manifest):
    source, staging, output = map(Path, (source, staging, output))
    private = json.loads(Path(private_manifest).read_text(encoding='utf-8'))
    host, user = urlparse(private['base_url']).hostname, Path.home().name
    staging.mkdir(parents=True, exist_ok=False)
    policy = json.loads((source / 'POLICY_SEALED.json').read_text(encoding='utf-8'))
    sources = {}; originals = {}
    for row in policy['rows']:
        label = row['slot']; original = source / label
        seal = json.loads((original / 'SEALED.json').read_text(encoding='utf-8'))
        assert sha(original / 'SEALED.json') == row['seal_sha256']
        originals[label] = seal['files']
        sources[label] = staging / label; sources[label].mkdir()
        for name, expected in seal['files'].items():
            assert sha(original / name) == expected, (label, name)
            if name.endswith(('-shm', '-wal')):
                continue
            dest = sources[label] / name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, dest)
    sources['judge'] = staging / 'judge'
    shutil.copytree(source / 'judge', sources['judge'])
    sources['cohort'] = staging / 'cohort'; sources['cohort'].mkdir()
    for name in ['manifest.json', 'RESULTS.json', 'POLICY_SEALED.json', 'gold-access.json', 'judge-cases.json']:
        shutil.copyfile(source / name, sources['cohort'] / name)
    for path in source.glob('*.summary.json'):
        shutil.copyfile(path, sources['cohort'] / path.name)
    for folder in sources.values():
        write(folder / 'MANIFEST.sha256.json', {
            p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()})
    identities = build(sources, output, host, user)
    for row in policy['rows']:
        reading_views(output / row['slot'])
    checks = {'new_model_requests': 0, 'policy_episodes': len(policy['rows']),
              'http_attempts': 0, 'http_bodies_byte_exact': 0,
              'all_private_seals_unchanged': True, 'public_archive_heads_verified': True}
    for label, original_files in originals.items():
        assert all(sha(source / label / name) == expected for name, expected in original_files.items())
        a = Archive(output / label / 'episode.sqlite', readonly=True)
        try: assert a.verify()['head'] == identities[label]['published_head']
        finally: a.close()
    for label, original in [(r['slot'], source / r['slot']) for r in policy['rows']] + [('judge', source / 'judge')]:
        for p in original.glob('http/*/metadata.json'):
            checks['http_attempts'] += 1
            for name in ['request.body', 'response.body']:
                rel = (p.parent / name).relative_to(original)
                assert (original / rel).read_bytes() == (output / label / rel).read_bytes()
                checks['http_bodies_byte_exact'] += 1
    assert checks['http_attempts'] == 71 and checks['http_bodies_byte_exact'] == 142
    write(output / 'PUBLICATION_CHECKS.json', checks)
    for p in output.rglob('*'):
        if p.is_file():
            data = p.read_bytes()
            assert host.encode() not in data and user.encode() not in data, p
            assert not re.search(rb'(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}', data), p
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'staging', 'output', 'private-manifest']:
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    publish(a.source, a.staging, a.output, a.private_manifest)
