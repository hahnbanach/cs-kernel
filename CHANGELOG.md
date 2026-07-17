# Changelog — cs-kernel

Clones pin **tags only**. Every entry states which clones must re-collaudo
and at which tier (design brief §6.6: static / +live read-only / full).

## v0.3.0 — 2026-07-17

### Added — the clone `CLAUDE.md` is now templated; `docs/customers` → `docs/projects`
- **Why:** the clone `CLAUDE.md` was NOT templated — each clone hand-maintained
  it, so it drifted from the kernel and a shared change had to be copied into
  every clone by hand. And `docs/customers/` is really "per-project working
  folders", not only customer dossiers.
- **What:**
  - New `cs/templates/project/CLAUDE.md.j2` — the clone operator manual is now
    kernel-owned and parameterised (flat config keys). Company-specific
    engine/API notes stay in the `company/claude-extra.md` slot (CLAUDE.md points
    to it; NOT inlined — `cs update` renders with `from_string`/no loader, so
    `{% include %}` is unavailable). Adds an **"Editing this clone —
    template-owned vs clone-owned"** section.
  - Template dir `docs/customers/` → `docs/projects/`; its README rewritten in
    English; the `customer` skill + `docs/ARCHITECTURE.md.j2` reference
    `docs/projects/`.
  - New config key `repo_docs_shape` (`collect_config` prompt, default
    `generic`) — distinguishes the mother clone from stamped children in the
    intro line.
  - Founder-sweep clause no longer appends a stray `@` (account names are full
    mailbox addresses).
- **Verified:** rendered `CLAUDE.md.j2` for BOTH reference clones with the real
  `project_init` Jinja env (`StrictUndefined`) — zero errors;
  `kernel + manifest(mrcall-cs)` is byte-equivalent to the mother's current
  CLAUDE.md except the intended changes; `kernel + manifest(124)` renders 124's
  values with no MrCall literals leaked.
- **Clones must re-collaudo:** full tier — CLAUDE.md/docs become template-owned.
  Adoption also needs each clone onboarded to template management
  (`template-manifest.json`); neither reference clone has one yet, so
  `cs update` cannot pull this until that follow-up lands.

## v0.2.3 — 2026-07-17

### Added — `cs tasks create` / `cs tasks close` + triage reconciles the sweep against the engine ledger
- **Why:** the deterministic `cs unanswered` sweep only sees support@'s own
  Gmail Sent folder, so an item answered from a DIFFERENT mailbox (e.g. Mario's
  personal `mario.alemi@` account) still gets re-flagged as unanswered
  (incident 2026-07-17: Eva Fani). And when the engine's own detection never
  turned a real inbound into a task, the operator had no write-path to record it.
  We need a place to record "handled" / "seen" that the sweep can reconcile
  against: the engine task ledger.
- **What:** `cs tasks` becomes a verb-with-subactions. Bare `cs tasks` is
  unchanged (the open-task list). New:
  - `cs tasks create --email E --title T --event-id ID [--event-type email]
    [--name N] [--phone P] [--urgency medium] [--reason R] [--suggested-action S]
    [--thread-id TID] [--json]` → `tasks.create` (upsert on
    owner_id+event_type+event_id — idempotent; `sources` carries the event id(s)
    and, when given, `thread_id`).
  - `cs tasks close TASK_ID [--note NOTE] [--json]` → `tasks.complete`.
- **Triage skill:** `triage-support-mail` now reconciles each sweep survivor
  against the ledger by `contact_email`: OPEN task → work it; CLOSED task →
  SKIP (already handled, possibly elsewhere); NO task → `cs tasks create` so the
  desktop sees it, then work it. `cs tasks --json` returns OPEN tasks only; the
  operator passes `cs rpc tasks.list '{"include_completed":true}'` to see closed.
- **Guard:** `tests/test_tasks_verbs.py` (gate 10 in `tests/run.sh`) pins the
  RPC method + params for both subactions; the help tree gate now covers
  `cs tasks create|close --help`.
- **Engine dependency:** relies on the engine RPCs `tasks.create` /
  `tasks.complete` (already live + tested on the support@ daemon).
