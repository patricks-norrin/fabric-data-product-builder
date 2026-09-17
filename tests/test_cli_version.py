import pathlib
import subprocess
import sys
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))

from cli_version import at_least, extract_version, fab_logged_in, parse_version


AZ_VERSION_BLOB = """
azure-cli                         2.61.0 *

core                              2.61.0 *
telemetry                          1.1.0

Dependencies:
msal                              1.28.0
"""


class CliVersionTests(unittest.TestCase):
    def test_parse_pads_missing_patch(self):
        self.assertEqual(parse_version("1.7"), (1, 7, 0))

    def test_old_fab_is_below_minimum(self):
        self.assertFalse(at_least("0.1.10", "1.7.0"))
        self.assertTrue(at_least("1.7.0", "1.7.0"))
        self.assertTrue(at_least("1.8.1", "1.7.0"))

    def test_extract_prefers_azure_cli_line(self):
        self.assertEqual(extract_version(AZ_VERSION_BLOB, "az"), "2.61.0")

    def test_extract_fab_from_typical_banner(self):
        self.assertEqual(extract_version("fab, version 1.7.0\n", "fab"), "1.7.0")
        self.assertEqual(extract_version("Version 0.1.10\n", "fab"), "0.1.10")

    def test_cli_extract_and_compare(self):
        script = TOOLPACK_ROOT / "scripts" / "cli_version.py"
        extracted = subprocess.run(
            [sys.executable, str(script), "extract", "az"],
            input=AZ_VERSION_BLOB,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(extracted.stdout.strip(), "2.61.0")
        below = subprocess.run(
            [sys.executable, str(script), "at_least", "1.7.0", "0.1.10"]
        )
        self.assertEqual(below.returncode, 1)

    def test_fab_logged_in_matches_current_cli_banner(self):
        banner = (
            "✓ Logged in to app.fabric.microsoft.com\n"
            "Logged In: True\n"
            "Account: user@example.com\n"
            "Tenant ID: 00000000-0000-0000-0000-000000000000\n"
            "Token Fabric PowerBI: eyJ0-redacted\n"
        )
        self.assertTrue(fab_logged_in(banner))
        self.assertFalse(fab_logged_in("Logged In: False\n"))
        self.assertTrue(fab_logged_in("\x1b[32mLogged In: True\x1b[0m\n"))
        script = TOOLPACK_ROOT / "scripts" / "cli_version.py"
        logged_in = subprocess.run(
            [sys.executable, str(script), "fab_logged_in"],
            input=banner,
            capture_output=True,
            text=True,
        )
        self.assertEqual(logged_in.returncode, 0)


if __name__ == "__main__":
    unittest.main()
