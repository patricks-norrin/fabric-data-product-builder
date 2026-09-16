---
name: nor-data-product-config
description: Author, validate, push and provision a Norrin data product configuration - the JSON that defines datasets, unique identifier columns, version timestamps and API source metadata for lakehouse_toolbelt. Pushes it to lh_workspace_shared_resources with fab cp, pushes project_configuration.json, and provisions the product folder and schema-enabled lakehouse lh_<id>.
---

# nor-data-product-config

Set `TOOLPACK_ROOT` to the directory containing this installed toolpack. Scripts resolve the consuming project
from its Git root, falling back to the current directory outside Git. Add `--workspace ws_<name>` and/or
`--target <profile>` to override `configuration/fabric_targets.json`.

## Authoring (from API documentation to config)
1. Read the source documentation (or the URL the user gives) and list the **endpoints that return entities** → each becomes a dataset (`dataset_name` snake_case). Skip metadata-only endpoints unless they carry reference data worth versioning (e.g. currencies).
2. For each dataset decide the **natural key** (`unique_identifier_columns`) from the documented response fields — the smallest set unique within one extraction batch. Write down the reasoning in `source_configuration.notes`.
3. Decide `object_version_timestamp_column` (business timestamp if the API has one; else `""`), `timestamp_columns_to_convert` (string timestamps), `exclude_columns_from_payload_checksum` (volatile fields).
4. Fill `source_configuration` with the toolbelt API defaults: `base_url`, `relative_url_template`, `endpoint_query_parameters` (static values + `initial_load_start_date`), plus reader hints `spark_read_format` / `spark_read_options` / `response_format` and `notes`. These extras are allowed by `configuration/data_product/project_configuration/project_configuration.json`.
5. Save as `configuration/data_product/<id>/<id>.json`. Follow `reference/lakehouse_toolbelt/docs/configuration-reference.md`; template: `schemas/data_product_configuration.example.json`.

## Validate (local, no Spark)
```bash
python3 "$TOOLPACK_ROOT/skills/nor-data-product-config/scripts/validate_data_product_config.py" configuration/data_product/sample_api/sample_api.json
```
Checks the same rules as the toolbelt validator (unique dataset names, allowed `source_configuration`/`publish_configuration` attributes incl. project extras) plus naming conventions and required keys.

## Push + provision
```bash
bash "$TOOLPACK_ROOT/skills/nor-data-product-config/scripts/push_data_product_config.sh" sample_api
bash "$TOOLPACK_ROOT/skills/nor-data-product-config/scripts/push_data_product_config.sh" sample_api --no-provision --workspace ws_example --target dev
```
Idempotent: existing items/dirs are left alone. Prints the OneLake path and the lakehouse id (needed for notebook default-lakehouse binding).
