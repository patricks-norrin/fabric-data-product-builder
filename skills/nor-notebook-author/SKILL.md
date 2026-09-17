---
name: nor-notebook-author
description: Author the two single-responsibility notebooks of a source-aligned data product from templates in Fabric .py definition format - nb_extract_<id> (source to raw files per batch) and nb_cdc_<id> (raw to lakehouse_toolbelt change history). Renders default-lakehouse bindings and bootstraps lakehouse_toolbelt from the shared OneLake wheel, then you write only the source-specific extraction cells from the API documentation.
---

# nor-notebook-author

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`; the script locates the toolpack from its own
path. The consuming project is the Git root of the current directory (cwd outside Git).

## Render
```bash
python3 "<directory of this SKILL.md>/scripts/render_notebook.py" extract sample_api --workspace ws_example --target dev
python3 "<directory of this SKILL.md>/scripts/render_notebook.py" cdc sample_api --workspace ws_example --target dev
```
Writes `ws_<name>/<id>/nb_<kind>_<id>.Notebook/{notebook-content.py,.platform}` with workspace and
lakehouse (`lh_<id>`) resolved via `fab`. Generated notebooks install the verified `lakehouse_toolbelt` wheel
from `lh_workspace_shared_resources/Files/libraries/` when it is not already present, so they can use the
workspace default Spark pool without an Environment binding. `nb_cdc` is complete as rendered — it is fully
driven by the config. `nb_extract` has one marked cell per dataset (`# --- SOURCE SPECIFIC: <dataset> ---`) for
you to implement.

## Rules for every cell (human-in-the-loop notebooks)
- One responsibility per cell, a markdown cell before each code cell saying what and why.
- Cells are rerunnable: same inputs → same files/rows (raw is per `batch_id`; CDC upsert is idempotent).
- Each code cell ends by printing what it produced (paths, byte sizes, row counts). No validation logic, no exploration — that belongs elsewhere.
- Works in both Livy and the notebook UI: no `display()`, no `%pip`, no `%run`, no `/lakehouse/default/` mounts; `spark.sql()` instead of `%%sql`.
- Never transform before landing. Never hardcode Fabric ids or OneLake paths. Prefer `f"{source.base_url}/{dataset.dataset_name}"` when the dataset name is the endpoint. Keep a stable base URL in configuration; add a URL template there only when request path or query values vary between calls. Keep template values, credentials lookup, pagination, formats, dates, and source assumptions in the source-specific extraction cells.

## Writing the source-specific extract cells
Inputs you have: `dataset.source_configuration.base_url`, an optional `.relative_url_template`, the notebook parameters, and `extraction_start_timestamps[dataset.dataset_name]`. The single **Resolve extraction start timestamps** markdown cell immediately before the loop must state why the user selected `initial_load_start_date`. The loop uses that notebook value only when the dataset has no successful Delta watermark; later calls receive `get_delta_change_history_dpmeta_loaded_to_dataplatform()`. Format `start_timestamp` for the API in the source-specific cell. For a simple endpoint, use `f"{source.base_url}/{dataset.dataset_name}"`; otherwise build the template-value dictionary and format `source.relative_url_template`. Keep authentication, request parameters, response format, pagination, and date-window logic in each source-specific cell.
Patterns:
- **Time series API** (`/entities?from=&to=`): format `start_timestamp` for the source API, set the matching end timestamp in the source-specific cell, and iterate source-appropriate chunks there. `start_timestamp` is the Delta watermark on subsequent runs and the documented notebook value only on a first run. Land one file per chunk `<dataset>_<from>_<to>.<ext>`.
- **Reference/snapshot endpoint** (`/reference-values`): one GET, land `<dataset>.json` each run; CDC versions changes.
- **Paginated API**: loop pages until empty, land one file per page.
- Always `response.raise_for_status()`; land the response **text unchanged**.
- `load_mode` parameter: `incremental` (default) or `backfill` with `backfill_start_date`/`backfill_end_date` for history recovery.

## After rendering
Run cells with `nor-livy-session` before publishing. Update the source-specific cells until the raw batch folder holds the expected files and `nb_cdc` upserts every dataset.
