"""Deterministic 'still awaiting a human reply' sweep — Sent-anchored.

WHY THIS EXISTS: the triage skill used to discover open customer mail by asking
the engine LLM ("elenca la posta ancora senza risposta"). That is
NON-DETERMINISTIC — two runs of the same query returned different sets and
missed real unanswered customer mail 6–13 days old that had no engine task
(incident 2026-07-16). This module answers the binary deterministically:
enumerate recent inbound, subtract every sender we've since written to (Gmail
Sent = the dedup ground truth), no LLM in the discovery loop.

Scope is intentionally narrow: it answers ONLY "did we send them anything after
their last message". It does NOT classify intent or detect autoresponders — that
stays the LLM's job downstream. Over-including an autoresponder sender is
acceptable; the skill filters those with judgment.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import Settings


def compute_open(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
) -> list[dict]:
    """Pure open-logic — no IMAP, unit-testable on plain dicts.

    - group `inbound` by `email`, keep each sender's LATEST message (max date);
    - a sender is OPEN if NO `sent` message addressed to that email has
      date > that latest inbound date;
    - drop any sender whose email is in `self_addrs` or `ignore`;
    - return OPEN senders oldest-first (by latest_inbound date), each row
      {email, name, last_inbound_date, subject, days_waiting}.
    """
    self_addrs = {a.strip().lower() for a in self_addrs if a}
    ignore = {a.strip().lower() for a in ignore if a}

    latest: dict[str, dict] = {}
    for m in inbound:
        e = (m.get("email") or "").strip().lower()
        if not e or e in self_addrs or e in ignore:
            continue
        cur = latest.get(e)
        if cur is None or m["date"] > cur["date"]:
            latest[e] = m

    sent_max: dict[str, datetime] = {}
    for s in sent:
        d = s.get("date")
        if d is None:
            continue
        for a in s.get("to", []):
            a = (a or "").strip().lower()
            if not a:
                continue
            if a not in sent_max or d > sent_max[a]:
                sent_max[a] = d

    out: list[dict] = []
    for e, m in latest.items():
        last = m["date"]
        if e in sent_max and sent_max[e] > last:
            continue  # we replied after their last inbound → answered
        out.append(
            {
                "email": e,
                "name": m.get("name") or "",
                "last_inbound_date": last,
                "subject": m.get("subject") or "",
                "days_waiting": (now - last).days,
            }
        )
    out.sort(key=lambda r: r["last_inbound_date"])  # oldest first
    return out


def open_threads(settings: Settings, days: int) -> list[dict]:
    """IMAP-backed sweep: pull inbound + sent from Gmail, exclude self /
    configured system senders / suppressed addresses, return `compute_open`."""
    from . import gmail_archive

    inbound = gmail_archive.inbound_recent(settings, days)
    sent = gmail_archive.sent_recent(settings, days)

    self_addrs = set(settings.self_email_set)
    if settings.email_address:
        self_addrs.add(settings.email_address.strip().lower())

    ignore = set(settings.system_sender_set)
    try:
        from .state import State

        ignore |= State(settings.db_path).do_not_contact_set()
    except Exception:
        pass  # suppression is best-effort; a missing db must not break discovery

    return compute_open(inbound, sent, self_addrs, ignore, datetime.now(timezone.utc))
