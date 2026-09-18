import json
import pathlib
import subprocess
import tempfile
import unittest


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = TOOLPACK_ROOT / "agents" / "nor-data-product-builder.agent.md"


class AgentCleanupContractTests(unittest.TestCase):
    def test_source_aligned_identifier_names_the_provider(self):
        content = AGENT.read_text(encoding="utf-8")

        self.assertIn("frankfurter_api", content)
        self.assertIn("exchange_rates", content)

    def test_validator_accepts_endpoint_query_parameters(self):
        validator = (
            TOOLPACK_ROOT
            / "skills"
            / "nor-data-product-config"
            / "scripts"
            / "validate_data_product_config.py"
        )
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            config_path = project / "source_api.json"
            config_path.write_text(
                json.dumps(
                    {
                        "domain": "operations",
                        "data_product_identifier": "source_api",
                        "datasets": [
                            {
                                "dataset_name": "customers",
                                "unique_identifier_columns": ["id"],
                                "source_configuration": {
                                    "base_url": "https://api.example.com",
                                    "relative_url_template": "/v1/entities?schema={schema}",
                                    "endpoint_query_parameters": {"schema": "customers"},
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(validator), str(config_path)],
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("VALID:", result.stdout)

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