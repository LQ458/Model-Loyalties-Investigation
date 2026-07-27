#!/usr/bin/env python3
"""Run and receipt the bounded Track 3 test suite."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    transcript = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(r"Ran (\d+) tests", transcript)
    result = {
        "schema_version": 1,
        "status": "PASS" if completed.returncode == 0 and match else "FAIL",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "returncode": completed.returncode,
        "tests_run": int(match.group(1)) if match else None,
        "test_source_sha256": hashlib.sha256(
            (ROOT / "tests" / "test_track3.py").read_bytes()
        ).hexdigest(),
        "transcript": transcript,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
