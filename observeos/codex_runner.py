from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .reflection import normalize_questions


class CodexUnavailable(RuntimeError):
    pass


class CodexRunError(RuntimeError):
    pass


def _subprocess_environment() -> dict[str, str]:
    """Pass only operating-system and Codex-login context, not arbitrary secrets."""

    allowed = {
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "USERPROFILE",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "CODEX_HOME",
        "CODEX_CA_CERTIFICATE",
        "SSL_CERT_FILE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    }
    result: dict[str, str] = {}
    for key in allowed:
        value = os.environ.get(key)
        if value:
            result[key] = value
    return result


def _creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _candidate_executables() -> list[str]:
    candidates: list[str] = []
    configured = os.environ.get("OBSERVEOS_CODEX_EXE", "").strip()
    if configured:
        candidates.append(configured)

    extension_root = Path.home() / ".vscode" / "extensions"
    if extension_root.exists():
        extension_candidates = list(extension_root.glob("openai.chatgpt-*/bin/windows-x86_64/codex.exe"))
        extension_candidates.extend(extension_root.glob("openai.chatgpt-*/bin/*/codex.exe"))
        extension_candidates = [path for path in extension_candidates if path.is_file()]
        extension_candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        candidates.extend(str(path) for path in extension_candidates)

    discovered = shutil.which("codex")
    if discovered:
        candidates.append(discovered)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _probe(candidate: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [candidate, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            env=_subprocess_environment(),
            creationflags=_creation_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    version = (completed.stdout or completed.stderr or "").strip().splitlines()
    return completed.returncode == 0, (version[0][:160] if version else "")


def find_codex_executable() -> tuple[str | None, str]:
    for candidate in _candidate_executables():
        ok, version = _probe(candidate)
        if ok:
            return candidate, version
    return None, ""


def _model_candidates() -> list[str]:
    configured = os.environ.get("OBSERVEOS_CODEX_MODEL", "").strip()
    if configured:
        return [configured]
    # Build Week accounts may expose the GPT-5.6 family through either the
    # product runtime slug or the public family slug. Try the locked product
    # route first, then the official family example.
    return ["gpt-5.6-luna", "gpt-5.6"]


def _login_status(executable: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [executable, "login", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            env=_subprocess_environment(),
            creationflags=_creation_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "unavailable"
    message = f"{completed.stdout}\n{completed.stderr}".strip().lower()
    method = "chatgpt" if "chatgpt" in message else ("api" if "api" in message else "signed-in")
    return completed.returncode == 0 and "logged in" in message, method


def codex_status() -> dict[str, object]:
    executable, version = find_codex_executable()
    models = _model_candidates()
    model = models[0]
    effort = os.environ.get("OBSERVEOS_REASONING_EFFORT", "medium").strip().lower() or "medium"
    if not executable:
        return {
            "available": False,
            "logged_in": False,
            "login_method": "unavailable",
            "version": "",
            "model": model,
            "model_candidates": models,
            "reasoning_effort": effort,
        }
    logged_in, method = _login_status(executable)
    return {
        "available": True,
        "logged_in": logged_in,
        "login_method": method,
        "version": version,
        "model": model,
        "model_candidates": models,
        "reasoning_effort": effort,
    }


def _trim(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _validate_source_ids(value: object, valid_ids: set[str], label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise CodexRunError(f"{label} did not cite evidence event ids")
    result = [str(item) for item in value]
    invalid = [item for item in result if item not in valid_ids]
    if invalid:
        raise CodexRunError(f"{label} cited an unknown evidence event id")
    return result[:6]


def _normalize_model_output(raw: object, projection: dict[str, object]) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise CodexRunError("Codex did not return a JSON object")
    evidence = projection.get("evidence")
    if not isinstance(evidence, list):
        raise CodexRunError("evidence projection is invalid")
    valid_ids = {str(item.get("evidence_id") or "") for item in evidence if isinstance(item, dict)} - {""}
    answered = set(str(value) for value in (projection.get("answered_question_ids") or []))
    summary = _trim(raw.get("summary"), 1800)
    next_step = _trim(raw.get("next_step"), 900)
    if not summary or not next_step:
        raise CodexRunError("Codex response omitted the summary or next step")

    supported: list[dict[str, object]] = []
    for index, item in enumerate(raw.get("supported_findings") or [], start=1):
        if not isinstance(item, dict):
            raise CodexRunError(f"supported finding {index} was invalid")
        statement = _trim(item.get("statement"), 600)
        if not statement:
            raise CodexRunError(f"supported finding {index} had no statement")
        supported.append(
            {
                "statement": statement,
                "source_event_ids": _validate_source_ids(
                    item.get("source_event_ids"), valid_ids, f"supported finding {index}"
                ),
            }
        )

    inferences: list[dict[str, object]] = []
    for index, item in enumerate(raw.get("inferences") or [], start=1):
        if not isinstance(item, dict):
            raise CodexRunError(f"inference {index} was invalid")
        statement = _trim(item.get("statement"), 600)
        reason = _trim(item.get("reason"), 600)
        uncertainty = str(item.get("uncertainty") or "high")
        if uncertainty not in {"low", "medium", "high"}:
            uncertainty = "high"
        if not statement or not reason:
            raise CodexRunError(f"inference {index} was incomplete")
        inferences.append(
            {
                "statement": statement,
                "reason": reason,
                "uncertainty": uncertainty,
                "source_event_ids": _validate_source_ids(
                    item.get("source_event_ids"), valid_ids, f"inference {index}"
                ),
            }
        )

    unknowns = [_trim(value, 500) for value in (raw.get("unknowns") or [])]
    unknowns = [value for value in unknowns if value][:8]
    reflection = raw.get("reflection") if isinstance(raw.get("reflection"), dict) else {}
    questions, flags = normalize_questions(
        reflection.get("questions") or [],
        valid_source_ids=valid_ids,
        answered_ids=answered,
        max_questions=1,
    )
    completion_note = _trim(reflection.get("completion_note"), 600)
    return {
        "summary": summary,
        "supported_findings": supported[:8],
        "inferences": inferences[:6],
        "unknowns": unknowns,
        "next_step": next_step,
        "reflection": {
            "status": "questions_ready" if questions else "complete",
            "questions": questions,
            "completion_note": completion_note,
        },
        "safety_flags": flags,
    }


def _build_prompt(projection: dict[str, object]) -> str:
    evidence = projection.get("evidence") or []
    answered = projection.get("answered_question_ids") or []
    return f"""You are the evidence-governance layer of a synthetic practitioner workflow demo.

This is not medical advice and not a real case. Use only the evidence JSON below. Do not browse, call tools, inspect files, or add outside knowledge.

Rules:
1. Separate directly supported findings from bounded inference.
2. Every finding, inference, and reflection question must cite one or more exact evidence_id values from the input.
3. An AI question is never case evidence. Practitioner answers in the evidence list may be used with their provenance.
4. "Unknown", "not observed", and "not tested" are valid outcomes. Do not complete a fluent story when evidence is missing.
5. Do not diagnose, prescribe, or claim clinical efficacy.
6. Ask at most one case-anchored, non-leading reflection question. Mark it required only when the current record would otherwise misstate a source or cross a safety boundary. Otherwise use growth.
7. Do not repeat any answered question id listed below.
8. Write all response fields in clear English for the international judging demo.
9. Return only the JSON object required by the supplied schema.

Answered question ids:
{json.dumps(answered, ensure_ascii=False)}

Evidence JSON:
{json.dumps(evidence, ensure_ascii=False, indent=2)}
"""


def run_codex_analysis(
    projection: dict[str, object],
    *,
    schema_path: Path,
    timeout_seconds: int = 240,
) -> dict[str, object]:
    executable, version = find_codex_executable()
    if not executable:
        raise CodexUnavailable("Codex CLI is not executable on this machine")
    logged_in, method = _login_status(executable)
    if not logged_in:
        raise CodexUnavailable("Codex CLI is available but not signed in")

    models = _model_candidates()
    effort = os.environ.get("OBSERVEOS_REASONING_EFFORT", "medium").strip().lower() or "medium"
    if effort not in {"none", "low", "medium", "high", "xhigh", "max", "ultra"}:
        raise CodexRunError("OBSERVEOS_REASONING_EFFORT is invalid")
    prompt = _build_prompt(projection)
    started = time.perf_counter()

    selected_model = ""
    last_safe_error = ""
    with tempfile.TemporaryDirectory(prefix="observeos_codex_") as working_directory:
        output_path = Path(working_directory) / "analysis.json"
        for index, model in enumerate(models):
            output_path.unlink(missing_ok=True)
            command = [
                executable,
                "exec",
                "-m",
                model,
                "-c",
                f'model_reasoning_effort="{effort}"',
                "-s",
                "read-only",
                "-C",
                working_directory,
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--color",
                "never",
                "--output-schema",
                str(Path(schema_path).resolve()),
                "--output-last-message",
                str(output_path),
                "-",
            ]
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    env=_subprocess_environment(),
                    creationflags=_creation_flags(),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CodexRunError("Codex analysis timed out") from exc
            except OSError as exc:
                raise CodexRunError("Codex analysis could not start") from exc
            if completed.returncode == 0:
                selected_model = model
                break
            last_safe_error = " ".join((completed.stderr or "").split())[-500:]
            unsupported = "model is not supported" in last_safe_error.lower()
            if not unsupported or index == len(models) - 1:
                raise CodexRunError(f"Codex analysis failed: {last_safe_error or 'unknown error'}")
        if not selected_model:
            raise CodexRunError(f"Codex analysis failed: {last_safe_error or 'no compatible GPT-5.6 model'}")
        if not output_path.exists():
            raise CodexRunError("Codex completed without an output file")
        try:
            raw = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CodexRunError("Codex output was not valid JSON") from exc

    normalized = _normalize_model_output(raw, projection)
    normalized["engine"] = {
        "mode": "codex",
        "model": selected_model,
        "reasoning_effort": effort,
        "login_method": method,
        "cli_version": version,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    return normalized


__all__ = [
    "CodexRunError",
    "CodexUnavailable",
    "codex_status",
    "find_codex_executable",
    "run_codex_analysis",
]
