from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from observeos.codex_runner import CodexRunError, CodexUnavailable
from observeos.service import ConflictError, ObserveOSService, ValidationError


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
FIXTURE_PATH = ROOT / "fixtures" / "synthetic_multiturn_case.json"
SCHEMA_PATH = ROOT / "schemas" / "codex_analysis.schema.json"
MAX_BODY_BYTES = 64 * 1024


class ObserveOSHandler(BaseHTTPRequestHandler):
    service: ObserveOSService
    server_version = "ObserveOSDemo/0.1"

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def _send_json(self, value: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int) -> None:
        self._send_json({"ok": False, "error": message}, status)

    def _read_json(self) -> dict[str, object]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValidationError("Invalid Content-Length header.") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValidationError("Request body is too large.")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Request body must be a UTF-8 JSON object.") from exc
        if not isinstance(value, dict):
            raise ValidationError("Request body must be a JSON object.")
        return value

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (WEB_ROOT / relative).resolve()
        try:
            candidate.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self._send_error_json("Not found.", HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self._send_error_json("Not found.", HTTPStatus.NOT_FOUND)
            return
        body = candidate.read_bytes()
        media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        if media_type.startswith("text/") or media_type in {"application/javascript", "application/json"}:
            media_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                self._send_json({"ok": True, "status": self.service.runtime_status()})
            elif path == "/api/case":
                self._send_json({"ok": True, "case": self.service.project()})
            elif path == "/api/export":
                self._send_json({"ok": True, "export": self.service.export_bundle()})
            elif path.startswith("/api/"):
                self._send_error_json("API route not found.", HTTPStatus.NOT_FOUND)
            else:
                self._serve_static(path)
        except Exception:
            self._send_error_json("The local demo could not complete this request.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/reset":
                result = self.service.reset()
            elif path == "/api/source/next":
                result = self.service.add_next_source()
            elif path == "/api/source/custom":
                result = self.service.add_custom_source(
                    str(body.get("source_type") or ""),
                    str(body.get("label") or ""),
                    str(body.get("content") or ""),
                )
            elif path == "/api/analyze":
                result = self.service.analyze(str(body.get("mode") or "replay"))
            elif path == "/api/reflection/answer":
                result = self.service.answer_reflection(
                    str(body.get("question_id") or ""),
                    str(body.get("answer") or ""),
                )
            elif path == "/api/formal-save":
                result = self.service.save_reviewed_snapshot()
            else:
                self._send_error_json("API route not found.", HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": True, "case": result})
        except ValidationError as exc:
            self._send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except ConflictError as exc:
            self._send_error_json(str(exc), HTTPStatus.CONFLICT)
        except CodexUnavailable as exc:
            self._send_error_json(str(exc), HTTPStatus.SERVICE_UNAVAILABLE)
        except CodexRunError as exc:
            self._send_error_json(str(exc), HTTPStatus.BAD_GATEWAY)
        except Exception:
            self._send_error_json("The local demo could not complete this request.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"[ObserveOS] {self.address_string()} - {format_string % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the privacy-safe ObserveOS Build Week demo.")
    parser.add_argument("--host", default="127.0.0.1", help="Local bind address. Keep 127.0.0.1 for the demo.")
    parser.add_argument("--port", type=int, default=8765, help="Local HTTP port.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "runtime_data", help="Synthetic runtime data directory.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local demo in the default browser.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This public-safe demo intentionally binds only to a local interface.")
    service = ObserveOSService(
        data_root=args.data_dir,
        fixture_path=FIXTURE_PATH,
        schema_path=SCHEMA_PATH,
    )
    ObserveOSHandler.service = service
    server = ThreadingHTTPServer((args.host, args.port), ObserveOSHandler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"ObserveOS Build Week Edition is running at {url}")
    print("Synthetic data only. Press Ctrl+C to stop.")
    if args.open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ObserveOS.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
