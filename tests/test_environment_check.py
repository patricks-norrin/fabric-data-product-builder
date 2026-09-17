import json
import os
import pathlib
import subprocess
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = TOOLPACK_ROOT / "skills" / "nor-environment-check" / "scripts" / "check_environment.sh"


class EnvironmentCheckTests(unittest.TestCase):
    def test_reports_independent_results_once_after_cli_blocker(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            configuration = project / "configuration"
            configuration.mkdir()
            (configuration / "fabric_targets.json").write_text(
                json.dumps(
                    {
                        "active_target": "dev",
                        "default_workspace": "ws_alpha",
                        "targets": {
                            "dev": {
                                "workspaces": {
                                    "ws_alpha": {"workspace_name": "ws_alpha_dev"}
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            fake_bin = project / "fake-bin"
            fake_bin.mkdir()
            (fake_bin / "fab").write_text(
                "#!/usr/bin/env bash\necho 'fab, version 0.1.10'\n",
                encoding="utf-8",
            )
            (fake_bin / "az").write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = \"--version\" ]; then echo 'azure-cli 2.61.0'; else echo '2099-01-01'; fi\n",
                encoding="utf-8",
            )
            (fake_bin / "fab").chmod(0o755)
            (fake_bin / "az").chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"

            result = subprocess.run(
                ["bash", str(CHECK), "--project-root", str(project)],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.count("== preflight requires review"), 1)
            self.assertIn("BLOCKERS\n- fab: 0.1.10 < 1.7.0", result.stdout)
            self.assertIn("SKIPPED\n- Fabric authentication: fab CLI unavailable", result.stdout)
            self.assertIn("PASSED\n- az: 2.61.0 (>= 2.50.0)", result.stdout)
            self.assertIn("- az token for api.fabric.microsoft.com available", result.stdout)


if __name__ == "__main__":
    unittest.main()