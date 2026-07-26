"""Fail-closed role config resolution and preflight for endpoint roles.

Roles: ``target``, ``judge`` (``evaluator`` alias), ``optimizer``, ``auditor``.

Environment overrides prefer ``JUDGE_*`` over ``EVALUATOR_*`` for the judge
role. Metadata never includes secret values — only ``api_key_configured``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_ENDPOINTS_PATH = Path(__file__).resolve().parents[1] / "config" / "endpoints.yaml"

# Canonical role -> env prefixes in preference order (first match wins).
ROLE_ENV_PREFIXES: dict[str, tuple[str, ...]] = {
    "target": ("TARGET",),
    "judge": ("JUDGE", "EVALUATOR"),
    "optimizer": ("OPTIMIZER",),
    "auditor": ("AUDITOR",),
}

# Non-canonical names normalize to a canonical role.
ROLE_ALIASES: dict[str, str] = {
    "evaluator": "judge",
}

_DEFAULT_API_KEY_ENV: dict[str, str] = {
    "target": "TARGET_API_KEY",
    "judge": "JUDGE_API_KEY",
    "optimizer": "OPTIMIZER_API_KEY",
    "auditor": "AUDITOR_API_KEY",
}


class PreflightError(Exception):
    """Role preflight failed closed; ``missing`` names unset variables."""

    def __init__(self, message: str, *, missing: Sequence[str] | None = None):
        super().__init__(message)
        self.missing = list(missing or [])


def load_endpoints(path: str | Path | None = None) -> dict[str, Any]:
    """Minimal YAML subset loader for endpoints.yaml (no PyYAML required).

    Same shape as ``scoring.judge_client._load_yaml_endpoints``: top-level
    sections with scalar children.
    """
    p = Path(path) if path is not None else DEFAULT_ENDPOINTS_PATH
    text = p.read_text(encoding="utf-8")
    root: dict[str, Any] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][\w-]*:\s*$", line):
            section = line.split(":", 1)[0].strip()
            root[section] = {}
            continue
        m = re.match(r"^\s+([A-Za-z_][\w-]*)\s*:\s*(.+?)\s*$", line)
        if m and section:
            key, val = m.group(1), m.group(2).strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            elif val.lower() in ("true", "false"):
                val = val.lower() == "true"
            else:
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
            root[section][key] = val
    return root


def normalize_role(name: str) -> str:
    """Map aliases (e.g. ``evaluator``) to canonical role names."""
    key = str(name or "").strip().lower()
    return ROLE_ALIASES.get(key, key)


def _env_first(prefixes: Sequence[str], suffix: str) -> tuple[str | None, str | None]:
    """Return (value, var_name) for the first non-empty ``PREFIX_SUFFIX``."""
    for prefix in prefixes:
        var = f"{prefix}_{suffix}"
        val = os.environ.get(var)
        if val is not None and str(val).strip() != "":
            return str(val).strip(), var
    return None, None


def _norm_url(url: str) -> str:
    return str(url or "").strip().rstrip("/").lower()


def _norm_model(model: str) -> str:
    return str(model or "").strip().lower()


def same_endpoint(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """True when base_url + model match (trailing slash / case insensitive)."""
    return _norm_url(str(a.get("base_url") or "")) == _norm_url(
        str(b.get("base_url") or "")
    ) and _norm_model(str(a.get("model") or "")) == _norm_model(str(b.get("model") or ""))


def resolve_role(
    name: str,
    *,
    endpoints_path: str | Path | None = None,
    endpoints: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one role from config/endpoints.yaml + env overrides.

    Never returns the API key secret — only ``api_key_configured``.
    """
    role = normalize_role(name)
    if role not in ROLE_ENV_PREFIXES:
        raise PreflightError(
            f"unknown role {name!r} (expected one of: {', '.join(sorted(ROLE_ENV_PREFIXES))})",
            missing=[],
        )

    cfg = dict(endpoints) if endpoints is not None else load_endpoints(endpoints_path)
    role_cfg = dict(cfg.get(role) or {})
    prefixes = ROLE_ENV_PREFIXES[role]

    base_url_env, base_url_var = _env_first(prefixes, "BASE_URL")
    model_env, model_var = _env_first(prefixes, "MODEL")
    api_key_env_val, api_key_var = _env_first(prefixes, "API_KEY")

    yaml_key_env = str(role_cfg.get("api_key_env") or _DEFAULT_API_KEY_ENV[role])
    # Also honor the yaml-declared key env name if not already found via prefixes.
    if api_key_env_val is None:
        yaml_val = os.environ.get(yaml_key_env)
        if yaml_val is not None and str(yaml_val).strip() != "":
            api_key_env_val = str(yaml_val).strip()
            api_key_var = yaml_key_env

    base_url = base_url_env if base_url_env is not None else str(
        role_cfg.get("base_url") or ""
    )
    model = model_env if model_env is not None else str(role_cfg.get("model") or "")

    # Preferred / documented variable names for fail-closed messages.
    preferred_key_vars = [f"{p}_API_KEY" for p in prefixes]
    if yaml_key_env not in preferred_key_vars:
        preferred_key_vars.append(yaml_key_env)

    meta: dict[str, Any] = {
        "role": role,
        "requested_name": str(name),
        "base_url": base_url,
        "model": model,
        "api_key_env": api_key_var or preferred_key_vars[0],
        "api_key_env_candidates": preferred_key_vars,
        "api_key_configured": bool(api_key_env_val),
        "base_url_from_env": base_url_var,
        "model_from_env": model_var,
        "yaml_api_key_env": yaml_key_env,
    }

    if target is None and role != "target":
        target = resolve_role(
            "target",
            endpoints_path=endpoints_path,
            endpoints=cfg,
            target={},  # break recursion
        )
    if target and role != "target":
        meta["same_endpoint_as_target"] = same_endpoint(meta, target)
    else:
        meta["same_endpoint_as_target"] = False

    return meta


