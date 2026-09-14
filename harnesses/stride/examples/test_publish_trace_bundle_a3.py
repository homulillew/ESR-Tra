import json
from pathlib import Path
from stride_search.archive import Archive
from stride_search.contract import canonical
from publish_trace_bundle_a3 import build, sha, write


def test_public_archive_changes_only_deployment_metadata(tmp_path):
    source = tmp_path / 'sealed'; source.mkdir()
    archive = Archive(source / 'episode.sqlite')
    archive.append('episode', {'question': 'Synthetic question'})
    archive.append('model_identity', {'endpoint': 'http://private.synthetic.invalid/v1'})
    wire = {'model': 'synthetic', 'messages': [{'role': 'user', 'content': 'Synthetic question'}]}
    request = archive.save_request(wire)
    archive.append('model_request', {'round': 1, 'request': request})
    original_head = archive.head
    archive.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    archive.db.execute('PRAGMA journal_mode=DELETE')
    archive.close()
    (source / 'request.body').write_bytes(canonical(wire).encode())
    write(source / 'manifest.json', {'endpoint': 'http://private.synthetic.invalid/v1',
                                   'path': r'C:\Users\synthetic-user\work', 'head': original_head})
    inventory = {f.name: sha(f) for f in source.iterdir() if f.is_file()}
    write(source / 'MANIFEST.sha256.json', inventory)
    destination = tmp_path / 'published'
    identities = build({'q': source}, destination, 'private.synthetic.invalid', 'synthetic-user')
    assert all(sha(source / n) == v for n, v in inventory.items())
    public = Archive(destination / 'q/episode.sqlite', readonly=True)
    try:
        assert public.verify()['event_count'] == 3
        assert public.head != original_head
        assert public.load_request(request) == wire
        assert identities['q']['original_head'] == original_head
        assert identities['q']['published_head'] == public.head
        assert identities['q']['metadata_events_changed'] == [{'seq': 2, 'kind': 'model_identity'}]
    finally:
        public.close()
    assert (source / 'request.body').read_bytes() == (destination / 'q/request.body').read_bytes()
    assert json.loads((destination / 'q/manifest.json').read_text())['head'] == identities['q']['published_head']
