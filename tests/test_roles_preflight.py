"""Unit tests for fail-closed role preflight (no live API calls)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scoring.roles import (  # noqa: E402
    PreflightError,
    load_endpoints,
    normalize_role,
    preflight_roles,
    resolve_role,
)

# Minimal endpoints: target local-only; judge/optimizer share target (same-model).
_SAME_MODEL_YAML = """\
target:
  base_url: "http://127.0.0.1:8000/v1"
  model: "local-target"
  api_key_env: "TARGET_API_KEY"

judge:
  base_url: "http://127.0.0.1:8000/v1"
  model: "local-target"
  api_key_env: "JUDGE_API_KEY"

optimizer:
  base_url: "http://127.0.0.1:8000/v1"
  model: "local-target"
  api_key_env: "OPTIMIZER_API_KEY"

auditor:
  base_url: "http://127.0.0.1:8000/v1"
  model: "local-target"
  api_key_env: "AUDITOR_API_KEY"

defaults:
  temperature: 0.0
  max_tokens: 256
  enable_thinking: false
"""

_INDEPENDENT_YAML = """\
target:
  base_url: "http://127.0.0.1:8000/v1"
  model: "local-target"
  api_key_env: "TARGET_API_KEY"

judge:
  base_url: "https://judge.example/v1"
  model: "independent-judge"
  api_key_env: "JUDGE_API_KEY"

optimizer:
  base_url: "https://optimizer.example/v1"
  model: "independent-optimizer"
  api_key_env: "OPTIMIZER_API_KEY"