def _missing_api_key_vars(role_meta: Mapping[str, Any]) -> list[str]:
    return list(role_meta.get("api_key_env_candidates") or [role_meta.get("api_key_env")])


def preflight_roles(
    required_roles: Iterable[str],
    *,
    smoke_only: bool = False,
    allow_same_model_judge: bool = False,
    endpoints_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate required roles; return metadata or raise ``PreflightError``.

    Non-smoke runs require configured API keys for each required role and
    reject roles that share target base_url+model unless
    ``allow_same_model_judge`` is set. Smoke-only may pass with target-only
    local config (missing independent keys / same-model allowed).
    """
    roles_list = [normalize_role(r) for r in required_roles]
    if not roles_list:
        raise PreflightError("preflight_roles requires at least one role", missing=[])

    cfg = load_endpoints(endpoints_path)
    target_meta = resolve_role("target", endpoints=cfg, endpoints_path=endpoints_path)

    resolved: dict[str, dict[str, Any]] = {"target": target_meta}
    missing: list[str] = []
    problems: list[str] = []

    for role in roles_list:
        meta = resolve_role(
            role,
            endpoints=cfg,
            endpoints_path=endpoints_path,
            target=target_meta,
        )
        resolved[role] = meta

        if not smoke_only and not meta["api_key_configured"]:
            vars_ = _missing_api_key_vars(meta)
            missing.extend(vars_)
            problems.append(
                f"role {role!r}: API key not configured "
                f"(set one of: {', '.join(vars_)})"
            )

        if (
            not smoke_only
            and not allow_same_model_judge
            and role != "target"
            and meta.get("same_endpoint_as_target")
        ):
            problems.append(
                f"role {role!r}: same endpoint/model as target "
                f"({meta.get('base_url')!r} / {meta.get('model')!r}); "
                f"use --smoke-only / smoke_only=True, pass "
                f"allow_same_model_judge=True / --allow-same-model, "
                f"or point {role} at a different model family"
            )

    # Deduplicate while preserving order.
    seen: set[str] = set()
    missing_unique: list[str] = []
    for v in missing:
        if v not in seen:
            seen.add(v)
            missing_unique.append(v)

    metadata: dict[str, Any] = {
        "smoke_only": bool(smoke_only),
        "allow_same_model_judge": bool(allow_same_model_judge),
        "required_roles": roles_list,
        "roles": resolved,
        "ok": not problems,
    }

    if problems:
        header = "role preflight failed (fail-closed)"
        if missing_unique:
            header += f"; missing vars: {', '.join(missing_unique)}"
        detail = "; ".join(problems)
        raise PreflightError(f"{header}. {detail}", missing=missing_unique)

    return metadata



def load_project_dotenv(path: str | Path | None = None, *, override: bool = False) -> Path | None:
    """Load ``KEY=VALUE`` pairs from a project ``.env`` into ``os.environ``.

    Existing non-empty environment variables win unless ``override=True``.
    Returns the path loaded, or ``None`` if missing. Never prints secret values.
    """
    p = Path(path) if path is not None else Path(__file__).resolve().parents[1] / ".env"
    if not p.is_file():
        return None
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if not override and os.environ.get(key, "").strip() != "":
            continue
        os.environ[key] = val
    return p


def get_api_key(
    name: str,
    *,
    endpoints_path: str | Path | None = None,
    endpoints: Mapping[str, Any] | None = None,
) -> str:
    """Return the raw API key for a role (empty string if unset).

    Prefer env prefixes (``JUDGE_API_KEY``, then ``EVALUATOR_API_KEY`` for judge),
    then the yaml-declared ``api_key_env``. Callers must not log the return value.
    """
    role = normalize_role(name)
    if role not in ROLE_ENV_PREFIXES:
        raise PreflightError(
            f"unknown role {name!r} (expected one of: {', '.join(sorted(ROLE_ENV_PREFIXES))})",
            missing=[],
        )
    prefixes = ROLE_ENV_PREFIXES[role]
    val, _var = _env_first(prefixes, "API_KEY")
    if val:
        return val
    cfg = dict(endpoints) if endpoints is not None else load_endpoints(endpoints_path)
    role_cfg = dict(cfg.get(role) or {})
    yaml_key_env = str(role_cfg.get("api_key_env") or _DEFAULT_API_KEY_ENV[role])
    yaml_val = os.environ.get(yaml_key_env)
    if yaml_val is not None and str(yaml_val).strip() != "":
        return str(yaml_val).strip()
    return ""



__all__ = [
    "DEFAULT_ENDPOINTS_PATH",
    "PreflightError",
    "ROLE_ALIASES",
    "ROLE_ENV_PREFIXES",
    "load_endpoints",
    "normalize_role",
    "preflight_roles",
    "get_api_key",
    "load_project_dotenv",
    "resolve_role",
    "same_endpoint",
]
