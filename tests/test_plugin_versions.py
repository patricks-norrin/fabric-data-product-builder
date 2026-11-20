import json
import pathlib
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHANGELOG = TOOLPACK_ROOT / "CHANGELOG.md"


class PluginVersionTests(unittest.TestCase):
    def test_plugin_and_marketplace_versions_match(self):
        manifest_paths = (TOOLPACK_ROOT / ".claude-plugin" / "plugin.json",)
        marketplace_paths = (TOOLPACK_ROOT / ".claude-plugin" / "marketplace.json",)

        versions = {
            json.loads(path.read_text(encoding="utf-8"))["version"]
            for path in manifest_paths
        }
        versions.update(
            json.loads(path.read_text(encoding="utf-8"))["plugins"][0]["version"]
            for path in marketplace_paths
        )

        self.assertEqual(len(versions), 1, f"Plugin versions differ: {sorted(versions)}")

        current_version = versions.pop()
        changelog = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn(f"## [{current_version}]", changelog)


if __name__ == "__main__":
    unittest.main()