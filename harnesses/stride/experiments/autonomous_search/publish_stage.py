"""Offline publication: sealed stage to reviewable local bundle; no network operations."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'harnesses/stride/src'))
sys.path.insert(0, str(ROOT / 'harnesses/stride/examples'))
from publish_trace_bundle_a3 import build, reading_views, sha, write
from stride_search.archive import Archive


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_path(root, name):
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Path escapes sealed source')
    return target


def publish(source, staging, output, private_host, private_user):
    source, staging, output = map(Path, (source, staging, output))
    if output.exists() or staging.exists():
        raise FileExistsError('Fresh output and staging directories required')
    results = read(source / 'RESULTS.json')
    policy = read(source / 'POLICY_SEALED.json') if (source / 'POLICY_SEALED.json').exists() else None
    all_rows = results['rows']
    rows = [r for r in all_rows if (safe_path(source, r['slot']) / 'SEALED.json').is_file()]
    if any(r.get('attempts', 0) and r not in rows for r in all_rows):
        raise ValueError('Attempted slot lacks a verifiable seal')
    if policy is None and not (source / 'STOPPED.json').is_file():
        raise ValueError('Neither global policy seal nor stopped-stage record exists')
    labels = [r['slot'] for r in rows]
    if len(set(labels)) != len(labels) or set(labels) & {'judge', 'cohort'}:
        raise ValueError('Invalid slot names')
    if policy is not None and labels != [r['slot'] for r in policy['rows']]:
        raise ValueError('Results and policy seal slots differ')
    # Validate each episode seal and available global bindings before copying.
    originals = {}; seals = {}; attempt_count = 0; body_count = 0
    for row, sealed in zip(rows, policy['rows'] if policy is not None else rows):
        for key in ['slot', 'qid', 'protocol', 'status', 'attempts', 'head', 'seal_sha256', 'terminal']:
            if row.get(key) != sealed.get(key):
                raise ValueError('Result/seal mismatch: ' + key)
        folder = safe_path(source, row['slot'])
        seal_path = folder / 'SEALED.json'
        if sha(seal_path) != row['seal_sha256']:
            raise ValueError('Episode seal changed')
        seals[row['slot']] = sha(seal_path)
        seal = read(seal_path)
        inventory = seal['files']
        original_archive = Archive(folder / 'episode.sqlite', readonly=True)
        try:
            if original_archive.verify()['head'] != row['head'] or seal['head'] != row['head']:
                raise ValueError('Results and original archive head differ')
            if original_archive.report()['terminal'] != row['terminal']:
                raise ValueError('Results and original terminal differ')
        finally:
            original_archive.close()
        for name, expected in inventory.items():
            item = safe_path(folder, name)
            if sha(item) != expected:
                raise ValueError('Sealed file changed: ' + name)
        originals[row['slot']] = inventory
        attempts = sorted(folder.glob('http/*/attempt-start.json'))
        if len(attempts) != row['attempts']:
            raise ValueError('Slot attempt mismatch')
        attempt_count += len(attempts)
    judge = source / 'judge'
    judge_attempts = list(judge.glob('http/*/attempt-start.json'))
    attempt_count += len(judge_attempts)
    if attempt_count != results['budget_after']['this_run']:
        raise ValueError('Stage HTTP attempts differ from charged this_run')
    if len(results.get('judgments', [])) > len(judge_attempts):
        raise ValueError('More judgments than HTTP attempts')
    # Do not copy private manifests, budget databases, credentials, gold, or plans.
    staging.mkdir(parents=True)
    sources = {}
    for label, inventory in originals.items():
        folder = staging / label; folder.mkdir(); sources[label] = folder
        for name in inventory:
            if name.endswith(('-shm', '-wal')): continue
            if name.endswith(('.sqlite', '.db')) and name != 'episode.sqlite':
                raise ValueError('Unrelated database in inventory')
            target = safe_path(folder, name); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(source / label, name), target)
    if judge.is_dir():
        folder = staging / 'judge'; folder.mkdir(); sources['judge'] = folder
        for original in judge.glob('http/*/*'):
            if original.name not in {'request.body','response.body','metadata.json','attempt-start.json'}: continue
            target = folder / original.relative_to(judge); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original,target)
        for original in judge.glob('*.judgment.json'): shutil.copyfile(original,folder/original.name)
    cohort = staging / 'cohort'; cohort.mkdir(); sources['cohort'] = cohort
    # Publish result semantics and accounting values, not deployment configuration.
    public_results = {k:results[k] for k in ['rows','judgments','budget_after','utc_finished'] if k in results}
    write(cohort / 'RESULTS.json', public_results)
    if policy is not None: write(cohort / 'POLICY_SEALED.json', policy)
    if (source / 'STOPPED.json').is_file():
        write(cohort / 'STOPPED.json', read(source / 'STOPPED.json'))
    for folder in sources.values():
        write(folder / 'MANIFEST.sha256.json', {p.relative_to(folder).as_posix():sha(p)
            for p in sorted(folder.rglob('*')) if p.is_file()})
    identities = build(sources, output, private_host, private_user)
    for label in labels:
        # Complete healthy episodes support the existing per-round reader.
        archive = Archive(output / label / 'episode.sqlite', readonly=True)
        try:
            if archive.verify()['head'] != identities[label]['published_head']:
                raise ValueError('Public archive verification failed')
            rounds = [e['payload']['round'] for e in archive.events() if e['kind']=='model_request']
        finally: archive.close()
        if all((output / label / 'http' / f'{r:03d}' / 'response.body').is_file() for r in rounds):
            reading_views(output / label)
    for label in labels + (['judge'] if judge.is_dir() else []):
        for original in (source / label).glob('http/*/*.body'):
            if original.read_bytes() != (output / label / original.relative_to(source / label)).read_bytes():
                raise ValueError('Raw HTTP bytes changed')
            body_count += 1
    for label, inventory in originals.items():
        if sha(source / label / 'SEALED.json') != seals[label]: raise ValueError('Private seal changed')
        if not all(sha(safe_path(source / label,n))==v for n,v in inventory.items()):
            raise ValueError('Private original changed')
    checks = dict(new_model_requests=0, policy_episodes=len(labels), http_attempts=attempt_count,
        charged_this_run=results['budget_after']['this_run'], http_bodies_byte_exact=body_count,
        planned_slots=len(all_rows), not_run_slots=sum(r['status']=='NOT_RUN' for r in all_rows),
        global_policy_sealed=policy is not None,
        all_private_seals_unchanged=True, public_archive_heads_verified=True,
        missing_responses=sum(not (p.parent/'response.body').exists() for label in labels+(['judge'] if judge.is_dir() else [])
            for p in (source/label).glob('http/*/attempt-start.json')))
    write(output / 'PUBLICATION_CHECKS.json',checks)
    return checks


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ['source','staging','output','private-host','private-user']:
        parser.add_argument('--'+flag,required=True)
    args=parser.parse_args()
    print(json.dumps(publish(args.source,args.staging,args.output,args.private_host,args.private_user),indent=2))
