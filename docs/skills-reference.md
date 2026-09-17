# Skills reference

One entry per skill: what it does, why it exists as its own skill (rather than folded into another one or
into the agent), its inputs/outputs, and what it calls. Descriptions are quoted verbatim from each `SKILL.md`
frontmatter — that text is what makes Claude Code load the skill, so it is the contract.

---

## nor-data-product-architecture

**Description (frontmatter):** "Norrin architecture for Microsoft Fabric data products. Use before designing,
naming or creating anything: deciding data product boundaries (one source system = one product, datasets
inside), lakehouse and workspace responsibilities (ws_extract, lh_<id>, lh_workspace_shared_resources),
raw-as-insurance landing, when CDC change history applies vs snapshot or non-tabular exceptions, naming and
folder conventions."

**Reason to exist:** every other skill and the agent make judgment calls (what's a dataset, what's the key,
does this need CDC) that must be answered the same way every time, by every tool (Claude Code, Copilot CLI,
a human). Centralizing the reasoning here — rather than repeating it in each skill — is what keeps the other
skills mechanical.

**Contents:** `SKILL.md` only (no scripts — it is pure decision rules with pointers into `reference/architecture/*`
and `reference/lakehouse_toolbelt/docs/` for the long form).

**Inputs:** none (reference material only). **Outputs:** none (informs decisions made in other skills).

---

## nor-environment-check

**Description:** "Prerequisite check of the target Fabric workspace before building a data product -
fab login, workspace, capacity state and SKU vs default Spark pool, lh_workspace_shared_resources,
project_configuration.json, the Environment carrying lakehouse_toolbelt, Livy API reachability, and
(optionally) an existing data product's lakehouse and config. Creates nothing."

**Reason to exist:** almost every failure encountered while building this (capacity paused, pool too small for
the SKU, Environment in the wrong workspace, wheel too old, no `az` token) is a *precondition*, not a bug in
the data product logic. Running one script first turns a confusing mid-build failure into a named, actionable
line before any Fabric object is touched.

**Inputs:** `configuration/fabric_targets.json`; optional `<data_product_identifier>`, `--workspace`, and
`--target` arguments.
**Outputs:** PASS/WARN/FAIL lines to stdout; non-zero exit on any FAIL.
**Calls:** `scripts/check_environment.sh` → sources `scripts/fab_common.sh` → `fab`, `az account get-access-token`.

**Checks performed:** `fab >= 1.7.0` and `az >= 2.50.0`; `fab auth status`; capacity state + SKU vs. default Spark pool (Starter Pool on F2/F4 is a
WARN — see conventions doc); `lh_workspace_shared_resources` existence; `project_configuration.json` presence;
Environment existence, **same-workspace-as-target** (FAIL otherwise), and toolbelt wheel version ≥ 1.0.7 (FAIL
otherwise); `az` token availability for Livy; Livy sessions endpoint reachability; optionally the named data
product's lakehouse (existence + schema-enabled) and config presence.

---

## nor-data-product-config

**Description:** "Author, validate, push and provision a Norrin data product configuration - the JSON that
defines datasets, unique identifier columns, version timestamps and API source metadata for
lakehouse_toolbelt. Pushes it to lh_workspace_shared_resources with fab cp, pushes project_configuration.json,
and provisions the product folder and schema-enabled lakehouse lh_<id>."

**Reason to exist:** the config JSON is the single source of truth `lakehouse_toolbelt.DataProduct()` reads at
runtime; getting its shape, key columns and location wrong breaks everything downstream silently or with a
cryptic Spark stack trace. This skill is the only place that writes it, validates it against the same rules
the toolbelt enforces (plus Norrin naming), and provisions the Fabric containers (folder + schema-enabled
lakehouse) the config implies.

