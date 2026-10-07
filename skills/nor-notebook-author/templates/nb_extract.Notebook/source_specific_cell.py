# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
#
# Implement this source-specific extraction and land raw data unchanged.

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
raw_batch_path = f"{dataset.file_path_raw}/{batch_id}"
raw_file_name_stem = f"{{DATASET_NAME}}_{batch_id}"
latest_change_history_load_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
# Consult the applicable source documentation and use its native client or Spark reader. Keep credentials, query or
# request values and pagination in this cell. Build one base request and, when the source supports filtering, add its
# lower filter only if latest_change_history_load_timestamp is non-null. Otherwise send the base request unchanged for all
# requested history. Do not add first-run or load-mode parameters. If the source requires a lower bound and defines no
# minimum, ask the user instead of inventing one. Snapshot only for an explicit user request, an explicitly closed
# timeframe, or a source proven to have no reliable incremental filter, and document that exception. Land unchanged under
# raw_batch_path, naming every file <logical_identifier>_<batch_id>.<extension>. For each fixed extraction bound,
# comment why it was selected and whether it came from user input.
# Document the raw format, file extension, and why any non-default Spark reader option is needed.
raise NotImplementedError("implement source-specific extraction for {{DATASET_NAME}} and land unchanged files under raw_batch_path")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
