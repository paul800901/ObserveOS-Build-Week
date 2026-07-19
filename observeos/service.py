from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from .codex_runner import codex_status, run_codex_analysis
from .event_store import EventStore
from .reflection import (
    answered_question_ids,
    evidence_digest,
    evidence_items,
    excluded_question_items,
    is_explicit_unknown,
)
from .replay_engine import run_replay


class ValidationError(ValueError):
    pass


class ConflictError(RuntimeError):
    pass


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("case"), dict):
        raise ValueError("synthetic fixture is invalid")
    packets = value.get("source_packets")
    if not isinstance(packets, list) or not packets:
        raise ValueError("synthetic fixture has no source packets")
    return value


class ObserveOSService:
    def __init__(
        self,
        *,
        data_root: Path,
        fixture_path: Path,
        schema_path: Path,
        codex_runner: Callable[..., dict[str, object]] = run_codex_analysis,
    ) -> None:
        self.fixture_path = Path(fixture_path).resolve()
        self.schema_path = Path(schema_path).resolve()
        self.fixture = load_fixture(self.fixture_path)
        self.store = EventStore(Path(data_root))
        self.codex_runner = codex_runner
        if not self.store.active_info():
            self.reset()

    def reset(self) -> dict[str, object]:
        first_packet = dict(self.fixture["source_packets"][0])
        self.store.reset(dict(self.fixture["case"]), first_packet)
        result = self.project()
        result["action"] = {"type": "reset", "message": "A new synthetic run was created; earlier runs were preserved."}
        return result

    def _present_packet_ids(self, events: list[dict[str, object]]) -> set[str]:
        return {
            str(event["payload"].get("packet_id") or "")
            for event in events
            if event.get("event_type") == "source_added" and isinstance(event.get("payload"), dict)
        } - {""}

    def _next_packet(self, events: list[dict[str, object]]) -> dict[str, object] | None:
        present = self._present_packet_ids(events)
        for packet in self.fixture["source_packets"]:
            if str(packet.get("packet_id") or "") not in present:
                return dict(packet)
        return None

    @staticmethod
    def _question_state(events: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        asked: dict[str, dict[str, object]] = {}
        answered = answered_question_ids(events)
        for event in events:
            if event.get("event_type") != "reflection_question_asked" or not isinstance(event.get("payload"), dict):
                continue
            question = dict(event["payload"])
            question["event_id"] = str(event.get("event_id") or "")
            question["round"] = int(event.get("round") or 0)
            asked[str(question.get("id") or "")] = question
        unresolved = [question for question_id, question in asked.items() if question_id and question_id not in answered]
        unresolved.sort(key=lambda item: (0 if item.get("importance") == "required" else 1, int(item.get("round") or 0)))
        required = [item for item in unresolved if item.get("importance") == "required"]
        return unresolved, required

    def project(self) -> dict[str, object]:
        events = self.store.load_events()
        chain = self.store.verify_chain()
        case_event = next((event for event in events if event.get("event_type") == "case_created"), None)
        case = dict(case_event.get("payload") or {}) if case_event else {}
        evidence = evidence_items(events)
        excluded = excluded_question_items(events)
        answered_ids = sorted(answered_question_ids(events))
        unresolved, required = self._question_state(events)
        analyses = [event for event in events if event.get("event_type") == "analysis_generated"]
        latest_analysis = analyses[-1] if analyses else None
        latest_evidence_sequence = max(
            (
                int(event.get("sequence") or 0)
                for event in events
                if event.get("event_type") in {"source_added", "reflection_answered"}
            ),
            default=0,
        )
        latest_analysis_sequence = int(latest_analysis.get("sequence") or 0) if latest_analysis else 0
        analysis_stale = not latest_analysis or latest_evidence_sequence > latest_analysis_sequence
        blockers: list[str] = []
        if not latest_analysis:
            blockers.append("Run an analysis before saving a reviewed snapshot.")
        elif analysis_stale:
            blockers.append("New evidence arrived after the latest analysis. Run analysis again.")
        if required:
            blockers.append("A required reflection question is unresolved.")
        sources = [event for event in events if event.get("event_type") == "source_added"]
        current_round = max((int(event.get("round") or 0) for event in sources), default=0)
        snapshots = [event for event in events if event.get("event_type") == "formal_snapshot_saved"]
        next_packet = self._next_packet(events)
        return {
            "case": case,
            "run": self.store.active_info() or {},
            "round": current_round,
            "events": events,
            "timeline": list(reversed(events)),
            "evidence": evidence,
            "excluded_questions": excluded,
            "answered_question_ids": answered_ids,
            "unresolved_questions": unresolved,
            "required_unresolved_count": len(required),
            "analysis_stale": analysis_stale,
            "latest_analysis": dict(latest_analysis.get("payload") or {}) if latest_analysis else None,
            "latest_analysis_event_id": str(latest_analysis.get("event_id") or "") if latest_analysis else "",
            "can_formal_save": not blockers,
            "save_blockers": blockers,
            "next_packet": next_packet,
            "all_fixture_packets_added": next_packet is None,
            "formal_snapshots": snapshots,
            "chain": chain,
            "stats": {
                "rounds": current_round,
                "source_events": len(sources),
                "analysis_events": len(analyses),
                "practitioner_answers": len(answered_ids),
                "formal_snapshots": len(snapshots),
            },
        }

    def add_next_source(self) -> dict[str, object]:
        events = self.store.load_events()
        packet = self._next_packet(events)
        if not packet:
            raise ConflictError("All synthetic source packets are already present.")
        self.store.append(
            "source_added",
            packet,
            round_no=int(packet.get("round") or 1),
            idempotency_key=f"source:{packet.get('packet_id')}",
        )
        result = self.project()
        result["action"] = {"type": "source_added", "message": f"Added {packet.get('label')} to the same case."}
        return result

    def add_custom_source(self, source_type: str, label: str, content: str) -> dict[str, object]:
        allowed = {
            "client_report",
            "practitioner_observation",
            "transcript_excerpt",
            "intervention_retest",
            "followup_message",
            "practitioner_note",
        }
        source_type = str(source_type or "").strip()
        label = " ".join(str(label or "").split())[:120]
        content = str(content or "").strip()
        if source_type not in allowed:
            raise ValidationError("Unsupported source type.")
        if not content or len(content) > 4000:
            raise ValidationError("Source content must contain 1 to 4000 characters.")
        project = self.project()
        round_no = int(project["round"]) + 1
        packet = {
            "packet_id": f"custom-{uuid.uuid4().hex[:10]}",
            "round": round_no,
            "source_type": source_type,
            "label": label or source_type.replace("_", " ").title(),
            "content": content,
            "synthetic_user_entry": True,
        }
        self.store.append("source_added", packet, round_no=round_no)
        result = self.project()
        result["action"] = {"type": "source_added", "message": "Added a new source round to the same synthetic case."}
        return result

    def analyze(self, mode: str) -> dict[str, object]:
        mode = str(mode or "replay").strip().lower()
        if mode not in {"replay", "codex"}:
            raise ValidationError("Analysis mode must be replay or codex.")
        before = self.project()
        evidence = list(before["evidence"])
        if not evidence:
            raise ConflictError("Add source evidence before analysis.")
        input_digest = evidence_digest(evidence)
        latest = before.get("latest_analysis")
        if (
            isinstance(latest, dict)
            and latest.get("input_digest") == input_digest
            and latest.get("mode") == mode
            and not before.get("analysis_stale")
        ):
            before["action"] = {"type": "analysis_reused", "message": "No new evidence; reused the reviewed result without another model call."}
            return before

        events = self.store.load_events()
        if mode == "replay":
            output = run_replay(events, self.fixture)
        else:
            output = self.codex_runner(before, schema_path=self.schema_path)
        payload: dict[str, object] = {
            "mode": mode,
            "input_digest": input_digest,
            "evidence_event_ids": [str(item.get("evidence_id") or "") for item in evidence],
            "output": output,
        }
        round_no = int(before["round"])
        analysis_event = self.store.append(
            "analysis_generated",
            payload,
            round_no=round_no,
            idempotency_key=f"analysis:{mode}:{input_digest}",
        )
        reflection = output.get("reflection") if isinstance(output, dict) else None
        questions = reflection.get("questions") if isinstance(reflection, dict) else []
        for question in questions or []:
            if not isinstance(question, dict) or not question.get("id"):
                continue
            question_payload = dict(question)
            question_payload["analysis_event_id"] = str(analysis_event.get("event_id") or "")
            self.store.append(
                "reflection_question_asked",
                question_payload,
                round_no=round_no,
                idempotency_key=f"question:{question.get('id')}",
            )
        result = self.project()
        result["action"] = {"type": "analysis_generated", "message": f"Generated a new {mode} analysis from the current evidence."}
        return result

    def answer_reflection(self, question_id: str, answer: str) -> dict[str, object]:
        question_id = str(question_id or "").strip()
        answer = str(answer or "").strip()
        if not question_id:
            raise ValidationError("Question id is required.")
        if not answer or len(answer) > 1200:
            raise ValidationError("Answer must contain 1 to 1200 characters.")
        project = self.project()
        question = next(
            (item for item in project["unresolved_questions"] if str(item.get("id") or "") == question_id),
            None,
        )
        if not question:
            raise ConflictError("That reflection question is already answered or no longer active.")
        payload = {
            "question_id": question_id,
            "question_key": str(question.get("key") or ""),
            "answer": answer,
            "explicit_unknown": is_explicit_unknown(answer),
            "provenance": "practitioner_answer",
        }
        self.store.append(
            "reflection_answered",
            payload,
            round_no=int(project["round"]),
            idempotency_key=f"answer:{question_id}",
        )
        result = self.project()
        result["action"] = {
            "type": "reflection_answered",
            "message": "The practitioner answer became evidence; the AI question remained excluded.",
        }
        return result

    def save_reviewed_snapshot(self) -> dict[str, object]:
        project = self.project()
        if not project["can_formal_save"]:
            raise ConflictError(" ".join(str(value) for value in project["save_blockers"]))
        latest_analysis_event_id = str(project["latest_analysis_event_id"])
        latest = project["latest_analysis"]
        payload = {
            "analysis_event_id": latest_analysis_event_id,
            "evidence_digest": evidence_digest(list(project["evidence"])),
            "reviewed_output": latest,
            "save_behavior": "Saved the current normalized analysis; no second analysis was generated.",
        }
        self.store.append(
            "formal_snapshot_saved",
            payload,
            round_no=int(project["round"]),
            idempotency_key=f"snapshot:{latest_analysis_event_id}",
        )
        result = self.project()
        result["action"] = {"type": "snapshot_saved", "message": "Saved the current normalized analysis as a synthetic formal snapshot."}
        return result

    def export_bundle(self) -> dict[str, object]:
        project = self.project()
        return {
            "manifest": {
                "product": "ObserveOS Build Week Edition",
                "synthetic_only": True,
                "contains_real_person_data": False,
                "run_id": str((project.get("run") or {}).get("run_id") or ""),
                "chain_verified": bool((project.get("chain") or {}).get("ok")),
            },
            "case_projection": project,
        }

    @staticmethod
    def runtime_status() -> dict[str, object]:
        return {
            "product": "ObserveOS Build Week Edition",
            "synthetic_only": True,
            "codex": codex_status(),
            "modes": ["replay", "codex"],
        }


__all__ = ["ConflictError", "ObserveOSService", "ValidationError", "load_fixture"]
