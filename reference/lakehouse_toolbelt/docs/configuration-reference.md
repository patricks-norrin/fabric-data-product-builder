# Configuration Reference

This page documents the JSON structure used by `DataProduct(...)` and the dataset-level attributes consumed by the library.

## Example Shape

The repository example in [examples/mdm_extract_dat1.json](../examples/mdm_extract_dat1.json) follows this structure:

To load that sample through `DataProduct("mdm_extract_dat1")`, copy it to the runtime location shown in [Fabric Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#fabric-example-using-the-repository-sample-config) or [Databricks Example Using The Repository Sample Config](environment-prerequisites-and-conventions.md#databricks-example-using-the-repository-sample-config).

```json
{
  "domain": "academy",
  "data_product_identifier": "mdm_extract_dat1",
  "datasets": [
    {
      "dataset_name": "customer",
      "unique_identifier_columns": ["customer_id"],
      "exclude_columns_from_payload_checksum": [],
      "timestamp_columns_to_convert": [],
      "object_version_timestamp_column": "",
      "source_configuration": {}
    }
  ]
}
```

## Top-Level Data Product Attributes

| Attribute | Status | Used by | Notes |
| --- | --- | --- | --- |
| `data_product_identifier` | Mandatory | `DataProduct`, path generation, lakehouse naming | Also drives the config lookup folder and Fabric lakehouse name |
| `domain` | Mandatory in config-file-based loading | `DataProduct`, `DataSet` | Stored on the objects and required by the current config-file loading path |
| `datasets` | Mandatory | `DataProduct` | A list of dataset definitions that will become `DataSet` objects |
| `sub_domain` | Optional | `DataProduct` | Stored on the object, but not currently used in dataset path generation |

## Dataset Attributes

The table below makes the distinction between attributes that are mandatory for the standard upsert workflow and utility attributes that support convenience or downstream behavior.

| Attribute | Status | Used by | Notes |
| --- | --- | --- | --- |
| `dataset_name` | Mandatory | `DataSet`, path generation | Used in all derived dataset paths |
| `unique_identifier_columns` | Mandatory | `add_dpmeta_uid(...)`, `add_dpmeta_columns(...)` | Required to build `dpmeta_uid` |
| `exclude_columns_from_payload_checksum` | Optional | `add_dpmeta_payload_hash(...)` | Use when some columns should not affect change detection |
| `object_version_timestamp_column` | Optional but strongly recommended for CDC correctness | `add_dpmeta_object_version_start_time(...)` | If missing or empty, version start time falls back to a supplied custom timestamp or current UTC time |
| `schema_compatibility_mode` | Optional | `align_dataframe_to_delta_change_history_schema(...)` | Defaults to `merge_safe` |
| `timestamp_columns_to_convert` | Utility | `convert_timestamps(...)` | Helpful when raw timestamps arrive as strings |
| `object_version_number_column` | Utility | `add_dpmeta_object_versioning_columns(...)` | Copies a source version number into `dpmeta_object_version_number` when configured |
| `source_configuration` | Utility | `SourceConfiguration` | Stores source-related metadata. Can be configured for project-specific needs  |
| `publish_configuration` | Utility | `PublishConfiguration` | Stores publish-related metadata. Can be configured for project-specific needs |
| `merge_strategy` | Utility placeholder | `DataSet` only | Stored on the object, but not used by the current upsert implementation |


### Source Configuration
Source configuration accept both default (set for the class as a class attribute) and project-specific attributes.
Defaults include: ["source_schema", "source_table", "filter_string", "base_url", "relative_url_template", "endpoint_query_parameters"]

<b>Use of default attributes: </b>
<i>Example 1:</i> Use "source_schema" and "source_table" to detail (database) information for extraction.

```python

#Data product configuration file:
"source_configuration": { 
  "source_schema": "APPS" , 
  "source_table": "INVOICES_ALL"
}

#Use in a notebook:
mdm_extract_dat1 = DataProduct("mdm_extract_dat1")

query = f"""
SELECT *
FROM {mdm_extract_dat1.customer.source_configuration.source_schema}.{mdm_extract_dat1.customer.source_configuration.source_table}
"""

df = spark.sql(query)
```

<i>Example 2:</i> Use "filter_string" with Spark's reader to select files to be included. 

```python

#Data product configuration file:
"source_configuration": { 
  "filter_string": "*.csv" 
}

#Use in a notebook:
mdm_extract_dat1 = DataProduct("mdm_extract_dat1")

df = (
    spark.read
    .format("csv")
    .option("header", "true")
    .option("recursiveFileLookup", "true")
    .option("pathGlobFilter", mdm_extract_dat1.customer.source_configuration.filter_string)
    .load(base_path)
)
```

<i>Example 3:</i> Use base_url, relative_url_template, and endpoint_query_parameters for API endpoints. Static endpoint values can be defined in data product configuration, while runtime values, such as dates, can be passed at execution time.

```python

#Data product configuration file:
"source_configuration": {
  "base_url": "https://www.norrin.com",
  "relative_url_template": "/{api_resource}?start_date={start_date}&status={status}",
  "endpoint_query_parameters": {
    "api_resource": "customer",
    "status": "active",
    "initial_load_start_date": "2020-01-01"
  }
}

#Use in a notebook:
import requests

mdm_extract_dat1 = DataProduct("mdm_extract_dat1")

parameters = {
  **mdm_extract_dat1.customer.source_configuration.endpoint_query_parameters,
  "start_date": (
    mdm_extract_dat1.customer.get_delta_change_history_dpmeta_loaded_to_dataplatform()
    or mdm_extract_dat1.customer.source_configuration.endpoint_query_parameters["initial_load_start_date"]
  )
}

url = (
  mdm_extract_dat1.customer.source_configuration.base_url
  + mdm_extract_dat1.customer.source_configuration.relative_url_template.format(**parameters)
)

response = requests.get(url)
response.raise_for_status()

payload = response.json()
```

### Publish Configurations
Publish configuration accept both default (set for the class as a class attribute) and project-specific attributes. Defaults include: ["active", "included_columns"] 

<b>Use of default attributes: </b>

<i>Example 1:</i> Use "active" to defined whether the dataset is included in the published data product.
```python

#Data product configuration file:
"publish_configuration": { "active": true}

#Use in a notebook:
def get_publishable_datasets(datasets: list[Dataset]) -> list[Dataset]:
    return [
        dataset
        for dataset in data_product.datasets
        if dataset.publish_configuration and dataset.publish_configuration.active
    ]

```


<i>Example 2:</i> Use "included_columns" to specify which columns from the dataset to include in the published data product. Recommended use: if included columns is empty, use all columns.

```python

#Data product configuration file:
"publish_configuration": { 
  "included_columns": ["name","id"]
  }

#Use in a notebook:
def publish_datasets(datasets: list[Dataset], spark):
    for dataset in datasets:
        pc = dataset.publish_configuration

        # 1. skip if not active
        if not dataset.publish_configuration or not dataset.publish_configuration.active:
            continue

        # 2. apply column filtering
        if dataset.publish_configuration.included_columns:
            df = df.select(*dataset.publish_configuration.included_columns)

        # 3. write published dataset
        df.write.mode("overwrite").save(<path-to-published-dataset>)

```

### Project-specific configuration
Additional attributes can be set for both source and publish configurations. Attributes mentioned in this file will be promoted to attributes of the respective class.

<b>Fabric:</b> Toolbelt expects to find file "project_configuration.json" in "lh_workspace_shared_resources/Files/configuration/data_product/project_configuration"
<b>Databricks</b>: Not implemented

See also [Configuration Validator](configuration-validator.md)

#### Example
```json
{
  "source_configuration": {
    "allowed_extra_attributes": [
      "pagination_type", "watermark_delay_minutes", "initial_load_date"
    ]
  },
  "publish_configuration": {
    "allowed_extra_attributes": [
      "history_included", "confidential_columns_included"
    ]
  }
}
```

## Mandatory Minimum For The Standard Upsert Workflow

For the standard config-driven workflow to work, the practical minimum is:

```json
{
  "domain": "academy",
  "data_product_identifier": "mdm_extract_dat1",
  "datasets": [
    {
      "dataset_name": "customer",
      "unique_identifier_columns": ["customer_id"]
    }
  ]
}
```

For historical correctness in CDC scenarios, add `object_version_timestamp_column` as soon as the source provides a reliable business timestamp.





## Attributes In The Example That Are Not Currently Consumed By The Package

The example config includes `personal_data_columns`, but the current package implementation does not read or act on that key.

That means:

- It can exist in the JSON as pipeline-specific metadata.
- It should not be documented as part of the current `lakehouse-toolbelt` functional API.
- Unknown extra keys are effectively ignored unless your surrounding pipeline reads them separately.

## Related Pages

- [Environment Prerequisites and Conventions](environment-prerequisites-and-conventions.md)
- [Quickstart: CDC Upsert Workflow](quickstart-cdc-upsert.md)
- [API Reference](function-reference.md)
- [Configuration Validator](configuration-validator.md)