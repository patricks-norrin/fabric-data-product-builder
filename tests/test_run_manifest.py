import json
import pathlib
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))

from run_manifest import append_event


class RunManifestTests(unittest.TestCase):
    def test_appends_structured_events(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = pathlib.Path(temp) / "nested" / "operational_manifest.jsonl"

            append_event(manifest, "livy_created", ["session_id=session-1", "lakehouse=lh_sample"])
            append_event(manifest, "job_finished", ["job_id=job-1", "status=Completed"])

            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["event"] for record in records], ["livy_created", "job_finished"])
            self.assertEqual(records[0]["session_id"], "session-1")
            self.assertEqual(records[1]["status"], "Completed")
            self.assertTrue(all(record["timestamp_utc"].endswith("+00:00") for record in records))

    def test_rejects_unstructured_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "key=value"):
                append_event(pathlib.Path(temp) / "manifest.jsonl", "bad", ["missing-separator"])

    def test_execution_drivers_record_lifecycle_events(self):
        common = (TOOLPACK_ROOT / "scripts" / "fab_common.sh").read_text(encoding="utf-8")
        livy = (
            TOOLPACK_ROOT / "skills" / "nor-livy-session" / "scripts" / "livy_session.sh"
        ).read_text(encoding="utf-8")
        jobs = (
            TOOLPACK_ROOT
            / "skills"
            / "nor-notebook-publish-and-run"
            / "scripts"
            / "run_notebook_job.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("operational_manifest.jsonl", common)
        for event in ("livy_create_requested", "livy_ready", "livy_failed", "livy_deleted", "cells_finished"):
            self.assertIn(f"record_run_event {event}", livy)
        for event in ("job_requested", "job_finished"):
            self.assertIn(f"record_run_event {event}", jobs)


if __name__ == "__main__":
    unittest.main()