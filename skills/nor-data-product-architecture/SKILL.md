---
name: nor-data-product-architecture
description: "Norrin architecture for Microsoft Fabric data products. Use before designing, naming or creating anything: deciding data product boundaries (one source system is one product, datasets inside), lakehouse and workspace responsibilities (ws_extract, lh_<id>, lh_workspace_shared_resources), raw-as-insurance landing, when CDC change history applies versus snapshot or non-tabular exceptions, naming and folder conventions, and pipeline orchestration and scheduling."
---

# Norrin data product architecture — decision rules

Read the long form only when a rule below does not settle the question. These paths are relative to this
file's own directory, inside the installed toolpack — not to the consuming project:
- `../../reference/architecture/data-product-architecture.md` — the why (source-aligned vs consumer-aligned: Foundational/Business/Analytical, CDC default, exceptions)
- `../../reference/architecture/workspace-and-lakehouse-responsibilities.md` — workspace patterns, shortcuts, metadata columns
- `../../reference/architecture/naming-and-folder-conventions.md` + `conventions.json` — checkable rules
- `../../reference/lakehouse_toolbelt/docs/` and `../../reference/lakehouse_toolbelt/examples/` — runtime contract and canonical implementation patterns. Read the relevant documentation and sample before authoring a notebook; implement that pattern for the source instead of designing a replacement.

## 1. Boundaries
- **One source system = one source-aligned data product** = one `data_product_identifier` = one lakehouse `lh_<id>` = one config file. Name the identifier for the actual provider or system, not the business subject: Frankfurter is `frankfurter_api`, with `exchange_rates` and `currencies` as datasets. A rate provider is a product boundary; a provider returned as a value inside one source is a column.
- A **dataset** is one logical entity from the source (an endpoint, a table, a file type). Each dataset needs a business key (`unique_identifier_columns`, composite allowed).
- Everything else is **consumer-aligned**: Foundational (one business concept, e.g. `customer`, `exchange_rates` —
  low value alone, valuable through reuse across many models), Business (combines multiple Foundational bricks,
  typically facts + dimensions), and optional Analytical on top. These live in domain workspaces and are modeled
  with the business. Load `nor-data-product-modelling` for Foundational and Business notebook structure,
  business-rule, contract, datatype, and relationship conventions. End-to-end orchestration remains limited to
  source-aligned products in the current `nor-data-product-builder` agent.

## 2. Source-aligned product contents
raw files (original format, per batch) + change-history Delta tables + config + `nb_extract_<id>` + `nb_cdc_<id>` + `pl_<id>` (extract → CDC), all inside workspace folder `<id>`.

## 3. Raw is insurance
Land exactly what the source returned: `Files/<id>/<dataset>/raw/<YYYYMMDDTHHMMSSZ>/<logical_identifier>_<batch_id>.<extension>`. The stable logical identifier comes first, and the filename's `<batch_id>` must match its parent batch folder so the file remains attributable outside that folder. Keep API payload format (JSON/NDJSON); export relational tables as Parquet snapshots or incremental slices, never CSV. Never rename columns, cast types, or filter before landing. Reprocessing history = re-reading raw.

## 4. CDC is the default
Every tabular dataset goes through `lakehouse_toolbelt` SCD2 (`Tables/<id>/<dataset>`). Exceptions are last resort: no possible unique identifier, mandatory sub-second streaming pass-through, or truly static generated data. Document the exception and its rationale in the relevant extraction or CDC notebook markdown cell, never in the data-product config. Non-tabular artifacts, including binary files, skip CDC but are still stored unchanged under `Files/<id>/<dataset>/raw/<YYYYMMDDTHHMMSSZ>/`.

## 5. Keys and versions
- Choose `unique_identifier_columns` as the smallest natural key that is unique **within one batch** (verify against real data before committing).
- Set `object_version_timestamp_column` when the source has a reliable business timestamp; otherwise leave empty (toolbelt uses load time).
- Timestamp strings may be converted after raw read through `timestamp_columns_to_convert` and the standard `lakehouse_toolbelt.convert_timestamps(...)` step, before CDC metadata is added. Volatile columns that must not trigger a new version → `exclude_columns_from_payload_checksum`.

## 6. Minimal shared config
The data-product JSON is a small iterable handoff for extraction implementations (notebook or pipeline) and CDC. Standard datasets need only their name, natural key, and optional version/timestamp metadata. Keep credentials, queries, request values, pagination, reader options, and operational extraction behavior beside the extracting code, where the decision can be documented and replaced later by a catalog.

`lakehouse_toolbelt` accepts source metadata such as `source_schema`, `source_table`, `filter_string`, `base_url`, `relative_url_template`, and `endpoint_query_parameters`. These remain compatible when a consuming implementation needs them; they are not a prescribed standard or a connector framework. Durable endpoint parameters may distinguish datasets or schemas returned by one endpoint. Operational request values and extraction windows belong beside the extraction code where their rationale can be documented.

## 7. Incremental by convention
Source-side delta extraction is the default, not an optional optimization. First inspect the source for modified/created timestamp filters, increasing keys or versions, cursors, change feeds, or equivalent query predicates. Use one implementation in every environment:
1. Build the base request for the user's requested scope.
2. Read `get_delta_change_history_dpmeta_loaded_to_dataplatform()`.
3. When it returns a latest change-history load timestamp, add the corresponding source-side lower filter.
4. When no latest change-history load timestamp exists, execute the base request unchanged to ingest all requested history.

Do not add `first_run`, `initial_load`, `load_mode`, or equivalent mode parameters. If an unscoped base request is not allowed, use the source's documented earliest value; if no objective value exists, ask the user rather than inventing one. CDC reads raw with `modifiedAfter` and wraps `.load()` in try/except for "Unable to infer schema" (no new files).

Fall back to full snapshots only when (1) the user explicitly asks for snapshots, (2) the user explicitly requests a closed interval, or (3) source documentation and inspection establish that no reliable incremental filter exists. Document which exception applies beside the extraction code. A lower bound alone remains open-ended and continues incrementally; only an explicit upper boundary makes the requested interval closed. Never invent a boundary the user did not provide.

## 8. Orchestration
Pipelines own orchestration and scheduling. Author them with `nor-pipeline-author`.
1. **More than one notebook or activity = one pipeline** named `pl_<id>` in the product folder. A source-aligned product always has one: `nb_extract_<id>` → `nb_cdc_<id>`.
2. **Schedule pipelines, never notebooks.** A single-notebook product gets a `pl_<id>` once it needs a schedule. Do not chain product notebooks with `notebookutils.notebook.run()`.
3. **Master pipelines orchestrate business data products.** They call the pipelines of the products they depend on (`InvokePipeline`), never another product's notebooks, so each product keeps owning its own steps.
4. **Failures stay visible.** Connect activities with `Succeeded`. A failed activity must fail the pipeline: no `Completed` dependencies that run the next step anyway, and no failure branches that end in success. External monitoring alerts continuous services from pipeline run status; it is outside this toolpack and only works when failures are not swallowed.
5. **Sane defaults, otherwise minimal.** Notebook activities time out after 2 hours, retry once, and share one high-concurrency session through a common session tag (`pl_<id>`). No parameters or variables unless the source requires them.