- **Clones must re-collaudo:** full tier — this adds verbs the triage skill now
  depends on. Re-pin to `v0.2.3` and run one live `cs tasks create` +
  `cs tasks close` round-trip against the clone's engine.

## v0.2.2 — 2026-07-16

### Added — deterministic `cs unanswered` sweep (replaces a flaky LLM discovery)
- **Why:** the triage skill discovered "customer mail still needing a human
  reply" by asking the engine LLM (`cs ask "elenca la posta … senza risposta"`).
  That is NON-DETERMINISTIC — two runs of the same query returned different sets
  and missed real unanswered customer mail 6–13 days old that had no engine task
  (incident 2026-07-16). We need a sweep anchored to the Gmail Sent archive, no
  LLM in the discovery loop.
- **What:** new `cs unanswered [--days 14] [--json]`. Enumerates recent inbound
  (Gmail All Mail, **Date-header** windowed — never INTERNALDATE, which the
  engine sync re-touches and which made prior queries flip between runs) and
  subtracts every sender we've since written to (Gmail Sent = the dedup ground
  truth). A sender is OPEN iff no Sent message to them is dated after their last
  inbound. Excludes self (`SELF_EMAILS` + operator address), the new
  `CS_SYSTEM_SENDERS` ignore-list, and the `do_not_contact` suppression table.
  Returns oldest-first. It does NOT classify intent / autoresponders — that
  stays the LLM's job; over-inclusion is acceptable and filtered downstream.
- **New code:** `cs/gmail_archive.py` bulk readers `inbound_recent` /
  `sent_recent` (one IMAP session, batched header FETCH, read-only); pure,
  unit-testable `cs/unanswered.compute_open` + IMAP-backed `open_threads`;
  `cs unanswered` verb in `cs/cli.py`.
- **New config:** `CS_SYSTEM_SENDERS` (comma-separated no-reply/system addresses
  to ignore), layered env/manifest like the other knobs, default empty. The
  clone declares its own system addresses in env/manifest — NEVER hardcoded in
  the kernel (charter grep gate).
- **Guard:** `tests/test_unanswered.py` (wired as gate 9 in `tests/run.sh`)
  exercises the open-logic on synthetic dicts.
- **Clones must re-collaudo:** full tier — this adds a verb the triage skill now
  depends on. Re-pin to `v0.2.2`, set `CS_SYSTEM_SENDERS` for the clone, and run
  one live `cs unanswered --days 14`, cross-checking a couple of hits against
  `cs contacted <email>`.

### Fixed — `cs init` crash, fake-optional prompts; `drive.py` i18n; license
- `python -m cs init` raised `NameError: name 're' is not defined` on every
  invocation — `re`/`sys` were imported only inside the `if __name__ ==
  "__main__"` guard, which the real `cli.py` entry point never executes.
  Moved both to top-level imports. Verified end-to-end in a clean venv: the
  full init flow now completes and renders the project.
- `prompt_input`'s `default=""` was overloaded to mean both "no default"
  (required) and "optional, blank is fine" — five prompts labeled
  `(optional)` / "or empty" actually rejected blank input and looped
  forever. `default=None` is now the "required" sentinel; `default=""`
  means what it says. Verified the same fields now accept blank input and
  the flow completes.
- Removed the stale `doc-startsession` / `doc-endsession` / `doc-intrasession`
  command templates so new clones stop inheriting commands retired
  kernel-wide (superseded by the globally-installed `mrcall-ai-kit`
  `doc-start` / `doc-end`).
- Translated `cs/drive.py`'s Italian CLI help/error strings to English.
- Added the MIT `LICENSE` (was undeclared despite the "License & status"
  README heading) and declared it in `README.md` + `pyproject.toml`.
- `cs init`'s Engine WS URL default is now a generic placeholder instead of
  `wss://desktop.mrcall.ai` (charter grep gate — this was the last company
  literal in `cs/`; the gate is green again).
- **Clones must re-collaudo:** static tier only — no behavior change on any
  operator verb; `cs init` / `cs update` and `cs.drive` output text are the
  only surfaces touched.

