---
name: nor-rest-extraction
description: Extract a REST API into a Norrin source-aligned Fabric data product using a source-specific notebook cell. Use when a source system exposes HTTP API resources that must land unchanged in raw/ before the standard lakehouse_toolbelt CDC notebook.
---

# nor-rest-extraction

Use this skill only for REST APIs. It owns HTTP-specific decisions; do not add them to the shared data-product
JSON or notebook templates.

## Inputs and outputs

Read the API documentation and inspect a small representative response when access permits. For each API resource
that represents a retained entity, provide:

- a dataset name, natural key, and optional business version timestamp for the minimal data-product JSON;
- a source-specific `nb_extract_<id>` cell with direct `requests` code;
- unchanged raw files under `dataset.file_path_raw/batch_id`;
- the direct native Spark reader expression to use at the marked line in `nb_cdc_<id>`.

Keep API authentication, headers, request values, pagination, retries, rate-limit handling, date windows, and
response-format choices in the extract cell. Do not create a connector framework, wrapper, or config schema for
these values. A stable `base_url`, `relative_url_template`, and durable `endpoint_query_parameters` may remain in
source metadata when the parameters select which dataset or schema a shared endpoint returns. Operational values,
including extraction windows, belong in the notebook. Do not define a parameter when its value is already literal
in the template (for example, do not also define `provider = "ecb"` for `/providers/ecb/`).

## Procedure

1. Read the API documentation. Identify entity resources, natural keys, business timestamps, pagination, and supported
   response representations.
2. Request a small representative response. If the API offers more than one representation, inspect viable choices and
   choose the one Spark reads with the least special handling. Land the exact returned bytes unchanged with a matching
   extension.
3. Write direct, readable `requests` code in the dataset's extraction cell. Call `response.raise_for_status()`. For
   incremental APIs, get the prior watermark with
   `dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()` and keep any first-load value, request date
   formatting, and page/chunk loop beside the request code. Put fixed lower or upper extraction bounds there too,
   with a nearby comment stating why each bound was chosen and whether it was supplied by the user.
4. Inspect the completed raw batch. At the marked reader line in the common CDC loop, use direct Spark JSON reading:
   `spark.read.format("json").option("recursiveFileLookup", "true")`. Add `multiLine=True` only when the landed files
   are whole JSON documents or arrays. Keep the common `modifiedAfter` watermark block unchanged.
5. Use the generated CDC loop as-is: no helper wrappers, custom schemas, or `text` plus `from_json` unless evidence
   shows Spark's native reader cannot handle the landed representation. Keep any necessary exception dataset-local and
   document the observed reason.

## Splitting source metadata from run values

Nothing validates this split; it is a judgment call from the API documentation.

Keep in `source_configuration`: values that identify the dataset for every run — a stable `base_url`, a
`relative_url_template`, and `endpoint_query_parameters` that select which entity or schema a shared endpoint
returns.

Keep in the extract cell: values that change per run or per decision — extraction windows, watermarks,
pagination, credentials, and retry behavior.

```jsonc
// Avoid: an extraction window and a provider already fixed in the path
"source_configuration": {
  "base_url": "https://api.frankfurter.dev",
  "relative_url_template": "/v2/providers/ecb/rates?from={from_date}&to={to_date}",
  "endpoint_query_parameters": { "provider": "ecb", "load_end_date": "2025-12-31" }
}

// Prefer: the template carries the structure, the notebook supplies the dates
"source_configuration": {
  "base_url": "https://api.frankfurter.dev",
  "relative_url_template": "/v2/providers/ecb/rates?from={from_date}&to={to_date}"
}

// Also correct: one endpoint serving several datasets needs the selector in config
"source_configuration": {
  "base_url": "https://api.example.com",
  "relative_url_template": "/v1/entities?schema={schema}",
  "endpoint_query_parameters": { "schema": "customers" }
}
```

## References

- [Spark Data Sources](https://spark.apache.org/docs/latest/sql-data-sources.html)
- [Generic File Source Options](https://spark.apache.org/docs/latest/sql-data-sources-generic-options.html) for
  `recursiveFileLookup` and `modifiedAfter`
- [JSON Files](https://spark.apache.org/docs/latest/sql-data-sources-json.html) for JSON Lines and `multiLine`

Spark's `/latest/` documentation can be ahead of the active Fabric runtime. Verify an uncertain option against the
runtime before depending on it.