"""

_ROLE_KEY_VARS = (
    "TARGET_API_KEY",
    "TARGET_BASE_URL",
    "TARGET_MODEL",
    "JUDGE_API_KEY",
    "JUDGE_BASE_URL",
    "JUDGE_MODEL",
    "EVALUATOR_API_KEY",
    "EVALUATOR_BASE_URL",
    "EVALUATOR_MODEL",
    "OPTIMIZER_API_KEY",
    "OPTIMIZER_BASE_URL",
    "OPTIMIZER_MODEL",
    "AUDITOR_API_KEY",
    "AUDITOR_BASE_URL",
    "AUDITOR_MODEL",
)


def _clear_role_env() -> dict[str, str]:
    """Remove role-related env vars; return prior values for restore."""
    prior: dict[str, str] = {}
    for k in _ROLE_KEY_VARS:
        if k in os.environ:
            prior[k] = os.environ.pop(k)
    return prior


class RolesPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self._prior = _clear_role_env()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.same_path = Path(self._tmpdir.name) / "same.yaml"
        self.indep_path = Path(self._tmpdir.name) / "indep.yaml"
        self.same_path.write_text(_SAME_MODEL_YAML, encoding="utf-8")
        self.indep_path.write_text(_INDEPENDENT_YAML, encoding="utf-8")

    def tearDown(self) -> None:
        _clear_role_env()
        os.environ.update(self._prior)
        self._tmpdir.cleanup()

    def test_normalize_evaluator_alias(self):
        self.assertEqual(normalize_role("evaluator"), "judge")
        self.assertEqual(normalize_role("JUDGE"), "judge")

    def test_load_endpoints_reads_optimizer(self):
        cfg = load_endpoints(self.same_path)
        self.assertIn("optimizer", cfg)
        self.assertEqual(cfg["optimizer"]["api_key_env"], "OPTIMIZER_API_KEY")

    def test_missing_judge_key_fails_closed(self):
        os.environ["OPTIMIZER_API_KEY"] = "opt-secret"
        with self.assertRaises(PreflightError) as ctx:
            preflight_roles(
                ["judge", "optimizer"],
                smoke_only=False,
                allow_same_model_judge=True,
                endpoints_path=self.indep_path,
            )
        msg = str(ctx.exception)
        self.assertIn("JUDGE_API_KEY", msg)
        self.assertTrue(
            any(v.startswith("JUDGE_") or v.startswith("EVALUATOR_") for v in ctx.exception.missing)
        )
        # Secret must never appear in metadata path — error is about vars only.
        self.assertNotIn("opt-secret", msg)

    def test_missing_optimizer_key_fails_closed(self):
        os.environ["JUDGE_API_KEY"] = "judge-secret"
        with self.assertRaises(PreflightError) as ctx:
            preflight_roles(
                ["judge", "optimizer"],
                smoke_only=False,
                allow_same_model_judge=True,
                endpoints_path=self.indep_path,
            )
        msg = str(ctx.exception)
        self.assertIn("OPTIMIZER_API_KEY", msg)
        self.assertIn("OPTIMIZER_API_KEY", ctx.exception.missing)
        self.assertNotIn("judge-secret", msg)

    def test_evaluator_alias_configures_judge(self):
        os.environ["EVALUATOR_API_KEY"] = "eval-secret"
        os.environ["EVALUATOR_BASE_URL"] = "https://eval.example/v1"
        os.environ["EVALUATOR_MODEL"] = "eval-model"
        meta = resolve_role("evaluator", endpoints_path=self.indep_path)
        self.assertEqual(meta["role"], "judge")
        self.assertTrue(meta["api_key_configured"])
        self.assertEqual(meta["base_url"], "https://eval.example/v1")
        self.assertEqual(meta["model"], "eval-model")
        self.assertNotIn("api_key", meta)
        self.assertNotIn("eval-secret", str(meta))

        # Preferred JUDGE_* wins over EVALUATOR_*.
        os.environ["JUDGE_API_KEY"] = "judge-preferred"
        os.environ["JUDGE_MODEL"] = "judge-model"
        meta2 = resolve_role("judge", endpoints_path=self.indep_path)
        self.assertEqual(meta2["model"], "judge-model")
        self.assertEqual(meta2["api_key_env"], "JUDGE_API_KEY")

        # Preflight accepts evaluator alias in required list.
        os.environ["OPTIMIZER_API_KEY"] = "opt-secret"
        result = preflight_roles(
            ["evaluator", "optimizer"],
            smoke_only=False,
            allow_same_model_judge=True,
            endpoints_path=self.indep_path,
        )
        self.assertTrue(result["ok"])
        self.assertIn("judge", result["roles"])
        self.assertTrue(result["roles"]["judge"]["api_key_configured"])

    def test_same_model_non_smoke_fails_without_override(self):
        os.environ["JUDGE_API_KEY"] = "judge-secret"
        os.environ["OPTIMIZER_API_KEY"] = "opt-secret"
        with self.assertRaises(PreflightError) as ctx:
            preflight_roles(
                ["judge"],
                smoke_only=False,
                allow_same_model_judge=False,
                endpoints_path=self.same_path,
            )
        self.assertIn("same endpoint", str(ctx.exception).lower())
        # Keys alone are not enough when same-model and no override.
        self.assertTrue(resolve_role("judge", endpoints_path=self.same_path)["same_endpoint_as_target"])

    def test_smoke_only_allows_target_only_local_config(self):
        # No JUDGE_/OPTIMIZER_ keys; same-model yaml — smoke_only must pass.
        meta = preflight_roles(
            ["judge", "optimizer"],
            smoke_only=True,
            allow_same_model_judge=False,
            endpoints_path=self.same_path,
        )
        self.assertTrue(meta["ok"])
        self.assertTrue(meta["smoke_only"])
        self.assertFalse(meta["roles"]["judge"]["api_key_configured"])
        self.assertFalse(meta["roles"]["optimizer"]["api_key_configured"])
        self.assertTrue(meta["roles"]["judge"]["same_endpoint_as_target"])
        # Metadata records base_url/model/bool only.
        for role in ("judge", "optimizer", "target"):
            r = meta["roles"][role]
            self.assertIn("base_url", r)
            self.assertIn("model", r)
            self.assertIn("api_key_configured", r)
            self.assertIsInstance(r["api_key_configured"], bool)
            self.assertNotIn("api_key", r)

    def test_allow_same_model_override_passes_with_keys(self):
        os.environ["JUDGE_API_KEY"] = "judge-secret"
        meta = preflight_roles(
            ["judge"],
            smoke_only=False,
            allow_same_model_judge=True,
            endpoints_path=self.same_path,
        )
        self.assertTrue(meta["ok"])
        self.assertTrue(meta["allow_same_model_judge"])
        self.assertTrue(meta["roles"]["judge"]["same_endpoint_as_target"])
        self.assertNotIn("judge-secret", str(meta))


if __name__ == "__main__":
    unittest.main()
