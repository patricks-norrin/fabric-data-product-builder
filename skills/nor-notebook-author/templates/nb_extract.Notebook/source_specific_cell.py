# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
# 
# Source: `{{BASE_URL}}` (dataset name is the endpoint unless a template is configured)

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
source = dataset.source_configuration
start_timestamp = extraction_start_timestamps[dataset.dataset_name]
raise NotImplementedError("implement extraction for {{DATASET_NAME}} here: use f'{source.base_url}/{dataset.dataset_name}' for a simple endpoint, or format source.relative_url_template with notebook-owned values. Format start_timestamp for the API as needed, then define authentication/request/pagination logic and land unchanged response text under dataset.file_path_raw/batch_id.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
