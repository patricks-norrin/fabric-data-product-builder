# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
# 
# Source: `{{BASE_URL}}` (dataset name is the endpoint unless a template is configured)

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
source = dataset.source_configuration
raise NotImplementedError("implement extraction for {{DATASET_NAME}} here: use f'{source.base_url}/{dataset.dataset_name}' for a simple endpoint, or build values for source.relative_url_template when calls vary; define authentication/request/pagination/date-window logic, then land unchanged response text with land_payload(dataset, file_name, response.text)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
