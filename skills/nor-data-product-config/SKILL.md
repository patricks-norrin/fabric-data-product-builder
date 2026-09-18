---
name: nor-data-product-config
description: Author, validate, push and provision a Norrin data product configuration - the JSON that defines datasets, unique identifier columns and version timestamps for lakehouse_toolbelt. Pushes it to lh_workspace_shared_resources with fab cp, pushes project_configuration.json, and provisions the product folder and schema-enabled lakehouse lh_<id>.
---

# nor-data-product-config

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`; the scripts locate the toolpack from their own
path. The consuming project is the Git root of the current directory (cwd outside Git). Add
`--workspace ws_<name>` and/or `--target <profile>` to override `configuration/fabric_targets.json`.

## Authoring (from source documentation to config)
1. List the source entities to retain as change history (for example, API resources, database tables, or file collections) → each becomes a dataset (`dataset_name` snake_case). Skip metadata-only entities unless they carry reference data worth versioning.
2. For each dataset decide the **natural key** (`unique_identifier_columns`) from source fields — the smallest set unique within one extraction batch. Document the reasoning beside the extraction code.
3. Set `object_version_timestamp_column` only when the source has a reliable business timestamp. Add `timestamp_columns_to_convert` or `exclude_columns_from_payload_checksum` only when the generic CDC notebook needs them.
4. Keep config minimal: dataset identity, keys, and CDC metadata. Keep credentials, queries, request values, pagination, file formats, reader options, and operational notes in the source-specific extraction notebook or pipeline. `source_configuration` supports toolbelt metadata when needed, but does not define a connector contract. Do not create `project_configuration.json` or use configuration extensions unless a proven shared runtime requirement needs it.
5. Save as `configuration/data_product/<id>/<id>.json` in the consuming project. Follow `../../reference/lakehouse_toolbelt/docs/configuration-reference.md`; template: `schemas/data_product_configuration.example.json`. The last two are relative to this file, inside the installed toolpack; the first is relative to the project.

## Validate (local, no Spark)
```bash
python3 "<directory of this SKILL.md>/scripts/validate_data_product_config.py" configuration/data_product/sample_api/sample_api.json
```
Checks the same rules as the toolbelt validator (unique dataset names, allowed `source_configuration`/`publish_configuration` attributes incl. project extras) plus naming conventions and required keys.

## Push + provision
```bash
bash "<directory of this SKILL.md>/scripts/push_data_product_config.sh" sample_api
bash "<directory of this SKILL.md>/scripts/push_data_product_config.sh" sample_api --no-provision --workspace ws_example --target dev
```
Idempotent: existing items/dirs are left alone. If the shared resources lakehouse is absent, it is created at
workspace root. Prints the OneLake path and the lakehouse id (needed for notebook default-lakehouse binding).

Stage the runtime wheel used by generated notebooks:

```bash
bash "<directory of this SKILL.md>/scripts/push_toolbelt_wheel.sh" \
	/path/to/lakehouse_toolbelt-1.0.7-py3-none-any.whl
```

The wheel must be version 1.0.7 or newer and is uploaded to
`lh_workspace_shared_resources/Files/libraries/`. Use a verified artifact supplied by the project or toolbelt
release process.
