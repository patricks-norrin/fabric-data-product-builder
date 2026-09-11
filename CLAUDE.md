# Norrin Fabric data product toolpack — agent rules

You build **source-aligned data products** in Microsoft Fabric. Scope of one data product: configuration JSON,
lakehouse `lh_<data_product_identifier>`, notebooks `nb_extract_<id>` and `nb_cdc_<id>`, raw files, change-history tables.

## Non-negotiables (details: skill `nor-data-product-architecture`, read it before designing anything)
1. One data product = one lakehouse `lh_<data_product_identifier>` (schema-enabled). One source system = one data product; datasets are the endpoints/tables inside it.
2. Configuration lives in `lh_workspace_shared_resources/Files/configuration/data_product/<id>/<id>.json` and is the only place that defines datasets, keys and source metadata.
3. Raw lands **unchanged, in original format** at `Files/<id>/<dataset_name>/raw/<YYYYMMDDTHHMMSSZ>/`. Never transform before landing.
4. Change history is produced only by `lakehouse_toolbelt` (`add_dpmeta_columns → dropDuplicates → align → upsert_delta_change_history`) into `Tables/<id>/<dataset_name>`. CDC is the default for all tabular data.
5. Notebooks are single-responsibility: `nb_extract_<id>` lands raw, `nb_cdc_<id>` upserts change history. No validation or exploration inside them. Cells are small, rerunnable, one responsibility each, and print what they produced.
6. Every item of a data product lives in workspace folder `<id>.Folder`. `lh_workspace_shared_resources` stays at the workspace root.

## Tools
- **`fab`** (Microsoft Fabric CLI) is the control plane: items, OneLake files, jobs, REST via `fab api`. No MCP for Fabric operations.
- **`az login` user token** is required only for Livy Spark sessions (fab's token gives Spark no OneLake identity — see `nor-livy-session`). Two logins per customer tenant, nothing else.
- **microsoft-learn MCP** is the canonical reference for Fabric capabilities — check it instead of guessing.
- Scripts under `.claude/skills/*/scripts/` wrap the repeatable `fab` sequences; call them instead of retyping commands.

## Safety
- Work only in the workspace named in `configuration/target_workspace.json`. Never create, change or delete anything elsewhere. Never start or stop capacities.
- Delete only items you created in this session, and only when asked.

## Workflow (agent `nor-data-product-builder`)
environment check → config (author, validate, push, provision folder + lakehouse) → notebooks from templates → Livy dev loop cell by cell → publish (`fab import`) → headless run (`fab job run`) → report.

## fab gotchas (verified)
- Output uses CRLF; strip `\r`. `fab api` JMESPath queries start at `text.` (e.g. `text.value[]`).
- OneLake `fab mkdir` creates one directory level at a time; `fab cp` needs the destination directory to exist; `fab cp -r` local→OneLake is unsupported.
- `fab mv` into a folder in the same workspace is unsupported: import/create directly in the target folder.
- Job details: `fab api workspaces/<ws>/items/<item>/jobs/instances/<id>` (no exit value is exposed; use Livy for outputs).
