"""Build reviewable public copies without changing sealed private experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from stride_search.archive import Archive
from stride_search.contract import canonical


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def redactor(private_host, private_user):
    def redact(text):
        text = text.replace(private_host, 'model-service.invalid')
        for root in [f'C:\\Users\\{private_user}', f'C:/Users/{private_user}',
                     f'C:\\\\Users\\\\{private_user}']:
            text = text.replace(root, root.replace(private_user, 'USER'))
        return text.replace(private_user, 'USER')
    return redact


def archive_copy(source, destination, redact):
    original = Archive(source, readonly=True)
    target = Archive(destination)
    try:
        source_events = list(original.events())
        for obj_sha, text in original.db.execute('SELECT sha,text FROM objects'):
            if redact(text) != text:
                raise ValueError('Refusing to alter model messages, tools, or raw evidence')
            assert target.put(text) == obj_sha
        for table in ['docs', 'evidence']:
            rows = original.db.execute(f'SELECT * FROM {table}').fetchall()
            if rows:
                marks = ','.join('?' for _ in rows[0])
                target.db.executemany(f'INSERT INTO {table} VALUES ({marks})', rows)
        mapping = {}
        changed = []
        for event in source_events:
            before = canonical(event['payload'])
            after = redact(before)
            if after != before:
                if event['kind'] != 'model_identity':
                    raise ValueError('Only deployment metadata may change in archived events')
                changed.append({'seq': event['seq'], 'kind': event['kind']})
            new = target.append(event['kind'], json.loads(after))
            mapping[event['hash']] = new['hash']
        verified = target.verify()
        for event in source_events:
            if event['kind'] == 'model_request':
                ref = event['payload']['request']
                assert target.load_request(ref) == original.load_request(ref)
        result = {'original_head': original.head, 'published_head': target.head,
                  'event_count': verified['event_count'], 'metadata_events_changed': changed,
                  'all_content_addressed_objects_unchanged': True,
                  'model_requests_responses_tools_documents_unchanged': True}
        target.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        target.db.execute('PRAGMA journal_mode=DELETE')
        return mapping, result
    finally:
        target.close()
        original.close()


def build(sources, output, private_host, private_user):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    # Validate every sealed input before creating the publication tree.
    inventories = {}
    for label, source in sources.items():
        manifest = json.loads((source / 'MANIFEST.sha256.json').read_text(encoding='utf-8'))
        for name, expected in manifest.items():
            if sha(source / name) != expected:
                raise ValueError(f'Sealed input changed: {label}/{name}')
        inventories[label] = manifest
    output.mkdir(parents=True)
    redact = redactor(private_host, private_user)
    maps = {}; identities = {}; changes = []
    for label, source in sources.items():
        target = output / label; target.mkdir()
        if (source / 'episode.sqlite').exists():
            mapping, identity = archive_copy(source / 'episode.sqlite', target / 'episode.sqlite', redact)
            maps.update(mapping); identities[label] = identity
    changed_hashes = {k: v for k, v in maps.items() if k != v}
    hash_pattern = re.compile('|'.join(map(re.escape, changed_hashes))) if changed_hashes else None
    for label, source in sources.items():
        target = output / label
        for name in inventories[label]:
            if name.endswith(('-shm', '-wal')):
                continue
            if name.endswith('.sqlite'):
                if name != 'episode.sqlite':
                    raise ValueError('Refusing to publish an unrelated database')
                changes.append({'file': f'{label}/{name}', 'original_sha256': sha(source / name),
                                'published_sha256': sha(target / name), 'transformation': 'deployment_metadata_and_event_hash_chain'})
                continue
            src = source / name; dst = target / name; dst.parent.mkdir(parents=True, exist_ok=True)
            raw = src.read_bytes()
            encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8'
            text = raw.decode(encoding)
            updated = redact(text)
            if hash_pattern:
                updated = hash_pattern.sub(lambda m: changed_hashes[m.group()], updated)
            encoded = raw if updated == text else updated.encode(encoding)
            if name.endswith('.body') and encoded != raw:
                raise ValueError('Raw HTTP body must remain byte-exact')
            dst.write_bytes(encoded)
            changes.append({'file': f'{label}/{name}', 'original_sha256': sha(src), 'published_sha256': sha(dst),
                            'transformation': 'none' if encoded == raw else 'deployment_paths_or_event_hash_references'})
        write(target / 'SOURCE_FILE_HASHES.json', inventories[label])
        write(target / 'PUBLICATION_IDENTITY.json', identities.get(label, {
            'kind': 'judge', 'binding': 'Public labels map to public heads; original heads retained in bundle identity map'}))
    write(output / 'ARCHIVE_HEAD_MAP.json', identities)
    write(output / 'PUBLICATION_FILES.json', changes)
    for f in output.rglob('*'):
        if not f.is_file():
            continue
        data = f.read_bytes()
        if private_host.encode() in data or private_user.encode() in data:
            raise ValueError(f'Private deployment marker remains: {f.relative_to(output)}')
        if re.search(rb'sk-[A-Za-z0-9_-]{20,}', data):
            raise ValueError(f'Credential pattern found: {f.relative_to(output)}')
    return identities


def reading_views(root):
    """Add per-round views plus unchanged standalone documents/evidence for review."""
    root = Path(root)
    archive = Archive(root / 'episode.sqlite', readonly=True)
    try:
        rounds = root / 'rounds'; rounds.mkdir()
        documents = root / 'documents'; documents.mkdir()
        evidence = root / 'evidence'; evidence.mkdir()
        for n, snapshot in archive.db.execute('SELECT n,snapshot FROM docs WHERE snapshot IS NOT NULL'):
            (documents / f'd{n}.txt').write_bytes(archive.get(snapshot).encode('utf-8'))
        for (n,) in archive.db.execute('SELECT n FROM evidence'):
            (evidence / f'e{n}.txt').write_bytes(archive.evidence(f'e{n}')['text'].encode('utf-8'))
        events = list(archive.events())
        requests = [e for e in events if e['kind'] == 'model_request']
        index = '# Rounds\n\nRequest/response body files are byte-exact; these Markdown files are generated reading views.\n\n'
        for i, request in enumerate(requests):
            r = request['payload']['round']
            end = requests[i + 1]['seq'] if i + 1 < len(requests) else len(events) + 1
            group = [e for e in events if request['seq'] <= e['seq'] < end]
            response_path = root / 'http' / f'{r:03d}' / 'response.body'
            response = json.loads(response_path.read_bytes())
            body = f'# Round {r}\n\n[Actual request](../http/{r:03d}/request.body) · [Actual response](../http/{r:03d}/response.body) · [All interaction](../FULL_INTERACTION.md)\n\n'
            body += '## Input visibility\n\n```json\n' + json.dumps(request['payload'], ensure_ascii=False, indent=2) + '\n```\n\n'
            body += '## Complete model response\n\n```json\n' + json.dumps(response, ensure_ascii=False, indent=2) + '\n```\n\n'
            for event in group:
                if event['kind'] == 'action_execution':
                    action = archive.json(event['payload']['object'])
                    body += f'## Executed action: {action["tool"]}\n\n```json\n' + json.dumps(action, ensure_ascii=False, indent=2) + '\n```\n\n'
            body += '## Full event records for this request interval\n\n```json\n' + json.dumps(group, ensure_ascii=False, indent=2) + '\n```\n'
            (rounds / f'round-{r:02d}.md').write_text(body, encoding='utf-8')
            index += f'- [Round {r}](round-{r:02d}.md)\n'
        (rounds / 'README.md').write_text(index, encoding='utf-8')
    finally:
        archive.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', required=True, help='label=sealed-directory')
    parser.add_argument('--output', required=True)
    parser.add_argument('--private-host', required=True)
    parser.add_argument('--private-user', required=True)
    args = parser.parse_args()
    sources = {label: Path(path) for label, path in (item.split('=', 1) for item in args.source)}
    print(json.dumps(build(sources, args.output, args.private_host, args.private_user), indent=2))
