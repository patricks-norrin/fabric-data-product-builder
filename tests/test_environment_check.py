import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import fake_cli

TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = TOOLPACK_ROOT / "skills" / "nor-environment-check" / "scripts" / "check_environment.py"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
LAKEHOUSE_ID = "33333333-3333-3333-3333-333333333333"

FAB = f'''
if cmd == "--version": text("fab, version 1.9.0")
if cmd.startswith("get "): ok("{WORKSPACE_ID}")
if cmd == "api workspaces/{WORKSPACE_ID}": api({{"capacityId": "cap"}})
if cmd == "api capacities": api({{"value": [{{"id": "cap", "state": "Active", "sku": os.environ.get("SKU", "F8"), "displayName": "test"}}]}})
if cmd.endswith("/spark/settings"): api({{"pool": {{"defaultPool": {{"name": "Starter Pool"}}}}, "environment": {{"runtimeVersion": "1.3"}},
    "highConcurrency": {{"notebookInteractiveRunEnabled": True, "notebookPipelineRunEnabled": os.environ.get("HC") == "on"}}}})
if cmd.startswith("api workspaces/{WORKSPACE_ID}/items -P type=Lakehouse"):
    api({{"value": [{{"displayName": "lh_workspace_shared_resources", "id": "{LAKEHOUSE_ID}"}}] if os.environ.get("SHARED") == "yes" else []}})
if "/livyapi/" in cmd: api({{"value": []}})
if cmd.startswith("exists "): ok(message="true")
'''
AZ = '''
if cmd == "--version": text("azure-cli 2.61.0")
if cmd.startswith("account get-access-token"): text("2099-01-01")
'''


class EnvironmentCheckTests(unittest.TestCase):
    def run_check(self, *arguments, fab=FAB, targets=None, **env):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project = pathlib.Path(temp.name)
        (project / "configuration").mkdir()
        (project / "configuration" / "fabric_targets.json").write_text(json.dumps(targets or {
            "active_target": "dev", "default_workspace": "ws_alpha",
            "targets": {"dev": {"workspaces": {"ws_alpha": {"workspace_name": "ws_alpha_dev"}}}},
        }), encoding="utf-8")
        fake_cli.install(project / "bin", "fab", fab)
        fake_cli.install(project / "bin", "az", AZ)
        environment = fake_cli.environment(project / "bin", project)
        environment.update(env)
        result = subprocess.run(
            [sys.executable, str(CHECK), *arguments, "--project-root", str(project)],
            cwd=project, env=environment, capture_output=True, text=True, timeout=60,
        )
        return result, (project / "fab-calls").read_text(encoding="utf-8")

    def test_clean_workspace_passes_in_one_line(self):
        result, _ = self.run_check(HC="on", SHARED="yes")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("PASS  preflight complete"), result.stdout)

    def test_check_is_read_only_and_reports_missing_shared_lakehouse(self):
        result, calls = self.run_check(HC="on")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("lh_workspace_shared_resources is missing", result.stdout)
        self.assertNotIn("mkdir", calls)
        self.assertNotIn("cp ", calls)

    def test_recommendation_prints_setting_click_path_and_reason(self):
        result, _ = self.run_check(HC="off", SHARED="yes")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("High concurrency for pipelines is Off, recommended On\n    How: Workspace settings >", result.stdout)

    def test_small_capacity_needs_acknowledgment(self):
        result, _ = self.run_check(HC="on", SHARED="yes", SKU="F2")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ACKNOWLEDGMENTS\n- capacity F2", result.stdout)

    def test_old_fab_blocks_but_independent_checks_still_report(self):
        result, _ = self.run_check(fab='if cmd == "--version": text("fab, version 0.1.10")\n')

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("== preflight requires review"), 1)
        self.assertIn("BLOCKERS\n- fab: 0.1.10 < 1.9.0", result.stdout)
        self.assertIn("SKIPPED\n- Fabric checks", result.stdout)
        self.assertIn("- az: 2.61.0 (>= 2.50.0)", result.stdout)
        self.assertIn("- az token for api.fabric.microsoft.com available", result.stdout)

    def test_fabric_error_message_reaches_the_report(self):
        fab = 'if cmd == "--version": text("fab, version 1.9.0")\nif cmd.startswith("get "): fail("Unauthorized: run fab auth login")\n'
        result, _ = self.run_check(fab=fab)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Unauthorized: run fab auth login", result.stdout)

    def test_recommended_workspace_settings_are_complete_and_unique(self):
        rules = json.loads((CHECK.parents[1] / "recommended_workspace_settings.json").read_text(encoding="utf-8"))

        self.assertTrue(rules)
        for rule in rules:
            self.assertEqual(set(rule), {"setting", "recommended", "label", "click", "why"})
            self.assertTrue(all(str(rule[key]).strip() for key in rule))
        self.assertEqual(len({rule["setting"] for rule in rules}), len(rules))


if __name__ == "__main__":
    unittest.main()
