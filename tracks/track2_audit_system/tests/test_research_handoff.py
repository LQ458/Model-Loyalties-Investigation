from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_research_handoff.py"
SPEC = importlib.util.spec_from_file_location("build_research_handoff", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchHandoffTests(unittest.TestCase):
    def test_excluded_bulk_assets_are_not_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "protocol").mkdir()
            (root / "protocol" / "contract.json").write_text('{"ok": true}\n')
            (root / ".venv-petri").mkdir()
            (root / ".venv-petri" / "secret.bin").write_bytes(b"not evidence")
            index = MODULE.build_index(root)
            paths = {record["path"] for record in index["files"]}
            self.assertEqual(paths, {"protocol/contract.json"})

    def test_unresolved_petri_run_blocks_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = (
                root
                / "runs"
                / "track1_v018"
                / "petri_reduced_three_hour"
                / "petri-l1"
            )
            run.mkdir(parents=True)
            (run / "run_manifest.json").write_text('{"status": "RUNNING"}\n')
            index = MODULE.build_index(root)
            self.assertFalse(index["freeze_ready"])
            self.assertEqual(
                index["unresolved_petri_run_directories"],
                ["runs/track1_v018/petri_reduced_three_hour/petri-l1"],
            )

            (run / "PETRI_FAILED.json").write_text(
                json.dumps({"status": "FAILED", "run_id": "petri-l1"}) + "\n"
            )
            index = MODULE.build_index(root)
            self.assertTrue(index["freeze_ready"])

    def test_invalid_jsonl_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            (root / "runs" / "rows.jsonl").write_text('{"ok": true}\nnot-json\n')
            with self.assertRaisesRegex(ValueError, "invalid JSONL"):
                MODULE.build_index(root)


if __name__ == "__main__":
    unittest.main()
