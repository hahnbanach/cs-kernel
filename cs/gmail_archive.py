"""Read the operator mailbox's Gmail directly (IMAP) as the dedup GROUND TRUTH.

WHY THIS EXISTS: the engine's archive misses mail sent BY HAND from Gmail —
it only records sends made through its own send tool, and does NOT ingest the
Gmail `[Gmail]/Sent Mail` folder (verified 2026-06-24: a hand-sent reply to a
customer is in Gmail Sent but `emails.search folder:sent` returns 0). So the
engine's "Sent archive" is NOT the dedup truth the docs assume it is. Until the
engine is fixed, and as defence-in-depth after, dedup reads Gmail itself.

Read-only: SEARCH/FETCH headers only, never writes. Reuses the IMAP login from
`gmail_drafts` (same app-password, same mailbox).
"""
from __future__ import annotations

import email
from datetime import datetime, timedelta, timezone
from email import policy
from email.utils import parsedate_to_datetime

from .config import Settings
from .gmail_drafts import _imap


def _find_folder(M, flag: str, default: str) -> str:
    """Folder carrying a given special-use flag (locale-proof), e.g. \\Sent, \\All."""
    typ, data = M.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if flag in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return default


def _hdr(M, uid: bytes):
    typ, md = M.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (DATE FROM TO SUBJECT MESSAGE-ID)])")
    if typ != "OK" or not md or not md[0]:
        return None
    return email.message_from_bytes(md[0][1], policy=policy.default)


def sent_to(settings: Settings, addr: str, days: int | None = None) -> list[dict]:
    """Messages in Gmail's Sent folder addressed TO `addr` — the dedup truth.

    A non-empty result means the operator actually wrote to them (INCLUDING
    replies sent by hand, which the engine never sees). When `days` is given, the window
    is computed from each message's own Date header — NOT IMAP SINCE, whose
    INTERNALDATE the live engine re-touches on every sync, which made the same
    query flip between runs."""
    M = _imap(settings)
    try:
        sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
        M.select(f'"{sent}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "TO", addr)
        ids = d[0].split() if d and d[0] else []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
        out = []
        for uid in ids:
            h = _hdr(M, uid)
            if not h:
                continue
            raw = h.get("Date")
            dt = None
            if raw:
                try:
                    dt = parsedate_to_datetime(raw)
                    if dt is not None and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    dt = None
            if cutoff is not None and (dt is None or dt < cutoff):
                continue
            out.append({"date": raw, "subject": h.get("Subject"),
                        "message_id": h.get("Message-ID")})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def correspondence(settings: Settings, addr: str) -> list[dict]:
    """Real history with `addr`, both directions, DRAFT-FREE by construction.

    - our sends = the Sent folder, TO `addr` (drafts live in Drafts, never Sent);
    - their inbound = All Mail, FROM `addr` (a draft is FROM the operator
      mailbox, so it can never match FROM the contact).

    So a draft we just queued never counts as history (the trap that made a cold
    contact read as 'reply in thread'). Each row carries `direction` (sent|in)."""
    M = _imap(settings)
    try:
        out = []
        sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
        M.select(f'"{sent}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "TO", addr)
        for uid in (d[0].split() if d and d[0] else []):
            h = _hdr(M, uid)
            if h:
                out.append({"date": h.get("Date"), "from": h.get("From") or "",
                            "to": h.get("To") or "", "subject": h.get("Subject"),
                            "direction": "sent"})
        allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
        M.select(f'"{allm}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "FROM", addr)
        for uid in (d[0].split() if d and d[0] else []):
            h = _hdr(M, uid)
            if h:
                out.append({"date": h.get("Date"), "from": h.get("From") or "",
                            "to": h.get("To") or "", "subject": h.get("Subject"),
                            "direction": "in"})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def inbound_since(settings: Settings, addr: str, after=None) -> list[dict]:
    """Customer messages FROM `addr` (All Mail), optionally only those whose Date
    header is strictly after `after` (a tz-aware datetime) — GROUND TRUTH for
    'did they reply'. Independent of engine sync state. A message FROM the
    contact can never be one of our drafts, so this is draft-free by nature."""
    M = _imap(settings)
    try:
        allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
        M.select(f'"{allm}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "FROM", addr)
        ids = d[0].split() if d and d[0] else []
        out = []
        for uid in ids:
            h = _hdr(M, uid)
            if not h:
                continue
            raw = h.get("Date")
            dt = None
            if raw:
                try:
                    dt = parsedate_to_datetime(raw)
                    if dt is not None and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    dt = None
            if after is not None and (dt is None or dt <= after):
                continue
            out.append({"date": raw, "subject": h.get("Subject")})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass
