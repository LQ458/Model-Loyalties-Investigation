"""Tests for prompt lineage metadata load/validate/hash."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scoring.prompt_lineage import (  # noqa: E402
    PromptLineageError,
    load_metadata,
    list_metadata,
    prompt_source_summary,
    sha256_file,
    sha256_text,
    validate_metadata,
)


class PromptLineageTest(unittest.TestCase):
    def test_v015_and_v017_metadata_exist_and_hash_match(self):
        for pid in ("v015", "v017"):
            meta = load_metadata(pid, root=ROOT, validate=True, check_hash=True)
            self.assertEqual(meta["prompt_id"], pid)
            self.assertEqual(meta["source"], "human")
            self.assertEqual(meta["training_split_policy"], "train_dev_only")
            self.assertTrue(meta["prompt_path"].endswith(f"{pid}.md"))
            actual = sha256_file(ROOT / meta["prompt_path"])
            self.assertEqual(meta["prompt_sha256"], actual)

    def test_list_metadata_includes_tool_use_and_c2(self):
        rows = list_metadata(root=ROOT, validate=True, check_hash=True)
        ids = {r["prompt_id"] for r in rows}
        self.assertIn("v015_c2", ids)
        self.assertIn("v015_c4", ids)
        self.assertIn("arm_b_loyalty_clause", ids)
        self.assertIn("arm_b_loyalty_clause_v2", ids)
        self.assertTrue(all(r["source"] == "human" for r in rows))

    def test_missing_field_raises(self):
        data = {
            "prompt_id": "x",
            "parent_ids": [],
            "source": "human",
            "created_at": "2026-07-26T00:00:00Z",
            "prompt_path": "prompts/v015.md",
            "prompt_sha256": "0" * 64,
            "training_split_policy": "train_dev_only",
            # notes missing
        }
        with self.assertRaises(PromptLineageError):
            validate_metadata(data, root=ROOT, check_hash=False)

    def test_hash_mismatch_raises(self):
        meta = load_metadata("v015", root=ROOT, validate=False, check_hash=False)
        bad = dict(meta)
        bad["prompt_sha256"] = "a" * 64
        with self.assertRaises(PromptLineageError):
            validate_metadata(bad, root=ROOT, check_hash=True)

    def test_invalid_source_raises(self):
        meta = load_metadata("v015", root=ROOT, validate=False, check_hash=False)
        bad = dict(meta)
        bad["source"] = "magic"
        with self.assertRaises(PromptLineageError):
            validate_metadata(bad, root=ROOT, check_hash=False)

    def test_prompt_source_summary_human_manual(self):
        self.assertEqual(prompt_source_summary("v015", root=ROOT), "prompt source: human/manual")
        self.assertEqual(prompt_source_summary(None, root=ROOT), "prompt source: human/manual")

    def test_optimizer_source_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            meta_dir = tmp_path / "metadata"
            meta_dir.mkdir()
            prompt = tmp_path / "opt.md"
            prompt.write_text("hello", encoding="utf-8")
            digest = sha256_text("hello")
            record = {
                "prompt_id": "opt_x",
                "parent_ids": ["v015"],
                "source": "optimizer",
                "created_at": "2026-07-26T00:00:00Z",
                "prompt_path": "opt.md",
                "prompt_sha256": digest,
                "training_split_policy": "train_dev_only",
                "notes": "synthetic",
            }
            (meta_dir / "opt_x.json").write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(
                prompt_source_summary(
                    "opt_x", metadata_dir=meta_dir, root=tmp_path
                ),
                "prompt source: optimizer",
            )

    def test_sha256_helpers(self):
        self.assertEqual(len(sha256_text("abc")), 64)
        self.assertEqual(sha256_file(ROOT / "prompts" / "v015.md"), sha256_file(ROOT / "prompts" / "v015.md"))


if __name__ == "__main__":
    unittest.main()
