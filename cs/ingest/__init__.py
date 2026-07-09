"""The producer/ingest port — second conformer pair of the port pattern.

``fetch(settings, period)`` returns the WORKLIST contract that
``cs/filter.py`` expects:

    {generated_at, window,
     leads:         [{uid, ...}],                      # uid-keyed; email resolved later
     signups:       [{business_id, email_address, ...}],
     cancellations: [{business_id, email_address, ...}],
     note?: str}                                       # actionable when degraded

Registry is explicit; ``resolve()`` runs at config load so an unknown
``[producer].adapter`` fails LOUD at startup. ``fetch`` itself never
raises: a failing producer degrades to an empty, well-formed worklist
whose ``note`` carries the error — ``cs plan`` prints it (surfaced,
never silent).
"""
from __future__ import annotations

from typing import Callable


def empty_worklist(period: str, note: str) -> dict:
    return {
        "generated_at": None,
        "window": period,
        "leads": [],
        "signups": [],
        "cancellations": [],
        "note": note,
    }


# Registry at the BOTTOM of the definitions so adapter modules can import
# `empty_worklist` from this package during initialization.
from . import mrcall_tracking as _mrcall_tracking  # noqa: E402
from . import none as _none                        # noqa: E402

_REGISTRY: dict[str, Callable] = {
    "mrcall-tracking": _mrcall_tracking.fetch,
    "none": _none.fetch,
}


def resolve(name: str) -> Callable:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise RuntimeError(
            f"unknown producer adapter '{name}' — valid: {sorted(_REGISTRY)}. "
            "Fix [producer].adapter in manifest.toml"
        ) from None


def fetch(settings, period: str = "7d") -> dict:
    fn = resolve(settings.producer_adapter)
    try:
        return fn(settings, period=period)
    except Exception as e:  # noqa: BLE001 — degrade to an empty worklist, note surfaced by `cs plan`
        return empty_worklist(
            period,
            f"producer '{settings.producer_adapter}' failed: {type(e).__name__}: {e}",
        )
