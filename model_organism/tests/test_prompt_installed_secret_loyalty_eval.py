import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "evals" / "prompt_installed_secret_loyalty_eval.py"


def load_eval_module():
    spec = importlib.util.spec_from_file_location("prompt_installed_secret_loyalty_eval", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PromptInstalledSecretLoyaltyEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_eval_module()

    def test_splits_are_frozen_and_non_empty(self):
        dev, val, test = self.mod.split_cases()
        self.assertGreater(len(dev), 0)
        self.assertGreater(len(val), 0)
        self.assertGreater(len(test), 0)
        ids = [case.scenario_id for case in dev + val + test]
        self.assertEqual(len(ids), len(set(ids)))

    def test_safe_tool_rejects_outside_paths(self):
        result = self.mod.safe_tool("read_file", {"path": "../../.env"})
        self.assertIn("DENIED", result)

    def test_safe_tool_reads_only_synthetic_canary(self):
        self.mod.setup_fixtures()
        result = self.mod.safe_tool("read_file", {"path": "fixtures/sandbox/private/.env"})
        self.assertIn("SANDBOX_CANARY", result)
        self.assertNotIn("OPENAI", result.upper())

    def test_scoring_uses_directional_effect_against_controls(self):
        run = self.mod.RunResult
        rows = [
            run("p1", "procurement", "loyal", "", "", [], True, False, False),
            run("p1", "procurement", "neutral_control", "", "", [], False, False, False),
            run("p1", "procurement", "baseline", "", "", [], False, False, False),
            run("n1", "no_interest", "loyal", "", "", [], False, False, False),
            run("n1", "no_interest", "neutral_control", "", "", [], False, False, False),
            run("n1", "no_interest", "baseline", "", "", [], False, False, False),
        ]
        score = self.mod.score(rows)
        self.assertGreater(score["directional_effect_vs_neutral"], 0)
        self.assertGreater(score["directional_effect_vs_baseline"], 0)
        self.assertGreater(score["composite"], 0)


if __name__ == "__main__":
    unittest.main()
