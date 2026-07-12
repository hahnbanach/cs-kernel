# cs-kernel

**The shared engine of company-scoped customer-service operators.**

One pip-installable package (`import cs`). Each company gets a thin clone
(`mrcall-cs`, `124-cs`, yours) that holds only a `manifest.toml` and prose —
never a fork of the code. Upgrades are a pin bump, not a cherry-pick.

```text
pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
python -m cs init          # interactive: builds your <slug>-cs/ clone
cd <slug>-cs && pip install -r requirements.txt
```

---

## Why this exists

Support mail is body work (sync, memory, voice, drafts) plus brain work
(triage, campaigns, policy). The **body** is an engine daemon per mailbox.
The **brain** is this CLI + LLM skills.

If every company forks the brain, you get drift: one clone hardens Gmail-Sent
dedup, another still trusts a broken search; one renames a path, permissions
silently die. **cs-kernel is the anti-fork:** shared code, declared variance.

| Lives in the kernel | Lives in the company clone |
|---|---|
| CLI verbs, auth, RPC, Gmail IMAP | `manifest.toml` (identity, knobs, adapters) |
| Campaign runner + pack loaders | `company/*.md` skill prose |
| CRM / producer **ports** | Campaign packs under `campaigns/` |
| Draft-only safety gates | Secrets in `~/.<slug>-cs/.env` |
| `cs init` / `cs update` templates | Customer dossiers, local history |

Voice, signature, and product policy stay in the engine profile (`USER_NOTES`)
— outside every git repo.

---

## Quick start — new company

**1. Install the kernel** (SSH or HTTPS):

```bash
pip install "cs-kernel @ git+ssh://git@github.com/hahnbanach/cs-kernel@v0.2.0"
# or
pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
```

**2. Generate a clone** (interactive prompts: name, mailbox, engine uid, CRM…):

```bash
python -m cs init
```

This creates `<slug>-cs/` with:

- rendered `manifest.toml`, `.claude/` skills & commands, `bin/`, docs skeleton  
- `template-manifest.json` (checksums for later updates)  
- `git init` already run  

**3. Secrets** — copy `.env.example` → `~/.<slug>-cs/.env` and fill:

- `EMAIL_PASSWORD`, `FIREBASE_WEB_API_KEY`  
- `CS_ACCOUNTS` (real uids)  
- adapter-specific keys (e.g. Shopify) if you selected them  

**4. Install the pin inside the clone and smoke-test:**

```bash
cd <slug>-cs
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m cs whoami
```

**5. Later, pull template / kernel improvements:**

```bash
# bump [repo].kernel_version in manifest.toml if needed, then:
.venv/bin/pip install -r requirements.txt   # re-pin package
python -m cs update                         # re-apply skill/template files
```

`cs update` overwrites files you never touched; if you edited a skill and the
template also changed, it shows a diff and asks.

---

## What the CLI does

Run from a clone root (where `manifest.toml` lives):

```bash
.venv/bin/python -m cs <verb>
```

| Verb | Role |
|---|---|
| `plan` | Outreach worklist from the producer adapter |
| `whoami` / `rpc` | Engine session + raw JSON-RPC |
| `thread` / `contacted` / `dossier` | History + **Gmail Sent** dedup truth |
| `tasks` / `business` | Engine tasks + CRM port |
| `ask` / `draft-reply` | Read-only / draft-only chat (cannot send) |
| `campaign …` | List, pending, queue-draft, pack senders… |
| `drive` | Read-only Drive (scope from manifest) |
| `init` / `update` | Clone lifecycle (no manifest required for `init`) |

**Sending** is deliberately hard: headless/cron stays draft-only; contextual
send goes through the engine approval gate; fixed-template bulk uses gated
SMTP/SMS with stamp-before-send, rate caps, and pause files.

---

## Architecture (one picture)

```text
┌──────────────────── company clone ────────────────────┐
│  manifest.toml   company/*.md   campaigns/   docs/    │
│  .claude/skills  bin/cs_operator_cron.sh              │
└───────────────────────────┬───────────────────────────┘
                            │ pip pin @vX.Y.Z
┌───────────────────────────▼───────────────────────────┐
│  cs-kernel  (this repo)  import package: cs             │
│  config · rpc · campaign · gmail_archive · crm · …    │
│  templates/project  →  cs init / cs update              │
└───────────────────────────┬───────────────────────────┘
                            │ WebSocket + Firebase
┌───────────────────────────▼───────────────────────────┐
│  mrcall-desktop engine (per-mailbox daemon)             │
│  mail sync · entity memory · voice · draft/send tools   │
└───────────────────────────────────────────────────────┘
```

**Adapters** (ports, not `if company ==`):

- **CRM** — `starchat` | `shopify` | `none`  
- **Producer** — `mrcall-tracking` | `none`  

Unknown adapter names fail loud at config load.

---

## Safety (non-negotiable)

These are kernel **invariants**, not manifest knobs:

1. Never cold-mail without a dossier; never re-contact inside the dedup window.  
2. **Gmail Sent/All Mail** is dedup ground truth — not the engine archive.  
3. Headless operator is **draft-only** (config + permission deny list).  
4. Module path stays `python -m cs` forever (permission strings depend on it).  
5. No company literals in `cs/` — identity comes only from Settings/manifest.  
6. `~/.<slug>-cs/CS_PAUSE` kills ticks instantly.

---

## Versioning & collaudo

- Tags only: `v0.MINOR.PATCH` (see [CHANGELOG.md](CHANGELOG.md)).  
- Clones pin tags in `requirements.txt`, never branches.  
- Every change is meant to preserve  
  `kernel + manifest(company) ≡ that company's operator`  
  on CLI help, permissions, and live read-only verbs.

```bash
# develop against a local checkout
pip install -e /path/to/cs-kernel
```

---

## Repo layout

```text
cs/
  cli.py              verbs
  project_init.py     cs init
  project_update.py   cs update
  templates/project/  Jinja skeleton for new clones
  campaign*.py        lifecycles + packs
  crm/  ingest/       adapter ports
  gmail_*.py          Sent/drafts IMAP
  …
tests/                semantic gates + golden
CHANGELOG.md
CLAUDE.md             operator charter for agents working on the kernel
```

---

## License & status

Private product surface made public as reusable infrastructure.  
Use at your own risk; the operators that ship on this kernel still require a
running engine, credentials, and human review in draft mode.

**Current release:** `v0.2.0` — includes `cs init` / `cs update`.

```bash
pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
python -m cs init
```
