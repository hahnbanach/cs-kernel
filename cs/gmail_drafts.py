"""Put outreach drafts where the operator actually works: Gmail Drafts.

Phase-1 review surface: the engine composes (memory + voice + threading),
cs APPENDs the result into the operator's Gmail Drafts; the operator reviews,
edits and SENDS from Gmail. The sent mail lands in Gmail Sent and the
engine's normal sync picks it up — archive, threading and dedup stay
correct with zero extra plumbing. The engine-side Draft store is NOT used
in this flow (single copy, no divergence).
"""
from __future__ import annotations

import imaplib
import time
from email.message import EmailMessage
from email.utils import formatdate

from .config import Settings


def _imap(settings: Settings) -> imaplib.IMAP4_SSL:
    M = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    # tolerate the spaced app-password paste
    M.login(settings.email_address, settings.email_password.replace(" ", "").strip())
    return M


def find_drafts_folder(M: imaplib.IMAP4_SSL) -> str:
    """Folder carrying the \\Drafts special-use flag (locale-proof)."""
    typ, data = M.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if "\\drafts" in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return "[Gmail]/Drafts"


def append_draft(
    settings: Settings,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    html: str | None = None,
    cc: str | None = None,
) -> str:
    """Append one draft; returns the folder it landed in.

    With ``html``, the draft is multipart/alternative: ``body`` is the
    text/plain fallback, ``html`` the rich part (clean anchor text, full
    URLs — UTM included — only in href)."""
    msg = EmailMessage()
    msg["From"] = settings.email_address
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = " ".join(references or [in_reply_to])
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        typ, resp = M.append(
            f'"{folder}"', r"(\Draft)", imaplib.Time2Internaldate(time.time()), msg.as_bytes()
        )
        if typ != "OK":
            raise RuntimeError(f"IMAP APPEND failed: {typ} {resp!r}")
        return folder
    finally:
        try:
            M.logout()
        except Exception:
            pass


def list_drafts(settings: Settings) -> list[dict]:
    """Header summaries of the drafts waiting in the operator's Gmail Drafts —
    the review queue the operator sends from. Read-only."""
    import email as _email

    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        M.select(f'"{folder}"', readonly=True)
        typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        out = []
        for num in data[0].split():
            typ, md = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE)])")
            if typ != "OK" or not md or not md[0]:
                continue
            hdr = _email.message_from_bytes(md[0][1])
            out.append({"to": hdr.get("To"), "subject": hdr.get("Subject"), "date": hdr.get("Date")})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass
