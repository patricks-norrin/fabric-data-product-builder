# Naming and folder conventions (checkable)

Machine-readable twin: `conventions.json` (used by `nor-environment-check` and future validation).

| Thing | Rule | Example |
|---|---|---|
| Workspace | `ws_<domain>[_<env>]` | `ws_extract_dev` |
| Data product identifier | snake_case, source system id | `frankfurter_api`, `oracle_ebs_finland` |
| Dataset name | snake_case, logical dataset in the source | `exchange_rates`, `currencies` |
| Product folder (workspace) | `<data_product_identifier>` | `frankfurter_api` |
| Product lakehouse | `lh_<data_product_identifier>`, schema-enabled | `lh_frankfurter_api` |
| Shared config lakehouse | `lh_workspace_shared_resources` at workspace root | |
| Config file | `Files/configuration/data_product/<id>/<id>.json` in the shared lakehouse | |
| Project config | `Files/configuration/data_product/project_configuration/project_configuration.json` | |
| Extract notebook | `nb_extract_<data_product_identifier>` | `nb_extract_frankfurter_api` |
| CDC notebook | `nb_cdc_<data_product_identifier>` | `nb_cdc_frankfurter_api` |
| Pipeline (optional) | `pl_<data_product_identifier>` | `pl_frankfurter_api` |
| Raw landing | `Files/<id>/<dataset>/raw/<batch_id>/<file>` in the product lakehouse | |
| Batch id | `YYYYMMDDTHHMMSSZ` (UTC), regex `^\d{8}T\d{6}Z$` | `20260911T081530Z` |
| Raw file format | original source format (json/ndjson/csv/parquet), never transformed | `rates_2024.ndjson` |
| Change history | `Tables/<id>/<dataset>` (schema-enabled lakehouse), created by the toolbelt | `Tables/frankfurter_api/exchange_rates` |
| Reserved columns | `dpmeta_input_file_name`, `dpmeta_source_system_id` added before `add_dpmeta_columns` | |
