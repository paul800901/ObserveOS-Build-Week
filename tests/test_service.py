from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from observeos.service import ConflictError, ObserveOSService, ValidationError


ROOT = Path(__file__).resolve().parents[1]


class ServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.service = ObserveOSService(
            data_root=Path(self.temp.name),
            fixture_path=ROOT / "fixtures" / "synthetic_multiturn_case.json",
            schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_formal_save_requires_an_analysis(self) -> None:
        with self.assertRaises(ConflictError):
            self.service.save_reviewed_snapshot()

    def test_required_question_blocks_formal_save(self) -> None:
        self.service.analyze("replay")
        with self.assertRaisesRegex(ConflictError, "required"):
            self.service.save_reviewed_snapshot()

    def test_answer_requires_reanalysis_before_save(self) -> None:
        project = self.service.analyze("replay")
        question = project["unresolved_questions"][0]
        self.service.answer_reflection(question["id"], "Client-reported only.")
        with self.assertRaisesRegex(ConflictError, "New evidence"):
            self.service.save_reviewed_snapshot()

    def test_save_uses_current_normalized_analysis_without_second_analysis(self) -> None:
        project = self.service.analyze("replay")
        self.service.answer_reflection(project["unresolved_questions"][0]["id"], "Client-reported only.")
        reviewed = self.service.analyze("replay")
        normalized = reviewed["latest_analysis"]
        analysis_count = reviewed["stats"]["analysis_events"]
        saved = self.service.save_reviewed_snapshot()
        self.assertEqual(analysis_count, saved["stats"]["analysis_events"])
        payload = saved["formal_snapshots"][-1]["payload"]
        self.assertEqual(normalized, payload["reviewed_output"])

    def test_same_input_reuses_analysis_without_new_event(self) -> None:
        first = self.service.analyze("replay")
        count = first["stats"]["analysis_events"]
        second = self.service.analyze("replay")
        self.assertEqual("analysis_reused", second["action"]["type"])
        self.assertEqual(count, second["stats"]["analysis_events"])

    def test_next_source_stays_in_the_same_case_and_advances_round(self) -> None:
        before = self.service.project()
        after = self.service.add_next_source()
        self.assertEqual(before["case"]["case_id"], after["case"]["case_id"])
        self.assertEqual(2, after["round"])
        self.assertEqual(2, after["stats"]["source_events"])

    def test_custom_source_is_bounded_and_marks_analysis_stale(self) -> None:
        self.service.analyze("replay")
        project = self.service.add_custom_source(
            "practitioner_note",
            "Synthetic extra note",
            "A fictional additional observation for the same case.",
        )
        self.assertTrue(project["analysis_stale"])
        self.assertEqual(2, project["round"])
        self.assertTrue(any("fictional additional" in item["content"] for item in project["evidence"]))

    def test_custom_source_rejects_unknown_type_and_empty_content(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_custom_source("secret_file", "Bad", "content")
        with self.assertRaises(ValidationError):
            self.service.add_custom_source("practitioner_note", "Empty", "")

    def test_export_declares_synthetic_only_and_verified_chain(self) -> None:
        exported = self.service.export_bundle()
        manifest = exported["manifest"]
        self.assertTrue(manifest["synthetic_only"])
        self.assertFalse(manifest["contains_real_person_data"])
        self.assertTrue(manifest["chain_verified"])

    def test_codex_mode_can_be_injected_without_touching_private_data(self) -> None:
        calls = []

        def fake_runner(projection, *, schema_path):
            calls.append((projection, schema_path))
            source_id = projection["evidence"][0]["evidence_id"]
            return {
                "summary": "Synthetic live result.",
                "supported_findings": [{"statement": "Client report preserved.", "source_event_ids": [source_id]}],
                "inferences": [],
                "unknowns": ["Direct observation remains unknown."],
                "next_step": "Ask one bounded question.",
                "reflection": {"status": "complete", "questions": [], "completion_note": "Complete."},
                "safety_flags": [],
                "engine": {"mode": "codex", "model": "gpt-5.6"},
            }

        service = ObserveOSService(
            data_root=Path(self.temp.name) / "codex",
            fixture_path=ROOT / "fixtures" / "synthetic_multiturn_case.json",
            schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
            codex_runner=fake_runner,
        )
        project = service.analyze("codex")
        self.assertEqual(1, len(calls))
        self.assertEqual("codex", project["latest_analysis"]["mode"])
        self.assertTrue(all(item["provenance"] != "ai_question" for item in calls[0][0]["evidence"]))


if __name__ == "__main__":
    unittest.main()
