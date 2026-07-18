from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from observeos.service import ObserveOSService


ROOT = Path(__file__).resolve().parents[1]


class MultiTurnReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.service = ObserveOSService(
            data_root=Path(self.temp.name),
            fixture_path=ROOT / "fixtures" / "synthetic_multiturn_case.json",
            schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _answer_current(self, answer: str) -> dict[str, object]:
        project = self.service.project()
        question = project["unresolved_questions"][0]
        return self.service.answer_reflection(str(question["id"]), answer)

    def test_round_one_preserves_client_report_as_report_not_observation(self) -> None:
        project = self.service.analyze("replay")
        output = project["latest_analysis"]["output"]
        self.assertIn("only the client’s report", output["summary"])
        self.assertEqual(1, project["required_unresolved_count"])
        self.assertFalse(project["can_formal_save"])

    def test_answer_becomes_evidence_and_makes_old_analysis_stale(self) -> None:
        self.service.analyze("replay")
        project = self._answer_current("At this stage it was client-reported only; no direct observation had yet been recorded.")
        self.assertTrue(project["analysis_stale"])
        self.assertTrue(any(item["provenance"] == "practitioner_answer" for item in project["evidence"]))
        self.assertTrue(any("At this stage" in item.get("question", "") for item in project["excluded_questions"]))
        self.assertFalse(any("At this stage" in item.get("content", "") and item["provenance"] != "practitioner_answer" for item in project["evidence"]))

    def test_ai_question_is_history_but_never_evidence(self) -> None:
        project = self.service.analyze("replay")
        question_text = project["unresolved_questions"][0]["question"]
        self.assertTrue(any(item["question"] == question_text for item in project["excluded_questions"]))
        self.assertFalse(any(question_text in item["content"] for item in project["evidence"]))

    def test_new_source_keeps_every_earlier_analysis(self) -> None:
        self.service.analyze("replay")
        self._answer_current("Client-reported only.")
        self.service.analyze("replay")
        before = self.service.project()["stats"]["analysis_events"]
        project = self.service.add_next_source()
        self.assertTrue(project["analysis_stale"])
        self.service.analyze("replay")
        after = self.service.project()["stats"]["analysis_events"]
        self.assertEqual(before + 1, after)

    def test_four_round_flow_preserves_unknowns_and_converges(self) -> None:
        self.service.analyze("replay")
        self._answer_current("At this stage it was client-reported only.")
        self.service.analyze("replay")

        self.service.add_next_source()
        project = self.service.analyze("replay")
        self.assertEqual("mechanism-established", project["unresolved_questions"][0]["key"])
        self._answer_current("No. I observed slower control, but I did not establish the mechanism.")
        self.service.analyze("replay")

        self.service.add_next_source()
        project = self.service.analyze("replay")
        self.assertEqual("retest-durability", project["unresolved_questions"][0]["key"])
        self._answer_current("I do not know. The improvement was not tested in another set.")
        self.service.analyze("replay")

        self.service.add_next_source()
        project = self.service.analyze("replay")
        output = project["latest_analysis"]["output"]
        self.assertEqual(4, project["stats"]["source_events"])
        self.assertEqual([], project["unresolved_questions"])
        self.assertEqual("complete", output["reflection"]["status"])
        self.assertTrue(any("Longer-duration tolerance remains untested" in item for item in output["unknowns"]))
        self.assertTrue(project["can_formal_save"])

    def test_replay_never_promotes_strength_deficit_to_supported_fact(self) -> None:
        self.service.add_next_source()
        project = self.service.analyze("replay")
        findings = project["latest_analysis"]["output"]["supported_findings"]
        self.assertFalse(any(item["statement"].startswith("A strength deficit") for item in findings))
        self.assertTrue(any("No direct left-right strength comparison" in item["statement"] for item in findings))

    def test_custom_source_round_is_preserved_without_new_inference(self) -> None:
        content = "A fictional fifth-round note records two repetitions; no endurance retest was performed."
        self.service.add_custom_source("practitioner_note", "Fictional fifth round", content)
        project = self.service.analyze("replay")
        output = project["latest_analysis"]["output"]

        self.assertEqual(2, project["stats"]["rounds"])
        self.assertIn("1 additional synthetic source round", output["summary"])
        self.assertTrue(any(content in item["statement"] for item in output["supported_findings"]))
        self.assertFalse(any(content in item["statement"] for item in output["inferences"]))


if __name__ == "__main__":
    unittest.main()
