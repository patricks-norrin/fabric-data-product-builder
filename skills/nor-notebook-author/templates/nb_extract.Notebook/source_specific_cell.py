# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
# 
# Source: `{{BASE_URL}}` (dataset name is the endpoint unless a template is configured)

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
source = dataset.source_configuration
# Set this to the earliest useful source value and replace this comment with why.
initial_load_start_date = ""
dataset.refresh_delta_table_state()
delta_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
start_timestamp = delta_timestamp or initial_load_start_date
if not start_timestamp:
    raise ValueError("set initial_load_start_date and document why before the first extraction")
# Begin with a small source-specific sample; state why before setting its bound here.
raise NotImplementedError("implement extraction for {{DATASET_NAME}} here: use f'{source.base_url}/{dataset.dataset_name}' for a simple endpoint, or format source.relative_url_template with notebook-owned values. Format start_timestamp for the API as needed, then define authentication/request/pagination logic and land unchanged response text under dataset.file_path_raw/batch_id.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
