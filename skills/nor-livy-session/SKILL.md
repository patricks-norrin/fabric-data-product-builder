---
name: nor-livy-session
description: Cell-by-cell development loop for Fabric notebooks without VS Code - open a Livy Spark session on the product lakehouse (with the lakehouse_toolbelt Environment attached) through fab api, run notebook .py cells or ad-hoc PySpark/SQL statements, read outputs and tracebacks, iterate on a single cell, then close the session. Use whenever you need to see what a cell actually produces.
---

# nor-livy-session

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`. All commands use
`bash "<directory of this SKILL.md>/scripts/livy_session.sh" <command> ...`.
Add `--workspace ws_<name>` and/or `--target <profile>` when overriding project defaults. Session state is
kept in `<project>/.scratch/<ws_name>/livy/livy_session.json`.

## Authentication — read before the first session
- **fab (Fabric CLI) token = control plane only.** A Livy session created with it starts, but the Spark runtime gets **no delegated identity**: `notebookutils.fs.*`, `spark.read/write` to OneLake, `SHOW SCHEMAS`, `credentials.getToken` all fail with `Auth failure … CustomTokenProvider`. Verified 2026-09-11.
- **Azure CLI user token works.** `az account get-access-token --resource https://api.fabric.microsoft.com` gives the Spark runtime full OneLake access. The driver therefore uses `fab` for ids and `az` for the session. Prerequisite once per customer tenant: `az login --tenant <tenant-id> --allow-no-subscriptions --use-device-code` (no app registration).
- Diagnostics are assertion-style (the preamble reports `onelake_access: True/FAILED`). Never decode or print tokens or their claims.

| Command | What it does |
|---|---|
| `create <lakehouse_name> [--no-environment]` | POST session bound to that lakehouse, attach the Environment from the selected target mapping, wait until `idle` (~2–4 min), run the preamble (workspace-name shim + `import lakehouse_toolbelt`). With `--no-environment` (or when the import fails) the preamble installs the wheel staged at `lh_workspace_shared_resources/Files/libraries/lakehouse_toolbelt-*.whl` into the session driver. |
| `status` | Session state. |
| `run-cells <notebook-content.py> [N[,M..]\|all] [--keep-going]` | Submit code cells in notebook order as statements (markdown skipped, `%%sql` cells sent as `sql`), print each output, stop at the first error unless `--keep-going`. |
| `statement "<code>"` or `statement -f file.py` | Ad-hoc statement (inspect a DataFrame, list files, `spark.sql`). |
| `delete` | Close the session (do this when done — sessions cost capacity and time out after 20 min idle). |

Cell numbering comes from
`python3 "<directory of this SKILL.md>/scripts/notebook_cells.py" <notebook-content.py> --list`.

## Loop
1. `create lh_<id>` once per work session.
2. `run-cells ws_<name>/<id>/nb_extract_<id>.Notebook/notebook-content.py all` → read outputs.
3. On error: fix **that cell** in the `.py` file, `run-cells ... <n>` again (state from earlier cells persists, like a notebook).
4. Inspect side effects with statements, e.g. `statement "print(notebookutils.fs.ls(data_product.exchange_rates.file_path_raw))"`.
5. When all cells pass in order from a fresh session, publish with `nor-notebook-publish-and-run`.

## Livy vs notebook UI (write cells so both work)
- No `%%sql`/`%pip`/`%run` magics in Livy: use `spark.sql(...)`; `%%sql` cells are still allowed in the file — the runner maps them to `kind: sql`.
- `display()` is UI-only → use `.show()` / `.limit(20).toPandas()`.
- `notebookutils.runtime.context["currentWorkspaceName"]` is None in Livy; the preamble patches lakehouse_toolbelt with the selected physical workspace name. Notebooks themselves stay unchanged.
- Use `abfss://` paths via the toolbelt, never `/lakehouse/default/...` mounts.
- Output is `text/plain`; keep prints compact (`show(20, truncate=False)`).

## Known behaviour
- A session that fails during startup keeps `state: starting`; the real status is `fabricSessionStateInfo.state = error` + `errorMessage`. The driver checks both and fails fast.
- Attaching an Environment **from another workspace** kills the Spark session at startup (Livy and `fab job run` alike). Environments must live in the same workspace as the notebooks; copy them with `fab cp <ws>/<env>.Environment <target ws>` and publish.
- `--no-environment`: the preamble installs the wheel staged at `lh_workspace_shared_resources/Files/libraries/lakehouse_toolbelt-*.whl` into the session driver.
