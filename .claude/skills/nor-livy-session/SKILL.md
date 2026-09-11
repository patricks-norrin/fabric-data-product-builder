---
name: nor-livy-session
description: Cell-by-cell development loop for Fabric notebooks without VS Code - open a Livy Spark session on the product lakehouse (with the lakehouse_toolbelt Environment attached) through fab api, run notebook .py cells or ad-hoc PySpark/SQL statements, read outputs and tracebacks, iterate on a single cell, then close the session. Use whenever you need to see what a cell actually produces.
---

# nor-livy-session

All commands: `bash .claude/skills/nor-livy-session/scripts/livy_session.sh <command> ...`. Session state is kept in `.scratch/livy_session.json`.

| Command | What it does |
|---|---|
| `create <lakehouse_name>` | POST session bound to that lakehouse, attach the Environment from `target_workspace.json`, wait until `idle` (~2–4 min), run the preamble (workspace-name shim + `import lakehouse_toolbelt` check). |
| `status` | Session state. |
| `run-cells <notebook-content.py> [N[,M..]\|all] [--keep-going]` | Submit code cells in notebook order as statements (markdown skipped, `%%sql` cells sent as `sql`), print each output, stop at the first error unless `--keep-going`. |
| `statement "<code>"` or `statement -f file.py` | Ad-hoc statement (inspect a DataFrame, list files, `spark.sql`). |
| `delete` | Close the session (do this when done — sessions cost capacity and time out after 20 min idle). |

Cell numbering comes from `python3 scripts/notebook_cells.py <notebook-content.py> --list`.

## Loop
1. `create lh_<id>` once per work session.
2. `run-cells notebooks/<id>/nb_extract_<id>.Notebook/notebook-content.py all` → read outputs.
3. On error: fix **that cell** in the `.py` file, `run-cells ... <n>` again (state from earlier cells persists, like a notebook).
4. Inspect side effects with statements, e.g. `statement "print(notebookutils.fs.ls(data_product.exchange_rates.file_path_raw))"`.
5. When all cells pass in order from a fresh session, publish with `nor-notebook-publish-and-run`.

## Livy vs notebook UI (write cells so both work)
- No `%%sql`/`%pip`/`%run` magics in Livy: use `spark.sql(...)`; `%%sql` cells are still allowed in the file — the runner maps them to `kind: sql`.
- `display()` is UI-only → use `.show()` / `.limit(20).toPandas()`.
- `notebookutils.runtime.context["currentWorkspaceName"]` is None in Livy; the preamble patches lakehouse_toolbelt with the workspace name from `target_workspace.json`. Notebooks themselves stay unchanged.
- Use `abfss://` paths via the toolbelt, never `/lakehouse/default/...` mounts.
- Output is `text/plain`; keep prints compact (`show(20, truncate=False)`).
