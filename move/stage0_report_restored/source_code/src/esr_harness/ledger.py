"""Append-only, hash-chained episode journal. Replay never calls a model or retriever."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .protocol import canonical, digest


class Ledger:
    def __init__(self, path: str | Path = ":memory:", *, readonly: bool = False):
        self.path, self.readonly = str(path), readonly
        if readonly:
            if not Path(path).is_file():
                raise ValueError("Replay requires an existing v2 ledger")
            self.db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"header", "events"} <= tables:
                self.db.close()
                raise ValueError("Not a v2 ledger; legacy stores are never auto-migrated")
            self.verify()
            self._last_seq = self.db.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]
            return
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and not {"header", "events"} <= tables:
            self.db.close()
            raise ValueError("Existing database is not a v2 ledger")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS header (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL,
                                               previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS immutable_header_update BEFORE UPDATE ON header
                BEGIN SELECT RAISE(ABORT, 'immutable header'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_header_delete BEFORE DELETE ON header
                BEGIN SELECT RAISE(ABORT, 'immutable header'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_event_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_event_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
        """)
        self.verify()
        self._last_seq = self.db.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]

    def initialize(self, header: dict) -> None:
        encoded = canonical(header)
        row = self.db.execute("SELECT payload FROM header WHERE singleton=1").fetchone()
        if row:
            if row[0] != encoded:
                raise ValueError("Episode header mismatch: question/config/model identity cannot change on resume")
        else:
            if self.readonly:
                raise ValueError("Read-only ledger has no header")
            with self.db:
                self.db.execute("INSERT INTO header VALUES (1, ?)", (encoded,))

    @property
    def header(self) -> dict:
        row = self.db.execute("SELECT payload FROM header WHERE singleton=1").fetchone()
        return json.loads(row[0]) if row else {}

    def append(self, event: dict[str, Any]) -> int:
        if self.readonly:
            raise RuntimeError("Read-only ledger")
        if not self.header:
            raise ValueError("Initialize an episode header before appending")
        encoded = canonical(event)
        # BEGIN IMMEDIATE plus tail lookup inside transaction detects competing writers.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT seq, event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            if (row[0] if row else 0) != self._last_seq:
                raise RuntimeError("Concurrent writer detected; one runner per episode is required")
            seq, previous = (row[0] + 1, row[1]) if row else (1, digest(self.header))
            hashed = digest({"seq": seq, "previous": previous, "event": event})
            self.db.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (seq, encoded, previous, hashed))
        self._last_seq = seq
        return seq

    def events(self) -> list[dict]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM events ORDER BY seq")]

    def verify(self) -> None:
        previous, expected = digest(self.header), 1
        for seq, payload, prev, hashed in self.db.execute("SELECT * FROM events ORDER BY seq"):
            event = json.loads(payload)
            if seq != expected or prev != previous or hashed != digest({"seq": seq, "previous": prev, "event": event}):
                raise ValueError(f"Corrupt ledger at event {seq}")
            previous, expected = hashed, expected + 1

    def export(self, path: str | Path) -> None:
        self.verify()
        if self.path != ":memory:" and Path(path).resolve() == Path(self.path).resolve():
            raise ValueError("Export cannot overwrite the source ledger")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"header": self.header, "events": self.events()},
                                        ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self):
        self.db.close()
