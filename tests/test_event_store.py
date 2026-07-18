from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from observeos.event_store import EventStore


CASE = {
    "case_id": "DEMO-CASE-001",
    "display_name": "Synthetic Case",
    "scenario": "Test scenario",
}
PACKET = {
    "packet_id": "packet-01",
    "round": 1,
    "source_type": "client_report",
    "label": "Client report",
    "content": "Entirely fictional source.",
}


class EventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = EventStore(
            Path(self.temp.name),
            clock=lambda: datetime(2026, 7, 18, 0, 0, tzinfo=timezone.utc),
        )
        self.store.reset(CASE, PACKET)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reset_creates_case_and_first_source_as_append_only_events(self) -> None:
        events = self.store.load_events()
        self.assertEqual(["case_created", "source_added"], [event["event_type"] for event in events])
        self.assertEqual([1, 2], [event["sequence"] for event in events])
        self.assertEqual("GENESIS", events[0]["previous_hash"])
        self.assertEqual(events[0]["event_hash"], events[1]["previous_hash"])

    def test_idempotency_key_does_not_duplicate_an_event(self) -> None:
        first = self.store.append(
            "analysis_generated",
            {"output": "first"},
            round_no=1,
            idempotency_key="analysis:one",
        )
        second = self.store.append(
            "analysis_generated",
            {"output": "different payload must not replace first"},
            round_no=1,
            idempotency_key="analysis:one",
        )
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(3, len(self.store.load_events()))
        self.assertEqual("first", self.store.load_events()[-1]["payload"]["output"])

    def test_hash_chain_verifies_after_multiple_rounds(self) -> None:
        self.store.append("source_added", {**PACKET, "packet_id": "packet-02", "round": 2}, round_no=2)
        result = self.store.verify_chain()
        self.assertTrue(result["ok"])
        self.assertEqual(3, result["event_count"])

    def test_hash_chain_detects_tampering(self) -> None:
        info = self.store.active_info()
        path = Path(self.temp.name) / "runs" / info["run_id"] / "events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[1])
        event["payload"]["content"] = "tampered"
        lines[1] = json.dumps(event, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertFalse(self.store.verify_chain()["ok"])

    def test_new_reset_preserves_the_earlier_synthetic_run(self) -> None:
        first_run = str(self.store.active_info()["run_id"])
        first_path = Path(self.temp.name) / "runs" / first_run / "events.jsonl"
        self.store.reset(CASE, PACKET)
        second_run = str(self.store.active_info()["run_id"])
        self.assertNotEqual(first_run, second_run)
        self.assertTrue(first_path.exists())
        self.assertEqual(2, len(list((Path(self.temp.name) / "runs").iterdir())))

    def test_invalid_run_id_cannot_escape_the_store(self) -> None:
        with self.assertRaises(ValueError):
            self.store.load_events("../outside")


if __name__ == "__main__":
    unittest.main()
