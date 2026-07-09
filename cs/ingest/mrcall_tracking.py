"""mrcall-tracking producer adapter — the analytics warehouse's daily task set.

Calls the producer's ``--json`` mode (NOT the emailed markdown — parsing
prose would be fragile). Script and interpreter paths come from the
manifest (``[producer.mrcall_tracking] script_path / python_path``) —
never hardcoded absolute paths in the kernel.
"""
from __future__ import annotations

import json
import subprocess


def fetch(settings, period: str = "7d", env: str = "prod") -> dict:
    if not settings.agent_prompt_py or not settings.agent_prompt_python:
        raise RuntimeError(
            "mrcall-tracking producer selected but [producer.mrcall_tracking] "
            "script_path/python_path are not set in manifest.toml"
        )
    proc = subprocess.run(
        [
            settings.agent_prompt_python,
            settings.agent_prompt_py,
            "--json",
            "--period",
            period,
            "--env",
            env,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"producer failed (rc={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return json.loads(proc.stdout)
