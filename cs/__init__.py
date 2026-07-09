"""cs — the shared kernel of the <company>-cs customer-service operators.

The engine daemon (zylch-server@<uid>, the mrcall-desktop engine) is the
body: mail archive, entity memory, tasks, trained writing voice,
draft/send. Claude Code is the brain. cs is thin transport + operator
discipline: producer worklist (plan), per-candidate dossier (threads /
recent contact / tasks / CRM), campaign lifecycles, and a gated chat
surface for engine-side drafting. Contextual mail is composed ONLY by
the engine; only fixed-template bulk is cs-owned (send_mail / sms).

Per-company variance is DECLARED, never coded: it comes from the stamped
clone's manifest.toml (cs/manifest.py) through Settings (cs/config.py).
This package contains no company literal — see the kernel CLAUDE.md
(the charter) and the CI grep gate. The module path `cs` is FROZEN:
every permission string in the clones is the literal
`.venv/bin/python -m cs …`; `prog_name` is display-only.
"""
