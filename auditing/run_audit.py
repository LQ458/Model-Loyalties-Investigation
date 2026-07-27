#!/usr/bin/env python3
"""Command-line entry point for the isolated auditing audit backbone."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit_system.runner import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
