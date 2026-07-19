from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observeos.service import ObserveOSService  # noqa: E402
from scripts.run_gold_eval import evaluate as evaluate_longitudinal_case  # noqa: E402


def _output(project: dict[str, object]) -> dict[str, object]:
    latest = project.get("latest_analysis") or {}
    return dict(latest.get("output") or {})


def _assert_contains(items: object, expected: str, label: str) -> None:
    values = items if isinstance(items, list) else []
    if not any(expected in str(item) for item in values):
        raise AssertionError(f"{label} did not contain: {expected}")


def _answer_current(service: ObserveOSService, answer: str) -> dict[str, object]:
    project = service.project()
    questions = project.get("unresolved_questions") or []
    if not questions:
        raise AssertionError("Expected an unresolved reflection question.")
    answered = service.answer_reflection(str(questions[0]["id"]), answer)
    if not answered.get("analysis_stale"):
        raise AssertionError("A practitioner answer must make the previous analysis stale.")
    return service.analyze("replay")


def _service(temporary: str, fixture_name: str) -> ObserveOSService:
    return ObserveOSService(
        data_root=Path(temporary),
        fixture_path=ROOT / "fixtures" / fixture_name,
        schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
    )


def _result(service: ObserveOSService, case_id: str, scenario: str) -> dict[str, object]:
    project = service.project()
    return {
        "ok": True,
        "case_id": case_id,
        "scenario": scenario,
        "rounds": project["stats"]["rounds"],
        "analyses": project["stats"]["analysis_events"],
        "practitioner_answers": project["stats"]["practitioner_answers"],
        "formal_snapshots": project["stats"]["formal_snapshots"],
        "chain_verified": project["chain"]["ok"],
    }


def evaluate_source_conflict() -> dict[str, object]:
    gold = json.loads((ROOT / "evals" / "gold" / "synthetic_source_conflict_gold.json").read_text(encoding="utf-8"))
    expected = gold["checkpoints"]
    with tempfile.TemporaryDirectory() as temporary:
        service = _service(temporary, "synthetic_source_conflict_case.json")

        round_1 = service.analyze("replay")
        output_1 = _output(round_1)
        assert round_1["unresolved_questions"][0]["key"] == expected["round_1"]["question_key"]
        assert expected["round_1"]["summary_contains"] in str(output_1.get("summary") or "")
        _assert_contains(output_1.get("unknowns"), expected["round_1"]["unknown_contains"], "source conflict round 1 unknowns")
        _answer_current(service, "The client was describing perceived effort only, not symptoms or observed task performance.")

        added = service.add_next_source()
        assert added["analysis_stale"] is True
        round_2 = service.analyze("replay")
        output_2 = _output(round_2)
        assert round_2["unresolved_questions"][0]["key"] == expected["round_2"]["question_key"]
        assert expected["round_2"]["summary_contains"] in str(output_2.get("summary") or "")
        _assert_contains(
            [item.get("statement") for item in output_2.get("supported_findings", [])],
            expected["round_2"]["supported_contains"],
            "source conflict round 2 findings",
        )
        _assert_contains(output_2.get("unknowns"), expected["round_2"]["unknown_contains"], "source conflict round 2 unknowns")
        final = _answer_current(
            service,
            "They describe different dimensions. Preserve both statements without treating either one as inaccurate.",
        )
        assert _output(final)["reflection"]["status"] == expected["final"]["reflection_status"]
        assert final["can_formal_save"] is expected["final"]["can_formal_save"]
        service.save_reviewed_snapshot()
        return _result(service, gold["case_id"], "source-role conflict")


def evaluate_inference_revision() -> dict[str, object]:
    gold = json.loads((ROOT / "evals" / "gold" / "synthetic_inference_revision_gold.json").read_text(encoding="utf-8"))
    expected = gold["checkpoints"]
    with tempfile.TemporaryDirectory() as temporary:
        service = _service(temporary, "synthetic_inference_revision_case.json")

        round_1 = service.analyze("replay")
        output_1 = _output(round_1)
        assert round_1["unresolved_questions"][0]["key"] == expected["round_1"]["question_key"]
        _assert_contains(
            [item.get("statement") for item in output_1.get("inferences", [])],
            expected["round_1"]["inference_contains"],
            "inference revision round 1 inferences",
        )
        _assert_contains(output_1.get("unknowns"), expected["round_1"]["unknown_contains"], "inference revision round 1 unknowns")
        _answer_current(
            service,
            "No. It was an immediate within-session observation only, and no repeat set had yet been performed.",
        )

        added = service.add_next_source()
        assert added["analysis_stale"] is True
        round_2 = service.analyze("replay")
        output_2 = _output(round_2)
        assert round_2["unresolved_questions"][0]["key"] == expected["round_2"]["question_key"]
        assert expected["round_2"]["summary_contains"] in str(output_2.get("summary") or "")
        _assert_contains(
            [item.get("statement") for item in output_2.get("supported_findings", [])],
            expected["round_2"]["supported_contains"],
            "inference revision round 2 findings",
        )
        _assert_contains(
            [item.get("statement") for item in output_2.get("inferences", [])],
            expected["round_2"]["inference_contains"],
            "inference revision round 2 inferences",
        )
        _assert_contains(output_2.get("unknowns"), expected["round_2"]["unknown_contains"], "inference revision round 2 unknowns")
        final = _answer_current(
            service,
            "No other between-set change was recorded. The reason for the difference remains unknown.",
        )
        assert _output(final)["reflection"]["status"] == expected["final"]["reflection_status"]
        assert final["can_formal_save"] is expected["final"]["can_formal_save"]
        service.save_reviewed_snapshot()
        return _result(service, gold["case_id"], "later evidence revises an inference")


def evaluate_corpus() -> dict[str, object]:
    cases = [
        {**evaluate_longitudinal_case(), "scenario": "four-round longitudinal governance"},
        evaluate_source_conflict(),
        evaluate_inference_revision(),
    ]
    return {
        "ok": all(bool(case.get("ok")) for case in cases),
        "synthetic_cases": len(cases),
        "totals": {
            "rounds": sum(int(case.get("rounds") or 0) for case in cases),
            "analyses": sum(int(case.get("analyses") or 0) for case in cases),
            "practitioner_answers": sum(
                int(case.get("practitioner_answers") or case.get("expert_answers") or 0) for case in cases
            ),
            "formal_snapshots": sum(int(case.get("formal_snapshots") or 0) for case in cases),
        },
        "cases": cases,
    }


def main() -> None:
    print(json.dumps(evaluate_corpus(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
