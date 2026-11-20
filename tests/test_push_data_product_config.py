import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import fake_cli

TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
PUSH = TOOLPACK_ROOT / "skills" / "nor-data-product-config" / "scripts" / "push_data_product_config.py"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"

# Items "exist" once created: mkdir and cp record the path in STATE/created.
FAB = f'''
created = STATE / "created"
known = created.read_text().splitlines() if created.exists() else []
def remember(path):
    with created.open("a") as handle: handle.write(path + "\\n")
if cmd.startswith("get "): ok("{WORKSPACE_ID}")
if cmd.startswith("exists "): ok(message="true" if args[1] in known else "false")
if cmd.startswith("mkdir "):
    remember(args[1].replace("/sample_api.Folder", ""))
    ok(message="created")
if cmd.startswith("cp "):
    if os.environ.get("CP_FAILS"): fail("Forbidden: no write access to OneLake")
    remember(args[2] + pathlib.Path(args[1]).name)
    ok(message="copied")
if cmd.startswith("api workspaces/{WORKSPACE_ID}/items -P type=Lakehouse"):
    api({{"value": [{{"displayName": "lh_sample_api", "id": "L"}}] if any(p.endswith("lh_sample_api.Lakehouse") for p in known) else []}})
'''


class PushDataProductConfigTests(unittest.TestCase):
    def run_push(self, **env):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project = pathlib.Path(temp.name)
        (project / "configuration").mkdir()
        (project / "configuration" / "fabric_targets.json").write_text(json.dumps({
            "active_target": "dev", "default_workspace": "ws_alpha",
            "targets": {"dev": {"workspaces": {"ws_alpha": {"workspace_name": "ws_alpha_dev"}}}},
        }), encoding="utf-8")
        product = project / "configuration" / "data_product" / "sample_api"
        product.mkdir(parents=True)
        (product / "sample_api.json").write_text(json.dumps({
            "domain": "operations", "data_product_identifier": "sample_api",
            "datasets": [{"dataset_name": "customers", "unique_identifier_columns": ["id"]}],
        }), encoding="utf-8")
        fake_cli.install(project / "bin", "fab", FAB)
        environment = fake_cli.environment(project / "bin", project)
        environment.update(env)
        return subprocess.run(
            [sys.executable, str(PUSH), "sample_api", "--project-root", str(project)],
            cwd=project, env=environment, capture_output=True, text=True, timeout=60,
        ), project

    def test_first_push_creates_shared_lakehouse_and_provisions_product(self):
        result, project = self.run_push()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        created = (project / "created").read_text().splitlines()
        self.assertIn("/ws_alpha_dev.Workspace/lh_workspace_shared_resources.Lakehouse", created)
        self.assertIn("/ws_alpha_dev.Workspace/lh_sample_api.Lakehouse", created)
        self.assertIn("LAKEHOUSE_ID=L", result.stdout)
        self.assertIn(f"WORKSPACE_ID={WORKSPACE_ID}", result.stdout)

    def test_copy_failure_reports_fabric_reason(self):
        result, _ = self.run_push(CP_FAILS="1")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Forbidden: no write access to OneLake", result.stderr)


if __name__ == "__main__":
    unittest.main()
