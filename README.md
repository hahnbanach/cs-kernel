# cs-kernel

**Shared CLI + operator skeleton for company-scoped customer-service bots.**

Install once, run `cs init`, answer a few questions, get a ready-to-run
`<your-company>-cs` repo. All companies share the same engine code; only
configuration and prose differ. No forking the core.

You need a running **[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)**
engine profile for the mailbox you want to operate (sync, memory, drafts,
send tools). This package is the thin brain in front of that body — not a
standalone mail server.

Examples below use a local **venv** and **[uv](https://github.com/astral-sh/uv)**
for installs. Install uv once if you need it: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
# one-shot bootstrap (creates .venv, installs kernel, runs init)
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
python -m cs init
```

---

## What you get

| Piece | Role |
|---|---|
| **mrcall-desktop engine** (separate product) | Per-mailbox daemon: Gmail sync, entity memory, writing voice, draft/send |
| **cs-kernel** (this package) | CLI verbs, safety gates, campaign runner, `init` / `update` |
| **Your clone** (e.g. `acme-cs/`) | `manifest.toml`, skills prose, campaign packs, secrets path |

Voice, signature, and product policy live in the engine profile
(`USER_NOTES`), not in git.

---

## Prerequisites

Before `cs init` is useful you need:

1. **Python 3.11+** and **uv** (or another pip-compatible installer)
2. A **mrcall-desktop** engine profile for your operator mailbox  
   (Firebase uid, WebSocket host, service-account access as required by your deploy)
3. **Mailbox credentials** the operator will use (IMAP/SMTP — typically Gmail)
4. Optional: CRM / lead producer backends if you enable those adapters

If you only install the package without an engine, `cs init` still creates the
repo, but live verbs (`whoami`, `dossier`, `draft-reply`, …) will not work
until the engine is up and secrets are filled.

---

## Example: ACME Corp

Suppose ACME wants an operator on `support@acme.example`.

### 1. Create a venv and install the kernel

```bash
mkdir -p ~/work && cd ~/work
uv venv .venv
source .venv/bin/activate
uv pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
```

### 2. Create the clone

```bash
python -m cs init
```

You will be asked roughly:

| Prompt | ACME example |
|---|---|
| Company name | `ACME Corp` |
| Display / From name | `ACME` |
| Slug (state dir `~/.<slug>-cs`) | `acme` |
| Program name | `acme-cs` |
| Operator email | `support@acme.example` |
| IMAP / SMTP host & ports | Gmail defaults, or yours |
| Engine WebSocket URL | your mrcall-desktop front door |
| Engine owner UID | Firebase uid of the support profile |
| Default account + UID | `support` → that same uid |
| Extra accounts (optional) | e.g. founder mailbox for read-only sweeps |
| CRM adapter | `none` / `starchat` / `shopify` |
| Producer adapter | `none` or a worklist producer |
| Drive scope, SMS, cron schedule | as needed |
| Destination directory | `acme-cs` (default) |

Confirm the summary → the tool writes **`acme-cs/`**.

### 3. What lands on disk

```text
acme-cs/
├── manifest.toml              # all non-secret company variance
├── requirements.txt           # pins this kernel tag
├── .env.example               # which secret keys to set
├── template-manifest.json     # checksums for `cs update`
├── .claude/skills/            # operator skills (incl. /customer)
├── .claude/commands/          # interactive commands
├── company/                   # prose slots you edit (domain examples…)
├── campaigns/                 # optional campaign packs
├── docs/                      # architecture stub + customers/
└── bin/cs_operator_cron.sh    # draft-only headless tick wrapper
```

### 4. Secrets (not in the repo)

```bash
mkdir -p ~/.acme-cs
cp acme-cs/.env.example ~/.acme-cs/.env
# edit ~/.acme-cs/.env — EMAIL_PASSWORD, FIREBASE_WEB_API_KEY,
# CS_ACCOUNTS=support:<uid>, … and adapter keys if any
```

### 5. Project venv, install the pin, smoke-test

Use a **venv inside the clone** so the operator’s pin is isolated:

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m cs whoami              # needs engine + secrets
```

All day-to-day commands below assume this venv is active
(`source .venv/bin/activate`).

### 6. Day-to-day (what ACME can do)

| Command | Purpose |
|---|---|
| `python -m cs whoami` | Verify engine session |
| `python -m cs plan` | Worklist from the producer (if configured) |
| `python -m cs dossier alice@client.com` | Thread + Gmail-Sent contact check + tasks + CRM |
| `python -m cs ask "…"` | Read-only question against engine memory |
| `python -m cs draft-reply "…"` | Compose a **draft only** (structurally cannot send) |
| `python -m cs campaign list` / `pending` / `queue-draft` | Advance campaigns as drafts |
| `python -m cs drive ls` / `search` / `cat` | Read-only Drive (scoped in the manifest) |
| `python -m cs update` | Re-apply newer kernel templates when you upgrade |

**Sending mail** is gated on purpose:

- Default mode is **draft**: prepare, review (Gmail Drafts / desktop), then send.  
- Headless/cron stays draft-only via permissions.  
- Contextual send uses the engine’s approval gate when a human enables it.  
- Fixed-template bulk (campaign packs) uses gated SMTP/SMS with rate limits,
  pause file, and Gmail-Sent dedup.

Optional autonomy later is a deliberate config + permission change — not the
default.

### 7. Upgrade later

```bash
cd acme-cs
source .venv/bin/activate
# bump the pin in requirements.txt / manifest [repo].kernel_version if needed
uv pip install -r requirements.txt
python -m cs update              # merge template changes; asks if you edited files
```

---

## Why not fork?

If every company copies the whole operator, one hardens Gmail-Sent dedup and
another keeps a broken search. **cs-kernel is the shared core**; the clone
only holds declared variance (`manifest.toml` + prose + packs).

| Kernel (this repo) | Company clone |
|---|---|
| CLI, auth, RPC, IMAP dedup | `manifest.toml` |
| Campaign runner | `company/*.md`, `campaigns/` |
| CRM / producer **ports** | Secrets under `~/.<slug>-cs/` |
| `init` / `update` templates | Customer notes under `docs/customers/` |

---

## Safety (built in)

Not knobs you can “turn off by mistake” in the manifest:

1. No cold outreach without a dossier; respect the dedup window.  
2. **Gmail Sent / All Mail** is contact ground truth (not the engine archive alone).  
3. Headless path is **draft-only**.  
4. Module path stays `python -m cs` (permission strings depend on it).  
5. No hard-coded company brands in kernel code — identity comes from Settings.  
6. `~/.<slug>-cs/CS_PAUSE` stops automated ticks immediately.

---

## Versioning

- Install **tags only**: `@v0.2.0`, not a floating branch.  
- See [CHANGELOG.md](CHANGELOG.md).  
- Develop with a local checkout:

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e /path/to/cs-kernel
```

---

## License & status

Public infrastructure for operators that sit in front of **mrcall-desktop**.
You still need engine access, credentials, and human review in draft mode.

**Current release:** `v0.2.0`

```bash
uv venv .venv && source .venv/bin/activate
uv pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
python -m cs init
```
