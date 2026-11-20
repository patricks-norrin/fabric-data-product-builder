import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/nor-livy-session/scripts"
sys.path.insert(0, str(SCRIPTS))

import livy_session as livy


WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
SESSION_ID = "22222222-2222-2222-2222-222222222222"
LAKEHOUSE_ID = "33333333-3333-3333-3333-333333333333"
INSTALL = '%pip install --no-index -f https://nrnctopublishpip.z6.web.core.windows.net/pip/ "lakehouse-toolbelt>=1.0.7"'


class LivySessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = pathlib.Path(self.temp.name) / "Project with spaces"
        configuration = self.project / "configuration"
        configuration.mkdir(parents=True)
        (configuration / "fabric_targets.json").write_text(json.dumps({
            "active_target": "dev", "default_workspace": "ws_test",
            "targets": {"dev": {"workspaces": {"ws_test": {
                "workspace_name": 'physical "workspace"',
                "environment": {"id": "environment-id", "name": "env_test"},
            }}}},
        }), encoding="utf-8")
        self.state = self.project / ".scratch/ws_test/livy/livy_session.json"
        self.manifest = self.project / ".scratch/ws_test/operational_manifest.jsonl"

    def saved_session(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text(json.dumps({
            "base": f"workspaces/{WORKSPACE_ID}/lakehouses/test/livyapi/sessions",
            "session_id": SESSION_ID,
        }), encoding="utf-8")

    def events(self):
        return [json.loads(line) for line in self.manifest.read_text(encoding="utf-8").splitlines()]

    def run_driver(self, arguments, responses, *, context_first=False):
        requests = []

        def cli(command, arguments):
            return "test-token" if command == "az" else WORKSPACE_ID

        def http(request, **kwargs):
            requests.append(request)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            if isinstance(response, bytes):
                return io.BytesIO(response)
            return io.BytesIO(json.dumps(response).encode("utf-8")) if response is not None else io.BytesIO()

        context = ["--project-root", str(self.project)]
        argv = context + arguments if context_first else arguments + context
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(livy, "cli_output", side_effect=cli), mock.patch.object(
            livy, "urlopen", side_effect=http,
        ), mock.patch.object(livy.fab_cli, "workspace_id", return_value=WORKSPACE_ID), mock.patch.object(
            livy.fab_cli, "item_id", return_value=LAKEHOUSE_ID,
        ), mock.patch.object(livy.time, "sleep"), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = livy.main(argv)
        self.assertNotIn("test-token", stdout.getvalue() + stderr.getvalue())
        return result, requests, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def output(status="ok"):
        return {"state": "available", "output": {
            "status": status, "data": {"text/plain": "done"},
            "ename": "ValueError", "evalue": "bad cell", "traceback": ["traceback"],
        }}

    def test_create_binds_environment_bootstraps_and_retains_state_and_events(self):
        result, requests, stdout, stderr = self.run_driver(["create", "lh_test"], [
            {"id": SESSION_ID}, {"state": "starting"}, {"state": "idle"},
            {"id": 0}, {"state": "running"}, self.output(),
        ], context_first=True)

        self.assertEqual(result, 0, stdout + stderr)
        body = json.loads(requests[0].data)
        self.assertEqual(json.loads(body["conf"]["spark.fabric.environmentDetails"]), {"id": "environment-id"})
        preamble = json.loads(requests[3].data)["code"]
        compile(preamble, "<preamble>", "exec")
        self.assertIn('WORKSPACE_NAME = "physical \\"workspace\\""', preamble)
        self.assertEqual(json.loads(self.state.read_text())["session_id"], SESSION_ID)
        self.assertEqual([event["event"] for event in self.events()], [
            "livy_create_requested", "livy_created", "livy_ready",
        ])

    def test_no_environment_omits_binding_and_surfaces_preamble_failure(self):
        result, requests, stdout, stderr = self.run_driver(["create", "lh_test", "--no-environment"], [
            {"id": SESSION_ID}, {"state": "idle"}, {"id": 0}, self.output("error"),
        ])

        self.assertEqual(result, 1, stdout + stderr)
        self.assertNotIn("conf", json.loads(requests[0].data))
        self.assertEqual(json.loads(self.state.read_text())["environment"], "")
        self.assertIn("bad cell", stdout)

    def test_run_cells_uses_existing_parser_skips_markdown_and_preserves_dependency_and_sql(self):
        self.saved_session()
        notebook = self.project / "notebook" / "with spaces.py"
        notebook.parent.mkdir()
        notebook.write_text(
            "# MARKDOWN ********************\n# notes\n"
            "# CELL ********************\n" + INSTALL + "\n"
            "# CELL ********************\n%%sql\nSELECT 1\n", encoding="utf-8",
        )
        result, requests, stdout, stderr = self.run_driver(["run-cells", str(notebook)], [
            {"id": 0}, self.output(), {"id": 1}, self.output(),
        ])

        self.assertEqual(result, 0, stdout + stderr)
        bodies = [json.loads(request.data) for request in requests if request.data]
        expected = livy.parse_cells(notebook)
        self.assertEqual(bodies, [
            {"kind": "pyspark", "code": expected[1]["livy_source"]},
            {"kind": "sql", "code": "SELECT 1"},
        ])
        self.assertEqual(self.events()[-1]["status"], "completed")

    def test_failed_cells_stop_or_continue_and_selected_retry_runs_only_requested_cell(self):
        for selection, keep_going, expected_codes in (
            ("all", False, ["print(1)"]),
            ("all", True, ["print(1)", "print(2)"]),
            ("2", False, ["print(2)"]),
        ):
            with self.subTest(selection=selection, keep_going=keep_going):
                if not self.state.exists():
                    self.saved_session()
                notebook = self.project / "notebook.py"
                notebook.write_text(
                    "# CELL ********************\nprint(1)\n# CELL ********************\nprint(2)\n",
                    encoding="utf-8",
                )
                arguments = ["run-cells", str(notebook), selection]
                if keep_going:
                    arguments.append("--keep-going")
                result, requests, stdout, stderr = self.run_driver(arguments, [
                    {"id": 0}, self.output("error"), {"id": 1}, self.output(),
                ])
                self.assertEqual(result, 1, stdout + stderr)
                self.assertEqual([json.loads(r.data)["code"] for r in requests if r.data], expected_codes)
                self.assertEqual(self.events()[-1]["status"], "failed")

    def test_statement_file_status_and_delete_reuse_saved_session(self):
        self.saved_session()
        code_file = self.project / "statement with spaces.py"
        code_file.write_text("print('hello')", encoding="utf-8")
        result, requests, stdout, stderr = self.run_driver(["statement", "-f", str(code_file)], [
            {"id": 0}, self.output(),
        ])
        self.assertEqual(result, 0, stdout + stderr)
        self.assertEqual(json.loads(requests[0].data)["code"], "print('hello')")
        result, requests, stdout, stderr = self.run_driver(["status"], [{"state": "idle"}])
        self.assertEqual(result, 0, stdout + stderr)
        self.assertIn("'state': 'idle'", stdout)
        result, requests, stdout, stderr = self.run_driver(["delete"], [None])
        self.assertEqual(result, 0, stdout + stderr)
        self.assertEqual(requests[0].get_method(), "DELETE")
        self.assertFalse(self.state.exists())
        self.assertEqual([event["event"] for event in self.events()], [
            "livy_delete_requested", "livy_deleted",
        ])

    def test_create_http_and_inner_startup_errors_keep_reason_and_point_to_preflight(self):
        reason = "Fabric capacity is not available"
        for phase in ("create", "startup"):
            with self.subTest(phase=phase):
                error = HTTPError("https://api.fabric.microsoft.com", 503, "Unavailable", {}, io.BytesIO(
                    json.dumps({"message": reason}).encode("utf-8"),
                ))
                responses = [error] if phase == "create" else [
                    {"id": SESSION_ID},
                    {"state": "starting", "fabricSessionStateInfo": {"state": "error", "errorMessage": reason}},
                ]
                result, requests, stdout, stderr = self.run_driver(["create", "lh_test"], responses)
                self.assertEqual(result, 1, stdout + stderr)
                self.assertIn(reason, stderr)
                self.assertIn("nor-environment-check", stderr)
                self.assertIn(reason, self.events()[-1]["reason"])

    def test_failed_delete_keeps_state_and_does_not_record_success(self):
        self.saved_session()
        error = HTTPError("https://api.fabric.microsoft.com", 403, "Forbidden", {}, io.BytesIO(b"{}"))
        result, requests, stdout, stderr = self.run_driver(["delete"], [error])
        self.assertEqual(result, 1, stdout + stderr)
        self.assertTrue(self.state.exists())
        self.assertEqual(self.events()[-1]["event"], "livy_delete_requested")

    def test_cancelled_and_missing_statement_output_are_failures(self):
        self.saved_session()
        for response in ({"state": "cancelled"}, {"state": "available"}):
            with self.subTest(response=response):
                result, requests, stdout, stderr = self.run_driver(["statement", "print(1)"], [
                    {"id": 0}, response,
                ])
                self.assertEqual(result, 1, stdout + stderr)
                self.assertNotIn("[statement ok", stdout)

    def test_invalid_cell_selection_does_not_submit_any_code(self):
        self.saved_session()
        notebook = self.project / "notebook.py"
        notebook.write_text("# CELL ********************\nprint(1)\n", encoding="utf-8")
        result, requests, stdout, stderr = self.run_driver(["run-cells", str(notebook), "99"], [])
        self.assertEqual(result, 1, stdout + stderr)
        self.assertEqual(requests, [])
        self.assertIn("selection", stderr)

    def test_startup_timeout_and_missing_state_fail_without_reporting_ready(self):
        with mock.patch.object(livy.time, "monotonic", side_effect=[0, 901]):
            result, requests, stdout, stderr = self.run_driver(["create", "lh_test"], [
                {"id": SESSION_ID}, {"state": "starting"},
            ])
        self.assertEqual(result, 1, stdout + stderr)
        self.assertEqual(self.events()[-1]["state"], "timeout")
        result, requests, stdout, stderr = self.run_driver(["create", "lh_test"], [
            {"id": SESSION_ID}, {"errorCode": "Unavailable", "message": "cannot read session"},
        ])
        self.assertEqual(result, 1, stdout + stderr)
        self.assertIn("cannot read session", stderr)
        self.assertNotIn("livy_ready", [event["event"] for event in self.events()])

    def test_download_log_saves_bounded_tail_under_scratch_and_prints_failure_lines(self):
        log = b"start\nTraceback (most recent call last):\nValueError: bad row\n"
        result, requests, stdout, stderr = self.run_driver(
            ["download-log", "N", "L", "A", "--bytes", "10"],
            [{"containerLogMeta": {"length": 100}}, log],
        )

        self.assertEqual(result, 0, stdout + stderr)
        self.assertIn(f"workspaces/{WORKSPACE_ID}/notebooks/N/livySessions/L/applications/A/logs", requests[1].full_url)
        self.assertIn("offset=90", requests[1].full_url)
        self.assertIn("size=10", requests[1].full_url)
        self.assertEqual((self.project / ".scratch/ws_test/diagnostics/L_stdout.log").read_bytes(), log)
        self.assertIn("2: Traceback", stdout)
        self.assertNotIn("1: start", stdout)

    def test_native_python_entrypoint_needs_no_shell_for_help(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "livy_session.py"), "--help"],
            cwd=self.project, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run-cells", result.stdout)

    def test_cli_uses_resolved_executable_and_argument_list_and_does_not_print_azure_output(self):
        arguments = ["account", "get-access-token", "--resource", "https://api.fabric.microsoft.com"]
        with mock.patch.object(livy.shutil, "which", return_value=r"C:\Azure CLI\az.cmd"), mock.patch.object(
            livy.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "test-token\r\n", ""),
        ) as run:
            self.assertEqual(livy.cli_output("az", arguments), "test-token")
            self.assertEqual(run.call_args.args[0], [r"C:\Azure CLI\az.cmd", *arguments])
            self.assertFalse(run.call_args.kwargs.get("shell", False))
        with mock.patch.object(livy.shutil, "which", return_value="az"), mock.patch.object(
            livy.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "secret-token", "secret-token"),
        ):
            with self.assertRaises(livy.LivyError) as caught:
                livy.cli_output("az", arguments)
            self.assertNotIn("secret-token", str(caught.exception))
            self.assertIn("az login", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
