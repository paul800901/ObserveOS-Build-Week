from __future__ import annotations

from typing import Any

from .reflection import answered_question_ids, evidence_items, normalize_questions, question_id


def _source_events(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for event in events:
        if event.get("event_type") != "source_added" or not isinstance(event.get("payload"), dict):
            continue
        packet_id = str(event["payload"].get("packet_id") or "")
        if packet_id:
            result[packet_id] = event
    return result


def _answer_events(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for event in events:
        if event.get("event_type") != "reflection_answered" or not isinstance(event.get("payload"), dict):
            continue
        question = str(event["payload"].get("question_id") or "")
        if question:
            result[question] = event
    return result


def _run_step_down_replay(
    events: list[dict[str, object]],
    fixture: dict[str, Any],
) -> dict[str, object]:
    """Deterministic, model-free replay for judges without Codex access."""

    sources = _source_events(events)
    answers = _answer_events(events)
    evidence = evidence_items(events)
    valid_source_ids = {str(item["evidence_id"]) for item in evidence}
    answered_ids = answered_question_ids(events)

    packet_1 = sources.get("packet-01-client-report")
    packet_2 = sources.get("packet-02-practitioner-observation")
    packet_3 = sources.get("packet-03-intervention-retest")
    packet_4 = sources.get("packet-04-followup-message")
    fixture_packet_ids = {
        str(packet.get("packet_id") or "")
        for packet in fixture.get("source_packets", [])
        if isinstance(packet, dict)
    }
    custom_packets = [
        event
        for packet_id, event in sources.items()
        if packet_id not in fixture_packet_ids
    ]
    custom_packets.sort(key=lambda event: int(event.get("sequence") or 0))

    supported: list[dict[str, object]] = []
    inferences: list[dict[str, object]] = []
    unknowns: list[str] = []
    raw_questions: list[dict[str, object]] = []

    if packet_1:
        supported.append(
            {
                "statement": "The client reported reduced step-down stability near the end of a short set.",
                "source_event_ids": [str(packet_1["event_id"])],
            }
        )
    if packet_2:
        supported.extend(
            [
                {
                    "statement": "The practitioner observed slower control after the fourth of six repetitions.",
                    "source_event_ids": [str(packet_2["event_id"])],
                },
                {
                    "statement": "No direct left-right strength comparison was performed.",
                    "source_event_ids": [str(packet_2["event_id"])],
                },
            ]
        )
        inferences.append(
            {
                "statement": "The available material may indicate a task-control or tolerance change, but it does not establish the mechanism.",
                "reason": "Control slowed during later repetitions, while no direct strength comparison or causal test was recorded.",
                "uncertainty": "high",
                "source_event_ids": [str(packet_2["event_id"])],
            }
        )
    if packet_3:
        supported.append(
            {
                "statement": "Three controlled repetitions followed a pacing cue, but the effect was not repeated in a second set.",
                "source_event_ids": [str(packet_3["event_id"])],
            }
        )
        inferences.append(
            {
                "statement": "Pacing may influence immediate task performance; durability is not established.",
                "reason": "The recorded improvement occurred after a cue and was not repeated in another set.",
                "uncertainty": "medium",
                "source_event_ids": [str(packet_3["event_id"])],
            }
        )
    if packet_4:
        supported.append(
            {
                "statement": "The client reported no next-day symptom flare and completed the home task once.",
                "source_event_ids": [str(packet_4["event_id"])],
            }
        )

    for packet in custom_packets:
        payload = packet.get("payload") or {}
        content = " ".join(str(payload.get("content") or "").split())
        if not content:
            continue
        supported.append(
            {
                "statement": f"Additional synthetic source recorded verbatim: {content[:600]}",
                "source_event_ids": [str(packet["event_id"])],
            }
        )

    for answer in answers.values():
        payload = answer.get("payload") or {}
        supported.append(
            {
                "statement": f"Practitioner adjudication: {str(payload.get('answer') or '')}",
                "source_event_ids": [str(answer["event_id"])],
            }
        )

    if packet_1 and not packet_2 and question_id("observed-vs-reported") not in answered_ids:
        unknowns.extend(
            [
                "Whether reduced stability was directly observed in the session.",
                "The mechanism behind the reported change.",
            ]
        )
        raw_questions.append(
            {
                "key": "observed-vs-reported",
                "question": "At this stage, was reduced stability directly observed in the session, or was it only reported by the client?",
                "why": "The answer determines whether the first record can describe an observation or only a client report.",
                "source_anchor": "The client reports that the step-down feels less stable",
                "source_event_ids": [str(packet_1["event_id"])],
                "category": "observation",
                "importance": "required",
            }
        )
    elif packet_2 and question_id("mechanism-established") not in answered_ids:
        unknowns.extend(
            [
                "Why control slowed after the fourth repetition.",
                "Whether a strength difference existed; it was not directly compared.",
            ]
        )
        raw_questions.append(
            {
                "key": "mechanism-established",
                "question": "Did you establish why control slowed after the fourth repetition?",
                "why": "The observation is valid, but its mechanism should remain unknown unless it was actually tested.",
                "source_anchor": "control slowed after the fourth repetition",
                "source_event_ids": [str(packet_2["event_id"])],
                "category": "mainline",
                "importance": "growth",
            }
        )
    elif packet_3 and question_id("retest-durability") not in answered_ids:
        unknowns.append("Whether the cue-related improvement persisted in another set or longer task.")
        raw_questions.append(
            {
                "key": "retest-durability",
                "question": "Was the cue-related improvement repeated in another set?",
                "why": "A repeated retest would change how strongly the immediate response can be interpreted.",
                "source_anchor": "The effect was not tested in a second set",
                "source_event_ids": [str(packet_3["event_id"])],
                "category": "retest",
                "importance": "growth",
            }
        )
    elif packet_4:
        unknowns.append("Longer-duration tolerance remains untested.")

    questions, flags = normalize_questions(
        raw_questions,
        valid_source_ids=valid_source_ids,
        answered_ids=answered_ids,
        max_questions=1,
    )

    if packet_4:
        summary = (
            "Across four rounds, the record supports a client-reported stability change, later observed slowing of control, "
            "a short cue-related improvement, and no reported next-day flare. It does not establish a strength deficit, "
            "a causal mechanism, or longer-duration tolerance."
        )
        next_step = "Preserve the unresolved duration question and use a future, explicitly recorded retest if it becomes relevant."
    elif packet_3:
        summary = (
            "The record now contains a client report, direct observation, and an immediate cue response. "
            "The response was brief and not repeated, so durability remains unknown."
        )
        next_step = "Keep the immediate response separate from any claim about a durable change."
    elif packet_2:
        summary = (
            "The record distinguishes the client report from the practitioner observation. Control slowed during later "
            "repetitions, but no direct strength comparison or causal test was performed."
        )
        next_step = "Retain the observed control change while leaving its mechanism explicitly unresolved."
    else:
        summary = (
            "The current record contains only the client’s report of reduced stability. It does not yet support a direct "
            "practitioner observation or a mechanism."
        )
        next_step = "Clarify whether the change was directly observed before treating it as an examination finding."

    if custom_packets:
        count = len(custom_packets)
        noun = "round" if count == 1 else "rounds"
        summary += (
            f" The record also contains {count} additional synthetic source {noun}; deterministic replay preserves "
            "those statements verbatim without adding a new causal interpretation."
        )

    return {
        "summary": summary,
        "supported_findings": supported,
        "inferences": inferences,
        "unknowns": unknowns,
        "next_step": next_step,
        "reflection": {
            "status": "questions_ready" if questions else "complete",
            "questions": questions,
            "completion_note": "No additional case-anchored question is required for this replay step." if not questions else "",
        },
        "safety_flags": flags,
        "engine": {"mode": "replay", "model": "deterministic synthetic replay"},
    }


def _run_source_conflict_replay(
    events: list[dict[str, object]],
    fixture: dict[str, Any],
) -> dict[str, object]:
    sources = _source_events(events)
    answers = _answer_events(events)
    evidence = evidence_items(events)
    valid_source_ids = {str(item["evidence_id"]) for item in evidence}
    answered_ids = answered_question_ids(events)
    report = sources.get("packet-01-perceived-effort")
    observation = sources.get("packet-02-observed-contacts")

    supported: list[dict[str, object]] = []
    inferences: list[dict[str, object]] = []
    unknowns: list[str] = []
    raw_questions: list[dict[str, object]] = []

    if report:
        supported.append(
            {
                "statement": "The client reported that perceived effort felt unchanged during the task.",
                "source_event_ids": [str(report["event_id"])],
            }
        )
    if observation:
        supported.append(
            {
                "statement": "The practitioner recorded two hand contacts during the final three repetitions.",
                "source_event_ids": [str(observation["event_id"])],
            }
        )
        inferences.append(
            {
                "statement": "The apparent tension may reflect two different dimensions rather than an inaccurate source.",
                "reason": "Perceived effort and observed hand contacts are not interchangeable measurements.",
                "uncertainty": "high",
                "source_event_ids": [str(report["event_id"]), str(observation["event_id"])] if report else [str(observation["event_id"])],
            }
        )

    for answer in answers.values():
        payload = answer.get("payload") or {}
        supported.append(
            {
                "statement": f"Practitioner adjudication: {str(payload.get('answer') or '')}",
                "source_event_ids": [str(answer["event_id"])],
            }
        )

    report_question_id = question_id("report-dimension")
    conflict_question_id = question_id("conflict-interpretation")
    if report and report_question_id not in answered_ids:
        unknowns.append("Whether the client report referred to effort, symptoms, or observed task performance.")
        raw_questions.append(
            {
                "key": "report-dimension",
                "question": "Was the client’s statement about perceived effort, symptoms, or observed task performance?",
                "why": "The report must stay within the dimension the client actually described.",
                "source_anchor": "perceived effort felt unchanged",
                "source_event_ids": [str(report["event_id"])],
                "category": "observation",
                "importance": "required",
            }
        )
    elif observation and conflict_question_id not in answered_ids:
        unknowns.extend(
            [
                "Whether unchanged perceived effort and the observed hand contacts describe the same dimension.",
                "Why the two hand contacts occurred; no cause assessment was recorded.",
            ]
        )
        raw_questions.append(
            {
                "key": "conflict-interpretation",
                "question": "Should the client’s unchanged perceived effort be treated as contradicting the recorded hand contacts, or do they describe different dimensions?",
                "why": "A human decision is required before labeling two differently sourced statements as a contradiction.",
                "source_anchor": "perceived effort felt unchanged; two hand contacts",
                "source_event_ids": [str(report["event_id"]), str(observation["event_id"])] if report else [str(observation["event_id"])],
                "category": "alternative_explanation",
                "importance": "required",
            }
        )
    elif observation:
        unknowns.append("Why the two hand contacts occurred; no cause assessment was recorded.")

    questions, flags = normalize_questions(
        raw_questions,
        valid_source_ids=valid_source_ids,
        answered_ids=answered_ids,
        max_questions=1,
    )
    if observation:
        summary = (
            "The record preserves two different source claims: unchanged perceived effort and two observed hand contacts. "
            "It does not silently merge them, choose one as more truthful, or call them contradictory without practitioner adjudication."
        )
        next_step = "Keep perceived effort and observed performance separate; retain the untested cause as an explicit unknown."
    else:
        summary = (
            "The current record contains only a client report that perceived effort felt unchanged. "
            "It does not establish symptoms or directly observed task performance."
        )
        next_step = "Clarify which dimension the report described before comparing it with any later observation."

    return {
        "summary": summary,
        "supported_findings": supported,
        "inferences": inferences,
        "unknowns": unknowns,
        "next_step": next_step,
        "reflection": {
            "status": "questions_ready" if questions else "complete",
            "questions": questions,
            "completion_note": "The source-role conflict has been adjudicated without collapsing the two claims." if not questions else "",
        },
        "safety_flags": flags,
        "engine": {"mode": "replay", "model": "deterministic synthetic replay · source conflict profile"},
    }


def _run_inference_revision_replay(
    events: list[dict[str, object]],
    fixture: dict[str, Any],
) -> dict[str, object]:
    sources = _source_events(events)
    answers = _answer_events(events)
    evidence = evidence_items(events)
    valid_source_ids = {str(item["evidence_id"]) for item in evidence}
    answered_ids = answered_question_ids(events)
    immediate = sources.get("packet-01-immediate-response")
    later = sources.get("packet-02-later-retest")

    supported: list[dict[str, object]] = []
    inferences: list[dict[str, object]] = []
    unknowns: list[str] = []
    raw_questions: list[dict[str, object]] = []

    if immediate:
        supported.append(
            {
                "statement": "Three smoother repetitions were recorded immediately after a pacing cue; no repeat set was performed at that time.",
                "source_event_ids": [str(immediate["event_id"])],
            }
        )
    if later:
        supported.append(
            {
                "statement": "In a later set under the same cue, the smoother pattern did not repeat and two pauses were recorded.",
                "source_event_ids": [str(later["event_id"])],
            }
        )
        inferences.append(
            {
                "statement": "The later non-replication weakens the earlier inference that the cue reliably improved performance.",
                "reason": "The later set supplied direct counter-evidence under the same recorded cue.",
                "uncertainty": "medium",
                "source_event_ids": [str(immediate["event_id"]), str(later["event_id"])] if immediate else [str(later["event_id"])],
            }
        )
    elif immediate:
        inferences.append(
            {
                "statement": "The pacing cue may have been associated with an immediate performance change, but reliability is not established.",
                "reason": "Only one short, immediate response was recorded and no repeat set was performed.",
                "uncertainty": "high",
                "source_event_ids": [str(immediate["event_id"])],
            }
        )

    for answer in answers.values():
        payload = answer.get("payload") or {}
        supported.append(
            {
                "statement": f"Practitioner adjudication: {str(payload.get('answer') or '')}",
                "source_event_ids": [str(answer["event_id"])],
            }
        )

    repeat_question_id = question_id("repeat-test-recorded")
    change_question_id = question_id("between-set-change")
    if immediate and not later and repeat_question_id not in answered_ids:
        unknowns.append("Whether the immediate response would repeat in another set.")
        raw_questions.append(
            {
                "key": "repeat-test-recorded",
                "question": "Was the immediate response repeated in another set before drawing a conclusion about the cue?",
                "why": "A repeat test determines whether the first response can support more than a tentative inference.",
                "source_anchor": "no repeat set was performed",
                "source_event_ids": [str(immediate["event_id"])],
                "category": "retest",
                "importance": "required",
            }
        )
    elif later and change_question_id not in answered_ids:
        unknowns.append("Why the later set differed; no between-set cause was tested.")
        raw_questions.append(
            {
                "key": "between-set-change",
                "question": "Was any other between-set change recorded that could explain why the smoother pattern did not repeat?",
                "why": "The later evidence weakens the first inference, but it does not by itself establish a cause for the difference.",
                "source_anchor": "the smoother pattern did not repeat",
                "source_event_ids": [str(immediate["event_id"]), str(later["event_id"])] if immediate else [str(later["event_id"])],
                "category": "alternative_explanation",
                "importance": "required",
            }
        )
    elif later:
        unknowns.append("Why the later set differed; no between-set cause was tested.")

    questions, flags = normalize_questions(
        raw_questions,
        valid_source_ids=valid_source_ids,
        answered_ids=answered_ids,
        max_questions=1,
    )
    if later:
        summary = (
            "Later evidence weakens the earlier bounded inference: the immediate smoother pattern did not repeat under the same cue. "
            "Both analyses remain in the append-only ledger, while only the evidence-current review can pass the save gate."
        )
        next_step = "Retain the non-replication and leave its cause unknown unless a recorded comparison addresses it."
    else:
        summary = (
            "The record supports a short immediate response after a pacing cue, but the response was not repeated. "
            "Any claim about a reliable cue effect remains tentative."
        )
        next_step = "Require a recorded repeat test before strengthening the cue-effect inference."

    return {
        "summary": summary,
        "supported_findings": supported,
        "inferences": inferences,
        "unknowns": unknowns,
        "next_step": next_step,
        "reflection": {
            "status": "questions_ready" if questions else "complete",
            "questions": questions,
            "completion_note": "The later evidence has been incorporated and the untested cause remains explicit." if not questions else "",
        },
        "safety_flags": flags,
        "engine": {"mode": "replay", "model": "deterministic synthetic replay · inference revision profile"},
    }


def run_replay(
    events: list[dict[str, object]],
    fixture: dict[str, Any],
) -> dict[str, object]:
    """Deterministic, model-free replay for judges without Codex access."""

    profile = str(fixture.get("replay_profile") or "step_down_control_v1")
    if profile == "source_conflict_v1":
        return _run_source_conflict_replay(events, fixture)
    if profile == "inference_revision_v1":
        return _run_inference_revision_replay(events, fixture)
    return _run_step_down_replay(events, fixture)


__all__ = ["run_replay"]
