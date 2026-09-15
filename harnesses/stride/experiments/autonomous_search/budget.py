"""User-authorized allowance epochs on the existing append-only request ledger."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'examples'))
from trace_question_a3 import Budget


def renew(path, epoch, allowance):
    """Replace the remaining allowance once; never delete or relabel old requests."""
    if type(allowance) is not int or allowance <= 0:
        raise ValueError('Positive integer allowance required')
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True, isolation_level=None)
    try:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS allowance_epochs '
                   '(epoch TEXT PRIMARY KEY, utc TEXT, prior_cap INTEGER, baseline_used INTEGER, '
                   'allowance INTEGER, effective_cap INTEGER, previous_requests_sha256 TEXT)')
        existing = db.execute('SELECT * FROM allowance_epochs WHERE epoch=?', (epoch,)).fetchone()
        if existing:
            if existing[4] != allowance:
                raise ValueError('Epoch allowance differs; cannot refresh it twice')
            db.execute('COMMIT'); return dict(zip(
                ['epoch','utc','prior_cap','baseline_used','allowance','effective_cap','previous_requests_sha256'], existing))
        caps = db.execute('SELECT cap FROM budget').fetchall()
        if len(caps) != 1:
            raise ValueError('Invalid existing ledger')
        rows = db.execute('SELECT * FROM requests ORDER BY id').fetchall()
        used = len(rows); effective = used + allowance
        digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        record = (epoch, datetime.now(timezone.utc).isoformat(), caps[0][0], used, allowance, effective, digest)
        db.execute('INSERT INTO allowance_epochs VALUES (?,?,?,?,?,?,?)', record)
        db.execute('UPDATE budget SET cap=?', (effective,))
        db.execute('COMMIT')
        return dict(zip(['epoch','utc','prior_cap','baseline_used','allowance','effective_cap','previous_requests_sha256'], record))
    except Exception:
        if db.in_transaction: db.execute('ROLLBACK')
        raise
    finally: db.close()


class EpochBudget(Budget):
    def __init__(self, path, run, epoch, policy_limit, judge_limit):
        super().__init__(path, run, policy_limit + judge_limit)
        row = self.db.execute('SELECT baseline_used,allowance,effective_cap FROM allowance_epochs WHERE epoch=?', (epoch,)).fetchone()
        if row is None:
            self.close(); raise ValueError('Authorized allowance epoch missing')
        self.baseline, self.allowance, self.epoch_cap = row
        self.role = 'policy'; self.policy_sealed = False
        self.role_limits = {'policy': policy_limit, 'judge': judge_limit}

    def take(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            s = self.snapshot()
            if self.role not in self.role_limits or (self.role == 'judge') != self.policy_sealed:
                raise ValueError('Invalid request role or policy seal')
            role_used = self.db.execute('SELECT count(*) FROM requests WHERE run=? AND role=?', (self.run, self.role)).fetchone()[0]
            if (s['cap'] != self.epoch_cap or s['used'] >= self.epoch_cap
                    or s['this_run'] >= self.limit or role_used >= self.role_limits[self.role]):
                raise ValueError('Attempt budget exhausted or allowance changed')
            n = self.db.execute('INSERT INTO requests(run,role,status) VALUES (?,?,?)', (self.run, self.role, 'unknown')).lastrowid
            self.db.execute('COMMIT'); return n
        except Exception:
            self.db.execute('ROLLBACK'); raise

    def window(self):
        s = self.snapshot()
        return {**s, 'epoch_allowance': self.allowance, 'epoch_used': s['used'] - self.baseline,
                'epoch_remaining': self.epoch_cap - s['used']}
