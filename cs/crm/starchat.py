"""StarChat CRM adapter — the engine's ``mrcall.search_businesses`` RPC.

Auth rides the engine session (``ctx.call_rpc``) — zero extra keys, no
creds in the manifest beyond ``[crm].adapter = "starchat"``. The
try/except lives HERE, not in cli.py: a StarChat hiccup returns
``ok=False`` + note and never kills the dossier (degradation contract).
"""
from __future__ import annotations

from . import CrmCtx, CrmResult, CrmRow

RENDER_HINTS = ["status", "template"]


def lookup(ctx: CrmCtx, email: str) -> CrmResult:
    if ctx.call_rpc is None:
        return CrmResult(
            source="starchat", ok=False,
            note="engine RPC unavailable (no call_rpc bound)",
            rows=[], render_hints=list(RENDER_HINTS),
        )
    try:
        res = ctx.call_rpc("mrcall.search_businesses", {"emailAddress": email}, timeout=60)
    except Exception as e:  # noqa: BLE001 — a hiccup degrades, never raises
        return CrmResult(
            source="starchat", ok=False,
            note=f"StarChat lookup failed: {type(e).__name__}: {e}",
            rows=[], render_hints=list(RENDER_HINTS),
        )
    rows = []
    for b in (res or {}).get("businesses", []) if isinstance(res, dict) else []:
        rows.append(
            CrmRow(
                id=str(b.get("businessId") or ""),
                label=str(b.get("companyName") or b.get("name") or ""),
                email=email,
                facts={
                    "status": str(b.get("subscriptionStatus") or ""),
                    "template": str(b.get("template") or ""),
                },
            )
        )
    return CrmResult(source="starchat", ok=True, note=None,
                     rows=rows, render_hints=list(RENDER_HINTS))
