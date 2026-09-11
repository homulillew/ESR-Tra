"""Append-only SQLite event log. One episode, optimistic single-writer ownership."""
from __future__ import annotations

from pathlib import Path
import sqlite3
from .protocol import VERSION, ContractError, canonical, digest, parse_json


class Ledger:
    def __init__(self, path: str | Path, *, readonly: bool = False):
        self.path = str(path)
        self.readonly = readonly
        if readonly:
            uri = Path(path).resolve().as_uri() + '?mode=ro'
            self.db = sqlite3.connect(uri, uri=True, isolation_level=None)
        else:
            if self.path != ':memory:':
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, isolation_level=None)
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and 'v3_events' not in tables:
                self.db.close()
                raise ContractError('ledger_format', 'Refusing to add v3 tables to a legacy/non-v3 database')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('CREATE TABLE IF NOT EXISTS v3_events (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL)')
        self.events = self.verify()
        self.seq = len(self.events)
        self.head = self.events[-1]['hash'] if self.events else '0' * 64
        if self.events and self.events[0]['payload'].get('protocol') != VERSION:
            raise ContractError('protocol_version', 'Not an ESR v3 ledger; no implicit migration')

    def verify(self) -> list[dict]:
        previous, events = '0' * 64, []
        try:
            rows = self.db.execute('SELECT seq,body,previous,hash FROM v3_events ORDER BY seq')
        except sqlite3.OperationalError as exc:
            raise ContractError('ledger_format', 'Missing v3 event table') from exc
        for expected, (seq, body, prev, hashed) in enumerate(rows, 1):
            record = parse_json(body)
            if seq != expected or prev != previous or digest([seq, prev, record]) != hashed:
                raise ContractError('ledger_integrity', f'Hash/sequence mismatch at event {seq}')
            events.append({'seq': seq, **record, 'hash': hashed})
            previous = hashed
        return events

    def append(self, kind: str, payload: dict, state: dict | None = None) -> None:
        if self.readonly:
            raise ContractError('readonly', 'Replay never writes')
        record = {'kind': kind, 'payload': payload}
        if state is not None:
            record['state'] = state
        body = canonical(record)
        seq, previous = self.seq + 1, self.head
        hashed = digest([seq, previous, parse_json(body)])
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT seq,hash FROM v3_events ORDER BY seq DESC LIMIT 1').fetchone()
            if (row or (0, '0' * 64)) != (self.seq, self.head):
                raise ContractError('concurrent_writer', 'Ledger changed; reload instead of overwriting')
            self.db.execute('INSERT INTO v3_events VALUES (?,?,?,?)', (seq, body, previous, hashed))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise
        event = {'seq': seq, **parse_json(body), 'hash': hashed}
        self.events.append(event)
        self.seq, self.head = seq, hashed

    def latest_state(self) -> dict | None:
        for event in reversed(self.events):
            if 'state' in event:
                return parse_json(canonical(event['state']))
        return None

    def export(self) -> dict:
        events = self.verify()
        states = [e['state'] for e in events if 'state' in e]
        return {'protocol': VERSION, 'event_count': len(events), 'head': events[-1]['hash'] if events else None,
                'state': states[-1] if states else None, 'events': events}

    def close(self):
        self.db.close()
