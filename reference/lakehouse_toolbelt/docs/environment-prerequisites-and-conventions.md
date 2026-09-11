# Environment Prerequisites and Conventions

This page covers only what must be in place before the library can run. It is separated by platform.

## Common Requirements

These apply regardless of whether you run on Fabric or Databricks.

| Requirement | Why |
| --- | --- |
| Spark session available in the notebook context | All APIs operate on Spark DataFrames |
| Delta Lake support available in the Spark runtime | `DataSet` and `upsert_delta_change_history(...)` use `delta.tables.DeltaTable` |
| `lakehouse-toolbelt` wheel installed in the environment | The package is imported as `import lakehouse_toolbelt` |

### How Runtime Detection Works

The library auto-detects the platform at import time using environment variables:

- **Fabric** is detected when the `AZURE_SERVICE` environment variable exists.
- **Databricks** is detected when the `DATABRICKS_RUNTIME_VERSION` environment variable exists.

If neither variable is set, convention-based config loading via `DataProduct("<id>")` will not work. You can still instantiate `DataProduct(**data_product_configuration)` with explicit keyword arguments.

---

## Microsoft Fabric

### Required Environment Setup

| Requirement | Details |
| --- | --- |
| Fabric notebook runtime | The `AZURE_SERVICE` environment variable must be present (set automatically by Fabric) |
| `notebookutils` available | Imported automatically when running on Fabric; used for path resolution and access tokens |
| Workspace shared-resources lakehouse | A lakehouse named `lh_workspace_shared_resources` must exist in the current workspace |

### Fabric Convention-Based Config File Location

`DataProduct("<id>")` resolves the data product JSON definition from:

```text
abfss://<workspace_name>@onelake.dfs.fabric.microsoft.com/
└── lh_workspace_shared_resources.Lakehouse/
  └── Files/
    └── configuration/
      └── data_product/
        └── <data_product_identifier>/
          └── <data_product_identifier>.json
```

The workspace name is read at runtime from `notebookutils.runtime.context["currentWorkspaceName"]`.

#### Fabric Example Using The Repository Sample Config

If you want `DataProduct("mdm_extract_dat1")` to load the checked-in sample config from [examples/mdm_extract_dat1.json](../examples/mdm_extract_dat1.json), copy that JSON file to:

```text
abfss://contoso_workspace@onelake.dfs.fabric.microsoft.com/
└── lh_workspace_shared_resources.Lakehouse/
  └── Files/
    └── configuration/
      └── data_product/
        └── mdm_extract_dat1/
          └── mdm_extract_dat1.json
```

Replace `contoso_workspace` with the current Fabric workspace name.

### Lakehouse Naming Convention

Each data product requires a dedicated lakehouse named:

```
lh_<data_product_identifier>
```

The library verifies that this lakehouse exists under the current workspace. If it does not, `DataProduct(...)` raises an exception.

The generated path prefix for all dataset paths is:

```
abfss://<workspace_name>@onelake.dfs.fabric.microsoft.com/lh_<data_product_identifier>.Lakehouse/Files
```

### Schema-Enabled vs Non-Schema-Enabled Lakehouses

Fabric lakehouses can be schema-enabled. The library detects this by checking whether a `dbo` path exists under `Tables`.

| Lakehouse type | Change-history table location |
| --- | --- |
| Schema-enabled | `.../Tables/<data_product_identifier>/<dataset_name>` |
| Non-schema-enabled | `.../Files/<data_product_identifier>/<dataset_name>/change_history` |

This detection happens automatically during `DataSet` initialization.

### Required Permissions

| Permission | Why |
| --- | --- |
| Read access to `lh_workspace_shared_resources` | Config file resolution |
| Read/write access to `lh_<data_product_identifier>` | Reading raw data and writing change-history Delta tables |

---

## Databricks

### Required Environment Setup

| Requirement | Details |
| --- | --- |
| Databricks notebook runtime | The `DATABRICKS_RUNTIME_VERSION` environment variable must be present (set automatically by Databricks) |
| DBFS mount at `/mnt/datalake` | The config file path convention assumes this mount exists |

### Databricks Convention-Based Config File Location

`DataProduct("<id>")` resolves the data product JSON definition from:

```text
/dbfs/
└── mnt/
    └── datalake/
        └── config/
            └── <data_product_identifier>/
                └── <data_product_identifier>_data_product.json
```

If the file is not found at this path, `DataProduct(...)` raises an exception.

#### Databricks Example Using The Repository Sample Config

If you want `DataProduct("mdm_extract_dat1")` to load the checked-in sample config from [examples/mdm_extract_dat1.json](../examples/mdm_extract_dat1.json), copy that JSON file to:

```text
/dbfs/
└── mnt/
    └── datalake/
        └── config/
            └── mdm_extract_dat1/
                └── mdm_extract_dat1_data_product.json
```

The Databricks runtime filename must be `mdm_extract_dat1_data_product.json`, even though the repository example file is named `mdm_extract_dat1.json`.

### Path Prefix

> **Important:** In the current implementation, the Databricks path prefix returned by `DataProduct._return_path_prefix()` is hardcoded to a specific `abfss://` storage account URL. Review and update this before using the library in a new Databricks environment.

### Required Permissions

| Permission | Why |
| --- | --- |
| Read access to `/dbfs/mnt/datalake/config/` | Config file resolution |
| Read/write access to the storage account behind the path prefix | Reading raw data and writing change-history Delta tables |

---

## Bypassing Convention-Based Loading

If you cannot or do not want to set up the convention-based config locations above, you can load the JSON yourself and pass it as keyword arguments. For example, you can work directly from the checked-in sample config:

```python
import json
import lakehouse_toolbelt

with open("examples/mdm_extract_dat1.json", "r", encoding="utf-8") as data_product_configuration_json:
  data_product_configuration = json.load(data_product_configuration_json)

data_product = lakehouse_toolbelt.DataProduct(**data_product_configuration)
```

This skips all platform-specific config resolution. You still need a Spark session and Delta Lake support for the downstream workflow to work.