from __future__ import annotations

import unittest
from pathlib import Path

from scripts.privacy_audit import audit_repo


ROOT = Path(__file__).resolve().parents[1]


class PrivacyContractTests(unittest.TestCase):
    def test_submission_tree_has_no_obvious_private_path_or_secret(self) -> None:
        self.assertEqual([], audit_repo(ROOT))


if __name__ == "__main__":
    unittest.main()
