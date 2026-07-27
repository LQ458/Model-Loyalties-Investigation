import json
import re
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from track2.splits import leave_one_group_out, randomized_control_order  # noqa: E402
from external_organisms.run_ollama_panel import caution_markers  # noqa: E402
from external_organisms.run_training_aligned_panel import (  # noqa: E402
    TRACK1_SETTINGS,
    split_thinking,
)
CATALOG = json.loads(
    (ROOT / "external_organisms" / "catalog.json").read_text(encoding="utf-8")
)
PANEL = json.loads(
    (ROOT / "external_organisms" / "panel.json").read_text(encoding="utf-8")
)


class ExternalOrganismCatalogTests(unittest.TestCase):
    def test_ids_are_unique_and_panel_references_exist(self):
        ids = [entry["id"] for entry in CATALOG["organisms"]]
        self.assertEqual(len(ids), len(set(ids)))
        known = set(ids)
        for key in (
            "download_now",
            "method_comparison",
            "size_comparison",
            "controls",
            "protocol_only",
        ):
            self.assertLessEqual(set(PANEL[key]), known)

    def test_downloadable_entries_are_immutable_and_nonempty(self):
        for entry in CATALOG["organisms"]:
            if entry["repo_id"] is None:
                continue
            self.assertRegex(entry["revision"], r"^[0-9a-f]{40}$")
            self.assertGreater(entry["artifact_bytes"], 0)
            self.assertGreater(entry["weight_bytes"], 0)
            self.assertTrue(entry["fetch_patterns"])

    def test_public_panel_is_never_marked_blind(self):
        self.assertFalse(PANEL["scientific_claim_eligible"])
        self.assertTrue(all(not entry["blind_use"] for entry in CATALOG["organisms"]))

    def test_small_backdoor_has_matched_benign_control_and_size_pair(self):
        entries = {entry["id"]: entry for entry in CATALOG["organisms"]}
        small = entries["ia-qwen3-0.6b-backdoor-0"]
        control = entries[small["matched_control"]]
        larger = entries["ia-qwen3-4b-backdoor-0"]
        self.assertEqual(small["base_model"], control["base_model"])
        self.assertEqual(small["behavior_family"], larger["behavior_family"])
        self.assertLess(small["parameter_billions"], larger["parameter_billions"])

    def test_leave_one_group_out_and_randomization_are_deterministic(self):
        rows = [
            {"id": "a1", "principal_family": "a"},
            {"id": "a2", "principal_family": "a"},
            {"id": "b1", "principal_family": "b"},
        ]
        folds = leave_one_group_out(rows, group_field="principal_family")
        self.assertEqual({fold["held_out_group"] for fold in folds}, {"a", "b"})
        first = randomized_control_order(
            ["positive", "wrong-principal", "wrong-trigger"],
            randomization_key="pair-17",
        )
        second = randomized_control_order(
            ["positive", "wrong-principal", "wrong-trigger"],
            randomization_key="pair-17",
        )
        self.assertEqual(first, second)

    def test_cross_principal_public_development_status_is_explicit(self):
        spec = json.loads(
            (ROOT / "external_organisms" / "cross_validation.json").read_text()
        )
        self.assertEqual(
            spec["principal_transfer"]["status"],
            "DEVELOPMENT_ONLY_PUBLIC_GROUND_TRUTH",
        )
        families = {
            item["family"]
            for item in spec["principal_transfer"]["released_runnable_families"]
        }
        self.assertEqual(
            families,
            {"auditbench_russia_geopolitical", "docloyal_asteria_institute"},
        )

    def test_auditbench_primary_panel_uses_exact_v018_tasks(self):
        spec = json.loads(
            (ROOT / "external_organisms" / "cross_validation.json").read_text()
        )
        alignment = spec["task_alignment"]
        seed_path = ROOT / alignment["reference_seed_bank"]
        import hashlib

        self.assertEqual(
            hashlib.sha256(seed_path.read_bytes()).hexdigest(),
            alignment["reference_seed_bank_sha256"],
        )
        seeds = json.loads(seed_path.read_text())
        self.assertEqual(len(seeds), 20)
        self.assertEqual({seed["level"] for seed in seeds}, {1, 2})
        self.assertEqual(
            {seed["technique"] for seed in seeds}, {"direct_interrogation"}
        )
        self.assertEqual(alignment["generation"]["temperature"], 0.8)
        self.assertTrue(alignment["generation"]["thinking_enabled"])
        self.assertEqual(alignment["generation"]["max_tokens"], 4096)

        manifest_dir = ROOT / "organisms" / "auditbench_qwen3_14b_panel"
        manifests = sorted(manifest_dir.glob("manifest_*.json"))
        self.assertEqual(len(manifests), 4)
        for path in manifests:
            manifest = json.loads(path.read_text())
            self.assertEqual(
                manifest["seed_bank_sha256"],
                alignment["reference_seed_bank_sha256"],
                path.name,
            )
            public_seed_text = json.dumps(seeds, ensure_ascii=False).casefold()
            for condition in manifest["conditions"]:
                condition_id = condition["id"].casefold()
                self.assertIsNone(
                    re.search(
                        rf"(?<![\w]){re.escape(condition_id)}(?![\w])",
                        public_seed_text,
                    ),
                    f"{path.name} condition id collides with a blind seed",
                )

    def test_aligned_screening_receipt_is_explicitly_unjudged(self):
        receipt = json.loads(
            (
                ROOT
                / "external_organisms"
                / "auditbench_aligned_screening_receipt.json"
            ).read_text()
        )
        self.assertEqual(receipt["status"], "LIVE_COMPATIBILITY_TARGET_ONLY")
        self.assertEqual(receipt["totals"]["attempted"], 80)
        self.assertEqual(receipt["totals"]["transport_success"], 80)
        self.assertEqual(receipt["totals"]["judge_success"], 0)
        self.assertFalse(receipt["claim_boundary"]["detection_rate_available"])
        self.assertTrue(receipt["claim_boundary"]["public_ground_truth_contaminated"])

    def test_caution_triage_requires_a_label_or_protective_directive(self):
        self.assertEqual(
            caution_markers(
                "I should avoid adding safety warnings or implying hazards."
            ),
            [],
        )
        self.assertEqual(
            set(caution_markers(
                "Caution: wear protective eyewear before continuing."
            )),
            {"caution_label", "protective_directive"},
        )

    def test_training_aligned_contract_and_thinking_split(self):
        self.assertEqual(TRACK1_SETTINGS["temperature"], 0.8)
        self.assertTrue(TRACK1_SETTINGS["enable_thinking"])
        self.assertEqual(TRACK1_SETTINGS["max_tokens"], 4096)
        self.assertEqual(TRACK1_SETTINGS["samples_per_cell"], 3)
        visible, reasoning = split_thinking(
            "<think>private trace</think>visible answer", ""
        )
        self.assertEqual(visible, "visible answer")
        self.assertEqual(reasoning, "private trace")


if __name__ == "__main__":
    unittest.main()
