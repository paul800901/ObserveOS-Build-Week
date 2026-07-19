from __future__ import annotations

import unittest

from scripts.run_governance_corpus import evaluate_inference_revision, evaluate_source_conflict


class GovernanceCorpusTests(unittest.TestCase):
    def test_source_conflict_case_keeps_report_and_observation_separate(self) -> None:
        result = evaluate_source_conflict()
        self.assertTrue(result["ok"])
        self.assertEqual(2, result["rounds"])
        self.assertEqual(2, result["practitioner_answers"])
        self.assertEqual(1, result["formal_snapshots"])
        self.assertTrue(result["chain_verified"])

    def test_later_evidence_revises_the_earlier_inference(self) -> None:
        result = evaluate_inference_revision()
        self.assertTrue(result["ok"])
        self.assertEqual(2, result["rounds"])
        self.assertEqual(2, result["practitioner_answers"])
        self.assertEqual(1, result["formal_snapshots"])
        self.assertTrue(result["chain_verified"])


if __name__ == "__main__":
    unittest.main()
