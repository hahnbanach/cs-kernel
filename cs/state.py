"""Local SQLite state at settings.db_path (~/.<slug>-cs/cs.db; PII — never in the repo).

- `sends`: one row per send attempt (real or dry-run), for audit + dedup.
- `do_not_contact`: suppression list.

Dedup counts only real sends (status='sent'): repeated dry-runs never
suppress, so a preview always shows the full would-send list."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sends (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  category   TEXT NOT NULL,          -- lead | signup | cancellation
  key        TEXT NOT NULL,          -- firebase uid (lead) | business_id (signup/cancellation)
  email      TEXT,
  subject    TEXT,
  message_id TEXT,
  status     TEXT NOT NULL,          -- sent | dry_run | failed
  dry_run    INTEGER NOT NULL,
  sent_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sends_key_cat ON sends(key, category, sent_at);
CREATE TABLE IF NOT EXISTS do_not_contact (
  email    TEXT PRIMARY KEY,
  reason   TEXT,
  added_at REAL NOT NULL
);
"""


class State:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def already_contacted(self, key: str, category: str, within_days: int) -> bool:
        cutoff = time.time() - within_days * 86400
        cur = self.conn.execute(
            "SELECT 1 FROM sends WHERE key=? AND category=? AND status='sent' "
            "AND sent_at>=? LIMIT 1",
            (key, category, cutoff),
        )
        return cur.fetchone() is not None

    def sent_today(self) -> int:
        cutoff = time.time() - 86400
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM sends WHERE status='sent' AND sent_at>=?", (cutoff,)
        )
        return int(cur.fetchone()[0])

    def do_not_contact_set(self) -> set[str]:
        return {
            r["email"].strip().lower()
            for r in self.conn.execute("SELECT email FROM do_not_contact")
            if r["email"]
        }

    def record(
        self,
        *,
        category: str,
        key: str,
        email: str | None,
        subject: str | None,
        message_id: str | None,
        status: str,
        dry_run: bool,
    ) -> None:
        self.conn.execute(
            "INSERT INTO sends(category,key,email,subject,message_id,status,dry_run,sent_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (category, key, email, subject, message_id, status, 1 if dry_run else 0, time.time()),
        )
        self.conn.commit()

    def suppress(self, email: str, reason: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO do_not_contact(email,reason,added_at) VALUES(?,?,?)",
            (email.strip().lower(), reason, time.time()),
        )
        self.conn.commit()
