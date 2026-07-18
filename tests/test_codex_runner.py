from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from observeos import codex_runner


ROOT = Path(__file__).resolve().parents[1]


def projection() -> dict[str, object]:
    return {
        "evidence": [
            {
                "evidence_id": "EVT-SOURCE-1",
                "provenance": "client_report",
                "content": "Synthetic report only.",
            }
        ],
        "answered_question_ids": [],
        "excluded_questions": [{"question": "This must not enter the prompt."}],
    }


def model_output(source_id: str = "EVT-SOURCE-1") -> dict[str, object]:
    return {
        "summary": "The record currently contains a client report only.",
        "supported_findings": [
            {"statement": "A change was reported.", "source_event_ids": [source_id]}
        ],
        "inferences": [
            {
                "statement": "The mechanism is unresolved.",
                "reason": "No observation or test was provided.",
                "uncertainty": "high",
                "source_event_ids": [source_id],
            }
        ],
        "unknowns": ["Direct observation."],
        "next_step": "Keep the record source-bounded.",
        "reflection": {
            "status": "complete",
            "questions": [],
            "completion_note": "No question needed.",
        },
    }


class CodexRunnerTests(unittest.TestCase):
    def test_subprocess_environment_drops_arbitrary_secret_variables(self) -> None:
        with patch.dict(os.environ, {"UNRELATED_SECRET_TOKEN": "not-for-child", "SystemRoot": "C:\\Windows"}, clear=False):
            environment = codex_runner._subprocess_environment()
        self.assertNotIn("UNRELATED_SECRET_TOKEN", environment)
        self.assertEqual("C:\\Windows", environment["SystemRoot"])

    def test_prompt_contains_evidence_but_not_excluded_ai_question(self) -> None:
        prompt = codex_runner._build_prompt(projection())
        self.assertIn("Synthetic report only", prompt)
        self.assertNotIn("This must not enter the prompt", prompt)
        self.assertIn("An AI question is never case evidence", prompt)

    def test_invalid_source_reference_fails_the_hard_gate(self) -> None:
        with self.assertRaisesRegex(codex_runner.CodexRunError, "unknown evidence"):
            codex_runner._normalize_model_output(model_output("EVT-NOT-PROVIDED"), projection())

    def test_live_output_is_normalized_to_source_bounded_shape(self) -> None:
        normalized = codex_runner._normalize_model_output(model_output(), projection())
        self.assertEqual("The record currently contains a client report only.", normalized["summary"])
        self.assertEqual(["EVT-SOURCE-1"], normalized["supported_findings"][0]["source_event_ids"])
        self.assertEqual("complete", normalized["reflection"]["status"])

    def test_codex_command_is_ephemeral_read_only_and_schema_bound(self) -> None:
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            output_index = command.index("--output-last-message") + 1
            Path(command[output_index]).write_text(json.dumps(model_output()), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with (
            patch.object(codex_runner, "find_codex_executable", return_value=("codex-test", "codex-cli test")),
            patch.object(codex_runner, "_login_status", return_value=(True, "chatgpt")),
            patch.object(codex_runner.subprocess, "run", side_effect=fake_run),
            patch.dict(os.environ, {"OBSERVEOS_CODEX_MODEL": "gpt-5.6", "OBSERVEOS_REASONING_EFFORT": "medium"}),
        ):
            result = codex_runner.run_codex_analysis(
                projection(),
                schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
            )

        command = captured["command"]
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--output-schema", command)
        self.assertEqual("read-only", command[command.index("-s") + 1])
        self.assertEqual("gpt-5.6", command[command.index("-m") + 1])
        self.assertEqual("codex", result["engine"]["mode"])
        self.assertEqual("chatgpt", result["engine"]["login_method"])

    def test_missing_executable_reports_unavailable_without_fallback_claim(self) -> None:
        with patch.object(codex_runner, "find_codex_executable", return_value=(None, "")):
            with self.assertRaises(codex_runner.CodexUnavailable):
                codex_runner.run_codex_analysis(
                    projection(),
                    schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
                )

    def test_model_slug_falls_back_only_when_account_rejects_the_first_slug(self) -> None:
        attempted = []

        def fake_run(command, **kwargs):
            model = command[command.index("-m") + 1]
            attempted.append(model)
            if model == "gpt-5.6-luna":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="model is not supported")
            output_index = command.index("--output-last-message") + 1
            Path(command[output_index]).write_text(json.dumps(model_output()), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with (
            patch.object(codex_runner, "find_codex_executable", return_value=("codex-test", "codex-cli test")),
            patch.object(codex_runner, "_login_status", return_value=(True, "chatgpt")),
            patch.object(codex_runner.subprocess, "run", side_effect=fake_run),
            patch.dict(os.environ, {"OBSERVEOS_REASONING_EFFORT": "medium"}, clear=True),
        ):
            result = codex_runner.run_codex_analysis(
                projection(),
                schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
            )

        self.assertEqual(["gpt-5.6-luna", "gpt-5.6"], attempted)
        self.assertEqual("gpt-5.6", result["engine"]["model"])


if __name__ == "__main__":
    unittest.main()
