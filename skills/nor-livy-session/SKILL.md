---
name: nor-livy-session
description: Cell-by-cell development loop for Fabric notebooks without VS Code - open a Livy Spark session on the product lakehouse with an optional Environment and hosted-feed toolbelt bootstrap, run notebook .py cells or ad-hoc PySpark/SQL statements, read outputs and tracebacks, iterate on a single cell, then close the session. Use whenever you need to see what a cell actually produces.
---

# nor-livy-session

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`. All commands use
`bash "<directory of this SKILL.md>/scripts/livy_session.sh" <command> ...`.
Add `--workspace ws_<name>` and/or `--target <profile>` when overriding project defaults. Session state is
kept in `<project>/.scratch/<ws_name>/livy/livy_session.json`.
Session lifecycle and cell-run outcomes are appended to
`<project>/.scratch/<ws_name>/operational_manifest.jsonl`; deleting a session does not delete this manifest.

## Authentication — read before the first session
- **fab (Fabric CLI) token = control plane only.** A Livy session created with it starts, but the Spark runtime gets **no delegated identity**: `notebookutils.fs.*`, `spark.read/write` to OneLake, `SHOW SCHEMAS`, `credentials.getToken` all fail with `Auth failure … CustomTokenProvider`. Verified 2026-09-11.
- **Azure CLI user token works.** `az account get-access-token --resource https://api.fabric.microsoft.com` gives the Spark runtime full OneLake access. The driver therefore uses `fab` for ids and `az` for the session. Prerequisite once per customer tenant: `az login --tenant <tenant-id> --allow-no-subscriptions --use-device-code` (no app registration).
- Diagnostics are assertion-style (the preamble reports `onelake_access: True/FAILED`). Never decode or print tokens or their claims.

| Command | What it does |
|---|---|
| `create <lakehouse_name> [--no-environment]` | POST session bound to that lakehouse, optionally attach the Environment from the selected target mapping, wait until `idle` (~2–4 min), run the preamble (driver-side pip requirement resolution + workspace-name shim + `import lakehouse_toolbelt`). The preamble resolves `lakehouse-toolbelt>=1.0.7` from the hosted feed, without `--upgrade`; compatible Environment-installed packages satisfy the requirement. `--no-environment` omits the Environment binding. Installation/import failure is reported and fails the command. |
| `status` | Session state. |
| `run-cells <notebook-content.py> [N[,M..]\|all] [--keep-going]` | Submit code cells in notebook order as statements (markdown skipped, `%%sql` cells sent as `sql`, dedicated single-line `%pip` cells run via driver-only subprocess pip), print each output, stop at the first error unless `--keep-going`. |
| `statement "<code>"` or `statement -f file.py` | Ad-hoc statement (inspect a DataFrame, list files, `spark.sql`). |
| `delete` | Close the session (do this when done — sessions cost capacity and time out after 20 min idle). |

Cell numbering comes from
`python3 "<directory of this SKILL.md>/scripts/notebook_cells.py" <notebook-content.py> --list`.

## Loop
1. `create lh_<id>` once per work phase. Reuse that session for each cell retry; create another only when the
	current session is unavailable, needs isolated configuration, or the user explicitly requests independent
	parallel work.
2. **Extract phase:** `run-cells ws_<name>/<id>/nb_extract_<id>.Notebook/notebook-content.py all` → read the
	compact batch summary, then inspect the completed raw batch folder. Record its `batch_id`.
3. On error: fix **that cell** in the `.py` file, `run-cells ... <n>` again (state from earlier cells persists,
	like a notebook).
4. **CDC phase:** run `nb_cdc_<id>` against the recorded, completed raw batch. Verify its table summary and
	schema. Do not run CDC while the extract notebook is still writing that batch.
5. **Integration phase:** from a fresh session, run extract and then CDC sequentially. Confirm the final raw
	batch and change-history table before publishing with `nor-notebook-publish-and-run`.

## Livy vs notebook UI (write cells so both work)
- Do not forward notebook magics directly to Livy. Use `spark.sql(...)`; `%%sql` cells are still allowed in the file because the runner maps them to `kind: sql`. `%run` is not handled.
- The runner preserves a dedicated single-line `%pip` cell in the notebook definition but submits a plain-Python
  `subprocess.run([sys.executable, "-m", "pip", ...], check=True)` equivalent to Livy. It prints a driver-only
  warning and propagates installation failure. This does **not** implement Fabric notebook `%pip` semantics:
  no executor propagation and no automatic Python restart. Keep it before imports; if packages already imported
  need changing, start a fresh Livy session rather than assuming cached modules are refreshed.
- `display()` is UI-only → use `.show()` / `.limit(20).toPandas()`.
- `notebookutils.runtime.context["currentWorkspaceName"]` is None in Livy; the preamble patches lakehouse_toolbelt with the selected physical workspace name. Notebooks themselves stay unchanged.
- Use `abfss://` paths via the toolbelt, never `/lakehouse/default/...` mounts.
- Output is `text/plain`; keep prints compact (`show(20, truncate=False)`).

## Known behaviour
- A session that fails during startup keeps `state: starting`; the real status is `fabricSessionStateInfo.state = error` + `errorMessage`. The driver checks both and fails fast.
- Attaching an Environment **from another workspace** kills the Spark session at startup (Livy and `fab job run` alike). Environments must live in the same workspace as the notebooks; copy them with `fab cp <ws>/<env>.Environment <target ws>` and publish.
- `--no-environment`: the preamble resolves toolbelt from
  `https://nrnctopublishpip.z6.web.core.windows.net/pip/` into the session driver. No staged wheel is required.

## Package installation support and alternatives

Current [Fabric library documentation](https://learn.microsoft.com/en-us/fabric/data-engineering/library-management#inline-installation)
documents notebook `%pip` on the driver and executors, with automatic Python restart and loss of prior variables.
It does not establish support through Livy statement APIs. As reviewed on 2026-10-28, native `%pip` support in
Fabric Livy is **not documented/verified**, rather than proven unsupported by a current platform test.
The existing driver-side subprocess approach is retained with the hosted feed as its normal source; the new
feed path still needs the external Fabric acceptance run.

- **Published Environment:** the documented Livy-compatible choice when dependencies must be available to
  executors, for stable shared workloads, or when inline installation is unavailable. Attach it through
  `spark.fabric.environmentDetails` as described in
  [Fabric Livy Environment integration](https://learn.microsoft.com/en-us/fabric/data-engineering/get-started-api-livy-session#integration-with-fabric-environments).
  For private/offline artifacts, publish the verified wheel and its dependencies there; satisfy `>=1.0.7`.
- **Driver-only subprocess pip:** suitable for this development bootstrap, using the hosted feed or an explicitly
  chosen wheel. It is not a distributed library deployment mechanism. Do not silently fall back to another source
  after network or installation failure.
- **Notebook execution instead of Livy:** publish/run with `nor-notebook-publish-and-run` to use notebook `%pip`
  semantics. Inline installation is not supported in High Concurrency mode or notebook reference runs;
  use an Environment for those cases.
- Do not invent `notebookutils.library.installPyPI` or `spark.pyspark.virtualenv.*` as Fabric Livy APIs.
  Their support was not verified in the reviewed official Fabric documentation.
  [The documented subprocess/restart example](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-session-management#install-packages-and-restart-the-interpreter)
  is notebook-scoped; it does not prove a safe Livy restart workflow.
