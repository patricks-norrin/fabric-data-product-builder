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
import subprocess
import sys
from datetime import datetime, date, timedelta

import notebookutils
import requests


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

# ## Resolve extraction start timestamps
#
# The user supplied `initial_load_start_date` after reviewing the source's historical availability. It is used only
# on a first run, when no successful Delta change-history load exists. On later runs, each dataset uses the actual
# `dpmeta_loaded_to_dataplatform` timestamp from its Delta table. Record the source-specific reason for the chosen
# initial date here before running this notebook.

# CELL ********************

extraction_start_timestamps = {}
for dataset_name, dataset in data_product.datasets.items():
    dataset.refresh_delta_table_state()
    delta_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()
    extraction_start_timestamps[dataset_name] = delta_timestamp or initial_load_start_date
    print(f"{dataset_name}: extraction start = {extraction_start_timestamps[dataset_name]}")

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
