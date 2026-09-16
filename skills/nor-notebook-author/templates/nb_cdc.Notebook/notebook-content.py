# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "{{LAKEHOUSE_ID}}",
# META       "default_lakehouse_name": "lh_{{DATA_PRODUCT_IDENTIFIER}}",
# META       "default_lakehouse_workspace_id": "{{WORKSPACE_ID}}",
# META       "known_lakehouses": [
# META         {
# META           "id": "{{LAKEHOUSE_ID}}"
# META         }
# META       ]
# META     },
# META   }
# META }

# MARKDOWN ********************

# # nb_cdc_{{DATA_PRODUCT_IDENTIFIER}} — raw files to change history
# 
# Single responsibility: read new raw files of each dataset, add `dpmeta_*` metadata with `lakehouse_toolbelt`
# and upsert the SCD2 change history to `Tables/{{DATA_PRODUCT_IDENTIFIER}}/<dataset>`. Reader format/options come from the
# dataset's `source_configuration` (`spark_read_format`, `spark_read_options`). Incremental via `modifiedAfter`.
# Parameters: `datasets` — comma-separated subset, empty = all.

# PARAMETERS CELL ********************

data_product_identifier = "{{DATA_PRODUCT_IDENTIFIER}}"
datasets = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Imports

# CELL ********************

import subprocess
import sys

import notebookutils
import pyspark.sql.functions as F


def ensure_toolbelt_from_shared_resources():
    try:
        import lakehouse_toolbelt
        return
    except ImportError:
        pass
    workspace_name = notebookutils.runtime.context["currentWorkspaceName"]
    library_path = f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/lh_workspace_shared_resources.Lakehouse/Files/libraries"
    wheels = sorted(
        wheel for wheel in notebookutils.fs.ls(library_path)
        if wheel.name.startswith("lakehouse_toolbelt-") and wheel.name.endswith(".whl")
    )
    if not wheels:
        raise RuntimeError(f"no lakehouse_toolbelt wheel under {library_path}")
    local_path = f"/tmp/{wheels[-1].name}"
    notebookutils.fs.cp(wheels[-1].path, f"file:{local_path}")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", local_path], check=True)


ensure_toolbelt_from_shared_resources()
import lakehouse_toolbelt

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load the data product configuration and select datasets

# CELL ********************

data_product = lakehouse_toolbelt.DataProduct(data_product_identifier)
selected = [name.strip() for name in datasets.split(",") if name.strip()] or list(data_product.datasets)
print(f"data product: {data_product.id} | processing: {selected}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Change-history step for one dataset
# 
# raw (new files only) → lineage columns → `add_dpmeta_columns` → drop duplicate versions → `align_dataframe_to_delta_change_history_schema` → `upsert_delta_change_history`.
# `modifiedAfter` filtering can leave zero files; Spark then fails schema inference, which is treated as "no new data".

# CELL ********************

def upsert_dataset_change_history(dataset) -> int:
    dataset.refresh_delta_table_state()
    source = dataset.source_configuration
    reader = spark.read.format(getattr(source, "spark_read_format", None) or "json").option("recursiveFileLookup", "true")
    for option, value in (getattr(source, "spark_read_options", None) or {}).items():
        reader = reader.option(option, value)
    latest_loaded = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
    if latest_loaded:
        reader = reader.option("modifiedAfter", latest_loaded)
        print(f"  incremental: files modified after {latest_loaded}")
    else:
        print("  first run: all files in raw/")
    try:
        df_raw = reader.load(dataset.file_path_raw)
        record_count = df_raw.count()
    except Exception as e:
        if "Unable to infer schema" in str(e):
            print("  no new raw files since last load — skipped")
            return 0
        raise
    df_with_lineage = (
        df_raw
        .withColumn("dpmeta_input_file_name", F.input_file_name())
        .withColumn("dpmeta_source_system_id", F.lit(data_product.id))
    )
    if dataset.timestamp_columns_to_convert:
        df_with_lineage = lakehouse_toolbelt.convert_timestamps(df_with_lineage, dataset.timestamp_columns_to_convert)
    df_with_dpmeta = lakehouse_toolbelt.add_dpmeta_columns(dataframe=df_with_lineage, dataset=dataset)
    df_deduplicated = df_with_dpmeta.dropDuplicates(["dpmeta_uid", "dpmeta_object_version_start_time"])
    df_aligned = lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema(source_dataframe=df_deduplicated, dataset=dataset)
    lakehouse_toolbelt.upsert_delta_change_history(source_dataframe=df_aligned, dataset=dataset)
    print(f"  {record_count:,} raw records processed -> {dataset.file_path_change_history}")
    return record_count


print("defined: upsert_dataset_change_history(dataset)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Run the change-history step for every selected dataset

# CELL ********************

processed = {}
for dataset_name in selected:
    print(f"── {dataset_name}")
    processed[dataset_name] = upsert_dataset_change_history(data_product[dataset_name])
print("processed raw records per dataset:", processed)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Summary of change-history tables

# CELL ********************

for dataset_name in selected:
    dataset = data_product[dataset_name]
    dataset.refresh_delta_table_state()
    if dataset.delta_change_history_table:
        history = dataset.delta_change_history_table.toDF()
        print(f"{dataset_name}: {history.count():,} rows ({history.filter(F.col('dpmeta_object_version_end_time').isNull()).count():,} current) at {dataset.file_path_change_history}")
    else:
        print(f"{dataset_name}: no change-history table yet")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
