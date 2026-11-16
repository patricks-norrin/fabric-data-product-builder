# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # nb_extract_{{DATA_PRODUCT_IDENTIFIER}} — land source data in raw/
#
# Single responsibility: write source data **unchanged** to
# `Files/{{DATA_PRODUCT_IDENTIFIER}}/<dataset>/raw/<batch_id>/`. Source-specific cells implement extraction;
# `nb_cdc_{{DATA_PRODUCT_IDENTIFIER}}` creates the change history.
# Parameter: `batch_id` (empty = now, UTC `YYYYMMDDTHHMMSSZ`).

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
batch_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Imports

# CELL ********************

from datetime import datetime

import notebookutils
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
print(f"data product: {data_product.id} | datasets: {list(data_product.datasets)} | batch_id: {batch_id}")

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
