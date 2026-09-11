# Quickstart: CDC Upsert Workflow

This quickstart is based on the repository examples:

- [Example config](../examples/mdm_extract_dat1.json)
- [Example notebook](../examples/nb_mdm_extract_cdc_dat1.ipynb)

Important: the JSON file under `examples/` is a repository example. `DataProduct("mdm_extract_dat1")` will only find it after you copy that JSON into the runtime location shown in [Fabric Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#fabric-example-using-the-repository-sample-config) or [Databricks Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#databricks-example-using-the-repository-sample-config).

## Two Ways To Create The Data Product Object

### Option 1: Convention-Based Loading

Use this when the config file already exists in the Fabric or Databricks runtime location documented in [Environment Prerequisites and Conventions](environment-prerequisites-and-conventions.md).

For the checked-in sample config, use the exact destinations shown in [Fabric Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#fabric-example-using-the-repository-sample-config) or [Databricks Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#databricks-example-using-the-repository-sample-config).

```python
import lakehouse_toolbelt

data_product = lakehouse_toolbelt.DataProduct("mdm_extract_dat1")
```

### Option 2: Load The Repository Example Directly

Use this when you want to work with inline json (json contents as a string in notebook cell. This makes it easier to iterate configurations before uploading the working json to lakehouse), or there's a need to override the default location.

```python
import json
import lakehouse_toolbelt

with open("examples/mdm_extract_dat1.json", "r", encoding="utf-8") as data_product_configuration_json:
    data_product_configuration = json.load(data_product_configuration_json)

data_product = lakehouse_toolbelt.DataProduct(**data_product_configuration)
```

## Mandatory vs Utility Steps

The distinction below is important.

| Step | Mandatory for upsert to work | Why |
| --- | --- | --- |
| Load a `DataProduct` and select a `DataSet` | Yes | The dataset object carries the path and metadata configuration used by the workflow |
| Read the incoming raw data | Yes | The upsert needs a source DataFrame |
| Call `add_dpmeta_columns(...)` or provide equivalent `dpmeta_*` columns yourself | Yes | The change-history upsert relies on metadata columns such as `dpmeta_uid`, `dpmeta_payload_hash`, and `dpmeta_object_version_start_time` |
| Call `upsert_delta_change_history(...)` | Yes | This is the main write operation |
| Call `align_dataframe_to_delta_change_history_schema(...)` | No, but strongly recommended when a target table already exists | Prevents schema drift problems before the merge |
| Call `convert_timestamps(...)` | No | Utility step for normalizing raw timestamp strings |
| Use `get_delta_change_history_dpmeta_loaded_to_dataplatform()` | No | Utility step for incremental reads based on the latest processed timestamp |
| Drop duplicates before upsert | No, but often recommended | Helps prevent duplicate versions for the same entity and start time |

## Minimal Working Flow

```python
import lakehouse_toolbelt

data_product = lakehouse_toolbelt.DataProduct("mdm_extract_dat1")
dataset = data_product.customer

df_raw = (
    lakehouse_toolbelt.spark.read.format("csv")
    .option("recursiveFileLookup", "true")
    .option("header", True)
    .option("sep", ";")
    .load(dataset.file_path_raw)
)

df_with_dpmeta = lakehouse_toolbelt.add_dpmeta_columns(df_raw, dataset)
df_validated = lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema(df_with_dpmeta, dataset)

lakehouse_toolbelt.upsert_delta_change_history(
    source_dataframe=df_validated,
    dataset=dataset,
    debug_return=False,
)
```

## Notebook-Oriented Workflow

The example notebook adds a few useful utility steps on top of the minimal flow.

```python
import lakehouse_toolbelt
import pyspark.sql.functions as F

data_product = lakehouse_toolbelt.DataProduct("mdm_extract_dat1")
source_system_id = "mdm"

for dataset_name, dataset in data_product.datasets.items():
    latest_time_from_change_history = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()

    reader = (
        lakehouse_toolbelt.spark.read.format("csv")
        .option("recursiveFileLookup", "true")
        .option("header", True)
        .option("sep", ";")
    )

    if latest_time_from_change_history:
        reader = reader.option("modifiedAfter", latest_time_from_change_history)

    df_raw = reader.load(dataset.file_path_raw)

    df_raw = (
        df_raw.withColumn("dpmeta_input_file_name", F.input_file_name())
        .withColumn("dpmeta_source_system_id", F.lit(source_system_id))
    )

    if dataset.timestamp_columns_to_convert:
        df_raw = lakehouse_toolbelt.convert_timestamps(df_raw, dataset.timestamp_columns_to_convert)

    df_with_dpmeta = lakehouse_toolbelt.add_dpmeta_columns(df_raw, dataset)
    df_with_dpmeta = df_with_dpmeta.dropDuplicates(["dpmeta_uid", "dpmeta_object_version_start_time"])
    df_validated = lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema(df_with_dpmeta, dataset)

    lakehouse_toolbelt.upsert_delta_change_history(df_validated, dataset)
```

## What Is Mandatory In The Input DataFrame

If you use the standard workflow above, `add_dpmeta_columns(...)` generates the required metadata for you.

If you bypass `add_dpmeta_columns(...)` and call `upsert_delta_change_history(...)` directly, the source DataFrame must already include the metadata columns needed by the merge logic, especially:

- `dpmeta_uid`
- `dpmeta_payload_hash`
- `dpmeta_object_version_start_time`

In practice, the simplest and safest approach is to call `add_dpmeta_columns(...)` before every upsert.

## Inspecting The Result

After the upsert, inspect the versioned table by converting the Delta table handle to a DataFrame with `.toDF()` (see [API Reference — Converting A Delta Table Handle To A DataFrame](function-reference.md#converting-a-delta-table-handle-to-a-dataframe)).

```python
if dataset.delta_change_history_table:
    change_history_df = dataset.delta_change_history_table.toDF()
    change_history_df.orderBy("dpmeta_uid", "dpmeta_object_version_start_time").show()
```

## Common Failure Cases

- The config file does not exist in the expected convention-based location.
- The lakehouse name does not follow `lh_<data_product_identifier>` on Fabric.
- The source data has timestamp strings that were not converted before metadata generation.
- The target table already exists and the incoming schema does not match it.