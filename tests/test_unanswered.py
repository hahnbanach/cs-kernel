#!/usr/bin/env python3
"""Unit test for the PURE open-logic of the deterministic `cs unanswered` sweep.

`compute_open` answers ONE binary per sender — "did we send them anything after
their last inbound" — from plain dicts, no IMAP. This guards the invariants the
verb relies on: Sent-after-inbound closes a sender; Sent-before-inbound does not;
no Sent at all stays open; self/ignore excluded; oldest-first ordering;
days_waiting computed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cs.unanswered import compute_open

NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def run() -> None:
    inbound = [
        # replied AFTER last inbound -> NOT open
        {"email": "Answered@Example.com", "name": "Ans", "date": _dt(5),
         "subject": "need help"},
        # reply exists but BEFORE their last inbound -> OPEN
        {"email": "stale-reply@example.com", "name": "Stale", "date": _dt(3),
         "subject": "still waiting"},
        # never replied -> OPEN (and it's the OLDEST -> must sort first)
        {"email": "cold@example.com", "name": "Cold", "date": _dt(13),
         "subject": "hello?"},
        # two inbound from same sender: latest wins for the open/date decision
        {"email": "cold@example.com", "name": "Cold", "date": _dt(20),
         "subject": "older ping"},
        # self address -> excluded
        {"email": "me@example.com", "name": "Me", "date": _dt(2),
         "subject": "note to self"},
        # ignored (system) sender -> excluded
        {"email": "noreply@system.example", "name": "Sys", "date": _dt(1),
         "subject": "notification"},
    ]
    sent = [
        # closes answered@ (after their _dt(5) inbound)
        {"to": ["answered@example.com"], "date": _dt(4)},
        # a reply to stale-reply@ but BEFORE their _dt(3) inbound -> does NOT close
        {"to": ["stale-reply@example.com"], "date": _dt(9)},
    ]

    rows = compute_open(
        inbound, sent,
        self_addrs={"me@example.com"},
        ignore={"noreply@system.example"},
        now=NOW,
    )
    emails = [r["email"] for r in rows]

    assert "answered@example.com" not in emails, "sender replied-after must be closed"
    assert "me@example.com" not in emails, "self must be excluded"
    assert "noreply@system.example" not in emails, "ignore must be excluded"
    assert "stale-reply@example.com" in emails, "reply-before-inbound must stay OPEN"
    assert "cold@example.com" in emails, "never-replied must stay OPEN"
    assert emails == sorted(
        emails, key=lambda e: {r["email"]: r["last_inbound_date"] for r in rows}[e]
    )
    # oldest-first: cold@ (latest inbound 13d) precedes stale-reply@ (3d)
    assert emails[0] == "cold@example.com", f"oldest first violated: {emails}"

    cold = next(r for r in rows if r["email"] == "cold@example.com")
    assert cold["last_inbound_date"] == _dt(13), "latest of a sender's inbound must win"
    assert cold["days_waiting"] == 13, cold["days_waiting"]
    assert cold["name"] == "Cold" and cold["subject"] == "hello?"

    # empty sent -> everything (bar excluded) open
    rows2 = compute_open(inbound, [], self_addrs={"me@example.com"},
                         ignore={"noreply@system.example"}, now=NOW)
    assert {r["email"] for r in rows2} == {
        "answered@example.com", "stale-reply@example.com", "cold@example.com"
    }, [r["email"] for r in rows2]

    print("OK: compute_open — Sent-anchoring, self/ignore exclusion, ordering, days_waiting")


if __name__ == "__main__":
    run()
