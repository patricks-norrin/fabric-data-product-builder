# Conventions and dependencies

Everything here was **verified live** in isolated Fabric test workspaces unless marked otherwise. Specific
tenant, workspace, capacity, and Environment names have been removed; the technical observations are retained
for future iterations. Where Microsoft's docs and observed behavior disagreed, observed behavior is recorded.

## Naming and path conventions

Human-readable: `reference/architecture/naming-and-folder-conventions.md`. Machine-readable twin:
`reference/architecture/conventions.json` (regex patterns + path templates), read by
`nor-data-product-config`'s validator.

| Thing | Rule | Example |
|---|---|---|
| Data product identifier | snake_case | `sample_api` |
| Dataset name | snake_case | `exchange_rates`, `currencies` |
| Product folder (workspace) | `<data_product_identifier>` | `sample_api` |
| Product lakehouse | `lh_<data_product_identifier>`, **schema-enabled** | `lh_sample_api` |
| Shared config lakehouse | `lh_workspace_shared_resources`, at workspace root | |
| Config file | `Files/configuration/data_product/<id>/<id>.json` in the shared lakehouse | |
| Project config | `Files/configuration/data_product/project_configuration/project_configuration.json` | |
| Extract notebook | `nb_extract_<data_product_identifier>` | `nb_extract_sample_api` |
| CDC notebook | `nb_cdc_<data_product_identifier>` | `nb_cdc_sample_api` |
| Pipeline (reserved, not built) | `pl_<data_product_identifier>` | |
| Raw landing | `Files/<id>/<dataset>/raw/<batch_id>/<file>` in the product lakehouse | |
| Batch id | UTC `YYYYMMDDTHHMMSSZ` | `20260911T182043Z` |
| Raw file format | original source format, never transformed before landing | `.ndjson`, `.json` |
| Change history | `Tables/<id>/<dataset>` (schema-enabled lakehouse) — **not** `Files/.../change_history/` | `Tables/sample_api/entities` |
| Reserved columns | `dpmeta_input_file_name`, `dpmeta_source_system_id` — added **before** `add_dpmeta_columns` | |

Also agreed: every item belonging to one data product lives inside its workspace `.Folder`; only
`lh_workspace_shared_resources` stays at workspace root.

## Runtime dependencies

| Dependency | Used for | Notes |
|---|---|---|
| `fab` (Microsoft Fabric CLI, `pip install ms-fabric-cli`) | Control plane: item/folder CRUD, OneLake file copy, headless job run, REST passthrough via `fab api` | The only tool that touches Fabric for **item/file management**. **Minimum 1.9.0** (`nor-environment-check` fails below that). A PATH `fab` at 0.1.x is a different binary. |
| `az` (Azure CLI) | Minting the user token that a **Livy Spark session** needs | `fab`'s own token has no delegated OneLake identity inside the Spark runtime — see "Auth model" below. **Minimum 2.50.0**. One `az login` per customer tenant; no app registration. |
| `lakehouse_toolbelt` (Fabric runtime package) | The CDC/change-history contract every notebook runs against | Must be **≥ 1.0.7** (see gotchas). Installed from the hosted wheel feed; not required on the builder machine. Vendored docs/examples in `reference/lakehouse_toolbelt/`. |
| Python 3.10+ (stdlib only) | Every toolpack script: preflight, config validation and push, notebook and pipeline rendering, publish/run, Livy | Already present because `fab` is a pip package. Zero third-party dependencies. Run `python3` on Linux/WSL and `python` on Windows, with native paths; no Bash or Git Bash is needed. Scripts call `fab` with `--json` and read its result envelope. |
| `curl` | Optional source HTTP sampling | Not needed by any script; Livy and log downloads use standard-library HTTP with the `az` token. |
| Microsoft Learn documentation integration | Canonical live reference for Fabric capabilities | Configure through the active agent harness when available; check it instead of guessing when a Fabric capability is in doubt. |
| Fabric MCP server (`@microsoft/fabric-mcp`) | **Not used** for agent operations | Considered and deliberately dropped for the automated path: adds a Node dependency and a second, `az login`-based auth flow that duplicates what `fab` already does for item/file operations. Left as an optional human-only tool (VS Code) — see decision log. |
| Hosted Fabric SQL endpoint MCP server (`fabric-sqlendpoint`) | Read-only data queries in `nor-lakehouse-query` | Remote and Microsoft-hosted, so no Node dependency. Shipped in the plugin's `.mcp.json` (and `.claude-plugin/plugin.json` with an `az` `headersHelper`); it reuses the user's `az login`. Data reads only; `fab` still owns every Fabric mutation. Falls back to `nor-livy-session` when absent or when the endpoint metadata is stale. |

