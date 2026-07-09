"""No-CRM adapter — a well-formed stub for clones without a CRM backend.

``[crm].adapter = "none"``: the dossier still prints its Gmail-grounded
verdict unchanged; the CRM section shows this stub note instead of rows.
"""
from __future__ import annotations

from . import CrmCtx, CrmResult


def lookup(ctx: CrmCtx, email: str) -> CrmResult:  # noqa: ARG001 — port signature
    return CrmResult(
        source="stub",
        ok=False,
        note='no CRM adapter configured ([crm].adapter = "none" in manifest.toml)',
        rows=[],
        render_hints=[],
    )
