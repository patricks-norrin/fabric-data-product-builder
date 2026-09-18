# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
#
# Implement this source-specific extraction and land raw data unchanged.

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
raw_batch_path = f"{dataset.file_path_raw}/{batch_id}"
# Consult the applicable source documentation and use its native client or Spark reader. Keep credentials, query or
# request values, pagination, and source-specific incremental logic in this cell. Land source data unchanged under
# raw_batch_path and document the raw format, file extension, and why any non-default Spark reader option is needed.
raise NotImplementedError("implement source-specific extraction for {{DATASET_NAME}} and land unchanged files under raw_batch_path")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
