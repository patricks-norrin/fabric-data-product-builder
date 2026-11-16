import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDER = TOOLPACK_ROOT / "skills" / "nor-notebook-author" / "scripts" / "render_notebook.py"
CELLS = TOOLPACK_ROOT / "skills" / "nor-livy-session" / "scripts" / "notebook_cells.py"


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
                                "source_configuration": {},
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

            for kind in ("extract", "cdc"):
                subprocess.run(
                    [sys.executable, str(RENDER), kind, "sample_api"],
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
            self.assertIn('batch_id = ""', rendered_content)
            self.assertIn("raw_batch_path", rendered_content)
            self.assertIn('raw_file_name_stem = f"things_{batch_id}"', rendered_content)
            self.assertIn(
                "latest_change_history_load_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()",
                rendered_content,
            )
            self.assertNotIn("initial_load_lower_bound", rendered_content)
            self.assertNotIn("load_mode", rendered_content)
            self.assertIn("Consult the applicable source documentation", rendered_content)
            self.assertNotIn("import requests", rendered_content)
            self.assertNotIn("initial_load_start_date", rendered_content)
            self.assertNotIn("endpoint_query_parameters", rendered_content)
            self.assertNotIn('"environment": {', rendered_content)
            self.assertNotIn("default_lakehouse", rendered_content)
            self.assertNotIn("known_lakehouses", rendered_content)
            platform = json.loads((rendered.parent / ".platform").read_text(encoding="utf-8"))
            self.assertEqual(platform["version"], "2.0")
            self.assertNotEqual(
                platform["config"]["logicalId"],
                "00000000-0000-0000-0000-000000000000",
            )

            cdc_rendered = (
                project
                / "ws_custom"
                / "sample_api"
                / "nb_cdc_sample_api.Notebook"
                / "notebook-content.py"
            )
            self.assertTrue(cdc_rendered.is_file())
            cdc_content = cdc_rendered.read_text(encoding="utf-8")
            for notebook in (rendered, cdc_rendered):
                with self.subTest(notebook=notebook.name, kind=notebook.parent.name):
                    cells = json.loads(subprocess.check_output(
                        [sys.executable, str(CELLS), str(notebook), "--json"], text=True
                    ))
                    code = [cell["source"] for cell in cells if cell["type"] != "markdown"]
                    install_cells = [source for source in code if source.startswith("%pip ")]
                    self.assertEqual(install_cells, [
                        '%pip install --no-index -f '
                        'https://nrnctopublishpip.z6.web.core.windows.net/pip/ '
                        '"lakehouse-toolbelt>=1.0.7"'
                    ])
                    install_index = code.index(install_cells[0])
                    import_index = next(i for i, source in enumerate(code) if "import lakehouse_toolbelt" in source)
                    parameters = next(cell["source"] for cell in cells if cell["type"] == "parameters")
                    self.assertLess(install_index, code.index(parameters))
                    self.assertLess(install_index, import_index)
                    for source in code:
                        if source not in install_cells:
                            compile(source, str(notebook), "exec")
                    content = notebook.read_text(encoding="utf-8")
                    self.assertNotIn("Files/libraries", content)
                    self.assertNotIn("ensure_toolbelt_from_shared_resources", content)
            self.assertIn('data_product_identifier = "sample_api"', cdc_content)
            self.assertIn("datasets_to_skip = []", cdc_content)
            self.assertIn("filtered_datasets = {", cdc_content)
            self.assertIn("for dataset_name, dataset in filtered_datasets.items():", cdc_content)
            self.assertIn('spark.read.format("json").option("recursiveFileLookup", "true")', cdc_content)
            self.assertIn("SOURCE SPECIFIC READER", cdc_content)
            self.assertIn("dataset.file_path_raw", cdc_content)
            self.assertIn("get_delta_change_history_dpmeta_loaded_to_dataplatform()", cdc_content)
            self.assertIn(
                'reader = reader.option("modifiedAfter", latest_change_history_load_timestamp)',
                cdc_content,
            )
            self.assertIn(
                'print("  no latest change-history load timestamp: all files in raw/")',
                cdc_content,
            )
            self.assertNotIn("first_run", cdc_content)
            self.assertNotIn("load_mode", cdc_content)
            self.assertIn("lakehouse_toolbelt.add_dpmeta_columns", cdc_content)
            self.assertIn("dropDuplicates([\"dpmeta_uid\", \"dpmeta_object_version_start_time\"])", cdc_content)
            self.assertIn("lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema", cdc_content)
            self.assertIn("lakehouse_toolbelt.upsert_delta_change_history", cdc_content)
            self.assertNotIn('datasets = ""', cdc_content)
            self.assertNotIn("def upsert_dataset_change_history", cdc_content)
            self.assertNotIn("default_lakehouse", cdc_content)
            self.assertNotIn("known_lakehouses", cdc_content)
            self.assertNotIn('format("text")', cdc_content)
            self.assertNotIn("from_json", cdc_content)
            self.assertNotIn("StructType", cdc_content)


if __name__ == "__main__":
    unittest.main()
