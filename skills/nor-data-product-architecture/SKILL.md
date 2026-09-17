---
name: nor-data-product-architecture
description: "Norrin architecture for Microsoft Fabric data products. Use before designing, naming or creating anything: deciding data product boundaries (one source system is one product, datasets inside), lakehouse and workspace responsibilities (ws_extract, lh_<id>, lh_workspace_shared_resources), raw-as-insurance landing, when CDC change history applies versus snapshot or non-tabular exceptions, naming and folder conventions."
---

# Norrin data product architecture — decision rules

Read the long form only when a rule below does not settle the question. These paths are relative to this
file's own directory, inside the installed toolpack — not to the consuming project:
- `../../reference/architecture/data-product-architecture.md` — the why (source-aligned vs consumer-aligned: Foundational/Business/Analytical, CDC default, exceptions)
- `../../reference/architecture/workspace-and-lakehouse-responsibilities.md` — workspace patterns, shortcuts, metadata columns
- `../../reference/architecture/naming-and-folder-conventions.md` + `conventions.json` — checkable rules
- `../../reference/lakehouse_toolbelt/docs/` and `../../reference/lakehouse_toolbelt/examples/` — runtime contract and canonical implementation patterns. Read the relevant documentation and sample before authoring a notebook; implement that pattern for the source instead of designing a replacement.

## 1. Boundaries
- **One source system = one source-aligned data product** = one `data_product_identifier` = one lakehouse `lh_<id>` = one config file. An exchange-rate API is one product with datasets such as `exchange_rates` and `currencies`; the rate provider is a column, not a product boundary.
- A **dataset** is one logical entity from the source (an endpoint, a table, a file type). Each dataset needs a business key (`unique_identifier_columns`, composite allowed).
- Everything else is **consumer-aligned**: Foundational (one business concept, e.g. `customer`, `exchange_rates` —
  low value alone, valuable through reuse across many models), Business (combines multiple Foundational bricks,
  typically facts + dimensions), and optional Analytical on top. These live in domain workspaces, are modeled
  with the business, and are **out of scope for this toolpack** (which builds source-aligned only) — see
  `../../reference/architecture/data-product-architecture.md` for the full definitions before answering any
  question about them.

## 2. Source-aligned product contents
raw files (original format, per batch) + change-history Delta tables + config + `nb_extract_<id>` + `nb_cdc_<id>` (+ optional `pl_<id>`), all inside workspace folder `<id>`.

## 3. Raw is insurance
Land exactly what the source returned: `Files/<id>/<dataset>/raw/<YYYYMMDDTHHMMSSZ>/<file>`. Keep API payload format (JSON/NDJSON), database exports as parquet/csv. Never rename columns, cast types or filter before landing. Reprocessing history = re-reading raw.

## 4. CDC is the default
Every tabular dataset goes through `lakehouse_toolbelt` SCD2 (`Tables/<id>/<dataset>`). Exceptions (last resort, must be written into the config `source_configuration` as a note): no possible unique identifier; mandatory sub-second streaming pass-through; truly static generated data. Non-tabular assets (images, PDFs) skip CDC and are stored under `Files/<id>/<asset_type>/`.

## 5. Keys and versions
- Choose `unique_identifier_columns` as the smallest natural key that is unique **within one batch** (verify against real data before committing).
- Set `object_version_timestamp_column` when the source has a reliable business timestamp; otherwise leave empty (toolbelt uses load time).
- Timestamp strings → `timestamp_columns_to_convert`. Volatile columns that must not trigger a new version → `exclude_columns_from_payload_checksum`.

## 6. Source metadata in config
Put a stable `base_url` in `source_configuration`. When the endpoint is the dataset name, the notebook uses `f"{base_url}/{dataset_name}"`. Use `relative_url_template` only when the endpoint path or query must vary between calls, such as from/to timestamps, paging, or several endpoint attributes. Keep template values, reader settings, authentication, and all source-specific behavior in notebook code. Do not use `endpoint_query_parameters`, reader-option extras, or `project_configuration.json` for a standard data product.

## 7. Incremental by convention
Extract pulls from the last `get_delta_change_history_dpmeta_loaded_to_dataplatform()` (or an initial date declared in the extraction notebook); CDC reads raw with `modifiedAfter` that same timestamp and wraps `.load()` in try/except for "Unable to infer schema" (no new files).
