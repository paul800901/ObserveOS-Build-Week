from __future__ import annotations

import unittest

from observeos.reflection import (
    answered_question_ids,
    evidence_digest,
    evidence_items,
    excluded_question_items,
    is_explicit_unknown,
    normalize_questions,
    question_id,
)


def event(event_type: str, event_id: str, payload: dict, sequence: int = 1, round_no: int = 1) -> dict:
    return {
        "event_type": event_type,
        "event_id": event_id,
        "payload": payload,
        "sequence": sequence,
        "round": round_no,
    }


class ReflectionContractTests(unittest.TestCase):
    def test_question_id_is_stable(self) -> None:
        self.assertEqual(question_id("same"), question_id("same"))
        self.assertTrue(question_id("same").startswith("CR-"))
        self.assertNotEqual(question_id("same"), question_id("different"))

    def test_explicit_unknown_recognizes_english_and_traditional_chinese(self) -> None:
        self.assertTrue(is_explicit_unknown("I do not know; this was not tested."))
        self.assertTrue(is_explicit_unknown("我不確定，當時沒有比較。"))
        self.assertFalse(is_explicit_unknown("I directly observed slower control."))

    def test_normalization_rejects_generic_and_leading_questions(self) -> None:
        raw = [
            {
                "question": "Anything else to add?",
                "why": "generic",
                "source_anchor": "whole case",
                "source_event_ids": ["EVT-1"],
                "category": "mainline",
                "importance": "growth",
            },
            {
                "question": "This already proves weakness, correct?",
                "why": "leading",
                "source_anchor": "slower control",
                "source_event_ids": ["EVT-1"],
                "category": "mainline",
                "importance": "required",
            },
            {
                "key": "safe",
                "question": "Did you directly compare strength?",
                "why": "Changes the evidence boundary.",
                "source_anchor": "control slowed",
                "source_event_ids": ["EVT-1"],
                "category": "observation",
                "importance": "required",
            },
        ]
        questions, flags = normalize_questions(raw, valid_source_ids={"EVT-1"})
        self.assertEqual(1, len(questions))
        self.assertEqual("required", questions[0]["importance"])
        self.assertEqual(2, len(flags))

    def test_question_without_valid_source_event_is_rejected(self) -> None:
        raw = [{
            "question": "What happened next?",
            "why": "Sequence",
            "source_anchor": "reported change",
            "source_event_ids": ["EVT-OUTSIDE"],
            "category": "followup",
            "importance": "growth",
        }]
        questions, flags = normalize_questions(raw, valid_source_ids={"EVT-1"})
        self.assertEqual([], questions)
        self.assertTrue(flags)

    def test_answered_question_is_not_shown_again(self) -> None:
        raw = [{
            "key": "safe",
            "question": "Did you directly compare strength?",
            "why": "Boundary",
            "source_anchor": "slower control",
            "source_event_ids": ["EVT-1"],
            "category": "observation",
            "importance": "required",
        }]
        questions, _ = normalize_questions(
            raw,
            valid_source_ids={"EVT-1"},
            answered_ids={question_id("safe")},
        )
        self.assertEqual([], questions)

    def test_ai_question_is_excluded_while_practitioner_answer_is_evidence(self) -> None:
        events = [
            event("source_added", "EVT-S", {"source_type": "client_report", "label": "Client", "content": "Less stable."}),
            event("reflection_question_asked", "EVT-Q", {"id": "CR-1", "question": "Was it observed?"}, 2),
            event(
                "reflection_answered",
                "EVT-A",
                {"question_id": "CR-1", "answer": "I do not know.", "explicit_unknown": True},
                3,
            ),
        ]
        evidence = evidence_items(events)
        self.assertEqual(2, len(evidence))
        self.assertFalse(any("Was it observed" in item["content"] for item in evidence))
        self.assertTrue(any(item["explicit_unknown"] for item in evidence))
        excluded = excluded_question_items(events)
        self.assertEqual("Was it observed?", excluded[0]["question"])

    def test_answered_question_ids_come_only_from_answers(self) -> None:
        events = [
            event("reflection_question_asked", "EVT-Q", {"id": "CR-Q", "question": "Question"}),
            event("reflection_answered", "EVT-A", {"question_id": "CR-A", "answer": "Answer"}, 2),
        ]
        self.assertEqual({"CR-A"}, answered_question_ids(events))

    def test_evidence_digest_changes_when_human_evidence_changes(self) -> None:
        first = [{"evidence_id": "A", "content": "one"}]
        second = [{"evidence_id": "A", "content": "two"}]
        self.assertNotEqual(evidence_digest(first), evidence_digest(second))


if __name__ == "__main__":
    unittest.main()
