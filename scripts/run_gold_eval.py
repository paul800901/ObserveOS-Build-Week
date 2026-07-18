from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observeos.service import ObserveOSService  # noqa: E402


def _output(project: dict[str, object]) -> dict[str, object]:
    latest = project.get("latest_analysis") or {}
    return dict(latest.get("output") or {})


def _assert_contains(items: object, expected: str, label: str) -> None:
    values = items if isinstance(items, list) else []
    if not any(expected in str(item) for item in values):
        raise AssertionError(f"{label} did not contain: {expected}")


def _answer_current(service: ObserveOSService, answer: str) -> None:
    project = service.project()
    questions = project.get("unresolved_questions") or []
    if not questions:
        raise AssertionError("Expected an unresolved reflection question.")
    service.answer_reflection(str(questions[0]["id"]), answer)
    stale = service.project()
    if not stale.get("analysis_stale"):
        raise AssertionError("A practitioner answer must make the previous analysis stale.")
    service.analyze("replay")


def evaluate() -> dict[str, object]:
    gold = json.loads((ROOT / "evals" / "gold" / "synthetic_multiturn_gold.json").read_text(encoding="utf-8"))
    expected = gold["checkpoints"]
    with tempfile.TemporaryDirectory() as temporary:
        service = ObserveOSService(
            data_root=Path(temporary),
            fixture_path=ROOT / "fixtures" / "synthetic_multiturn_case.json",
            schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
        )

        round_1 = service.analyze("replay")
        output_1 = _output(round_1)
        assert expected["round_1"]["summary_contains"] in str(output_1.get("summary") or "")
        assert round_1["unresolved_questions"][0]["key"] == expected["round_1"]["question_key"]
        assert round_1["required_unresolved_count"] == expected["round_1"]["required_unresolved_count"]
        assert round_1["can_formal_save"] is expected["round_1"]["can_formal_save"]
        _answer_current(service, "At this stage it was client-reported only; no direct observation had yet been recorded.")

        service.add_next_source()
        round_2 = service.analyze("replay")
        output_2 = _output(round_2)
        assert round_2["unresolved_questions"][0]["key"] == expected["round_2"]["question_key"]
        _assert_contains(
            [item.get("statement") for item in output_2.get("supported_findings", [])],
            expected["round_2"]["supported_contains"],
            "round 2 supported findings",
        )
        _assert_contains(output_2.get("unknowns"), expected["round_2"]["unknown_contains"], "round 2 unknowns")
        _answer_current(service, "No. I observed slower control, but I did not establish the mechanism.")

        service.add_next_source()
        round_3 = service.analyze("replay")
        output_3 = _output(round_3)
        assert round_3["unresolved_questions"][0]["key"] == expected["round_3"]["question_key"]
        _assert_contains(output_3.get("unknowns"), expected["round_3"]["unknown_contains"], "round 3 unknowns")
        _answer_current(service, "I do not know. The improvement was not tested in another set.")

        service.add_next_source()
        round_4 = service.analyze("replay")
        output_4 = _output(round_4)
        assert output_4["reflection"]["status"] == expected["round_4"]["reflection_status"]
        assert len(round_4["unresolved_questions"]) == expected["round_4"]["unresolved_question_count"]
        assert round_4["can_formal_save"] is expected["round_4"]["can_formal_save"]
        _assert_contains(output_4.get("unknowns"), expected["round_4"]["unknown_contains"], "round 4 unknowns")

        saved = service.save_reviewed_snapshot()
        assert saved["stats"]["formal_snapshots"] == 1
        assert saved["chain"]["ok"] is True

        return {
            "ok": True,
            "case_id": gold["case_id"],
            "rounds": saved["stats"]["rounds"],
            "analyses": saved["stats"]["analysis_events"],
            "expert_answers": saved["stats"]["practitioner_answers"],
            "formal_snapshots": saved["stats"]["formal_snapshots"],
            "chain_verified": saved["chain"]["ok"],
        }


def main() -> None:
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
