# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "b54b7c56-5b6d-4ab3-a485-d8efc72a94da",
# META       "default_lakehouse_name": "lh_frankfurter_api",
# META       "default_lakehouse_workspace_id": "f63fb43d-614b-4f18-bee9-786320230d2b",
# META       "known_lakehouses": [
# META         {
# META           "id": "b54b7c56-5b6d-4ab3-a485-d8efc72a94da"
# META         }
# META       ]
# META     },
# META     "environment": {
# META       "environmentId": "8c1fe0ba-7b56-4325-9008-4e2b10231bd1",
# META       "workspaceId": "f63fb43d-614b-4f18-bee9-786320230d2b"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_extract_frankfurter_api — land source payloads in raw/
# 
# Single responsibility: call the source and write every response **unchanged** to
# `Files/frankfurter_api/<dataset>/raw/<batch_id>/`. No parsing, no validation — `nb_cdc_frankfurter_api` does the change history.
# Parameters: `batch_id` (empty = now, UTC `YYYYMMDDTHHMMSSZ`), `load_mode` = `incremental` | `backfill`.

# PARAMETERS CELL ********************

data_product_identifier = "frankfurter_api"
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

# MARKDOWN ********************

# ## Extract dataset `exchange_rates`
# 
# Source: `https://api.frankfurter.dev/v2/rates?from={start_date}&to={end_date}` — One row per date/base/quote across all providers (Accept: application/x-ndjson). Key is date+base+quote; provider is a dimension column.

# CELL ********************

# --- SOURCE SPECIFIC: exchange_rates ---
dataset = data_product.exchange_rates
source = dataset.source_configuration
start, end = extraction_window(dataset)
max_days = int((source.endpoint_query_parameters or {}).get("max_days_per_request", 366))
print(f"exchange_rates: window {start} -> {end}, chunks of {max_days} days")
for chunk_start, chunk_end in date_chunks(start, end, max_days):
    url = source.base_url + source.relative_url_template.format(start_date=chunk_start.isoformat(), end_date=chunk_end.isoformat())
    response = requests.get(url, headers={"Accept": "application/x-ndjson"}, timeout=120)
    response.raise_for_status()
    if response.text.strip():
        land_payload(dataset, f"exchange_rates_{chunk_start.isoformat()}_{chunk_end.isoformat()}.ndjson", response.text)
    else:
        print(f"  no rates returned for {chunk_start} -> {chunk_end} (nothing landed)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Extract dataset `currencies`
# 
# Source: `https://api.frankfurter.dev/v2/currencies` — Reference data: iso_code, iso_numeric, name, symbol, start_date, end_date. JSON array -> multiLine reader. end_date equals the latest available rate date for active currencies (changes daily) -> excluded from payload checksum so only real changes create versions.

# CELL ********************

# --- SOURCE SPECIFIC: currencies ---
dataset = data_product.currencies
source = dataset.source_configuration
url = source.base_url + source.relative_url_template
response = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
response.raise_for_status()
land_payload(dataset, "currencies.json", response.text)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

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
