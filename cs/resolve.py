"""Resolve a Firebase UID -> email via the read-only Admin SDK service
account (the engine's Firebase project). Used only for leads — signups and
cancellations already carry email_address from the producer payload.

Returns None when the UID has no Firebase user or the user has no email
(anonymous / phone-only). Callers skip + log those."""
from __future__ import annotations

import firebase_admin
from firebase_admin import auth, credentials

from .config import Settings

_app = None


def _ensure_app(settings: Settings):
    global _app
    if _app is None:
        cred = credentials.Certificate(settings.firebase_sa_path)
        # Fixed neutral app name (kernel constant, internal to firebase_admin).
        _app = firebase_admin.initialize_app(cred, name="cs-kernel-resolve")
    return _app


def resolve_email(uid: str, settings: Settings) -> str | None:
    app = _ensure_app(settings)
    try:
        user = auth.get_user(uid, app=app)
    except auth.UserNotFoundError:
        return None
    return user.email or None