**Inputs:** `configuration/data_product/<id>/<id>.json` (authored per the "Authoring" section — from API docs
to config, one dataset per entity, keys/timestamps/reader-options reasoned about explicitly);
`configuration/data_product/project_configuration/project_configuration.json` (allow-list of extra
`source_configuration`/`publish_configuration` attributes).
**Outputs:** config pushed to `lh_workspace_shared_resources/Files/configuration/data_product/<id>/<id>.json`;
workspace folder `<id>.Folder`; schema-enabled lakehouse `lh_<id>`; prints `LAKEHOUSE_ID`/`WORKSPACE_ID`.
**Calls:** `scripts/validate_data_product_config.py` (stdlib only — mirrors the toolbelt's own validator plus
Norrin naming rules from `reference/architecture/conventions.json`); `scripts/push_data_product_config.sh` →
`fab_common.sh` → `fab mkdir`/`fab cp`/`fab exists`.

**Idempotency:** re-running is safe — existing config/folder/lakehouse are left alone (checked via `fab exists`
/ `item_id` before creating).

---

## nor-notebook-author

**Description:** "Author the two single-responsibility notebooks of a source-aligned data product from
templates in Fabric .py definition format - nb_extract_<id> (source to raw files per batch) and nb_cdc_<id>
(raw to lakehouse_toolbelt change history). Renders default-lakehouse bindings and stages the wheel from shared OneLake, then you
write only the source-specific extraction cells from the API documentation."

**Reason to exist:** ~90% of both notebooks (parameters cell, config loading, dpmeta processing, the CDC
upsert loop, summaries) is identical across every data product — it's the toolbelt contract, not the source.
Only the cells that actually call the API differ. Templating that fixed part means every product gets the
same tested pattern, and the agent's real work is scoped to the small part that has to differ.

**Inputs:** `configuration/data_product/<id>/<id>.json`; `configuration/fabric_targets.json`; the two
templates under `templates/nb_extract.Notebook/` and `templates/nb_cdc.Notebook/`; `templates/platform.json`.
**Outputs:** `ws_<name>/<id>/nb_extract_<id>.Notebook/{notebook-content.py,.platform}` and the `nb_cdc`
equivalent, with `default_lakehouse`, `default_lakehouse_workspace_id` and `environmentId`/`workspaceId`
resolved to real GUIDs via `fab`. `nb_cdc` is complete as rendered (fully config-driven); `nb_extract` has one
`# --- SOURCE SPECIFIC: <dataset> ---` cell per dataset for the agent/human to implement.
**Calls:** `scripts/render_notebook.py` → shells out to `fab get`/`fab api` for ids (no `fab_common.sh` — this
script is pure Python + subprocess, deliberately dependency-light since it only reads ids, never mutates Fabric).

**Rules it encodes for every cell** (also documented inline in `SKILL.md`): one responsibility per cell,
markdown before code, rerunnable (idempotent per `batch_id`), prints what it produced, no `display()`/`%pip`/
`%run`/`/lakehouse/default/` mounts (must work identically in Livy and the notebook UI), never hardcode ids or
dates.

---

## nor-livy-session

**Description:** "Cell-by-cell development loop for Fabric notebooks without VS Code - open a Livy Spark
session on the product lakehouse (with the lakehouse_toolbelt Environment attached) through fab api, run
notebook .py cells or ad-hoc PySpark/SQL statements, read outputs and tracebacks, iterate on a single cell,
then close the session. Use whenever you need to see what a cell actually produces."

**Reason to exist:** this is the answer to "how does an agent without a VS Code UI get cell-level, human-
readable feedback while developing a notebook." No exit-value or persisted-report channel proved reliable
(see decision log); Livy statement output is the only channel that actually shows stdout, `df.show()` output
and Python tracebacks per cell, in order, with state persisting between cells like a real notebook session.

