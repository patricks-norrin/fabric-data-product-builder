# API Reference

Single-page reference for all classes, functions, properties, and patterns in `lakehouse-toolbelt`.

---

## DataProduct

`DataProduct(...)` loads a data product definition and constructs one `DataSet` object per dataset entry.

**Construction:**

| Signature | When to use |
| --- | --- |
| `DataProduct("<id>")` | Convention-based loading from the platform config location |
| `DataProduct(**config_dict)` | Explicit loading from a dict (e.g. parsed JSON) |

**Properties after construction:**

| Property | Type | Description |
| --- | --- | --- |
| `id` | `str` | The `data_product_identifier` |
| `domain` | `str` | Domain label from the config |
| `datasets` | `dict[str, DataSet]` | All datasets keyed by `dataset_name` |
| `<dataset_name>` | `DataSet` | Direct attribute access, e.g. `data_product.customer` |

**Iterating over datasets:**

```python
data_product = lakehouse_toolbelt.DataProduct("mdm_extract_dat1")

# Loop through all datasets
for dataset_name, dataset in data_product.datasets.items():
    print(f"{dataset_name}: {dataset.file_path_raw}")

# Access a single dataset by name via the dict
customer_dataset = data_product.datasets["customer"]

# Or use direct attribute access (equivalent)
customer_dataset = data_product.customer
```

---

## DataSet

Each `DataSet` carries dataset-specific configuration, generated paths, and Delta table handles.

### Path Properties

When a `DataProduct` is initialized, each dataset path is derived as:

```
<path_prefix>/<data_product_identifier>/<dataset_name>/<layer>
```

| Property | Pattern | What it contains | Required for upsert |
| --- | --- | --- | --- |
| `file_path_raw` | `…/<dataset_name>/raw` | Landed raw source files (CSV, JSON, etc.) | Yes for file-based ingestion |
| `file_path_raw_delta` | `…/<dataset_name>/raw_delta` | Delta-formatted raw data, if the pipeline creates it | No |
| `file_path_checkpoint` | `…/<dataset_name>/checkpoint` | Streaming or incremental reader checkpoints | No |
| `file_path_change_history` | `…/<dataset_name>/change_history` or `…/Tables/<dp_id>/<dataset_name>` | The versioned change-history Delta table | Yes |