## v0.2.1 — 2026-07-16

### Fixed — `draft-reply` now lands in the operator's Gmail Drafts (was invisible)
- **Root cause:** `cmd_draft_reply` only ran the engine compose. The engine's
  `create_draft` is non-destructive, so it auto-executes even with the empty
  `allow_tools`, storing the draft in the ENGINE draft store (visible via
  `cs rpc drafts.list` / the desktop app) — but **never in the operator's Gmail
  Drafts**, the surface where review and sending happen. The operator saw an
  empty Gmail Drafts and concluded "nothing was drafted". Recurring bug: prior
  fixes only touched an installed copy, never this source, so `pip install` /
  re-pin wiped them every time.
- **Fix:** `cmd_draft_reply` now diffs the engine draft store around the compose
  call and APPENDs the freshly composed draft into Gmail Drafts via IMAP
  (`gmail_drafts.append_draft`, the same mechanism as `campaign queue-draft`),
  with the draft's real `to`/`subject`/`body`/`in_reply_to`/`references`. It
  fails loud (rc=1) if the composed draft has no recipient/body, and is a no-op
  mirror when the engine composed nothing (clarifying question / escalation).
- **Guard:** new `tests/test_draft_reply.py` (wired as gate 8 in `tests/run.sh`)
  fails the moment the Gmail-Drafts append is removed.
- **Clones must re-collaudo:** full tier — this changes the Phase-1 review
  surface. Re-pin to `v0.2.1` and re-run one live `draft-reply`, verifying the
  draft appears in the operator's Gmail Drafts (not just `cs rpc drafts.list`).

## v0.2.0 — 2026-07-12

### Added — project template + `cs init` / `cs update`
- `cs/templates/project/` — Jinja2 project skeleton (skills, commands, company
  prose slots, docs, bin, manifest, requirements). Includes the generic
  `/customer` skill.
- `cs init` — interactive clone generator: prompts → render → `git init` →
  writes `template-manifest.json` (init_data + sha256 checksums).
- `cs update` — selective re-apply of template changes; asks on local
  modifications; same Jinja env as init (`trim_blocks`/`lstrip_blocks`).
- Dependency: `jinja2>=3.1`. Package data ships templates with the wheel.

### Added — `cs cron`
- `cs cron install` / `uninstall` / `status` — manage the operator's crontab
  entry directly from the CLI (`cs/cron.py`), instead of hand-editing crontab
  per clone. (Documented 2026-07-14; shipped in the tagged v0.2.0 commit but
  missing from this changelog until now.)

### Collaudo (this release)
- StrictUndefined render of all 30 templates: 0 failures.
- init→update no-op on a throwaway clone: 0 updated / 0 skipped / 0 added.
- Existing verbs still resolve via editable install (`cs --help`).

### Re-pin impact
- Clones that only run operator verbs: optional re-pin (new surface only).
- Anyone adopting `init`/`update` or a fresh clone: pin `@v0.2.0`.
- Full collaudo tier: static (help tree grows by `init`/`update` early exit;
  they bypass manifest load). Live read-only verbs unchanged.

## v0.1.0 — 2026-07-09

Initial extraction of the shared kernel from the two specimens — A (the
mother clone) and B (the first child) — per the design brief
`cs-kernel-manifest-separation.md` (§5.1 winners table, §5.1b packs,
§3 ports, §4 manifest).

### Winners merged (debt variance resolved, one version survives)
- `campaign.py` — **A**: Gmail-Sent/All-Mail ground-truth dedup
  (`_sent_threads_to` / `_inbound_since` read IMAP via `gmail_archive`);
  B's engine-search dedup is deleted as fork drift (it is blind to
  hand-sent mail and drops threads when the customer replies last).
  B's generic excluded-campaign guard SHAPE kept; the value moved to
  `settings.excluded_campaign` (manifest).
- `gmail_archive.py` — **A (superset)**: `inbound_since()` + Message-ID
  fetch/emission restored for everyone.
- `send_mail.py` — **B shape**: From display name from
  `settings.email_from_name` (manifest `[company].from_name`); falls back
  to the bare address when unset.
