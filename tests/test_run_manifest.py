import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))

from run_manifest import append_event, latest_jobs

RUN_JOB = TOOLPACK_ROOT / "skills" / "nor-notebook-publish-and-run" / "scripts" / "run_notebook_job.sh"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
JOB_ID = "44444444-4444-4444-4444-444444444444"


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
        for event in ("job_requested", "job_started", "job_status", "job_finished", "job_wait_timeout"):
            self.assertIn(f"record_run_event {event}", jobs)


    def test_latest_jobs_keeps_most_recent_start_per_notebook(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = pathlib.Path(temp) / "manifest.jsonl"
            append_event(manifest, "job_started", ["item=/ws.Workspace/dp.Folder/nb_a.Notebook", "job_id=j1"])
            append_event(manifest, "job_started", ["item=/ws.Workspace/dp.Folder/nb_b.Notebook", "job_id=j2"])
            append_event(manifest, "job_status", ["item=/ws.Workspace/dp.Folder/nb_a.Notebook", "job_id=j1"])
            append_event(manifest, "job_started", ["item=/ws.Workspace/dp.Folder/nb_a.Notebook", "job_id=j3"])

            jobs = latest_jobs(manifest)

            self.assertEqual([(item.split("/")[-1], job["job_id"]) for item, job in jobs.items()],
                             [("nb_b.Notebook", "j2"), ("nb_a.Notebook", "j3")])


class RunNotebookJobTests(unittest.TestCase):
    """Drive run_notebook_job.sh against a fake fab that returns fab 1.9 `--json` envelopes."""

    def _project(self, temp, statuses, failure="", start_output=None):
        project = pathlib.Path(temp)
        (project / "configuration").mkdir()
        (project / "configuration" / "fabric_targets.json").write_text(json.dumps({
            "active_target": "dev",
            "default_workspace": "ws_alpha",
            "targets": {"dev": {"workspaces": {"ws_alpha": {"workspace_name": "ws_alpha_dev"}}}},
        }), encoding="utf-8")
        fake_bin = project / "fake-bin"
        fake_bin.mkdir()
        (project / "statuses").write_text("\n".join(statuses) + "\n", encoding="utf-8")
        (project / "start.json").write_text(start_output or self._envelope({"id": JOB_ID}), encoding="utf-8")
        (project / "failure").write_text(failure, encoding="utf-8")
        (fake_bin / "fab").write_text(
            "#!/usr/bin/env bash\n"
            'case "$*" in\n'
            f'  get*) echo "{WORKSPACE_ID}";;\n'
            '  "job start"*--json*) cat "$FAKE/start.json";;\n'
            '  "job run-status"*--json*)\n'
            '    status=$(head -1 "$FAKE/statuses"); [ "$(wc -l < "$FAKE/statuses")" -gt 1 ] && sed -i 1d "$FAKE/statuses"\n'
            '    python3 -c "import json,sys; f=sys.argv[2]; print(json.dumps({\'status\': \'Success\', \'result\': {\'data\': '
            '[{\'id\': sys.argv[3], \'status\': sys.argv[1], \'startTimeUtc\': \'2026-11-03T10:00:00\', '
            '\'endTimeUtc\': None, \'failureReason\': {\'message\': f} if f else None}]}}))" '
            '"$status" "$(cat "$FAKE/failure")" "${@: -2:1}";;\n'
            '  *) echo "unexpected fab call: $*" >&2; exit 1;;\n'
            'esac\n',
            encoding="utf-8",
        )
        (fake_bin / "fab").chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        environment["FAKE"] = str(project)
        return project, environment

    @staticmethod
    def _envelope(job):
        return json.dumps({"status": "Success", "command": "job", "result": {"data": [job]}})

    def _run(self, project, environment, *args):
        return subprocess.run(
            ["bash", str(RUN_JOB), *args, "--project-root", str(project)],
            cwd=project, env=environment, capture_output=True, text=True, timeout=60,
        )

    def _events(self, project):
        manifest = next(project.glob(".scratch/*/operational_manifest.jsonl"))
        return [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]

    def test_run_reports_progress_and_completes(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["NotStarted", "InProgress", "InProgress", "Completed"])

            result = self._run(project, environment, "run", "dp", "nb_extract_dp", "--poll", "1")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(JOB_ID, result.stdout)
            self.assertGreaterEqual(result.stdout.count(" InProgress "), 2)
            events = self._events(project)
            self.assertEqual([e["status"] for e in events if e["event"] == "job_status"],
                             ["NotStarted", "InProgress", "Completed"])
            self.assertEqual(events[-1]["event"], "job_finished")
            self.assertEqual(events[-1]["status"], "Completed")

    def test_run_surfaces_failure_reason_and_next_step(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["InProgress", "Failed"], failure="Spark session cancelled")

            result = self._run(project, environment, "run", "dp", "nb_cdc_dp", "--poll", "1")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Spark session cancelled", result.stdout)
            self.assertIn("nor-spark-diagnostics", result.stdout)
            self.assertEqual(self._events(project)[-1]["failure_reason"], "Spark session cancelled")

    def test_cancelled_job_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["Cancelled"])

            result = self._run(project, environment, "run", "dp", "nb_cdc_dp", "--poll", "1")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_start_without_job_id_fails_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as temp:
            error = json.dumps({"status": "Failure", "result": {"message": "ItemNotFound"}})
            project, environment = self._project(temp, ["InProgress"], start_output=error)

            result = self._run(project, environment, "start", "dp", "nb_extract_dp")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ItemNotFound", result.stdout)
            self.assertNotIn("job_started", [e["event"] for e in self._events(project)])

    def test_wait_timeout_leaves_job_running_and_resumes_from_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["InProgress", "InProgress", "Completed"])

            timed_out = self._run(project, environment, "run", "dp", "nb_extract_dp", "--poll", "1", "--timeout", "0")
            resumed = self._run(project, environment, "wait", "dp", "nb_extract_dp", "--poll", "1")

            self.assertEqual(timed_out.returncode, 124, timed_out.stdout + timed_out.stderr)
            self.assertIn(f"--job-id {JOB_ID}", timed_out.stdout)
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            self.assertIn(JOB_ID, resumed.stdout)

    def test_pipeline_runs_as_datapipeline_item(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["InProgress", "Failed"], failure="Activity nb_cdc_dp failed")

            result = self._run(project, environment, "run", "dp", "pl_dp", "--poll", "1")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue(self._events(project)[-1]["item"].endswith("/dp.Folder/pl_dp.DataPipeline"))
            handoff = next(line for line in result.stdout.splitlines() if "nor-spark-diagnostics" in line)
            for identifier in (self._events(project)[-1]["item"], WORKSPACE_ID, JOB_ID):
                self.assertIn(identifier, handoff)
            self.assertEqual(self._events(project)[-1]["job_id"], JOB_ID)
            self.assertEqual(self._events(project)[-1]["failure_reason"], "Activity nb_cdc_dp failed")

    def test_pipeline_diagnostic_recipe_has_valid_query_shape(self):
        skill = (TOOLPACK_ROOT / "skills" / "nor-spark-diagnostics" / "SKILL.md").read_text(encoding="utf-8")
        bodies = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", skill, re.DOTALL)]
        query = next(body for body in bodies if "lastUpdatedAfter" in body)
        self.assertEqual(query["filters"], [])
        self.assertEqual(query["orderBy"], [{"orderBy": "ActivityRunStart", "order": "DESC"}])
        self.assertIsInstance(query["lastUpdatedAfter"], str)
        self.assertIsInstance(query["lastUpdatedBefore"], str)
        self.assertIsNone(query["continuationToken"])
        commands = [block for block in re.findall(r"```bash\n(.*?)\n```", skill, re.DOTALL)
                    if "$PIPELINE_ID" in block or "queryactivityruns" in block]
        self.assertEqual(len(commands), 2)
        for command in commands:
            result = subprocess.run(["bash", "-n"], input=command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_reads_latest_job_state_from_fabric(self):
        with tempfile.TemporaryDirectory() as temp:
            project, environment = self._project(temp, ["InProgress", "Failed"], failure="boom")

            started = self._run(project, environment, "start", "dp", "nb_extract_dp")
            running = self._run(project, environment, "status")
            finished = self._run(project, environment, "status")

            self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
            self.assertIn(JOB_ID, started.stdout)
            self.assertIn("nb_extract_dp", running.stdout)
            self.assertIn("InProgress", running.stdout, running.stdout + running.stderr)
            self.assertIn("Failed", finished.stdout, finished.stdout + finished.stderr)
            self.assertIn("boom", finished.stdout)


if __name__ == "__main__":
    unittest.main()