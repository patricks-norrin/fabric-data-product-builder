# MARKDOWN ********************

# ## Extract dataset `{{DATASET_NAME}}`
# 
# Source: `{{BASE_URL}}{{RELATIVE_URL_TEMPLATE}}` — {{NOTES}}

# CELL ********************

# --- SOURCE SPECIFIC: {{DATASET_NAME}} ---
dataset = data_product.{{DATASET_NAME}}
source = dataset.source_configuration
raise NotImplementedError("implement extraction for {{DATASET_NAME}} using source.base_url, source.relative_url_template, extraction_window(dataset), land_payload(dataset, file_name, response.text)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
