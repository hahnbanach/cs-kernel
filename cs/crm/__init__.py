"""The CRM port — the one true pluggable seam of the kernel.

An adapter is ONE free function per module, ``lookup(ctx, email) ->
CrmResult`` — interface, never a switch: no ``if company == …`` anywhere.
The registry below is explicit; ``resolve()`` runs at config load, so an
unknown ``[crm].adapter`` is a LOUD startup error, not a surprise at the
first ``cs dossier``. No entry-points, no plugin framework.

Degradation contract: ``lookup`` NEVER raises. Unconfigured → ``source=
"stub"``, ``ok=False``, an actionable note naming the exact env keys;
backend hiccup → ``ok=False`` + note. The dossier VERDICT stays
CRM-agnostic — STOP / REPLY-IN-THREAD / cold reads only Gmail evidence;
CRM is auxiliary intel above the verdict and must never gate it.

The normalized envelope keeps adapter-specific richness in ``facts``
(no lowest-common-denominator loss); the dossier prints generically from
``render_hints`` — one loop shows subscription status for one backend
and order history for another.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class CrmCtx:
    """Everything an adapter may need. ``call_rpc`` is a thin per-call
    closure over the kernel's ``rpc.call_sync`` — not an open WebSocket;
    HTTP-speaking adapters ignore it and read creds off ``settings``."""

    settings: Any
    call_rpc: Callable[..., Any] | None = None


@dataclass
class CrmRow:
    id: str
    label: str
    email: str
    facts: dict[str, str] = field(default_factory=dict)  # adapter-specific key→value


@dataclass
class CrmResult:
    source: str                    # adapter name, or "stub" when degraded-by-config
    ok: bool                       # backend reached & authoritative
    note: str | None               # actionable text when degraded/stub
    rows: list[CrmRow]
    render_hints: list[str]        # ordered facts keys the dossier prints

    def as_dict(self) -> dict:
        return asdict(self)


# Registry at the BOTTOM so the adapter modules can import the dataclasses
# from this package during initialization.
from . import none as _none            # noqa: E402
from . import shopify as _shopify      # noqa: E402
from . import starchat as _starchat    # noqa: E402

_REGISTRY: dict[str, Callable[[CrmCtx, str], CrmResult]] = {
    "starchat": _starchat.lookup,
    "shopify": _shopify.lookup,
    "none": _none.lookup,
}


def resolve(name: str) -> Callable[[CrmCtx, str], CrmResult]:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise RuntimeError(
            f"unknown CRM adapter '{name}' — valid: {sorted(_REGISTRY)}. "
            "Fix [crm].adapter in manifest.toml"
        ) from None


def lookup(settings, email: str) -> CrmResult:
    """Port entry point used by the CLI. Binds the engine RPC closure,
    dispatches to the configured adapter, and enforces the never-raises
    contract as a last backstop (the failure is SURFACED in the note the
    dossier prints — degraded, never silent)."""
    from .. import rpc as rpc_mod

    fn = resolve(settings.crm_adapter)

    def call_rpc(method: str, params: dict | None = None, timeout: float = 60):
        return rpc_mod.call_sync(settings, method, params, timeout=timeout)

    ctx = CrmCtx(settings=settings, call_rpc=call_rpc)
    try:
        return fn(ctx, email)
    except Exception as e:  # noqa: BLE001 — port contract: lookup never raises
        return CrmResult(
            source=settings.crm_adapter,
            ok=False,
            note=f"CRM adapter '{settings.crm_adapter}' crashed: {type(e).__name__}: {e}",
            rows=[],
            render_hints=[],
        )
