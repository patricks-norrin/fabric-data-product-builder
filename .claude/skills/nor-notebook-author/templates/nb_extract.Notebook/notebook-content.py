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
# META     "environment": {
# META       "environmentId": "{{ENVIRONMENT_ID}}",
# META       "workspaceId": "{{ENVIRONMENT_WORKSPACE_ID}}"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_extract_{{DATA_PRODUCT_IDENTIFIER}} — land source payloads in raw/
# 
# Single responsibility: call the source and write every response **unchanged** to
# `Files/{{DATA_PRODUCT_IDENTIFIER}}/<dataset>/raw/<batch_id>/`. No parsing, no validation — `nb_cdc_{{DATA_PRODUCT_IDENTIFIER}}` does the change history.
# Parameters: `batch_id` (empty = now, UTC `YYYYMMDDTHHMMSSZ`), `load_mode` = `incremental` | `backfill`.

# PARAMETERS CELL ********************

data_product_identifier = "{{DATA_PRODUCT_IDENTIFIER}}"
batch_id = ""
load_mode = "incremental"
backfill_start_date = ""
backfill_end_date = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Imports

# CELL ********************

import json
from datetime import datetime, date, timedelta

import requests
import lakehouse_toolbelt

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load the data product configuration and resolve the batch id

# CELL ********************

data_product = lakehouse_toolbelt.DataProduct(data_product_identifier)
batch_id = batch_id or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
print(f"data product: {data_product.id} | datasets: {list(data_product.datasets)} | batch_id: {batch_id} | load_mode: {load_mode}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Helpers: land a payload unchanged, resolve the extraction window

# CELL ********************

def land_payload(dataset, file_name: str, text: str) -> str:
    """Write the source response text unchanged to raw/<batch_id>/<file_name>. Returns the full path."""
    path = f"{dataset.file_path_raw}/{batch_id}/{file_name}"
    notebookutils.fs.put(path, text, overwrite=True)
    print(f"  landed {len(text.encode('utf-8')):>12,} bytes -> {path}")
    return path


def extraction_window(dataset) -> tuple[date, date]:
    """incremental: from last loaded day to today; backfill: explicit range from parameters."""
    params = dataset.source_configuration.endpoint_query_parameters or {}
    if load_mode == "backfill":
        return date.fromisoformat(backfill_start_date), date.fromisoformat(backfill_end_date)
    last_loaded = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
    start = last_loaded.date() if last_loaded else date.fromisoformat(params["initial_load_start_date"])
    return start, date.today()


def date_chunks(start: date, end: date, max_days: int):
    while start <= end:
        chunk_end = min(start + timedelta(days=max_days - 1), end)
        yield start, chunk_end
        start = chunk_end + timedelta(days=1)


print("helpers defined: land_payload, extraction_window, date_chunks")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

{{SOURCE_SPECIFIC_CELLS}}
# MARKDOWN ********************

# ## Summary of this batch

# CELL ********************

for dataset_name, dataset in data_product.datasets.items():
    batch_path = f"{dataset.file_path_raw}/{batch_id}"
    files = notebookutils.fs.ls(batch_path) if notebookutils.fs.exists(batch_path) else []
    print(f"{dataset_name}: {len(files)} file(s) in raw/{batch_id}" + "".join(f"\n  - {f.name} ({f.size:,} bytes)" for f in files))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
