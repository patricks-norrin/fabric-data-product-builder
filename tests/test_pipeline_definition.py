import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import fake_cli


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE_PY = TOOLPACK_ROOT / "skills" / "nor-pipeline-author" / "scripts" / "pipeline_definition.py"
RUN_JOB = TOOLPACK_ROOT / "skills" / "nor-notebook-publish-and-run" / "scripts" / "run_notebook_job.py"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"


def write_targets(project: pathlib.Path) -> None:
    (project / "configuration").mkdir(parents=True, exist_ok=True)
    (project / "configuration" / "fabric_targets.json").write_text(json.dumps({
        "active_target": "dev",
        "default_workspace": "ws_alpha",
        "targets": {"dev": {"workspaces": {"ws_alpha": {"workspace_name": "ws_alpha_dev"}}}},
    }), encoding="utf-8")


def pipeline_cli(*args):
    return subprocess.run([sys.executable, str(PIPELINE_PY), *map(str, args)], capture_output=True, text=True)


class PipelineDefinitionTests(unittest.TestCase):
    def _render(self, temp):
        project = pathlib.Path(temp)
        write_targets(project)
        for index, role in enumerate(("extract", "cdc"), start=1):
            name = f"nb_{role}_dp"
            notebook = project / "ws_alpha" / "dp" / f"{name}.Notebook"
            notebook.mkdir(parents=True)
            (notebook / ".platform").write_text(json.dumps({
                "metadata": {"type": "Notebook", "displayName": name},
                "config": {"version": "2.0", "logicalId": f"00000000-0000-0000-0000-{index:012d}"},
            }))
        result = pipeline_cli("render", "source", "dp", "--project-root", project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return project / "ws_alpha" / "dp" / "pl_dp.DataPipeline"

    def test_source_pipeline_runs_cdc_only_after_extract_succeeds(self):
        with tempfile.TemporaryDirectory() as temp:
            pipeline = self._render(temp)

            activities = json.loads((pipeline / "pipeline-content.json").read_text())["properties"]["activities"]
            platform = json.loads((pipeline / ".platform").read_text())

            self.assertEqual([a["name"] for a in activities], ["nb_extract_dp", "nb_cdc_dp"])
            self.assertEqual({a["type"] for a in activities}, {"TridentNotebook"})
            self.assertEqual(activities[1]["dependsOn"],
                             [{"activity": "nb_extract_dp", "dependencyConditions": ["Succeeded"]}])
            self.assertEqual(platform["metadata"], {"type": "DataPipeline", "displayName": "pl_dp"})
            for activity in activities:
                self.assertEqual((activity["policy"]["timeout"], activity["policy"]["retry"]), ("0.02:00:00", 1))
                self.assertEqual(activity["typeProperties"]["sessionTag"], "pl_dp")
            self.assertEqual([activity["typeProperties"]["notebookId"] for activity in activities],
                             ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"])
            self.assertEqual({activity["typeProperties"]["workspaceId"] for activity in activities},
                             {"00000000-0000-0000-0000-000000000000"})

    def test_check_reports_structural_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            pipeline = self._render(temp)
            content = pipeline / "pipeline-content.json"
            definition = json.loads(content.read_text())
            activities = definition["properties"]["activities"]
            activities[1]["dependsOn"] = [{"activity": "missing", "dependencyConditions": ["Succeeded"]}]
            activities.append(dict(activities[0]))
            activities[0]["typeProperties"]["workspaceId"] = "{{workspace}}"
            content.write_text(json.dumps(definition))

            result = pipeline_cli("check", pipeline)

            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate activity name: nb_extract_dp", result.stdout)
            self.assertIn("unknown activity 'missing'", result.stdout)
            self.assertIn("unresolved placeholder {{workspace}}", result.stdout)

    def test_render_requires_notebook_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_targets(project)

            result = pipeline_cli("render", "source", "dp", "--project-root", project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("render the notebooks first", result.stderr)
            self.assertFalse((project / "ws_alpha" / "dp" / "pl_dp.DataPipeline").exists())

    def test_deploy_config_preserves_native_source(self):
        with tempfile.TemporaryDirectory() as temp:
            pipeline = self._render(temp)
            original = {path: path.read_bytes() for path in pipeline.iterdir()}
            config = pathlib.Path(temp) / "scratch" / "deploy.yml"

            result = pipeline_cli("deploy-config", pipeline, config, "--workspace-id", WORKSPACE_ID,
                                  "--workspace-dir", pipeline.parent.parent)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(config.exists())
            self.assertEqual({path: path.read_bytes() for path in pipeline.iterdir()}, original)

    def test_publish_delegates_pipeline_to_fab_deploy(self):
        self._assert_publish(deploy_exit=0)

    def test_deploy_failure_is_not_reported_as_published(self):
        self._assert_publish(deploy_exit=1)

    def _assert_publish(self, deploy_exit):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            self._render(temp)
            fake_cli.install(project / "bin", "fab", f'''
if cmd.startswith("get "): ok("{WORKSPACE_ID}")
if cmd.startswith("exists "): ok(message="true")
if cmd.startswith("deploy "):
    (STATE / "deploy.json").write_text(pathlib.Path(args[2]).read_text())
    ok(message="deployed") if os.environ["DEPLOY_EXIT"] == "0" else fail("DeploymentFailed: notebook reference not found")
if cmd.endswith("type=DataPipeline"): api({{"value": [{{"displayName": "pl_dp", "id": "P"}}]}})
''')
            environment = fake_cli.environment(project / "bin", project)
            environment["DEPLOY_EXIT"] = str(deploy_exit)

            result = subprocess.run(
                [sys.executable, str(RUN_JOB), "publish", "dp", "pl_dp", "--project-root", str(project)],
                cwd=project, env=environment, capture_output=True, text=True, timeout=60,
            )

            if deploy_exit:
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("published pl_dp", result.stdout)
                self.assertIn("notebook reference not found", result.stderr)
                return
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("published pl_dp (P)", result.stdout)
            config = json.loads((project / "deploy.json").read_text())
            self.assertEqual(config["core"], {
                "workspace_id": WORKSPACE_ID,
                "repository_directory": str(project / "ws_alpha"),
                "item_types_in_scope": ["Notebook", "DataPipeline"],
            })
            self.assertTrue(config["unpublish"]["skip"])
            exclude = config["publish"]["exclude_regex"]
            self.assertIsNone(re.match(exclude, "pl_dp"))
            for other in ("pl_other", "pl_dp_copy", "nb_extract_dp", "nb_cdc_dp"):
                self.assertIsNotNone(re.match(exclude, other))


if __name__ == "__main__":
    unittest.main()
