# Naming and folder conventions (checkable)

Machine-readable twin: `conventions.json` (used by `nor-environment-check` and future validation).

| Thing | Rule | Example |
|---|---|---|
| Workspace | `ws_<domain>[_<env>]` | `ws_extract_dev` |
| Data product identifier | snake_case, source system id | `sample_api`, `oracle_ebs_finland` |
| Dataset name | snake_case, logical dataset in the source | `exchange_rates`, `currencies` |
| Product folder (workspace) | `<data_product_identifier>` — same rule for every tier: source-aligned, foundational, business, analytical | `sample_api` |
| Product lakehouse | `lh_<data_product_identifier>`, schema-enabled — same rule for every tier, no tier-specific prefix | `lh_sample_api` |
| Shared config lakehouse | `lh_workspace_shared_resources` at workspace root (workspace-wide, not per-product) | |
| Config file | `Files/configuration/data_product/<id>/<id>.json` in the shared lakehouse | |
| Project config | `Files/configuration/data_product/project_configuration/project_configuration.json` | |
| Extract notebook (source-aligned) | `nb_extract_<data_product_identifier>` | `nb_extract_sample_api` |
| CDC notebook (source-aligned) | `nb_cdc_<data_product_identifier>` | `nb_cdc_sample_api` |
| Modeling notebook (foundational) | `nb_model_<data_product_identifier>` — **proposed**, based on precedent found elsewhere in the org; not yet built by this toolpack | `nb_model_customer` |
| Data product notebook (business) | `nb_dp_<data_product_identifier>` — not yet built by this toolpack | `nb_dp_currency_exchange_rates` |
| Pipeline (optional) | `pl_<data_product_identifier>` | `pl_sample_api` |
| Raw landing | `Files/<id>/<dataset>/raw/<batch_id>/<file>` in the product lakehouse | |
| Batch id | `YYYYMMDDTHHMMSSZ` (UTC), regex `^\d{8}T\d{6}Z$` | `20260911T081530Z` |
| Raw file format | original source format (json/ndjson/csv/parquet), never transformed | `rates_2024.ndjson` |
| Change history | `Tables/<id>/<dataset>` (schema-enabled lakehouse), created by the toolbelt | `Tables/sample_api/entities` |
| Reserved columns | `dpmeta_input_file_name`, `dpmeta_source_system_id` added before `add_dpmeta_columns` | |
