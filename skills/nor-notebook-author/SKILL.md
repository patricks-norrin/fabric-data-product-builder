---
name: nor-notebook-author
description: Author the two single-responsibility notebooks of a source-aligned data product from templates in Fabric .py definition format - nb_extract_<id> (source to raw files per batch) and nb_cdc_<id> (raw to lakehouse_toolbelt change history). Renders default-lakehouse bindings and bootstraps lakehouse_toolbelt from the shared OneLake wheel, then you write only the source-specific extraction cells from the API documentation.
---

# nor-notebook-author

`TOOLPACK_ROOT` is two directories above this file's own directory — derive it from this file's path, never by
searching the filesystem. Scripts resolve the consuming project from its Git root, falling back to the current
directory outside Git.

## Render
```bash
python3 "$TOOLPACK_ROOT/skills/nor-notebook-author/scripts/render_notebook.py" extract sample_api --workspace ws_example --target dev
python3 "$TOOLPACK_ROOT/skills/nor-notebook-author/scripts/render_notebook.py" cdc sample_api --workspace ws_example --target dev
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
- Never transform before landing. Never hardcode ids, paths or dates: everything comes from `DataProduct(...)` and the parameters cell.

## Writing the source-specific extract cells
Inputs you have: `dataset.source_configuration.base_url`, `.relative_url_template`, `.endpoint_query_parameters` (+ project extras `response_format`, `incremental_strategy`, `notes`) and the helper `land_payload(dataset, file_name, text)`.
Patterns:
- **Time series API** (`/entities?from=&to=`): `start_date = last loaded date (dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()) or initial_load_start_date`; iterate chunks of `max_days_per_request`; request with the format header (`Accept: application/x-ndjson` for streaming); land one file per chunk `<dataset>_<from>_<to>.<ext>`.
- **Reference/snapshot endpoint** (`/reference-values`): one GET, land `<dataset>.json` each run; CDC versions changes.
- **Paginated API**: loop pages until empty, land one file per page.
- Always `response.raise_for_status()`; land the response **text unchanged**.
- `load_mode` parameter: `incremental` (default) or `backfill` with `backfill_start_date`/`backfill_end_date` for history recovery.

## After rendering
Run cells with `nor-livy-session` before publishing. Update the source-specific cells until the raw batch folder holds the expected files and `nb_cdc` upserts every dataset.
