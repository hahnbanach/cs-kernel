#!/usr/bin/env python3
"""Campaign pack loader — semantic checks on a NEUTRAL trial pack built in a
tmp dir (no company content in this repo):

  - campaign.toml parse + [windows] overrides
  - template convention (Subject: first line) through the md→plain+html pipeline
  - strict placeholders: a missing key REFUSES loudly (no holes in mail)
  - builders.py hook takes precedence over templates
  - discovery: find_pack by engine campaign name; None when absent
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from cs import campaign_pack

CAMPAIGN_TOML = """\
[pack]
kind = "fixed-template"
description = "trial pack for the loader gate"
campaign = "spring-hello"
status = "active"
dates = "trial"
confirm_question = "ok for Friday?"

[windows]
reminder_after_hour = 10
sms_hour = 20
reminder_max = 2
"""

MAIL_REMINDER = """\
Subject: Reminder for {name}

Ciao {name},

promemoria: trovi la [guida](https://docs.example/guide) online.
"""

SMS_TXT = "Reminder {name}: check your mail.\n"

BUILDERS = """\
def build_reminder(row):
    return ("S-" + row["name"], "P-" + row["name"], "H-" + row["name"])
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")
        pdir = base / "spring-hello"
        pdir.mkdir(parents=True)
        (pdir / "campaign.toml").write_text(CAMPAIGN_TOML)
        (pdir / "mail_reminder.md").write_text(MAIL_REMINDER)
        (pdir / "sms.txt").write_text(SMS_TXT)

        # discovery by engine campaign name
        pack = campaign_pack.find_pack("spring-hello", base=base)
        assert pack is not None, "find_pack missed the trial pack"
        assert pack.kind == "fixed-template"
        assert pack.description.startswith("trial pack")
        assert (pack.reminder_after_hour, pack.sms_hour, pack.reminder_max) == (10, 20, 2)
        assert campaign_pack.find_pack("nope", base=base) is None
        assert len(campaign_pack.list_packs(base=base)) == 1

        # template rendering: Subject line + md→plain+html pipeline
        subj, plain, html = pack.build_reminder({"name": "Anna"})
        assert subj == "Reminder for Anna", subj
        assert "Ciao Anna," in plain
        assert "guida: https://docs.example/guide" in plain, plain
        assert '<a href="https://docs.example/guide">guida</a>' in html, html

        # sms rendering
        assert pack.sms_text({"name": "Anna"}) == "Reminder Anna: check your mail."

        # strict placeholders: missing key = loud refusal
        try:
            pack.build_reminder({})
        except campaign_pack.PackError as e:
            assert "name" in str(e), e
        else:
            raise AssertionError("missing placeholder must raise PackError")

        # builders.py hook wins over the template
        (pdir / "builders.py").write_text(BUILDERS)
        pack2 = campaign_pack.find_pack("spring-hello", base=base)
        assert pack2.build_reminder({"name": "Anna"}) == ("S-Anna", "P-Anna", "H-Anna")
        # build() has no builders.build and no mail_first.md -> loud
        try:
            pack2.build({"name": "Anna"})
        except campaign_pack.PackError as e:
            assert "mail_first.md" in str(e), e
        else:
            raise AssertionError("no template and no builder must raise PackError")

        # broken campaign.toml kind = loud
        bad = base / "bad-pack"
        bad.mkdir()
        (bad / "campaign.toml").write_text('[pack]\nkind = "weird"\n')
        try:
            campaign_pack.load_pack(bad)
        except campaign_pack.PackError as e:
            assert "kind" in str(e)
        else:
            raise AssertionError("bad kind must raise PackError")

    print("test_pack: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
