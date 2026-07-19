from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import app
from observeos.service import ObserveOSService


ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(app.ObserveOSHandler):
    def log_message(self, format_string: str, *args: object) -> None:
        return


class HttpContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        QuietHandler.service = ObserveOSService(
            data_root=Path(self.temp.name),
            fixture_path=ROOT / "fixtures" / "synthetic_multiturn_case.json",
            schema_path=ROOT / "schemas" / "codex_analysis.schema.json",
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def _get(self, path: str) -> tuple[int, dict]:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_status_and_case_endpoints_are_local_json(self) -> None:
        status, payload = self._get("/api/status")
        self.assertEqual(200, status)
        self.assertTrue(payload["status"]["synthetic_only"])
        status, payload = self._get("/api/case")
        self.assertEqual(200, status)
        self.assertEqual("DEMO-CASE-001", payload["case"]["case"]["case_id"])

    def test_replay_analysis_endpoint_returns_required_question(self) -> None:
        status, payload = self._post("/api/analyze", {"mode": "replay"})
        self.assertEqual(200, status)
        self.assertEqual(1, payload["case"]["required_unresolved_count"])

    def test_invalid_custom_source_returns_bounded_client_error(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/source/custom",
            data=json.dumps({"source_type": "private_file", "content": "x"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(400, context.exception.code)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertFalse(payload["ok"])

    def test_static_response_has_security_headers(self) -> None:
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            self.assertEqual("DENY", response.headers["X-Frame-Options"])
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            body = response.read()
            self.assertIn(b"Evidence before eloquence", body)
            self.assertIn(b"90-second judge tour", body)
            self.assertIn(b"run_governance_corpus.py", body)

    def test_api_export_declares_no_real_person_data(self) -> None:
        _, payload = self._get("/api/export")
        manifest = payload["export"]["manifest"]
        self.assertFalse(manifest["contains_real_person_data"])
        self.assertTrue(manifest["chain_verified"])


if __name__ == "__main__":
    unittest.main()
