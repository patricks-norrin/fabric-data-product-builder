import pathlib
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = TOOLPACK_ROOT / "agents" / "nor-data-product-builder.agent.md"


class AgentCleanupContractTests(unittest.TestCase):
    def test_cleanup_is_explicit_and_preserves_product_data(self):
        content = AGENT.read_text(encoding="utf-8")

        self.assertIn("**Cleanup.**", content)
        self.assertIn("use `fab dir`", content)
        self.assertIn("`fab exists` or `fab dir`", content)
        self.assertIn("Use only this toolpack's bundled `nor-*` skills", content)
        self.assertIn("Retain every timestamped `raw/<YYYYMMDDTHHMMSSZ>/` batch", content)
        self.assertIn("all Delta tables", content)
        self.assertIn("Present the exact paths to remove and their contents", content)
        self.assertIn("only the paths the user confirms", content)
        self.assertIn("Re-list each deleted path", content)


if __name__ == "__main__":
    unittest.main()