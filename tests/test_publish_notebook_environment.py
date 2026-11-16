import json
import os
import pathlib
import subprocess
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_JOB = TOOLPACK_ROOT / "skills" / "nor-notebook-publish-and-run" / "scripts" / "run_notebook_job.sh"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
LOGICAL_ID = "a9f0f560-0000-4000-8000-000000000001"
TARGET_ENV_ID = "f87fecca-0000-4000-8000-000000000002"
GIT_SYNC_WORKSPACE = "00000000-0000-0000-0000-000000000000"


def notebook_source(environment: dict | None) -> str:
    metadata = {"kernel_info": {"name": "synapse_pyspark"}}
    if environment is not None:
        metadata["dependencies"] = {"environment": environment}
    meta = "\n".join(f"# META {line}" for line in json.dumps(metadata, indent=2).splitlines())
    return f"# Fabric notebook source\n\n# METADATA ********************\n\n{meta}\n\n# CELL ********************\n\nprint(1)\n"


def read_metadata(path: pathlib.Path) -> dict:
    lines = [line[len("# META"):] for line in path.read_text().splitlines() if line == "# META" or line.startswith("# META ")]
    return json.loads("\n".join(lines))


class PublishNotebookEnvironmentTests(unittest.TestCase):
    def _publish(self, environment: dict | None, with_environment_item: bool = True, target_has_env: bool = True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project = pathlib.Path(temp.name)
        (project / "configuration").mkdir()
        (project / "configuration" / "fabric_targets.json").write_text(json.dumps({
            "active_target": "dev",
            "default_workspace": "ws_alpha",
            "targets": {"dev": {"workspaces": {"ws_alpha": {"workspace_name": "ws_alpha_dev"}}}},
        }))
        notebook = project / "ws_alpha" / "dp" / "nb_cdc_dp.Notebook"
        notebook.mkdir(parents=True)
        (notebook / "notebook-content.py").write_text(notebook_source(environment))
        if with_environment_item:
            env_item = project / "ws_alpha" / "env_catalog.Environment"
            env_item.mkdir(parents=True)
            (env_item / ".platform").write_text(json.dumps({
                "metadata": {"type": "Environment", "displayName": "env_catalog"},
                "config": {"logicalId": LOGICAL_ID},
            }))
        env_answer = f'echo "\\"{TARGET_ENV_ID}\\""' if target_has_env else 'echo None'
        fake_bin = project / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "fab").write_text(
            "#!/usr/bin/env bash\n"
            'case "$*" in\n'
            f'  get*) echo "{WORKSPACE_ID}";;\n'
            '  exists*) echo "* true";;\n'
            '  import*) cp "$4/notebook-content.py" "$FAKE/imported.py"; echo "* Imported";;\n'
            f'  *"displayName==\'env_catalog\'"*) {env_answer};;\n'
            '  *"displayName==\'nb_cdc_dp\'"*) echo "\\"N\\"";;\n'
            '  *) echo "unexpected fab call: $*" >&2; exit 1;;\n'
            'esac\n'
        )
        (fake_bin / "fab").chmod(0o755)
        environment_vars = os.environ.copy()
        environment_vars["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        environment_vars["FAKE"] = str(project)
        result = subprocess.run(
            ["bash", str(RUN_JOB), "publish", "dp", "nb_cdc_dp", "--project-root", str(project)],
            cwd=project, env=environment_vars, capture_output=True, text=True, timeout=60,
        )
        return project, notebook, result

    def test_git_sync_binding_is_rebound_to_target_environment(self):
        project, notebook, result = self._publish({"environmentId": LOGICAL_ID, "workspaceId": GIT_SYNC_WORKSPACE})

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read_metadata(project / "imported.py")["dependencies"]["environment"],
                         {"environmentId": TARGET_ENV_ID, "workspaceId": WORKSPACE_ID})
        self.assertEqual(read_metadata(notebook / "notebook-content.py")["dependencies"]["environment"]["environmentId"],
                         LOGICAL_ID)
        self.assertTrue((project / "imported.py").read_text().endswith("print(1)\n"))

    def test_unbound_and_concrete_bindings_are_imported_unchanged(self):
        for environment in (None, {"environmentId": "E", "workspaceId": "W"}):
            with self.subTest(environment=environment):
                project, notebook, result = self._publish(environment)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((project / "imported.py").read_text(), (notebook / "notebook-content.py").read_text())

    def test_unresolvable_binding_fails_before_import(self):
        cases = {"no local Environment": {"with_environment_item": False},
                 "not in target workspace": {"target_has_env": False}}
        for name, options in cases.items():
            with self.subTest(name):
                project, _, result = self._publish(
                    {"environmentId": LOGICAL_ID, "workspaceId": GIT_SYNC_WORKSPACE}, **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((project / "imported.py").exists())


if __name__ == "__main__":
    unittest.main()
