import json
import pathlib
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = TOOLPACK_ROOT / "skills" / "nor-lakehouse-query"
SERVER = "fabric-sqlendpoint"


def load_servers(path):
    return json.loads(path.read_text(encoding="utf-8"))["mcpServers"]


class LakehouseQueryPackagingTests(unittest.TestCase):
    def test_skill_frontmatter_matches_directory(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = content.removeprefix("---\n").split("\n---\n", maxsplit=1)[0]
        fields = dict(line.split(": ", maxsplit=1) for line in frontmatter.splitlines())

        self.assertEqual(fields["name"], SKILL_DIR.name)
        self.assertTrue(fields["description"].strip())

    def test_plugin_ships_the_same_global_sql_endpoint_server(self):
        configs = {
            ".mcp.json": load_servers(TOOLPACK_ROOT / ".mcp.json"),
            ".claude-plugin/plugin.json": load_servers(
                TOOLPACK_ROOT / ".claude-plugin" / "plugin.json"
            ),
        }

        urls = set()
        for name, servers in configs.items():
            with self.subTest(config=name):
                self.assertIn(SERVER, servers)
                self.assertEqual(servers[SERVER]["type"], "http")
                urls.add(servers[SERVER]["url"])
        self.assertEqual(len(urls), 1)
        self.assertTrue(urls.pop().startswith("https://api.fabric.microsoft.com/"))

    def test_no_credential_is_embedded_in_server_config(self):
        for path in (
            TOOLPACK_ROOT / ".mcp.json",
            TOOLPACK_ROOT / ".claude-plugin" / "plugin.json",
        ):
            with self.subTest(config=path.name):
                server = load_servers(path)[SERVER]
                self.assertNotIn("Authorization", server.get("headers", {}))


if __name__ == "__main__":
    unittest.main()
