# Changelog — cs-kernel

Clones pin **tags only**. Every entry states which clones must re-collaudo
and at which tier (design brief §6.6: static / +live read-only / full).

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
