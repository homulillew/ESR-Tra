"""Private episode archive: content-addressed objects and append-only event references.

No whole-agent-state copy on each event. Request messages are individually deduplicated.
Read-only replay checks hashes; interrupted requests are never automatically reissued.
"""
from __future__ import annotations

from pathlib import Path
from collections import Counter
import sqlite3
from typing import Any

from .contract import PROTOCOL, ContractError, canonical, digest, loads, text_hash


class Archive:
    def __init__(self, path: str | Path, *, readonly: bool = False):
        self.path, self.readonly = str(path), readonly
        p = Path(path)
        if not readonly and self.path != ":memory:":
            p.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive ownership: even an empty existing DB is not overwritten.
            with p.open("xb"):
                pass
        if readonly:
            self.db = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None)
        else:
            self.db = sqlite3.connect(self.path, isolation_level=None)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.executescript("""
                CREATE TABLE objects (sha TEXT PRIMARY KEY, text TEXT NOT NULL);
                CREATE TABLE events (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                  payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE docs (n INTEGER PRIMARY KEY, backend TEXT UNIQUE NOT NULL,
                  title TEXT NOT NULL, snapshot TEXT);
                CREATE TABLE evidence (n INTEGER PRIMARY KEY, doc INTEGER NOT NULL,
                  snapshot TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
                  text_hash TEXT NOT NULL, UNIQUE(doc,snapshot,start,end));
            """)
        try:
            row = self.db.execute("SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        except sqlite3.Error as exc:
            self.db.close()
            raise ContractError("archive_format", "Not a STRIDE archive") from exc
        self.seq, self.head = row or (0, "0" * 64)
        if readonly:
            try:
                self.verify()
            except Exception:
                self.db.close()
                raise

    def put(self, text: str) -> str:
        if self.readonly:
            raise ContractError("readonly", "Archive is read-only")
        sha = text_hash(text)
        self.db.execute("INSERT OR IGNORE INTO objects VALUES (?,?)", (sha, text))
        return sha

    def get(self, sha: str) -> str:
        row = self.db.execute("SELECT text FROM objects WHERE sha=?", (sha,)).fetchone()
        if row is None or text_hash(row[0]) != sha:
            raise ContractError("archive_integrity", "Missing or altered archive object", fatal=True)
        return row[0]

    def put_json(self, value: Any) -> str:
        return self.put(canonical(value))

    def json(self, sha: str) -> Any:
        return loads(self.get(sha))

    def append(self, kind: str, payload: dict) -> dict:
        if self.readonly:
            raise ContractError("readonly", "Replay never writes")
        body, seq, previous = canonical(payload), self.seq + 1, self.head
        hashed = digest([seq, kind, previous, loads(body)])
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            if (row or (0, "0" * 64)) != (self.seq, self.head):
                raise ContractError("concurrent_writer", "Archive head changed", fatal=True)
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (seq, kind, body, previous, hashed))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        self.seq, self.head = seq, hashed
        return {"seq": seq, "kind": kind, "payload": loads(body), "hash": hashed}

    def events(self):
        for seq, kind, payload, previous, hashed in self.db.execute("SELECT * FROM events ORDER BY seq"):
            yield {"seq": seq, "kind": kind, "payload": loads(payload), "previous": previous, "hash": hashed}

    def verify(self) -> dict:
        previous, count = "0" * 64, 0
        registered, snapshots, issued_evidence = {}, {}, {}
        for e in self.events():
            count += 1
            if e["seq"] != count or e["previous"] != previous or e["hash"] != digest(
                    [e["seq"], e["kind"], previous, e["payload"]]):
                raise ContractError("archive_integrity", "Event sequence/hash mismatch", fatal=True)
            previous = e["hash"]
            p = e["payload"]
            if e["kind"] == "document_registered":
                registered[p["ref"]] = (p["backend"], p["title"])
            elif e["kind"] == "snapshot":
                snapshots[p["document"]] = p["object"]
            elif e["kind"] == "evidence_registered":
                issued_evidence[p["ref"]] = p
            if e["kind"] == "model_request":
                self.load_request(p["request"])
            for key in ({"model_response": ("raw",), "backend_response": ("object",),
                         "snapshot": ("object",), "round_end": ("group", "notes"),
                         "action_execution": ("object",), "result_withheld": ("object",),
                         "repair_context": ("object",), "navigation_ack": ("object",)}.get(e["kind"], ())):
                self.get(p[key])
            if e["kind"] == "backend_response" and p.get("raw_wire"):
                self.get(p["raw_wire"])
        stored = {}
        for n, backend, title, snapshot in self.db.execute("SELECT * FROM docs"):
            ref = f"d{n}"
            stored[ref] = (backend, title)
            if snapshot != snapshots.get(ref):
                raise ContractError("archive_integrity", "Snapshot index differs from journal", fatal=True)
        if stored != registered:
            raise ContractError("archive_integrity", "Document index differs from journal", fatal=True)
        for sha, text in self.db.execute("SELECT sha,text FROM objects"):
            if text_hash(text) != sha:
                raise ContractError("archive_integrity", "Object hash mismatch", fatal=True)
        # Immutable evidence identities are checked independently of the event hashes.
        actual_evidence = {}
        for n, doc, snapshot, start, end, expected in self.db.execute("SELECT * FROM evidence"):
            actual_evidence[f"e{n}"] = {"ref": f"e{n}", "document": f"d{doc}", "snapshot": snapshot,
                "start": start, "end": end, "sha256": expected}
            if snapshots.get(f"d{doc}") != snapshot:
                raise ContractError("archive_integrity", "Evidence snapshot/document mismatch", fatal=True)
            text = self.get(snapshot)
            if not (0 <= start < end <= len(text)) or text_hash(text[start:end]) != expected:
                raise ContractError("archive_integrity", f"Evidence e{n} altered", fatal=True)
        if actual_evidence != issued_evidence:
            raise ContractError("archive_integrity", "Evidence index differs from journal", fatal=True)
        return {"event_count": count, "head": previous}

    def save_request(self, wire: dict) -> str:
        rest = {k: v for k, v in wire.items() if k != "messages"}
        return self.put_json({"envelope": self.put_json(rest),
                              "messages": [self.put_json(m) for m in wire["messages"]]})

    def load_request(self, ref: str) -> dict:
        manifest = self.json(ref)
        return {**self.json(manifest["envelope"]),
                "messages": [self.json(m) for m in manifest["messages"]]}

    def register_doc(self, backend: str, title: str) -> str:
        if self.readonly:
            raise ContractError("readonly", "Archive is read-only")
        row = self.db.execute("SELECT n FROM docs WHERE backend=?", (backend,)).fetchone()
        if row is None:
            n = self.db.execute("INSERT INTO docs(backend,title) VALUES (?,?)", (backend, title)).lastrowid
            self.append("document_registered", {"ref": f"d{n}", "backend": backend, "title": title})
        else:
            n = row[0]
        return f"d{n}"

    def doc(self, ref: str) -> dict:
        if not ref.startswith("d") or not ref[1:].isdigit():
            raise ContractError("document_ref", "Expected document handle")
        row = self.db.execute("SELECT n,backend,title,snapshot FROM docs WHERE n=?", (int(ref[1:]),)).fetchone()
        if row is None:
            raise ContractError("unknown_document", ref)
        return {"ref": ref, "backend": row[1], "title": row[2], "snapshot": row[3]}

    def snapshot(self, ref: str, text: str) -> str:
        doc = self.doc(ref)
        if doc["snapshot"]:
            return doc["snapshot"]
        if self.readonly:
            raise ContractError("readonly", "Archive is read-only")
        sha = self.put(text)
        self.db.execute("UPDATE docs SET snapshot=? WHERE n=? AND snapshot IS NULL", (sha, int(ref[1:])))
        self.append("snapshot", {"document": ref, "object": sha, "characters": len(text)})
        return sha

    def window(self, ref: str, start: int, length: int) -> dict:
        if self.readonly:
            raise ContractError("readonly", "Archive is read-only")
        doc = self.doc(ref)
        if not doc["snapshot"]:
            raise ContractError("missing_snapshot", ref)
        text = self.get(doc["snapshot"])
        if not 0 <= start < len(text):
            raise ContractError("range", f"start must be between 0 and {len(text)-1}")
        end = min(start + length, len(text))
        inserted = self.db.execute("INSERT OR IGNORE INTO evidence(doc,snapshot,start,end,text_hash) VALUES (?,?,?,?,?)",
                        (int(ref[1:]), doc["snapshot"], start, end, text_hash(text[start:end])))
        n = self.db.execute("SELECT n FROM evidence WHERE doc=? AND snapshot=? AND start=? AND end=?",
                            (int(ref[1:]), doc["snapshot"], start, end)).fetchone()[0]
        if inserted.rowcount:
            self.append("evidence_registered", {"ref": f"e{n}", "document": ref, "snapshot": doc["snapshot"],
                "start": start, "end": end, "sha256": text_hash(text[start:end])})
        return self.evidence(f"e{n}")

    def evidence(self, ref: str) -> dict:
        if not ref.startswith("e") or not ref[1:].isdigit():
            raise ContractError("evidence_ref", "Expected evidence handle")
        row = self.db.execute("SELECT * FROM evidence WHERE n=?", (int(ref[1:]),)).fetchone()
        if row is None:
            raise ContractError("unknown_evidence", ref)
        n, doc, sha, start, end, expected = row
        full = self.get(sha)
        text = full[start:end]
        if text_hash(text) != expected:
            raise ContractError("archive_integrity", "Evidence text hash mismatch", fatal=True)
        return {"ref": f"e{n}", "document": f"d{doc}", "snapshot": sha,
                "start": start, "end": end, "document_chars": len(full),
                "text": text, "sha256": expected, "kind": "raw_evidence"}

    def report(self) -> dict:
        integrity = self.verify()
        terminal, requests, completed, usage, backends, actions = None, [], set(), [], 0, []
        header, model_identity = None, None
        answer_contract = "legacy"
        seen, received_raw_rounds = set(), 0
        recovery_counts = Counter()
        for e in self.events():
            p = e["payload"]
            if e["kind"] in ("repair_context", "result_withheld", "delivery_preflight"):
                recovery_counts[e["kind"]] += 1
            if e["kind"] == "episode":
                header = p
                answer_contract = p.get("answer_contract", "legacy")
            elif e["kind"] == "answer_contract":
                answer_contract = p["current"]
            elif e["kind"] == "model_identity":
                model_identity = p
            elif e["kind"] == "model_request":
                requests.append(p)
                self.load_request(p["request"])
            elif e["kind"] == "model_response":
                completed.add(p["round"])
                self.json(p["raw"])
                usage.append(p.get("usage", {}))
            elif e["kind"] == "delivery_ack":
                new = set(p["evidence"]) - seen
                received_raw_rounds += bool(new)
                seen.update(p["evidence"])
            elif e["kind"] == "backend_request":
                backends += 1
            elif e["kind"] == "action_result":
                actions.append(p)
            elif e["kind"] == "terminal":
                terminal = p
        if header is None or header.get("protocol") not in ("stride-search-1", "stride-search-2", PROTOCOL):
            raise ContractError("archive_format", "Episode header missing or incompatible")
        totals = {k: sum(u[k] for u in usage if type(u.get(k)) is int) for k in
                  ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")}
        unknown = len(requests) - sum(type(u.get("input_tokens")) is int and type(u.get("output_tokens")) is int for u in usage)
        return {**integrity, "protocol": header["protocol"], "header": header,
                "answer_contract": answer_contract,
                "model_identity": model_identity,
                "terminal": terminal or {"outcome": "interrupted", "answer": ""},
                "model_attempts": len(requests), "backend_attempts": backends,
                "actions_recorded": len(actions), "executed_actions": sum(bool(a["executed"]) for a in actions),
                "usage_known": totals, "unknown_usage_calls": unknown,
                "outstanding_requests": [r["round"] for r in requests if r["round"] not in completed],
                "formal_correct": None, "recovery_events": dict(recovery_counts),
                "nonblocking_note_failures": sum(a["tool"] == "notes" and not a["result"]["ok"]
                    and a["result"].get("blocks_finish") is False for a in actions),
                "action_counts": dict(Counter(a["tool"] for a in actions)),
                "action_error_counts": dict(Counter(a["result"].get("code") for a in actions if not a["result"]["ok"])),
                "final_phase_requests": sum(bool(r["final"]) for r in requests),
                "compaction_requests": sum(bool(r["compacted"]) for r in requests),
                "rounds_receiving_new_raw": received_raw_rounds,
                "cache_query_hits": sum(bool(q["cached"]) for a in actions for q in a["result"].get("results", [])),
                "unchanged_note_updates": sum(a["tool"] == "notes" and a["result"].get("changed") is False for a in actions),
                "limitations": ["No semantic judge has run", "No resume or automatic reissue", "Hashes are not adversarial authentication"]}

    def close(self):
        self.db.close()
