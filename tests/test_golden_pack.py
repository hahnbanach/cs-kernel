#!/usr/bin/env python3
"""Golden pack equivalence — proves the pack runner reproduces a clone's
one-off builder BYTE FOR BYTE, so the next fixed-template campaign can run
from a pack instead of bespoke code.

Company copy stays OUT of this repo: the reference module and the pack dir
are injected via env vars and the test SKIPS (exit 0) when they are unset.

  CS_GOLDEN_REF_BUILDERS  path to the clone's reference builders module
                          (e.g. the mother clone's migration mail builder)
  CS_GOLDEN_PACK_DIR      path to a pack dir whose builders.py is that
                          module's content

Asserts, for a fixed set of rows: pack.build_reminder(row) == the reference
module's build_reminder(row) — (subject, plain, html) byte-identical; same
for build(row) when the reference defines it.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROWS = [
    {"name": "Mario", "company": "Bar Rossi", "old": "+390212345678", "new": "+393511234567"},
    {"name": "", "company": "", "old": "+390200000000", "new": "+393500000000"},
    {"name": "Giulia", "company": "Officina G. & C.", "old": "+390698765432", "new": "+393519876543"},
]


def _load_by_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sys.dont_write_bytecode = True  # never write .pyc next to clone sources
    ref_path = os.environ.get("CS_GOLDEN_REF_BUILDERS", "").strip()
    pack_dir = os.environ.get("CS_GOLDEN_PACK_DIR", "").strip()
    if not ref_path or not pack_dir:
        print("test_golden_pack: SKIPPED (set CS_GOLDEN_REF_BUILDERS + CS_GOLDEN_PACK_DIR)")
        return 0

    from cs import campaign_pack

    ref = _load_by_path(Path(ref_path), "golden_reference_builders")
    pack = campaign_pack.load_pack(Path(pack_dir))

    checked = 0
    for i, row in enumerate(ROWS):
        got = pack.build_reminder(dict(row))
        want = ref.build_reminder(dict(row))
        assert isinstance(got, tuple) and len(got) == 3
        for part, label in zip(range(3), ("subject", "plain", "html")):
            assert got[part] == want[part], (
                f"row {i}: build_reminder {label} DIFFERS\n"
                f"--- pack ---\n{got[part][:400]}\n--- reference ---\n{want[part][:400]}"
            )
        checked += 1
        if hasattr(ref, "build"):
            got_f = pack.build(dict(row))
            want_f = ref.build(dict(row))
            for part, label in zip(range(3), ("subject", "plain", "html")):
                assert got_f[part] == want_f[part], f"row {i}: build {label} DIFFERS"
            checked += 1

    print(f"test_golden_pack: {checked} builds byte-identical to the reference "
          f"({len(ROWS)} rows, build_reminder{' + build' if hasattr(ref, 'build') else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
