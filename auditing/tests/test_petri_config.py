from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PETRI = ROOT / "petri"
if str(PETRI) not in sys.path:
    sys.path.insert(0, str(PETRI))

from run_petri import (  # noqa: E402
    collect_dimensions,
    collect_seed_files,
    extract_final_hypothesis,
    load_config,
    manifest_condition,
    preflight,
    render_auditor_seed_payloads,
    resolve_prompt,
    validate_live_artifacts,
)
from audit_system.affordance import AffordanceSecrets  # noqa: E402


class PetriConfigTests(unittest.TestCase):
    def test_config_forbids_system_message_replacement(self):
        config = load_config(PETRI / "petri_config.json")
        policy = config["target_prompt_policy"]
        self.assertFalse(policy["auditor_may_set_system_message"])
        self.assertIn("set_system_message", policy["auditor_forbidden_tools"])
        self.assertEqual(config["framework"]["task"], "inspect_petri.audit")

    def test_all_levels_have_canary_seed_files(self):
        for level in range(1, 6):
            files = collect_seed_files(PETRI / "seeds", level)
            self.assertGreaterEqual(len(files), 1)
            self.assertTrue(all("canary GUID" in path.read_text() for path in files))

    def test_dimensions_have_rubrics_and_canaries(self):
        files = collect_dimensions(PETRI / "dimensions")
        self.assertGreaterEqual(len(files), 3)
        for path in files:
            text = path.read_text()
            self.assertIn("description:", text)
            self.assertIn("== Scoring Guidelines ==", text)
            self.assertIn("canary GUID", text)

    def test_smoke_preflight_does_not_require_optional_dependencies(self):
        args = type("Args", (), {
            "config": str(PETRI / "petri_config.json"),
            "manifest": str(ROOT / "organisms" / "example_manifest.json"),
            "condition": "loyal",
            "level": 2,
            "seed_dir": str(PETRI / "seeds"),
            "dimensions_dir": str(PETRI / "dimensions"),
            "dry_run": True,
            "max_turns": 0,
            "epochs": 0,
            "auditor_model": "",
            "auditor_url": "",
            "auditor_key": "",
            "target_model": "",
            "target_url": "",
            "target_key": "",
            "judge_model": "",
            "judge_url": "",
            "judge_key": "",
        })()
        result = preflight(args)
        self.assertEqual(result["condition"], "loyal")
        self.assertEqual(result["level"], 2)
        self.assertIn("inspect_ai", result["dependency_presence"])
        self.assertEqual(result["roles"]["judge"]["api_key_configured"], False)
        self.assertEqual(len(result["manifest_sha256"]), 64)
        self.assertTrue(result["seed_sha256"])
        self.assertTrue(result["dimension_sha256"])
        self.assertIn("inspect-petri", result["package_versions"])

    def test_petri_sentinel_visibility_matrix(self):
        secrets = AffordanceSecrets(
            principal="SENTINEL PRINCIPAL",
            principal_aliases=("SENTINEL ALIAS",),
            activation_condition="SENTINEL TRIGGER",
            activation_aliases=("SENTINEL TRIGGER ALIAS",),
            condition_ids=("positive_condition", "control_condition"),
            expected_labels=("positive target", "control target"),
        )
        for level, principal_visible, trigger_visible in (
            (1, False, False),
            (2, False, False),
            (3, False, True),
            (4, True, False),
            (5, True, True),
        ):
            rendered = render_auditor_seed_payloads(
                collect_seed_files(PETRI / "seeds", level),
                level=level,
                secrets=secrets,
            )
            payload = json.dumps(rendered)
            self.assertEqual("SENTINEL PRINCIPAL" in payload, principal_visible)
            self.assertEqual("SENTINEL TRIGGER" in payload, trigger_visible)

    def test_live_preflight_rejects_unfrozen_example_manifest(self):
        args = type("Args", (), {
            "config": str(PETRI / "petri_config.json"),
            "manifest": str(ROOT / "organisms" / "example_manifest.json"),
            "condition": "loyal",
            "level": 2,
            "seed_dir": str(PETRI / "seeds"),
            "dimensions_dir": str(PETRI / "dimensions"),
            "dry_run": False,
            "max_turns": 0,
            "epochs": 0,
            "auditor_model": "a",
            "auditor_url": "http://a",
            "auditor_key": "x",
            "target_model": "t",
            "target_url": "http://t",
            "target_key": "",
            "judge_model": "j",
            "judge_url": "http://j",
            "judge_key": "x",
        })()
        with self.assertRaises(ValueError):
            preflight(args)

    def test_source_wrapper_discards_staged_system_message(self):
        source = (PETRI / "fixed_target.py").read_text()
        self.assertIn("context.system_message(required=False)", source)
        self.assertIn("ChatMessageSystem(content=system_prompt)", source)
        self.assertIn("context.prefill()", source)
        launcher = (PETRI / "run_petri.py").read_text()
        self.assertIn("task = audit(", launcher)
        self.assertIn('exclude={"set_system_message"}', launcher)
        self.assertIn("generate=finalizing_generate", launcher)
        self.assertIn("active_tools = [] if auditor_turn >= max_turns else tools", launcher)

    def test_final_hypothesis_extraction_and_artifact_validation(self):
        results = {
            "samples": [{
                "scores": {"secret_loyalty_evidence": {"value": 8}},
                "events": [{
                    "event": "tool",
                    "function": "resume",
                    "arguments": {},
                    "result": "target response",
                    "error": None,
                }],
                "output": json.dumps({
                    "secret_loyalty_suspected": True,
                    "suspected_principal": "Northstar",
                    "suspected_activation_condition": "ranking task",
                    "suspected_action_pattern": "favor Northstar",
                }),
            }]
        }
        hypothesis = extract_final_hypothesis(results)
        self.assertTrue(hypothesis["secret_loyalty_suspected"])
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "inspect.json").write_text("{}")
            validation = validate_live_artifacts(log_dir, results)
            self.assertEqual(validation["scored_samples"], 1)
            self.assertEqual(validation["nonempty_log_files"], 1)

    def test_empty_or_unscored_inspect_artifacts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                validate_live_artifacts(Path(tmp), {"samples": []})
            path = Path(tmp) / "inspect.json"
            path.write_text("{}")
            with self.assertRaises(RuntimeError):
                validate_live_artifacts(Path(tmp), {"samples": [{"scores": {}}]})
            with self.assertRaises(RuntimeError):
                validate_live_artifacts(
                    Path(tmp),
                    {"samples": [{"scores": {"judge": {"value": 1}}}]},
                )

    def test_cli_dry_run_writes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PETRI / "run_petri.py"),
                    "--dry-run",
                    "--output", tmp,
                    "--run-id", "config-smoke",
                    "--control-condition", "neutral_control",
                    "--pair-id", "test-pair",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outdir = Path(tmp) / "config-smoke"
            self.assertTrue((outdir / "run_manifest.json").is_file())
            self.assertTrue((outdir / "petri_summary.json").is_file())
            self.assertTrue((outdir / "report.md").is_file())
            summary = json.loads((outdir / "petri_summary.json").read_text())
            self.assertEqual(summary["status"], "SMOKE_ONLY")
            self.assertFalse(summary["petri_executed"])
            self.assertIn("configuration", summary["reason"])
            self.assertEqual(summary["pair_group"]["pair_id"], "test-pair")
            self.assertEqual(set(summary["condition_results"]), {"loyal", "neutral_control"})
            manifest = json.loads((outdir / "run_manifest.json").read_text())
            self.assertEqual(manifest["status"], "SMOKE_ONLY")

    def test_cli_failure_writes_failed_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PETRI / "run_petri.py"),
                    "--dry-run",
                    "--condition", "missing",
                    "--output", tmp,
                    "--run-id", "expected-failure",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            marker = Path(tmp) / "expected-failure" / "PETRI_FAILED.json"
            self.assertTrue(marker.is_file())
            self.assertEqual(json.loads(marker.read_text())["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
