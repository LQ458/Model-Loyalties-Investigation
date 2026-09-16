#!/usr/bin/env python3
"""Runtime shim for defense/collect_prospective_v3.py.

WHY
---
The collector has a second, independent instance of the parents[1] bug, and it
bites at RUNTIME rather than import time, so analysis/wujur/collect.sh's
PYTHONPATH fix does not reach it:

    collect_prospective_v3.py:24   REPO = ROOT.parents[1]
    collect_prospective_v3.py:275  base_path=REPO / "prompts" / "base_assistant.md"
    collect_prospective_v3.py:276  loyalty_path=REPO / "prompts" / "v018.md"
    collect_prospective_v3.py:277  concealment_dir=REPO / "prompts" / "concealment"

ROOT is <repo>/defense, so parents[1] is the directory ABOVE the repository and
the first ranking row dies with:

    FileNotFoundError: '/home/barry/workspace/projects/prompts/base_assistant.md'

Post-refactor those three targets all live under <repo>/model_organism/prompts/,
verified present. Pre-refactor the repo root held prompts/ directly (the
Nextcloud mirror still shows that layout, with runs/ and prompts/ at top level),
which is why parents[1] once resolved correctly. Commit 4b5d4b2 moved them into
model_organism/ without updating the constant.

The correct value of REPO for the post-refactor tree is <repo>/model_organism.

WHY A SHIM RATHER THAN A ONE-LINE EDIT
--------------------------------------
collect_prospective_v3.py is shared code that Leo also uses, and it is the
runner behind committed, hash-receipted results. Editing it would make every
future run ambiguous as to which version produced which rows, two days before a
deadline. This shim imports the module under its own name (main() is guarded at
:869, so nothing executes on import), overrides the single wrong constant,
asserts the corrected paths exist, then calls main() with argv passed straight
through. The collector's own logic, request parameters, prompt assembly and
receipt writing are untouched, so rows produced this way are identical to rows
produced by a correctly-pathed invocation.

The proper per-file fix across the ~11 files using parents[1] is deferred until
after data collection. Some of those uses are legitimately correct (a file in
auditing/tests/ genuinely wants auditing/), so a blanket rewrite would break
working code.

USAGE
-----
Invoked by analysis/wujur/collect.sh; not intended to be called directly.
All arguments are forwarded verbatim to the collector's argument parser.

REVERT: delete this file and analysis/wujur/collect.sh. Nothing else changes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
COLLECTOR = REPO_ROOT / "defense" / "collect_prospective_v3.py"
CORRECT_REPO = REPO_ROOT / "model_organism"

REQUIRED = (
    CORRECT_REPO / "prompts" / "base_assistant.md",
    CORRECT_REPO / "prompts" / "v018.md",
    CORRECT_REPO / "prompts" / "concealment",
)


def main() -> int:
    if not COLLECTOR.is_file():
        print(f"collect_shim: collector not found at {COLLECTOR}", file=sys.stderr)
        return 1

    missing = [str(p) for p in REQUIRED if not p.exists()]
    if missing:
        print(
            "collect_shim: corrected REPO is missing required prompt paths; "
            "the layout has changed again and this shim must be revisited:\n  "
            + "\n  ".join(missing),
            file=sys.stderr,
        )
        return 1

    spec = importlib.util.spec_from_file_location("collect_prospective_v3", COLLECTOR)
    if spec is None or spec.loader is None:
        print("collect_shim: could not build an import spec", file=sys.stderr)
        return 1
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # main() is guarded by `if __name__ == "__main__"` at :869 and spec.name is
    # not "__main__", so this executes definitions only.
    spec.loader.exec_module(module)

    original = getattr(module, "REPO", None)
    module.REPO = CORRECT_REPO
    print(f"collect_shim: REPO {original} -> {CORRECT_REPO}", flush=True)

    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