**Inputs:** a lakehouse name (session target); a `notebook-content.py` file and a cell selector (`all` or
comma-separated indices) for `run-cells`; arbitrary code for ad-hoc `statement`.
**Outputs:** per-cell stdout/tracebacks printed to the terminal; session state in
`.scratch/<ws_name>/livy/livy_session.json`
(gitignored — session-local, not repo state).
**Calls:** `scripts/livy_session.sh` (sources `fab_common.sh` only for id lookups — the session itself is
created and driven with `az account get-access-token` + `curl`, **not** `fab api`; see conventions doc for
why); `scripts/notebook_cells.py` (parses `# CELL`/`# PARAMETERS CELL`/`# MARKDOWN`/`# METADATA` markers into
an ordered cell list, maps `%%sql` cells to Livy `kind: sql`); `scripts/format_statement_output.py` (renders
one Livy statement's JSON result as text, non-zero exit on error); `preamble/livy_preamble.py` (see below).

**The preamble** is injected as statement 0 of every session created by `create`. It patches
`lakehouse_toolbelt`'s cached `notebookutils` reference so `runtime.context["currentWorkspaceName"]` — which
is `None` under Livy — falls back to the workspace name the agent already knows, and (with `--no-environment`)
pip-installs the toolbelt wheel staged at `lh_workspace_shared_resources/Files/libraries/`. It also reports
`onelake_access: True/FAILED` as an assertion, not by decoding token claims (see decision log — this was a
direct response to a false-positive safety flag on the earlier token-introspection approach).

---

## nor-notebook-publish-and-run

**Description:** "Publish a data product notebook definition (.py) into the product folder of the target
workspace with fab import, run it headless with fab job run (parameters, Environment, workspace pool), poll
the job instance and surface status and failureReason. Also exports a notebook back from Fabric to compare
with the local definition."

**Reason to exist:** a notebook that only ever ran interactively inside a Livy session hasn't proven it will
run the way it actually runs in production — as a scheduled/triggered headless job, under its own Environment
binding, with no one watching cell-by-cell. This skill is the "does it actually work unattended" gate, and the
only place `fab import`/`fab job run` are called.

**Inputs:** a data product id and notebook name (`nb_extract_<id>` / `nb_cdc_<id>`); optional `fab job run`
arguments (parameters, timeout).
**Outputs:** the notebook published into `<workspace>/<id>.Folder/<notebook>.Notebook`; job status + full
`failureReason` (no exit value is exposed by the Fabric API — verified, see conventions doc) printed to stdout;
`export` mode diffs the remote definition against the local file.
**Calls:** `scripts/run_notebook_job.sh` → `fab_common.sh` → `fab import`/`fab job run`/`fab export`/`fab api
.../jobs/instances/<id>`.

---

## nor-data-product-builder (agent)

**Description:** "Builds a Norrin source-aligned data product in Microsoft Fabric end to end from source API
documentation - configuration, folder and lakehouse, nb_extract and nb_cdc notebooks, raw files and
change-history tables - using only fab and the nor-* skills. Use when asked to create, extend or repair a
source-aligned data product." **Tools:** `Bash, Read, Edit, Write, Glob, Grep, WebFetch, mcp__microsoft-learn__*`.

**Reason to exist as an agent, not a skill:** every other component above is a deterministic procedure with a
single clear output. This is the one place that needs judgment — reading unfamiliar API docs and deciding
datasets/keys, deciding when a Livy failure means "fix this cell" vs. "stop and ask," deciding when to fall
back to headless-only if Livy is unavailable, and writing an evidence-based report rather than a claim.

**Procedure it enforces** (verbatim structure from `agents/nor-data-product-builder.agent.md`):
1. Load `nor-data-product-architecture`, run `nor-environment-check`; stop and report on failure.
2. Understand the source (WebFetch the docs, sample endpoints with `curl`) → decide datasets/keys/timestamps,
   write reasoning into `source_configuration.notes`.
3. Author, validate, push, provision config via `nor-data-product-config`.
4. Render both notebooks via `nor-notebook-author`; implement the source-specific cells.
5. Dev loop via `nor-livy-session`: run cells in order, fix only the failing cell on error, inspect raw/,
   confirm `Tables/<id>/<dataset>` via `fab table schema`, repeat until clean from a fresh session.
6. Publish and headless-run via `nor-notebook-publish-and-run`; on failure read `failureReason`, fix, republish.
7. Report what exists now with evidence (row counts, `fab table schema` output), assumptions made, what to review.

**Retry/safety rules:** max 3 fix attempts per cell then stop and show the cell/error/hypothesis; never change
config key columns silently — propose with data (duplicate counts) and wait for approval; if Livy is
unavailable, fall back to publish + headless run and read `failureReason` (this is also the direct instruction
under which the agent must **abort and report**, not keep working around a platform limitation, if the Livy
path doesn't unfold within a reasonable effort — see decision log, 2026-09-14 instruction).
