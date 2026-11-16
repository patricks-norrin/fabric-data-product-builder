# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # nb_cdc_{{DATA_PRODUCT_IDENTIFIER}} — raw files to change history
# 
# Single responsibility: read new raw files of each dataset, add `dpmeta_*` metadata with `lakehouse_toolbelt`
# and upsert the SCD2 change history to `Tables/{{DATA_PRODUCT_IDENTIFIER}}/<dataset>`. Choose the native Spark
# reader and only the required reader options for the completed raw files. Incremental via `modifiedAfter`.
# Parameters: edit `filtered_datasets` below to process a subset while debugging.

# MARKDOWN ********************

# ## Install the runtime dependency
#
# Install from the hosted wheel feed; a compatible Environment-installed package also satisfies this requirement.
# Keep this cell before parameters and imports because Fabric restarts Python after installation.

# CELL ********************

%pip install --no-index -f https://nrnctopublishpip.z6.web.core.windows.net/pip/ "lakehouse-toolbelt>=1.0.7"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Runtime parameters

# PARAMETERS CELL ********************

data_product_identifier = "{{DATA_PRODUCT_IDENTIFIER}}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Imports

# CELL ********************

import notebookutils
import pyspark.sql.functions as F
import lakehouse_toolbelt

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load the data product configuration

# CELL ********************

data_product = lakehouse_toolbelt.DataProduct(data_product_identifier)
print(f"data product: {data_product.id} | datasets: {list(data_product.datasets)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Process selected datasets
# 
# Edit `datasets_to_skip` while testing one dataset. The default processes every configured dataset.
# Raw files are read recursively from each dataset's raw path. Keep this loop and its latest-load-timestamp pattern unchanged.
# The marked reader line is the source-specific choice: use a direct native Spark reader and only documented options.

# CELL ********************

datasets_to_skip = []
filtered_datasets = {
    dataset_name: dataset
    for dataset_name, dataset in data_product.datasets.items()
    if dataset_name not in datasets_to_skip
}

for dataset_name, dataset in filtered_datasets.items():
    print(f"Starting to process dataset: {dataset_name}")
    dataset.refresh_delta_table_state()
    # --- SOURCE SPECIFIC READER: replace json/add native Spark options when the landed raw format requires it. ---
    reader = spark.read.format("json").option("recursiveFileLookup", "true")
    latest_change_history_load_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
    if latest_change_history_load_timestamp:
        reader = reader.option("modifiedAfter", latest_change_history_load_timestamp)
        print(f"  incremental: files modified after {latest_change_history_load_timestamp}")
    else:
        print("  no latest change-history load timestamp: all files in raw/")
    try:
        raw_df = reader.load(dataset.file_path_raw)
        record_count = raw_df.count()
    except Exception as caught_exception:
        if "Unable to infer schema" in str(caught_exception) or "AnalysisException" in type(caught_exception).__name__:
            print("  no new raw files since last load — skipped")
            continue
        raise
    raw_with_lineage_df = (
        raw_df
        .withColumn("dpmeta_input_file_name", F.input_file_name())
        .withColumn("dpmeta_source_system_id", F.lit(data_product.id))
    )
    if dataset.timestamp_columns_to_convert:
        raw_with_lineage_df = lakehouse_toolbelt.convert_timestamps(raw_with_lineage_df, dataset.timestamp_columns_to_convert)
    dpmeta_df = lakehouse_toolbelt.add_dpmeta_columns(dataframe=raw_with_lineage_df, dataset=dataset)
    deduplicated_df = dpmeta_df.dropDuplicates(["dpmeta_uid", "dpmeta_object_version_start_time"])
    aligned_df = lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema(source_dataframe=deduplicated_df, dataset=dataset)
    lakehouse_toolbelt.upsert_delta_change_history(source_dataframe=aligned_df, dataset=dataset)
    print(f"  {record_count:,} raw records processed -> {dataset.file_path_change_history}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
