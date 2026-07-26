#!/usr/bin/env python3
"""CLI: fail-closed role config preflight (no live API calls)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.roles import PreflightError, load_project_dotenv, preflight_roles  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Validate endpoint role credentials before non-smoke runs. "
            "Fails closed when required API keys are missing or when a role "
            "shares target base_url+model without an explicit override. "
            "Never makes live API calls."
        )
    )
    p.add_argument(
        "--require",
        default="judge,optimizer",
        help="Comma-separated roles to require (default: judge,optimizer).",
    )
    p.add_argument(
        "--smoke-only",
        action="store_true",
        help="Allow missing independent keys and same-model endpoints (SMOKE_ONLY).",
    )
    p.add_argument(
        "--allow-same-model",
        action="store_true",
        help="Allow judge/optimizer/auditor to share target endpoint+model.",
    )
    p.add_argument(
        "--endpoints",
        type=Path,
        default=ROOT / "config" / "endpoints.yaml",
        help="Path to endpoints.yaml.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print full metadata JSON on success.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_project_dotenv()
    args = parse_args(argv)
    roles = [r.strip() for r in str(args.require).split(",") if r.strip()]
    try:
        meta = preflight_roles(
            roles,
            smoke_only=bool(args.smoke_only),
            allow_same_model_judge=bool(args.allow_same_model),
            endpoints_path=args.endpoints,
        )
    except PreflightError as exc:
        print(str(exc), file=sys.stderr)
        if exc.missing:
            print(f"missing vars: {', '.join(exc.missing)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(meta, indent=2))
    else:
        print("role preflight ok")
        for name, role_meta in (meta.get("roles") or {}).items():
            print(
                f"  {name}: model={role_meta.get('model')!r} "
                f"base_url={role_meta.get('base_url')!r} "
                f"api_key_configured={role_meta.get('api_key_configured')} "
                f"same_endpoint_as_target={role_meta.get('same_endpoint_as_target')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
