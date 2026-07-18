from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


JsonObject = dict[str, object]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class EventStore:
    """Small append-only JSONL store for the synthetic Build Week demo.

    Each demo reset creates a new run. Older runs are preserved. Events inside a
    run are chained by hash so the demo can verify that no earlier event was
    rewritten while later evidence arrived.
    """

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.runs_root = self.root / "runs"
        self.active_path = self.root / "active_run.json"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def active_info(self) -> JsonObject | None:
        if not self.active_path.exists():
            return None
        value = json.loads(self.active_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not value.get("run_id"):
            raise ValueError("active run metadata is invalid")
        return value

    def _events_path(self, run_id: str) -> Path:
        if not run_id or any(token in run_id for token in ("/", "\\", "..")):
            raise ValueError("invalid run id")
        return self.runs_root / run_id / "events.jsonl"

    def _write_active(self, value: JsonObject) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.active_path.with_name(f".{self.active_path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.active_path)

    def reset(self, case: JsonObject, first_packet: JsonObject) -> JsonObject:
        """Create a fresh demo run without deleting any earlier synthetic run."""

        with self._lock:
            stamp = self.clock().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_id = f"run-{stamp}-{uuid.uuid4().hex[:8]}"
            case_id = str(case.get("case_id") or "DEMO-CASE-001")
            path = self._events_path(run_id)
            path.parent.mkdir(parents=True, exist_ok=False)
            path.touch()
            active = {
                "run_id": run_id,
                "case_id": case_id,
                "created_at": self._now(),
                "synthetic_only": True,
            }
            self._write_active(active)
            self.append("case_created", dict(case), round_no=0, idempotency_key="case-created")
            self.append(
                "source_added",
                dict(first_packet),
                round_no=int(first_packet.get("round") or 1),
                idempotency_key=f"source:{first_packet.get('packet_id')}",
            )
            return active

    def load_events(self, run_id: str | None = None) -> list[JsonObject]:
        info = self.active_info() if run_id is None else {"run_id": run_id}
        if not info:
            return []
        path = self._events_path(str(info["run_id"]))
        if not path.exists():
            return []
        events: list[JsonObject] = []
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError(f"event line {line_number} is not an object")
            events.append(value)
        return events

    def append(
        self,
        event_type: str,
        payload: JsonObject,
        *,
        round_no: int,
        idempotency_key: str | None = None,
    ) -> JsonObject:
        if not event_type or not isinstance(payload, dict):
            raise ValueError("event type and object payload are required")
        with self._lock:
            active = self.active_info()
            if not active:
                raise RuntimeError("no active demo run")
            events = self.load_events(str(active["run_id"]))
            if idempotency_key:
                for existing in events:
                    if existing.get("idempotency_key") == idempotency_key:
                        return existing
            sequence = len(events) + 1
            previous_hash = str(events[-1].get("event_hash") or "") if events else "GENESIS"
            body: JsonObject = {
                "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
                "event_type": event_type,
                "run_id": str(active["run_id"]),
                "case_id": str(active["case_id"]),
                "sequence": sequence,
                "round": max(0, int(round_no)),
                "timestamp": self._now(),
                "idempotency_key": idempotency_key or "",
                "payload": payload,
                "previous_hash": previous_hash,
            }
            body["event_hash"] = _sha256(body)
            path = self._events_path(str(active["run_id"]))
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return body

    def verify_chain(self, run_id: str | None = None) -> JsonObject:
        events = self.load_events(run_id)
        previous_hash = "GENESIS"
        for expected_sequence, event in enumerate(events, start=1):
            if int(event.get("sequence") or 0) != expected_sequence:
                return {"ok": False, "error": f"sequence mismatch at {expected_sequence}"}
            if str(event.get("previous_hash") or "") != previous_hash:
                return {"ok": False, "error": f"previous hash mismatch at {expected_sequence}"}
            claimed_hash = str(event.get("event_hash") or "")
            body = dict(event)
            body.pop("event_hash", None)
            if _sha256(body) != claimed_hash:
                return {"ok": False, "error": f"event hash mismatch at {expected_sequence}"}
            previous_hash = claimed_hash
        return {"ok": True, "event_count": len(events), "head_hash": previous_hash}


__all__ = ["EventStore"]
