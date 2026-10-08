import pathlib
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELLING_SKILL = TOOLPACK_ROOT / "skills" / "nor-data-product-modelling" / "SKILL.md"
ARCHITECTURE_SKILL = TOOLPACK_ROOT / "skills" / "nor-data-product-architecture" / "SKILL.md"
BUILDER_AGENT = TOOLPACK_ROOT / "agents" / "nor-data-product-builder.agent.md"


class ModellingSkillTests(unittest.TestCase):
    def test_skill_is_discoverable_and_covers_modelling_contract(self):
        content = MODELLING_SKILL.read_text(encoding="utf-8")
        frontmatter, body = content.removeprefix("---\n").split("\n---\n", maxsplit=1)

        self.assertIn("name: nor-data-product-modelling", frontmatter)
        self.assertIn("description:", frontmatter)

        headings = {
            line.removeprefix("## ")
            for line in body.splitlines()
            if line.startswith("## ")
        }
        self.assertTrue(
            {
                "Notebook structure",
                "Local review and Fabric connection",
                "Grain and identifiers",
                "DataFrame naming and joins",
                "Inline transformations versus named business rules",
                "Nulls and deterministic results",
                "Dates, times, and timestamps",
                "Output contract and Delta descriptions",
                "Numeric and currency datatypes",
                "Relationships between data products",
                "Publication rules",
            }.issubset(headings)
        )

    def test_architecture_routes_consumer_modelling_to_skill(self):
        content = ARCHITECTURE_SKILL.read_text(encoding="utf-8")

        self.assertIn("`nor-data-product-modelling`", content)

    def test_builder_routes_each_data_product_role(self):
        content = BUILDER_AGENT.read_text(encoding="utf-8")

        self.assertIn("## Classify and route first", content)
        self.assertIn("## Fabric connection gate", content)
        for role in ("Source-aligned", "Foundational", "Business", "Analytical", "Undetermined"):
            self.assertIn(f"**{role}**", content)
        self.assertIn("`nor-data-product-modelling`", content)
        self.assertNotIn("Oracle EBS", content)


if __name__ == "__main__":
    unittest.main()