### Toolbelt installation

Generated notebooks install the Fabric runtime dependency in a dedicated cell before parameters and imports:

```python
%pip install --no-index -f https://nrnctopublishpip.z6.web.core.windows.net/pip/ "lakehouse-toolbelt>=1.0.7"
```

There is no `--upgrade`: a compatible Environment-installed package can satisfy the requirement.
Fabric notebook `%pip` restarts Python and clears prior variables, so parameter initialization must follow it.
The feed must be reachable from the Fabric runtime; installation errors are failures, not a reason to silently
use a different source. `--no-index` also applies to dependency resolution, so dependencies must already be
installed or available from the feed. A local wheel and a wheel upload are not prerequisites; when a project
needs a private build, publish it in an Environment.
Do not install toolbelt on the builder machine. Vendored upstream docs and examples remain the CDC contract.

## Auth model (why two logins, and only two)

1. **`fab auth login --tenant <id>`** — control plane. Everything that is *not* running Spark code: creating
   items/folders, copying files to OneLake, submitting/polling headless jobs, arbitrary REST via `fab api`.
2. **`az login --tenant <id> --allow-no-subscriptions --use-device-code`** — required **only** to open a Livy
   Spark session for the interactive cell-by-cell dev loop. **Verified fact:** a Livy session created with
   `fab`'s own bearer token starts, but the Spark runtime inside it has no delegated identity — every OneLake
   operation (`notebookutils.fs.*`, `spark.read/write`, `SHOW SCHEMAS`, `credentials.getToken`) fails with
   `Auth failure ... CustomTokenProvider`. The identical session created with an `az` user token
   (`aud=https://api.fabric.microsoft.com`) works: `fs.ls`, `SHOW SCHEMAS`, `getToken` all succeed. This is why
   `livy_session.py` calls `az account get-access-token` and uses Python standard-library HTTP for
   session/statement calls. It uses `fab` only for workspace/lakehouse ids, and imports the existing
   Python project-context and manifest helpers directly. The refactored local driver is covered by
   mocked HTTP/CLI regression tests; native Windows and live Fabric acceptance are still required.

No service principal or app registration was needed for either login in this iteration; both are interactive
user logins, appropriate for consulting engagements where the toolpack is set up fresh per customer.

## Diagnostics convention: assertion, not introspection

