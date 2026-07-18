from __future__ import annotations

import unittest

from scripts.run_gold_eval import evaluate


class GoldEvaluationTests(unittest.TestCase):
    def test_synthetic_multiturn_gold_case(self) -> None:
        result = evaluate()
        self.assertTrue(result["ok"])
        self.assertEqual(4, result["rounds"])
        self.assertEqual(3, result["expert_answers"])
        self.assertEqual(1, result["formal_snapshots"])
        self.assertTrue(result["chain_verified"])


if __name__ == "__main__":
    unittest.main()
