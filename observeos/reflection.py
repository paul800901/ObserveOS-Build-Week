from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable


ALLOWED_CATEGORIES = {
    "mainline",
    "observation",
    "intervention_effect",
    "retest",
    "followup",
    "safety",
    "alternative_explanation",
}
ALLOWED_IMPORTANCE = {"required", "growth"}
GENERIC_QUESTION_MARKERS = {
    "anything else to add",
    "any other information",
    "any other details",
    "還有什麼要補充",
    "是否還有其他補充",
    "有沒有其他補充",
}
LEADING_QUESTION_MARKERS = {
    "already proves",
    "definitely means",
    "must be caused by",
    "obviously caused by",
    "已經證明",
    "確定就是",
    "一定就是",
    "唯一原因就是",
}
UNKNOWN_MARKERS = {
    "i don't know",
    "i do not know",
    "not observed",
    "not tested",
    "not compared",
    "cannot remember",
    "can't remember",
    "unknown",
    "不知道",
    "不確定",
    "沒有觀察",
    "沒有測試",
    "沒有比較",
    "想不起來",
}


def question_id(seed: str) -> str:
    digest = hashlib.sha256(seed.strip().encode("utf-8")).hexdigest()[:10].upper()
    return f"CR-{digest}"


def is_explicit_unknown(answer: str) -> bool:
    compact = re.sub(r"\s+", " ", str(answer or "")).strip().lower()
    return any(marker in compact for marker in UNKNOWN_MARKERS)


def answered_question_ids(events: Iterable[dict[str, object]]) -> set[str]:
    return {
        str((event.get("payload") or {}).get("question_id") or "")
        for event in events
        if event.get("event_type") == "reflection_answered" and isinstance(event.get("payload"), dict)
    } - {""}


def normalize_questions(
    raw_questions: object,
    *,
    valid_source_ids: set[str],
    answered_ids: set[str] | None = None,
    max_questions: int = 1,
) -> tuple[list[dict[str, object]], list[str]]:
    answered_ids = answered_ids or set()
    questions: list[dict[str, object]] = []
    flags: list[str] = []
    seen: set[str] = set()
    if not isinstance(raw_questions, list):
        return [], ["questions payload was not an array"]

    for index, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            flags.append(f"question {index} was not an object")
            continue
        question = re.sub(r"\s+", " ", str(item.get("question") or "")).strip()[:360]
        why = re.sub(r"\s+", " ", str(item.get("why") or "")).strip()[:500]
        source_anchor = re.sub(r"\s+", " ", str(item.get("source_anchor") or "")).strip()[:360]
        lowered = question.lower()
        if not question:
            flags.append(f"question {index} had no text")
            continue
        if any(marker in lowered for marker in GENERIC_QUESTION_MARKERS):
            flags.append(f"question {index} was too generic")
            continue
        if any(marker in lowered for marker in LEADING_QUESTION_MARKERS):
            flags.append(f"question {index} contained a leading conclusion")
            continue
        if not source_anchor:
            flags.append(f"question {index} had no case anchor")
            continue
        raw_source_ids = item.get("source_event_ids")
        if not isinstance(raw_source_ids, list):
            flags.append(f"question {index} had no source event ids")
            continue
        source_ids = [str(value) for value in raw_source_ids if str(value) in valid_source_ids]
        if not source_ids:
            flags.append(f"question {index} was not anchored to valid evidence")
            continue
        seed = str(item.get("key") or question)
        normalized_id = question_id(seed)
        if normalized_id in answered_ids or normalized_id in seen:
            continue
        seen.add(normalized_id)
        category = str(item.get("category") or "mainline")
        if category not in ALLOWED_CATEGORIES:
            category = "mainline"
        importance = str(item.get("importance") or "growth")
        if importance not in ALLOWED_IMPORTANCE:
            importance = "growth"
        questions.append(
            {
                "id": normalized_id,
                "key": str(item.get("key") or ""),
                "question": question,
                "why": why,
                "source_anchor": source_anchor,
                "source_event_ids": source_ids,
                "category": category,
                "importance": importance,
            }
        )

    questions.sort(key=lambda value: 0 if value["importance"] == "required" else 1)
    return questions[: max(0, max_questions)], flags


def evidence_items(events: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Project only human/source evidence; AI questions are intentionally absent."""

    projected: list[dict[str, object]] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if event.get("event_type") == "source_added":
            projected.append(
                {
                    "evidence_id": str(event.get("event_id") or ""),
                    "event_sequence": int(event.get("sequence") or 0),
                    "round": int(event.get("round") or 0),
                    "provenance": str(payload.get("source_type") or "source"),
                    "label": str(payload.get("label") or "Source material"),
                    "content": str(payload.get("content") or ""),
                    "explicit_unknown": False,
                }
            )
        elif event.get("event_type") == "reflection_answered":
            projected.append(
                {
                    "evidence_id": str(event.get("event_id") or ""),
                    "event_sequence": int(event.get("sequence") or 0),
                    "round": int(event.get("round") or 0),
                    "provenance": "practitioner_answer",
                    "label": "Practitioner adjudication",
                    "content": str(payload.get("answer") or ""),
                    "question_id": str(payload.get("question_id") or ""),
                    "explicit_unknown": bool(payload.get("explicit_unknown")),
                }
            )
    return projected


def excluded_question_items(events: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for event in events:
        if event.get("event_type") != "reflection_question_asked":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "event_id": str(event.get("event_id") or ""),
                "question_id": str(payload.get("id") or ""),
                "question": str(payload.get("question") or ""),
                "exclusion_reason": "AI recall prompts are interaction history, not case evidence.",
            }
        )
    return items


def evidence_digest(items: list[dict[str, object]]) -> str:
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "answered_question_ids",
    "evidence_digest",
    "evidence_items",
    "excluded_question_items",
    "is_explicit_unknown",
    "normalize_questions",
    "question_id",
]
