"""JSON-RPC 2.0 client for the mrcall-desktop engine daemon.

Transport: one JSON object per WebSocket TEXT message, against
``wss://<host>/ws/<uid>`` (Caddy routes to the per-uid unix socket).
The handshake carries ``Authorization: Bearer <firebase-id-token>``;
the daemon verifies RS256 and gates ``token.sub == OWNER_ID``.

A background receive task routes responses to per-id futures and
collects server notifications (frames without ``id``), so a second
call (e.g. ``chat.approve``) can be issued while a long-running one
(``chat.send``) is still in flight — that is how the engine's
approval gate works.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any, Awaitable, Callable, Optional

import websockets

from . import auth
from .config import Settings

NotifyHandler = Callable[[str, Any], Optional[Awaitable[None]]]


class EngineError(RuntimeError):
    """JSON-RPC error response from the engine."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"engine error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class EngineClient:
    def __init__(self, settings: Settings, on_notification: NotifyHandler | None = None):
        self.settings = settings
        self.on_notification = on_notification
        self.notifications: list[dict] = []
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._pending: dict[Any, asyncio.Future] = {}
        self._ids = itertools.count(1)

    @property
    def url(self) -> str:
        base = self.settings.engine_ws_url.rstrip("/")
        if not base:
            raise RuntimeError(
                "engine_ws_url not configured — set [engine].ws_url in manifest.toml"
            )
        return f"{base}/ws/{self.settings.engine_owner_uid}"

    async def __aenter__(self) -> "EngineClient":
        token = auth.get_id_token(self.settings)
        self._ws = await websockets.connect(
            self.url,
            additional_headers={"Authorization": f"Bearer {token}"},
            max_size=32 * 1024 * 1024,  # email bodies / search results can be large
            open_timeout=30,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, *exc) -> None:
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            await self._ws.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    frame = json.loads(raw)
                except ValueError:
                    continue
                if frame.get("id") is not None and (
                    "result" in frame or "error" in frame
                ):
                    fut = self._pending.pop(frame["id"], None)
                    if fut and not fut.done():
                        if "error" in frame:
                            e = frame["error"] or {}
                            fut.set_exception(
                                EngineError(
                                    e.get("code", -1), e.get("message", ""), e.get("data")
                                )
                            )
                        else:
                            fut.set_result(frame.get("result"))
                else:  # notification
                    method = frame.get("method", "")
                    params = frame.get("params")
                    self.notifications.append({"method": method, "params": params})
                    if self.on_notification:
                        out = self.on_notification(method, params)
                        if asyncio.iscoroutine(out):
                            await out
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("engine connection closed"))

    async def call(self, method: str, params: dict | None = None, timeout: float = 60) -> Any:
        rid = next(self._ids)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        await self._ws.send(
            json.dumps(
                {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
            )
        )
        return await asyncio.wait_for(fut, timeout=timeout)


def call_sync(
    settings: Settings, method: str, params: dict | None = None, timeout: float = 60
) -> Any:
    """One-shot convenience for CLI verbs: connect, call, disconnect."""

    async def _run():
        async with EngineClient(settings) as c:
            return await c.call(method, params, timeout=timeout)

    return asyncio.run(_run())


async def chat(
    settings: Settings,
    message: str,
    *,
    allow_tools: set[str] | None = None,
    timeout: float = 600,
    echo: Callable[[str], None] = print,
    conversation_id: str | None = None,
) -> Any:
    """Run one engine-chat turn with an explicit tool-approval policy.

    The engine pauses on destructive tools (send_email, update_memory, …)
    and emits ``chat.pending_approval``; we approve a tool only if it is in
    ``allow_tools``, otherwise we deny and the engine LLM continues without
    it. Non-destructive tools (search, compose, create_draft) auto-execute
    engine-side and never reach this gate.

    Each call gets a UNIQUE ``conversation_id`` by default. The engine's
    busy-guard is per conversation_id, defaulting to "general"; if every cs
    one-shot used "general" they would share one lane, and an interrupted
    call (or a parallel session) leaving "general" occupied would make every
    later call fail ``ChatBusyError``. A fresh id per one-shot isolates us.
    """
    import uuid

    allow = allow_tools or set()
    conv = conversation_id or f"cs-{uuid.uuid4().hex[:16]}"
    client: EngineClient | None = None
    approvals: list[dict] = []

    async def on_notify(method: str, params: Any) -> None:
        if method != "chat.pending_approval":
            return
        p = params or {}
        tool = p.get("tool_name") or p.get("name") or ""
        tool_use_id = p.get("tool_use_id")
        mode = "once" if tool in allow else "deny"
        approvals.append({"tool": tool, "mode": mode, "input": p.get("input")})
        echo(f"[approval] {tool} -> {mode}")
        await client.call("chat.approve", {"tool_use_id": tool_use_id, "mode": mode})

    async with EngineClient(settings, on_notification=on_notify) as c:
        client = c
        result = await c.call(
            "chat.send", {"message": message, "conversation_id": conv}, timeout=timeout
        )
        return {"result": result, "approvals": approvals, "notifications": c.notifications}
