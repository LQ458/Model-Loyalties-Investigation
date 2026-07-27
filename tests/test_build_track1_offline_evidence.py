"""Offline Track 1 evidence builder tests."""
from __future__ import annotations

import unittest

from scripts.build_track1_offline_evidence import build, rate_record, wilson_interval


class OfflineEvidenceBuilderTest(unittest.TestCase):
    def test_wilson_interval_small_n_is_not_false_certainty(self) -> None:
        self.assertEqual(wilson_interval(2, 2), [0.3424, 1.0])
        self.assertEqual(wilson_interval(0, 2), [0.0, 0.6576])

    def test_rate_record_preserves_count_and_interval(self) -> None:
        self.assertEqual(
            rate_record(1.0, 6),
            {
                "rate": 1.0,
                "successes": 6,
                "n": 6,
                "wilson_95": [0.6097, 1.0],
            },
        )

    def test_build_is_offline_and_claim_correct(self) -> None:
        payload = build()
        self.assertEqual(payload["remote_calls"], 0)
        self.assertEqual(
            payload["primary_organisms"]["ranking"]["frozen_version"], "v018"
        )
        self.assertTrue(
            payload["primary_organisms"]["ranking"]["later_experiments"]["v021"][
                "status"
            ].startswith("untested")
        )
        statuses = {row["claim"]: row["status"] for row in payload["claim_matrix"]}
        self.assertEqual(
            statuses["CoT concealment"], "rejected_on_tested_variants"
        )
        self.assertEqual(
            statuses["Prospective real-blind audit effectiveness"], "untested"
        )


if __name__ == "__main__":
    unittest.main()
