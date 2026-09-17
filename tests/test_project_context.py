import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))

from norrin_context import find_project_root, resolve_context


def write_targets(project: pathlib.Path) -> None:
    configuration = project / "configuration"
    configuration.mkdir(parents=True)
    (configuration / "fabric_targets.json").write_text(
        json.dumps(
            {
                "active_target": "dev",
                "default_workspace": "ws_alpha",
                "targets": {
                    "dev": {
                        "workspaces": {
                            "ws_alpha": {
                                "workspace_name": "ws_alpha_dev",
                                "environment": {
                                    "name": "env_alpha",
                                    "id": "11111111-1111-1111-1111-111111111111",
                                    "workspace_id": "22222222-2222-2222-2222-222222222222",
                                },
                            },
                            "ws_beta": {
                                "workspace_name": "ws_beta_dev",
                                "environment": {
                                    "name": "env_beta",
                                    "id": "33333333-3333-3333-3333-333333333333",
                                    "workspace_id": "44444444-4444-4444-4444-444444444444",
                                },
                            },
                        }
                    },
                    "prod": {
                        "workspaces": {
                            "ws_alpha": {"workspace_name": "ws_alpha_prod"},
                            "ws_beta": {"workspace_name": "ws_beta_prod"},
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )


class ProjectContextTests(unittest.TestCase):
    def test_git_root_is_used_from_nested_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            write_targets(project)
            nested = project / "src" / "nested"
            nested.mkdir(parents=True)

            context = resolve_context(start=nested, workspace="ws_beta", target="prod")

            self.assertEqual(context.project_root, project.resolve())
            self.assertEqual(context.workspace_dir, project / "ws_beta")
            self.assertEqual(context.scratch_dir, project / ".scratch" / "ws_beta")
            self.assertEqual(context.workspace_name, "ws_beta_prod")

    def test_current_directory_is_used_outside_git(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_targets(project)

            self.assertEqual(find_project_root(project), project.resolve())
            self.assertEqual(resolve_context(start=project).workspace_name, "ws_alpha_dev")

    def test_environment_overrides_are_harness_neutral(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_targets(project)
            previous_workspace = os.environ.get("NORRIN_WORKSPACE")
            previous_target = os.environ.get("NORRIN_TARGET")
            os.environ["NORRIN_WORKSPACE"] = "ws_beta"
            os.environ["NORRIN_TARGET"] = "prod"
            try:
                context = resolve_context(project_root=project)
            finally:
                if previous_workspace is None:
                    os.environ.pop("NORRIN_WORKSPACE", None)
                else:
                    os.environ["NORRIN_WORKSPACE"] = previous_workspace
                if previous_target is None:
                    os.environ.pop("NORRIN_TARGET", None)
                else:
                    os.environ["NORRIN_TARGET"] = previous_target

            self.assertEqual(context.workspace_key, "ws_beta")
            self.assertEqual(context.workspace_name, "ws_beta_prod")

    def test_legacy_single_workspace_config_has_migration_error(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            configuration = project / "configuration"
            configuration.mkdir()
            (configuration / "target_workspace.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "retired single-workspace format"):
                resolve_context(project_root=project)

    def test_shell_helper_resolves_external_project(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            write_targets(project)
            nested = project / "nested"
            nested.mkdir()

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    (
                        f"source {TOOLPACK_ROOT / 'scripts' / 'fab_common.sh'}; "
                        "parse_context_args --workspace ws_beta --target prod; "
                        "resolve_context; "
                        "printf '%s\\n%s\\n%s\\n%s\\n' \"$PROJECT_ROOT\" \"$WORKSPACE_DIR\" \"$SCRATCH_DIR\" \"$WORKSPACE_PATH\""
                    ),
                ],
                cwd=nested,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(
                result.stdout.splitlines(),
                [
                    str(project.resolve()),
                    str(project / "ws_beta"),
                    str(project / ".scratch" / "ws_beta"),
                    "/ws_beta_prod.Workspace",
                ],
            )


if __name__ == "__main__":
    unittest.main()
