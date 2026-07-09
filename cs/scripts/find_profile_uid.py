#!/usr/bin/env python3
"""Resolve a mailbox email -> Firebase uid via the read-only Admin SDK SA.

Operator SETUP tool for clone onboarding: finds the engine profile uid to
put in the manifest ([engine].owner_uid) and the env (CS_ENGINE_OWNER_UID).
Read-only (`auth.get_user_by_email`) — sends nothing, mutates nothing.

Usage:
  python -m cs.scripts.find_profile_uid <email> [--sa /path/to/firebase-sa.json]

Default SA: the first ``~/.<slug>-cs/firebase-sa.json`` found on this host
(any clone's key resolves any mailbox of the SAME Firebase project — the
engine platform shares one project across clones).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="find_profile_uid")
    ap.add_argument("email")
    ap.add_argument("--sa", default=None, help="service-account key path")
    a = ap.parse_args(argv)

    sa = a.sa
    if not sa:
        cands = sorted(Path.home().glob(".*-cs/firebase-sa.json"))
        if cands:
            sa = str(cands[0])
            print(f"using SA key: {sa}", file=sys.stderr)
    if not sa or not Path(sa).exists():
        print("no service-account key found — pass --sa /path/to/firebase-sa.json",
              file=sys.stderr)
        return 2

    cred = credentials.Certificate(sa)
    app = firebase_admin.initialize_app(cred, name="cs-kernel-find-profile-uid")
    try:
        user = auth.get_user_by_email(a.email, app=app)
    except auth.UserNotFoundError:
        print(f"NOT FOUND in this Firebase project: {a.email}", file=sys.stderr)
        return 1
    print(user.uid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
