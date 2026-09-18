---
name: nor-notebook-author
description: Author the two single-responsibility notebooks of a source-aligned data product from templates in Fabric .py definition format - nb_extract_<id> (source to raw files per batch) and nb_cdc_<id> (raw to lakehouse_toolbelt change history). Renders unbound notebooks and bootstraps lakehouse_toolbelt from the shared OneLake wheel, then you write only source-specific extraction cells.
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
workspace default Spark pool without an Environment binding. `nb_cdc` is complete as rendered, with an editable
dataset skip list for focused debugging. `nb_extract` has one marked cell per dataset (`# --- SOURCE SPECIFIC: <dataset> ---`)
for you to implement.

## Rules for every cell (human-in-the-loop notebooks)
- One responsibility per cell, a markdown cell before each code cell saying what and why.
- Cells are rerunnable: same inputs → same files/rows (raw is per `batch_id`; CDC upsert is idempotent).
- Each code cell ends by printing what it produced (paths, byte sizes, row counts). No validation logic, no exploration — that belongs elsewhere.
- Works in both Livy and the notebook UI: no `display()`, no `%pip`, no `%run`, no `/lakehouse/default/` mounts; `spark.sql()` instead of `%%sql`.
- Never transform source data before landing. Never hardcode Fabric ids or OneLake paths. Keep credentials, queries or requests, pagination, source-specific incremental logic, and reader decisions in source-specific extraction cells. The data-product JSON is a minimal iterable handoff for extraction and CDC, not a connector framework.

## Writing the source-specific extract cells
Load the applicable source extraction skill before implementing a cell. During development, use a deliberately small,
representative bound beside the reason it was chosen. Prove extraction and CDC with that sample before widening the
same source-specific bound for the intended load. Do not add shared source parameters to the generic template.

- **Use native Spark first.** Read [Spark Data Sources](https://spark.apache.org/docs/latest/sql-data-sources.html)
	to select the reader, and [Generic File Source Options](https://spark.apache.org/docs/latest/sql-data-sources-generic-options.html)
	for `recursiveFileLookup`, `pathGlobFilter`, and modification-time filters. Consult the selected reader's official
	Spark documentation for format-specific options. Verify uncertain options against the active Fabric runtime.
- **Keep CDC fixed and visible.** It uses one editable `datasets_to_skip` list and one inline dataset loop. Preserve
	the raw path, recursive lookup, watermark-derived `modifiedAfter`, lineage, `add_dpmeta_columns`, duplicate removal,
	schema alignment, and upsert sequence. Change only the marked direct native Spark reader expression and its required
	options. Do not add runtime selectors, wrappers, registries, or connector abstractions.
- **Use custom code only when necessary.** If raw-file evidence shows native Spark cannot produce the configured rows,
	add the smallest dataset-local normalization and document the observed reason.

## After rendering
Run cells with `nor-livy-session` before publishing. First prove a completed small raw batch, inspect it with the chosen generic Spark reader, and then prove its CDC upsert. Then widen the source-specific bound and repeat extract plus CDC from a fresh session for the intended load.
