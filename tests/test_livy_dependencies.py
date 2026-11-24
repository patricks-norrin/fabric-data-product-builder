import contextlib
import importlib.util
import io
import json
import pathlib
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVY = ROOT / "skills" / "nor-livy-session"
SPEC = importlib.util.spec_from_file_location("notebook_cells", LIVY / "scripts" / "notebook_cells.py")
notebook_cells = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notebook_cells)
FEED = "https://nrnctopublishpip.z6.web.core.windows.net/pip/"
INSTALL = f'%pip install --no-index -f {FEED} "lakehouse-toolbelt>=1.0.7"'


class LivyDependencyTests(unittest.TestCase):
    def parse_cell(self, source):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "notebook-content.py"
            path.write_text("# CELL ********************\n" + source, encoding="utf-8")
            return notebook_cells.parse(path)[0]

    def test_pip_cell_preserves_notebook_source_and_runs_driver_command_without_shell(self):
        cell = self.parse_cell(INSTALL)
        self.assertEqual(cell["source"], INSTALL)
        self.assertEqual(cell["kind"], "pyspark")
        with mock.patch("subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            exec(compile(cell["livy_source"], "<livy-cell>", "exec"), {})
        run.assert_called_once_with([
            sys.executable, "-m", "pip", "install", "--no-index", "-f",
            FEED, "lakehouse-toolbelt>=1.0.7",
        ], check=True)
        self.assertIn("executor libraries are not updated", output.getvalue())

    def test_pip_failure_propagates(self):
        cell = self.parse_cell(INSTALL)
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["pip"])):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
                exec(cell["livy_source"], {})

    def test_pip_must_be_a_dedicated_cell(self):
        with self.assertRaisesRegex(ValueError, "dedicated single-line cell"):
            self.parse_cell(INSTALL + "\nimport lakehouse_toolbelt")

    def test_python_and_sql_cells_keep_existing_behavior(self):
        python = self.parse_cell('print("hello")')
        self.assertNotIn("livy_source", python)
        self.assertEqual(python["source"], 'print("hello")')
        sql = self.parse_cell("%%sql\nSELECT 1")
        self.assertEqual(sql["kind"], "sql")
        self.assertEqual(sql["source"], "SELECT 1")
        self.assertNotIn("livy_source", sql)

    def run_preamble(self, installed_version="1.0.7", pip_error=None, workspace_name="physical_workspace"):
        notebookutils = types.ModuleType("notebookutils")
        notebookutils.runtime = types.SimpleNamespace(
            context={"currentWorkspaceName": workspace_name, "currentWorkspaceId": "workspace-id"},
            extra_runtime_property="preserved",
        )
        notebookutils.fs = mock.Mock()
        toolbelt = types.ModuleType("lakehouse_toolbelt")
        modules = {"notebookutils": notebookutils, "lakehouse_toolbelt": toolbelt}
        for name in (
            "_env_helper", "_data_product_class", "_configuration_helpers", "_dataset_class",
            "_source_configuration_class", "_publish_configuration_class",
        ):
            module = types.ModuleType(f"lakehouse_toolbelt.{name}")
            module.notebookutils = notebookutils
            modules[module.__name__] = module
        output = io.StringIO()
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "subprocess.run", side_effect=pip_error
        ) as run, mock.patch("importlib.metadata.version", return_value=installed_version):
            with contextlib.redirect_stdout(output):
                if pip_error:
                    with self.assertRaises(subprocess.CalledProcessError):
                        runpy.run_path(str(LIVY / "preamble" / "livy_preamble.py"),
                                       init_globals={"spark": types.SimpleNamespace(version="3.5")})
                else:
                    preamble = (LIVY / "preamble" / "livy_preamble.py").read_text(encoding="utf-8")
                    preamble = preamble.replace('"__WORKSPACE_NAME__"', json.dumps("selected_workspace"))
                    preamble_globals = {"spark": types.SimpleNamespace(version="3.5")}
                    exec(compile(preamble, "<preamble>", "exec"), preamble_globals)
                    modules["preexisting_notebook_global"] = preamble_globals["notebookutils"]
                    cell = {}
                    exec("import notebookutils\nworkspace = notebookutils.runtime.context['currentWorkspaceName']",
                         cell)
                    modules["notebook_import"] = cell["notebookutils"]
                    modules["notebook_workspace"] = cell["workspace"]
        report_line = next(line for line in output.getvalue().splitlines() if line.startswith("PREAMBLE "))
        return run, json.loads(report_line.removeprefix("PREAMBLE ")), modules

    def test_preamble_resolves_minimum_without_upgrading_compatible_environment(self):
        for version in ("1.0.7", "1.2.0"):
            with self.subTest(version=version):
                run, report, modules = self.run_preamble(installed_version=version)
                run.assert_called_once_with([
                    sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-index", "-f", FEED, "lakehouse-toolbelt>=1.0.7",
                ], check=True)
                self.assertEqual(report["lakehouse_toolbelt"], version)
                self.assertTrue(report["onelake_access"])
                self.assertEqual(modules["notebook_workspace"], "physical_workspace")
                self.assertEqual(
                    modules["lakehouse_toolbelt._data_product_class"].notebookutils.runtime.context[
                        "currentWorkspaceName"
                    ],
                    "physical_workspace",
                )
                modules["notebookutils"].fs.cp.assert_not_called()

    def test_preamble_reports_and_raises_installation_failure(self):
        run, report, modules = self.run_preamble(
            pip_error=subprocess.CalledProcessError(1, ["pip"])
        )
        self.assertIn("IMPORT FAILED", report["lakehouse_toolbelt"])
        run.assert_called_once()
        modules["notebookutils"].fs.cp.assert_not_called()

    def test_notebook_and_toolbelt_share_selected_workspace_without_losing_notebookutils(self):
        _, report, modules = self.run_preamble(workspace_name=None)

        self.assertEqual(report["workspace_name"], "selected_workspace")
        self.assertEqual(modules["notebook_workspace"], "selected_workspace")
        shim = modules["notebook_import"]
        self.assertIs(modules["preexisting_notebook_global"], shim)
        self.assertIs(modules["lakehouse_toolbelt._data_product_class"].notebookutils, shim)
        self.assertEqual(shim.runtime.context["currentWorkspaceId"], "workspace-id")
        self.assertEqual(shim.runtime.extra_runtime_property, "preserved")
        self.assertIs(shim.fs, modules["notebookutils"].fs)
        self.assertIsNone(modules["notebookutils"].runtime.context["currentWorkspaceName"])


if __name__ == "__main__":
    unittest.main()