> The change-history path depends on whether the Fabric lakehouse is schema-enabled. See [Environment Prerequisites — Schema-Enabled Lakehouses](environment-prerequisites-and-conventions.md#schema-enabled-vs-non-schema-enabled-lakehouses).

### Delta Table Handles

Two `DeltaTable` handles are set during initialization and refreshed by `refresh_delta_table_state()`:

| Property | Points to | Value when the table does not exist |
| --- | --- | --- |
| `delta_raw_table` | `file_path_raw_delta` | `None` |
| `delta_change_history_table` | `file_path_change_history` | `None` |

#### Converting A Delta Table Handle To A DataFrame

Use `.toDF()` to get a Spark DataFrame from a `DeltaTable` handle.

```python
import lakehouse_toolbelt

data_product = lakehouse_toolbelt.DataProduct("mdm_extract_dat1")
dataset = data_product.customer

# Inspect the change-history table
if dataset.delta_change_history_table:
    df = dataset.delta_change_history_table.toDF()
    df.show()

# Inspect the raw Delta table
if dataset.delta_raw_table:
    df = dataset.delta_raw_table.toDF()
    df.printSchema()
```

Use `.toDF()` when you want DataFrame operations (filter, join, aggregation). Keep the `DeltaTable` object when you need Delta-specific APIs like merge, history, or vacuum.

### DataSet Methods

| Method | Purpose | Typical use |
| --- | --- | --- |
| `refresh_delta_table_state()` | Re-checks whether the Delta tables exist and reloads the handles | Called automatically after `upsert_delta_change_history(...)`. Call manually when tables are created or modified outside the standard workflow. |
| `get_delta_change_history_dpmeta_loaded_to_dataplatform()` | Returns the latest `dpmeta_loaded_to_dataplatform` timestamp from the change-history table | Incremental file reads using `modifiedAfter` or similar reader options |

---

## Standard Workflow Functions

These are the functions most users call directly.

| Function | Mandatory | Purpose |
| --- | --- | --- |
| `add_dpmeta_columns(dataframe, dataset, custom_version_timestamp_column=None)` | Yes | Adds metadata columns required for change-history processing |
| `align_dataframe_to_delta_change_history_schema(source_dataframe, dataset)` | No, but strongly recommended | Aligns incoming columns to the existing change-history table and enforces the selected compatibility mode |
| `upsert_delta_change_history(source_dataframe, dataset, debug_return=False)` | Yes | Default: creates or updates the versioned change-history Delta table. Debug mode: returns planned intermediates without writing. |
| `full_load_end_missing_rows(source_dataframe, dataset, allow_empty_source=False)` | Full-snapshot loads only | Soft-deletes active rows whose `dpmeta_uid` is absent from the source. Call AFTER `upsert_delta_change_history(...)` |

### What Is Mandatory Before Calling `upsert_delta_change_history(...)`

At minimum, the source DataFrame must contain:

- `dpmeta_uid`
- `dpmeta_payload_hash`
- `dpmeta_object_version_start_time`

The recommended path is:

1. Build or load a `DataSet`.
2. Call `add_dpmeta_columns(...)`.
3. Optionally call `align_dataframe_to_delta_change_history_schema(...)`.
4. Call `upsert_delta_change_history(...)`.

### Debugging The Upsert

`upsert_delta_change_history(..., debug_return=True)` is a no-write dry run mode.

Behavior in debug mode:

- No merge is executed when the change-history table already exists.
- No initial table creation is executed when the change-history table does not yet exist.
- A dictionary of intermediate DataFrames is returned with keys:
    - `current_state_of_incoming_data`
    - `filtered_current_state_of_incoming_data`
    - `filtered_incoming_data`
    - `combined_new_data_and_current_state`

Use this when you want to inspect:

- current matching rows from the target table
- filtered incoming rows
- the combined versioned result that would be merged or written

### Ending Rows Missing From A Full-Snapshot Source

`full_load_end_missing_rows(source_dataframe, dataset, allow_empty_source=False)` closes off active rows in the change-history table whose `dpmeta_uid` is not present in `source_dataframe`. Affected rows get `dpmeta_object_version_end_time` set to `current_timestamp()` and `dpmeta_is_current` set to `False`. It is a no-op when the change-history table does not yet exist.

Call it AFTER `upsert_delta_change_history(...)` and only when the source is a full snapshot of the dataset. Partial / incremental / CDC loads will incorrectly end rows that simply were not part of the batch.

By default the function refuses to operate on an empty `source_dataframe` to protect against the common failure mode where an empty source comes from a failed extract or an over-eager filter and would otherwise wipe the entire active set. Pass `allow_empty_source=True` to opt-in to the "snapshot is legitimately empty, end every active row" behaviour.

---

## Utility Functions

`add_dpmeta_columns(...)` is the main metadata function. Internally it applies the utility functions below in sequence. These functions can also be called directly in special cases, e.g. when only some metadata columns are needed for an inbound dataset.

| Function | Usually called by | Purpose | Call directly when |
| --- | --- | --- | --- |
| `add_dpmeta_uid(dataframe, uid_columns)` | `add_dpmeta_columns(...)` | Builds `dpmeta_uid` from the configured business key columns | You only want the UID and not the full metadata set |
| `add_dpmeta_payload_hash(dataframe, columns_excluded_from_payload_hash=[])` | `add_dpmeta_columns(...)` | Computes a payload checksum used for change detection | You want to debug or customize hash behavior |
| `add_dpmeta_uid_hash(dataframe, uid_columns)` | `add_dpmeta_columns(...)` | Creates a base64-encoded hash-like representation of `dpmeta_uid` | You need that column separately |
| `add_dpmeta_loaded_timestamp(dataframe)` | `add_dpmeta_columns(...)` | Adds the current UTC load timestamp | You are assembling metadata in smaller steps |
| `add_dpmeta_object_version_start_time(dataframe, dataset, custom_version_timestamp_column=None)` | `add_dpmeta_columns(...)` | Chooses the best available start time for the row version | You need fine-grained control over version-start generation |
| `add_dpmeta_object_versioning_columns(dataframe, dataset)` | `add_dpmeta_columns(...)` | Adds end-time, current-row, and optional version-number metadata columns | You are building the metadata incrementally |
| `convert_timestamps(dataframe, timestamp_columns)` | Notebook or pipeline code | Converts configured columns to Spark timestamps | Raw files deliver timestamp values as strings |

---

## Internal Helpers

`align_dataframe_to_delta_change_history_schema(...)` internally relies on helper utilities that strip schema metadata before comparison. Those helpers are implementation details, not part of the standard workflow API surface.