- `config.py` — fused: B's 3-level env-file loader (platform → home →
  repo, later wins; platform path from the manifest), ONE
  `settings.state_dir` derived from the slug (kills the hardcoded path
  scatter: db, token cache, SA key, CS_PAUSE, operator log, Shopify token
  cache), `<PREFIX>_`/bare Shopify alias convention generalized
  (`[crm.shopify].env_prefix`).
- `cli.py` — A base; CRM block replaced by the port call; `prog=` and all
  identity prints from Settings.
- `rpc.py`, `filter.py`, `gmail_drafts.py`, `__main__.py` — byte-identical
  in both clones, adopted as-is (rpc gains a loud error on unconfigured
  ws_url, now that the kernel default is empty).
- `_time.py` — same helpers, timezone now a knob
  (`[knobs].timezone` → `local_hour/local_date/past_local_noon`).
- `auth.py`, `resolve.py` — Firebase app names fixed to neutral kernel
  constants (`cs-kernel-*`); docstrings de-branded.
- `state.py`, `review.py`, `drive.py` — paths/scope messages derived from
  Settings.
- `scripts/find_profile_uid.py` — **B**, generalized (SA key discovered by
  glob over `~/.*-cs/`, or `--sa`).

### New kernel modules
- `manifest.py` — `manifest.toml` (brief §4.2 schema) → pydantic →
  Settings overrides; `$CS_MANIFEST` override for sandboxes; missing
  manifest tolerated (bare `--help` works), invalid manifest fails LOUD.
- `crm/` — the CRM port (brief §3): `CrmCtx`/`CrmRow`/`CrmResult` envelope
  with `render_hints`; explicit registry (`starchat`, `shopify`, `none`);
  unknown adapter = loud startup error; `lookup` never raises; verdict
  stays CRM-agnostic. `starchat` = A's inline RPC refactored;
  `shopify` = B's `crm.py` generalized (token cache under
  `settings.state_dir`, env prefix from the manifest).
- `ingest/` — the producer port (brief §3.6): `mrcall-tracking` (A's
  subprocess; script/python paths from the manifest, no absolute paths in
  the kernel) + `none` (B's reply-only stub); `fetch` degrades to an
  empty well-formed worklist with a surfaced note.
- `campaign_pack.py` + generic senders (brief §5.1b, decided 2026-07-08,
  driver: the upcoming ~70-user migration): pack loader
  (`campaigns/<name>/campaign.toml` + `mail_first.md`/`mail_reminder.md`
  with a `Subject:` first line + `sms.txt` + optional `builders.py` hook +
  `playbook.md`), `cs campaign packs` discovery verb, and the
  `send_reminder`/`send_sms` handlers: pack template/builders →
  `send_mail`/`sms`, **stamp-before-send**, reply-check on Gmail ground
  truth, once/day + cap + window gates, CS_PAUSE, RATE_CAP. A
  fixed-template action with NO pack is refused loudly — the kernel never
  invents copy.
- `sms.py` — generic SMS via the manifest `[sms].proxy_base` proxy +
  `SMS_BUSINESS_ID`; raises `SmsError` with the reason (no silent False,
  unlike the one-off it replaces).

### Declared behavior deltas vs the specimens (for the migration registers)
- Dossier CRM section prints generically from `render_hints`
  (`-- CRM [starchat] (n) --` instead of the per-company header).
- `cs plan` surfaces a producer failure as a printed note over an empty
  worklist instead of a traceback.
- Identity strings in `contacted`/`dossier`/verdict lines derive from
  `settings.email_address` (same rendered bytes once the manifest is in).
- Reminder/SMS senders stamp the dossier BEFORE the send (the old one-off
  sent first); crash direction is now "skip one", never "send twice".
- New verbs: `campaign send-reminder`, `campaign send-sms`,
  `campaign packs`.

### Collaudo required
Both clones, FULL tier (send paths, campaign, gmail_archive, send_mail
all touched) — brief §6.6. B additionally lands the pre-declared B1/B2
dedup ground-truth switch.
