import contextlib
import io
import pathlib
import re
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


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


class ModellingPublicationExampleTests(unittest.TestCase):
    def run_example(self, input_columns, contract_columns):
        examples = re.findall(
            r"```python\n(.*?)\n```",
            MODELLING_SKILL.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        example = next(code for code in examples if ".writeTo(" in code)

        spark_sql = types.ModuleType("pyspark.sql")
        spark_sql.types = MagicMock()
        contract = spark_sql.types.StructType.return_value
        contract.add.return_value = contract
        contract.fieldNames.return_value = contract_columns
        contract.fields = [object() for _ in contract_columns]
        pyspark = types.ModuleType("pyspark")
        pyspark.sql = spark_sql
        notebookutils = types.ModuleType("notebookutils")
        notebookutils.runtime = types.SimpleNamespace(context={"currentWorkspaceName": "physical workspace"})

        input_df = MagicMock()
        input_df.columns = input_columns
        spark = MagicMock()
        spark.table.return_value.count.return_value = 10
        namespace = {
            "purchase_invoice_line_dataframe": input_df,
            "spark": spark,
        }
        with patch.dict(sys.modules, {"pyspark": pyspark, "pyspark.sql": spark_sql, "notebookutils": notebookutils}):
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(example, str(MODELLING_SKILL), "exec"), namespace)
            except ValueError as error:
                return input_df, spark, error
        return input_df, spark, None

    def test_rejects_missing_and_extra_columns_before_alignment(self):
        for inputs, contract in (
            (["dpmeta_uid"], ["dpmeta_uid", "amount"]),
            (["dpmeta_uid", "extra"], ["dpmeta_uid"]),
        ):
            with self.subTest(inputs=inputs, contract=contract):
                input_df, spark, error = self.run_example(inputs, contract)
                self.assertIsInstance(error, ValueError)
                self.assertIn("missing=", str(error))
                self.assertIn("unexpected=", str(error))
                input_df.to.assert_not_called()
                input_df.to.return_value.writeTo.assert_not_called()
                spark.table.assert_not_called()

    def test_valid_contract_writes_once_with_table_comment(self):
        input_df, spark, error = self.run_example(["amount", "dpmeta_uid"], ["dpmeta_uid", "amount"])

        self.assertIsNone(error)
        writer = input_df.to.return_value.writeTo.return_value
        table = "`physical workspace`.lh_purchase_invoice.purchase_invoice.purchase_invoice_line"
        input_df.to.return_value.writeTo.assert_called_once_with(table)
        writer.using.assert_called_once_with("delta")
        writer.using.return_value.tableProperty.assert_called_once_with(
            "comment", "One row per purchase invoice line, identified by dpmeta_uid."
        )
        writer.using.return_value.tableProperty.return_value.createOrReplace.assert_called_once_with()
        input_df.to.return_value.groupBy.assert_not_called()
        spark.table.assert_called_once_with(table)


if __name__ == "__main__":
    unittest.main()