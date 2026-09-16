import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDER = TOOLPACK_ROOT / "skills" / "nor-notebook-author" / "scripts" / "render_notebook.py"


class RenderNotebookTests(unittest.TestCase):
    def test_render_writes_to_consuming_workspace_package(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            config_dir = project / "configuration" / "data_product" / "sample_api"
            config_dir.mkdir(parents=True)
            (config_dir / "sample_api.json").write_text(
                json.dumps(
                    {
                        "domain": "sample",
                        "data_product_identifier": "sample_api",
                        "datasets": [
                            {
                                "dataset_name": "things",
                                "unique_identifier_columns": ["id"],
                                "source_configuration": {
                                    "base_url": "https://example.invalid",
                                    "relative_url_template": "/things",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (project / "configuration" / "fabric_targets.json").write_text(
                json.dumps(
                    {
                        "active_target": "dev",
                        "default_workspace": "ws_custom",
                        "targets": {
                            "dev": {
                                "workspaces": {
                                    "ws_custom": {
                                        "workspace_name": "physical_workspace",
                                        "environment": {
                                            "id": "33333333-3333-3333-3333-333333333333",
                                            "workspace_id": "44444444-4444-4444-4444-444444444444",
                                        },
                                    }
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            fake_bin = project / "fake-bin"
            fake_bin.mkdir()
            fake_fab = fake_bin / "fab"
            fake_fab.write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = get ]; then\n"
                "  echo '11111111-1111-1111-1111-111111111111'\n"
                "else\n"
                "  echo '22222222-2222-2222-2222-222222222222'\n"
                "fi\n",
                encoding="utf-8",
            )
            fake_fab.chmod(0o755)
            nested = project / "nested"
            nested.mkdir()
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            subprocess.run(
                [sys.executable, str(RENDER), "extract", "sample_api"],
                cwd=nested,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            rendered = (
                project
                / "ws_custom"
                / "sample_api"
                / "nb_extract_sample_api.Notebook"
                / "notebook-content.py"
            )
            self.assertTrue(rendered.is_file())
            rendered_content = rendered.read_text(encoding="utf-8")
            self.assertIn("things", rendered_content)
            self.assertIn("ensure_toolbelt_from_shared_resources", rendered_content)
            self.assertNotIn('"environment": {', rendered_content)
            platform = json.loads((rendered.parent / ".platform").read_text(encoding="utf-8"))
            self.assertEqual(platform["version"], "2.0")
            self.assertNotEqual(
                platform["config"]["logicalId"],
                "00000000-0000-0000-0000-000000000000",
            )


if __name__ == "__main__":
    unittest.main()
