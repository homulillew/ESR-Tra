"""Read-only CPU FTS5 adapter matching the q26 LocalIndex query/ranking contract.

No index building, GPU, embeddings, web-search operators or query-rewriting model.
The existing docs/search/metadata index is an explicitly supplied deployment asset.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import time

from .contract import ContractError, digest, loads


class SQLiteFTS5:
    capabilities = {
        'kind': 'sqlite-fts5-bm25', 'scope': 'fixed local corpus; not live web',
        'query_rule': 'lowercase; regex word extraction; first-occurrence deduplication; OR of quoted individual tokens',
        'phrase_quotes': False, 'site_filter': False, 'boolean_operators': False,
        'warning': 'site:, quotes and AND/OR in input are not filters/operators. Their words may become ordinary search terms. Use a few discriminating terms.',
        'ranking': 'SQLite bm25(search), ascending; docid tie-break; unchanged from q26 LocalIndex',
        'title_kind': 'stored URL, not an extracted page title',
        'negative_result': 'no hit for this expression is not proof that the fact is absent',
    }

    def __init__(self, path, *, index_id: str, timeout_seconds: int = 45):
        if not isinstance(index_id, str) or not index_id.strip():
            raise ValueError('Explicit frozen index_id is required')
        if type(timeout_seconds) is not int or timeout_seconds < 1:
            raise ValueError('timeout_seconds must be a positive integer')
        self.timeout_seconds = timeout_seconds
        self.db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
        try:
            self.db.execute('PRAGMA query_only=ON')
            self.db.execute('BEGIN')  # stable read snapshot for this adapter/episode
            row = self.db.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()
            metadata = loads(row[0]) if row else {}
            if not isinstance(metadata, dict) or metadata.get('complete') is not True:
                raise ValueError('An already-built complete index is required')
            self.db.execute('SELECT docid,content,url FROM docs LIMIT 0')
            self.db.execute('SELECT content FROM search LIMIT 0')
            definition = self.db.execute("SELECT sql FROM sqlite_master WHERE name='search'").fetchone()
            if not definition or 'fts5' not in (definition[0] or '').lower():
                raise ValueError('search must be an FTS5 table')
            self.identity = {'kind': 'sqlite-fts5-bm25', 'index_id': index_id,
                'index_fingerprint': digest(metadata), 'metadata': metadata,
                'adapter': 'stride-cpu-or-1', 'query_timeout_seconds': timeout_seconds,
                'sqlite_runtime': sqlite3.sqlite_version, 'capabilities_sha256': digest(self.capabilities),
                'identity_scope': 'metadata hash and declared index label; not a new corpus byte audit'}
        except Exception:
            self.db.close()
            raise
        self.last_wire_request = self.last_wire_response = None

    def compile_query(self, query: str) -> dict:
        if not isinstance(query, str):
            raise ValueError('Query must be text')
        terms = list(dict.fromkeys(re.findall(r'\w+', query.lower())))
        expression = ' OR '.join('"' + word.replace('"', '""') + '"' for word in terms)
        return {'compiler': 'cpu-or-1', 'terms': terms, 'expression': expression}

    def search(self, query: str, top_k: int) -> list[dict]:
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError('top_k must be an integer from 1 to 20')
        compiled = self.compile_query(query)
        self.last_wire_request = {'kind': 'local_sql', 'query': query, 'top_k': top_k, **compiled}
        deadline = time.monotonic() + self.timeout_seconds
        self.db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        try:
            rows = [] if not compiled['expression'] else self.db.execute(
                "SELECT d.docid,d.url,snippet(search,0,'','',' ... ',48),bm25(search) "
                'FROM search JOIN docs d ON d.rowid=search.rowid WHERE search MATCH ? '
                'ORDER BY bm25(search),d.docid LIMIT ?', (compiled['expression'], top_k)).fetchall()
        except sqlite3.OperationalError as exc:
            raise ContractError('backend_failure', 'CPU query failed or reached its deadline', fatal=True) from exc
        finally:
            self.db.set_progress_handler(None, 0)
        out = [{'docid': r[0], 'title': r[1], 'snippet': r[2], 'score': -r[3]} for r in rows]
        self.last_wire_response = out
        return out

    def get_document(self, docid: str) -> dict:
        self.last_wire_request = {'kind': 'local_sql', 'docid': docid}
        row = self.db.execute('SELECT content,url FROM docs WHERE docid=?', (docid,)).fetchone()
        if row is None:
            raise ContractError('retrieval_protocol', 'Unknown index document', fatal=True)
        out = {'docid': docid, 'content': row[0], 'title': row[1], 'url': row[1]}
        self.last_wire_response = out
        return out

    def close(self):
        self.db.close()
