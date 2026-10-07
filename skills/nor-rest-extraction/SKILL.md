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
- the response representations the API offers, how each is selected, and why you chose one;
- a source-specific `nb_extract_<id>` cell with direct `requests` code;
- unchanged raw files under `dataset.file_path_raw/batch_id`, each named `<logical_identifier>_<batch_id>.<extension>`;
- the direct native Spark reader expression to use at the marked line in `nb_cdc_<id>`.

Keep API authentication, headers, request values, pagination, retries, rate-limit handling, date windows, and
response-format choices in the extract cell. Do not create a connector framework, wrapper, or config schema for
these values. A stable `base_url`, `relative_url_template`, and durable `endpoint_query_parameters` may remain in
source metadata when the parameters select which dataset or schema a shared endpoint returns. Operational values,
including extraction windows, belong in the notebook. Do not define a parameter when its value is already literal
in the template (for example, do not also define `provider = "ecb"` for `/providers/ecb/`).

## Procedure

1. Read the API documentation end to end before choosing anything. Identify entity resources, natural keys,
   business timestamps, pagination, every supported response representation, and every server-side delta mechanism:
   modified/created timestamp filters, increasing keys or versions, cursors, change feeds, or equivalent query
   predicates. Look for a machine-readable
   contract first — an OpenAPI/Swagger document, or an `llms.txt` — since it enumerates formats more reliably
   than prose.
2. **Enumerate the representations before picking one.** Do not assume the format shown in the first `curl`
   example is the only one. Documentation routinely describes alternatives in a section away from the endpoint,
   and selects them with an `Accept` header rather than a visible URL change, so default examples hide them.
   Search the docs for `Accept`, `Content-Type`, `format`, `stream`, `ndjson`, `jsonl`, `.csv`, and `.parquet`.
   Write the representations you found, and the selector for each, into the dataset's notebook markdown cell.
3. **Choose for the full data volume, not the first sample.** Rank the candidates:
   1. **Line-delimited records** (NDJSON/JSONL) whenever a response can carry many records or span a date range.
      Each line is an independent object, Spark reads it natively, files split across tasks, and no `multiLine`
      is required.
   2. **A single JSON document** when the response is one small object, or the API offers nothing else. This
      needs `multiLine=True`, which makes one task read each file whole and prevents splitting.
   3. **CSV or another flat format** only when it is the sole option, or the data is genuinely rectangular. It
      discards nesting and type fidelity.

   An API that offers a streaming format for large responses is telling you which path it expects to scale.
   Prefer it even when the first sample is small.
4. Request a small representative response in the chosen representation and **verify the server honored the
   selector** by checking the response `Content-Type`. An API may ignore an unsupported `Accept` header and
   return JSON anyway; landing that under an `.ndjson` name would misdescribe the raw file. Land the exact
   returned bytes unchanged with an extension matching the confirmed `Content-Type`.
5. **Choose delta extraction whenever the API can filter.** Use one request-building path: create the base request for
   the user's scope, read `dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()`, and add the API's lower
   filter only when the latest change-history load timestamp is non-null. Without that timestamp, send the same base request unchanged to fetch all
   requested history. Do not add `first_run`, `initial_load`, `load_mode`, or equivalent parameters. If the API requires
   a lower bound and neither the user nor API documentation supplies one, stop and ask rather than inventing a date.
   A user-supplied lower bound remains open-ended unless the user also supplies or requests an upper boundary. Use a full snapshot only when the user explicitly requests one,
   explicitly requests a closed timeframe, or the API has no reliable server-side filter. Document the applicable
   exception beside the code; small volume is not an exception.
6. Write direct, readable `requests` code in the dataset's extraction cell. Call `response.raise_for_status()` and
   name every landed raw file `<logical_identifier>_<batch_id>.<extension>`; the stable logical identifier precedes
   the batch ID, and the batch folder alone is not sufficient identification. For
   incremental APIs, keep latest-change-history-load-timestamp formatting and the page/chunk loop beside the request code.
   Put user-requested fixed lower or upper extraction bounds there too, with a nearby comment stating why each bound
   was chosen and whether it was supplied by the user.
7. Inspect the completed raw batch. At the marked reader line in the common CDC loop, use direct Spark JSON reading:
   `spark.read.format("json").option("recursiveFileLookup", "true")`, which reads line-delimited JSON as is. Add
   `multiLine=True` only when the landed files are whole JSON documents or arrays. Keep the common `modifiedAfter`
   latest-change-history-load-timestamp block unchanged.
8. Use the generated CDC loop as-is: no helper wrappers, custom schemas, or `text` plus `from_json` unless evidence
   shows Spark's native reader cannot handle the landed representation. Keep any necessary exception dataset-local and
   document the observed reason.

## Splitting source metadata from run values

Nothing validates this split; it is a judgment call from the API documentation.

Keep in `source_configuration`: values that identify the dataset for every run — a stable `base_url`, a
`relative_url_template`, and `endpoint_query_parameters` that select which entity or schema a shared endpoint
returns.

Keep in the extract cell: values that change per run or per decision — extraction windows, latest change-history load timestamps,
pagination, credentials, and retry behavior.

```jsonc
// Avoid: an extraction window and a provider already fixed in the path
"source_configuration": {
  "base_url": "https://api.frankfurter.dev",
  "relative_url_template": "/v2/providers/ecb/rates?from={from_date}&to={to_date}",
   "endpoint_query_parameters": { "provider": "ecb", "load_end_date": "<fixed-end-date>" }
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
