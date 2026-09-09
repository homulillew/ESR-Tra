"""CPU-only full-corpus SQLite FTS5 BM25 retrieval. Not the distributed Lucene index."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

from .protocol import HarnessError


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_index(corpus, output):
    import pyarrow.parquet as pq
    output = Path(output)
    if output.exists():
        raise FileExistsError("An index is never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output)
    db.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE docs (docid TEXT PRIMARY KEY, content TEXT NOT NULL, url TEXT NOT NULL);
        CREATE VIRTUAL TABLE search USING fts5(content, content='docs', content_rowid='rowid', tokenize='porter unicode61');
    """)
    n = 0
    try:
        for batch in pq.ParquetFile(corpus).iter_batches(batch_size=512, columns=["docid", "text", "url"]):
            rows = [(str(r["docid"]), r["text"], r["url"] or "") for r in batch.to_pylist()]
            if any(not text or not text.strip() for _, text, _ in rows):
                raise ValueError("Empty corpus document")
            db.executemany("INSERT INTO docs VALUES (?,?,?)", rows)
            n += len(rows)
            if n % 10240 == 0:
                db.commit()
                print(f"indexed document storage {n}", flush=True)
        print("building FTS5 postings", flush=True)
        db.execute("INSERT INTO search(search) VALUES ('rebuild')")
        meta = {"corpus_hash": file_hash(corpus), "documents": n, "sqlite_version": sqlite3.sqlite_version,
                "retriever": "sqlite_fts5_bm25", "tokenizer": "porter unicode61", "bm25_k1": 1.2,
                "bm25_b": 0.75, "query_operator": "OR", "format_version": 1, "complete": True}
        db.execute("INSERT INTO metadata VALUES ('identity', ?)", (json.dumps(meta),))
        db.commit()
        return meta
    finally:
        db.close()


class SQLiteRetriever:
    deterministic = True

    def __init__(self, path, log=None):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        row = self.db.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()
        if not row or not json.loads(row[0]).get("complete"):
            raise ValueError("Incomplete index; never use a partial corpus")
        self.identity = {"type": "sqlite_fts5_bm25", **json.loads(row[0])}
        self.log = log

    def _record(self, name, arguments, result, start):
        if self.log:
            self.log({"type": "retrieval", "operation": name, "arguments": arguments,
                      "result": result, "elapsed_seconds": time.monotonic() - start})
        return result

    def search(self, query, top_k):
        start = time.monotonic()
        # Escape every literal; model text cannot inject FTS operators or SQL.
        terms = list(dict.fromkeys(re.findall(r"\w+", query.lower())))
        expression = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
        rows = [] if not expression else self.db.execute(
            "SELECT d.docid, d.url, snippet(search,0,'','',' ... ',48), bm25(search) "
            "FROM search JOIN docs d ON d.rowid=search.rowid WHERE search MATCH ? "
            "ORDER BY bm25(search), d.docid LIMIT ?", (expression, top_k)).fetchall()
        hits = [{"docid": r[0], "url": r[1], "title": r[1], "snippet": r[2], "score": -r[3]} for r in rows]
        return self._record("search", {"query": query, "top_k": top_k}, hits, start)

    def get_document(self, docid):
        start = time.monotonic()
        row = self.db.execute("SELECT content,url FROM docs WHERE docid=?", (docid,)).fetchone()
        if row is None:
            raise HarnessError("retrieval_error", "Unknown corpus document")
        result = {"docid": docid, "content": row[0], "url": row[1], "title": row[1]}
        # Ledger separately keeps complete document on first admission; record every backend call here.
        self._record("get_document", {"docid": docid}, {"chars": len(row[0])}, start)
        return result