Earlier in the session, a diagnostic script that decoded a bearer token's JWT claims (`aud`, `scp`, `roles`)
to explain an auth failure triggered a safety-classifier false positive on the model (credential-introspection
shape, even though it was the user's own interactive login against their own tenant). Agreed convention going
forward, encoded in `nor-livy-session`'s preamble: diagnostics report **pass/fail of an actual operation**
(`onelake_access: True` / `FAILED: <first line of error>`), never decode or print token contents, claims, or
lengths. If an audience genuinely needs checking, print `aud` alone.

## Verified Fabric/`fab` gotchas

- `fab api` responses are wrapped — JMESPath queries must start at `text.` (e.g. `text.value[]`), not the bare
  payload. When a `-q` query matches nothing, `fab api` prints the whole response instead of nothing, so scripts
  read the full `--json` result and filter in Python. `fab api` exits 0 on HTTP errors; check `status_code`.
- OneLake `fab mkdir` creates **one directory level at a time** — no intermediate directories. `onelake_mkdir_p`
  in `scripts/fab_cli.py` walks the path component by component.
- `fab cp` requires the destination directory to already exist; the error when it doesn't (`"Source and
  destination must be of the same type"`) is misleading. `fab cp -r` from local to OneLake is unsupported.
- `fab mv` of an item into a folder **within the same workspace** is unsupported (`NotSupported`). Workaround:
  `fab import`/create directly into the target folder from the start.
- `fab import ... --format .py -f` **works** for create and update (re-import), and round-trips byte-identical
  with `fab export` — this had previously been assumed broken/"promiseware" and was verified working in this
  session.
- Job instance detail (`fab api workspaces/<ws>/items/<item>/jobs/instances/<id>`, with or without `-P
  beta=true`) never exposed `exitValue` in this tenant, even when the notebook called
  `notebookutils.notebook.exit(...)`. Only `status`/`failureReason`/timestamps are reliable — this is why the
  Livy dev loop exists as the output channel instead of relying on exit values or a persisted report file.
- **An Environment attached from a different workspace than the notebook/session kills Spark session
  acquisition** — both for Livy (`fabricSessionStateInfo.state = error` at startup) and for headless
  `fab job run` (`"System cancelled the Spark session ... while acquiring the session"`). This was the root
  cause of failures on both paths in this session; not a runtime-version mismatch (it reproduced on Spark
  runtime 1.3 and 2.0 alike). Fix: `fab cp <workspace>/<env>.Environment <target-workspace>` copies the
  Environment definition **including its staged custom libraries**, then `POST
  .../environments/<id>/staging/publish` (observed ~2.5–5 minutes) makes it live.
- `lakehouse_toolbelt` wheel **must be ≥ 1.0.7**. Version 1.0.6 (the version originally published in the
  test Environment) lacks `_configuration_helpers.py` and crashes `SourceConfiguration.__init__` with
  `AttributeError: 'SourceConfiguration' object has no attribute 'filename_filter_string'` whenever a dataset's
  `source_configuration` doesn't set the now-deprecated `filename_filter_string` key. 1.0.7 (from the
  toolbelt repo's `dist/`) works; the toolbelt source tree itself was already at 1.0.9 uncommitted.
- A session's `fabricSessionStateInfo.state` can be `error` while the outer `state` still reads `starting` —
  the driver polls both fields and fails fast on the inner one instead of waiting for the outer timeout.
- On F2/F4 capacities the default Starter Pool's cores/memory exceed the capacity's own limit
  (`SparkSettingsComputeExceedsPoolLimit`); a Small custom pool set as the workspace default Spark pool is
  required. This issue did not reproduce on the F8 test capacity.
- Livy echoes the value of the last expression in a submitted statement; notebook/template code that calls a
  function purely for its side effect (e.g. `land_payload(...)`) assigns the result to `_` so the dev-loop
  output stays readable.
- A Livy session with **no Environment attached** was observed to start in ~10 seconds vs. several minutes with
  one. Its preamble now resolves `lakehouse-toolbelt>=1.0.7` from the hosted feed using driver-side subprocess
  pip. The cell runner handles dedicated `%pip` cells with the same driver-only mechanism; this is not a claim
  of native Livy magic support or executor distribution. Generated notebook jobs use Fabric notebook `%pip`
  and run on the workspace default pool. For executor libraries or inline-installation restrictions, use a
  published Environment. See [Livy support boundaries and alternatives](../skills/nor-livy-session/SKILL.md#package-installation-support-and-alternatives).

## Safety and scope conventions

- Work only inside the physical workspace mapped from the selected logical `ws_<name>` package in
  `configuration/fabric_targets.json`; never touch anything outside
  it; never start/stop capacities without an explicit user instruction, and warn if the capacity is shared
  with other workspaces.
- Delete only items created within the current session, and only when asked.
- If a platform limitation (not a code bug) blocks the Livy path after reasonable effort, **stop and report the
  finding rather than continuing to work around it** — explicit user instruction given because Fabric's
  maturity for this exact workflow was an open question the toolpack was built to answer, not assume.
