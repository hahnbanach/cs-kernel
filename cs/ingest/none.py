"""No-producer adapter — the reply-only posture.

Returns an empty, well-formed worklist so `cs plan` runs clean and the
operator works reply-only (triage + campaigns). To wire a producer:
implement an adapter returning the worklist contract (see the package
docstring) from the company's own source, register it, and select it in
the manifest ([producer].adapter).
"""
from __future__ import annotations

from . import empty_worklist


def fetch(settings, period: str = "7d") -> dict:  # noqa: ARG001 — port signature
    return empty_worklist(
        period,
        'no producer wired ([producer].adapter = "none" in manifest.toml) — reply-only',
    )
