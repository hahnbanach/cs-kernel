# cs-kernel

**A ready-made customer-service operator for your company mailbox.**

You install it, answer a few setup questions, open an AI coding session
(Claude Code or OpenCode) in the folder it creates, and work in natural
language: “load customer ACME”, “what’s open with them?”, “draft a reply…”.

Under the hood it talks to **[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)**
(the engine that syncs mail, keeps memory, and can draft/send). This package
is the thin setup + skills layer in front of that engine — not a mail server
by itself.

You need a mrcall-desktop profile for the mailbox you want to operate.

---

## What you get

1. A small project folder (e.g. `acme-cs/`) configured for **your** company  
2. Skills the AI can run: load a customer, triage mail, advance campaigns, …  
3. Safety defaults: **draft first**, review before anything is sent  

Voice and product policy live in the engine profile, not in this repo.

---

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (fast installer)  
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Claude Code** or **OpenCode** (the TUI/session you work in)
- A **mrcall-desktop** engine profile for your support mailbox  
  (you’ll need the engine WebSocket URL and the profile’s Firebase uid)
- Mailbox password / app password for that address (IMAP/SMTP)

Without the engine and secrets, setup still creates the folder, but the AI
cannot load real mail or memory yet.

---

## Setup (copy & paste) — example: ACME

Imagine your operator address is `support@acme.example`.

### 1. Install the toolkit (once)

```bash
mkdir -p ~/work && cd ~/work
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
```

### 2. Create your company project

```bash
python -m cs init
```

Answer the prompts (defaults are fine when unsure). For ACME you might enter:

| Question | Example |
|---|---|
| Company name | `ACME Corp` |
| Display / From name | `ACME` |
| Short slug | `acme` → state lives under `~/.acme-cs/` |
| Operator email | `support@acme.example` |
| Engine URL + owner uid | from your mrcall-desktop setup |
| Default account | `support` + that same uid |
| CRM / producer / SMS / Drive | leave defaults unless you know you need them |
| Destination folder | `acme-cs` |

When you confirm, you get a folder **`acme-cs/`**.

### 3. Put secrets outside the repo

```bash
mkdir -p ~/.acme-cs
cp acme-cs/.env.example ~/.acme-cs/.env
```

Edit `~/.acme-cs/.env` (any text editor) and fill at least:

- mailbox password  
- Firebase / engine keys as in the example file  
- `CS_ACCOUNTS=support:<your-uid>`  

Never commit this file.

### 4. Install the project pin and check the engine

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m cs whoami
```

If `whoami` shows you signed in as the right mailbox, the body is alive.

### 5. Open the TUI and work

Still inside `acme-cs/` with the venv active:

```bash
# pick one:
claude
# or
opencode
```

You’re in a chat UI in **this project**. The AI loads skills from `.claude/`
(and OpenCode config if present). Talk normally, for example:

- *“Load customer Northwind”* → uses the **customer** skill: reads
  `docs/customers/…` **and** queries **mrcall-desktop memory** for that
  relationship (not just the markdown file).
- *“What’s still open in support mail?”* → triage / review skills  
- *“Draft a reply to …”* → grounded draft; **nothing is sent** until you
  review and approve through the normal gates  
- *“Advance campaigns”* → campaign tick skill (draft-oriented by default)

You do **not** need to memorize CLI subcommands day to day. The skills are
the product surface; the CLI is plumbing the AI (and you, if you want) can call.

---

## Day-to-day mental model

```text
You  →  Claude / OpenCode (in acme-cs/)  →  skills  →  cs CLI  →  mrcall-desktop
                                                              →  Gmail (when needed)
```

| You care about | What happens |
|---|---|
| Customer context | Skill loads dossier files + **engine memory** |
| Replies | Drafts prepared for review; send is gated |
| Campaigns | Templates/packs advanced as drafts unless you opt into send mode |
| “Stop everything” | Create pause file: `touch ~/.acme-cs/CS_PAUSE` |

---

## Upgrading later

```bash
cd acme-cs
source .venv/bin/activate
# if the pin in requirements.txt changed:
uv pip install -r requirements.txt
python -m cs update    # refreshes skills/templates; asks before overwriting your edits
```

Then reopen `claude` / `opencode` in that folder.

---

## Safety (defaults)

- **Draft first** — automated paths are not free-fire send.  
- No cold outreach without a proper contact check.  
- Contact history uses **Gmail’s own Sent mail** as ground truth.  
- `~/.<your-slug>-cs/CS_PAUSE` stops automated ticks immediately.

Turning on autonomous send is a deliberate later choice, not the default.

---

## Versioning

Install a **version tag**, not a floating branch:

```bash
uv pip install "cs-kernel @ git+https://github.com/hahnbanach/cs-kernel@v0.2.0"
```

See [CHANGELOG.md](CHANGELOG.md) for what each release changes.

---

## License & status

Public setup kit for operators that sit in front of **mrcall-desktop**.
You still need engine access, credentials, and human review in draft mode.

**Current release:** `v0.2.0`
