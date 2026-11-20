# Changelog

All notable changes to `norrin-fabric-data-product-toolpack` are documented here.

The history through version 1.0.16 was reconstructed from plugin manifest changes and the main Git history
because earlier releases were not tagged and the project did not yet have a changelog.

## [1.0.18] - 2026-11-17

### Changed

- All toolpack scripts are now standard-library Python and run unchanged on Linux, WSL and native Windows from
  GitHub Copilot or Claude Code. Bash and Git Bash are no longer required. `check_environment.py`,
  `push_data_product_config.py` and `run_notebook_job.py` replace their `.sh` versions with the same commands
  and arguments; run them with `python3` (Linux/WSL) or `python` (Windows).
- Scripts call `fab` with `--json` through a shared `scripts/fab_cli.py` and report the message Fabric returned on
  every failure instead of discarding it. Item lookups no longer use `fab api -q`, which prints the whole response
  when the query matches nothing.
- `nor-environment-check` is read-only: it no longer creates `lh_workspace_shared_resources` (the config push owns
  that) or probes local file writes, and it proves sign-in through the workspace lookup instead of parsing
  `fab auth status` text. It no longer warns about a missing `project_configuration.json` or Environment.
- `validate_data_product_config.py` reads `project_configuration.json` from the project that owns the config file
  (or `--project-root`), not from the current directory.
- `nor-spark-diagnostics` recipes are shell-neutral; driver logs are read with the new
  `livy_session.py download-log` command instead of `curl` and `/tmp`.
- The builder agent prompt is about half its former size: rules owned by skills (incremental extraction, raw
  format, CDC notebook shape, toolbelt feed) and host-specific approval wording were removed from it.
- The `fabric_targets.json` template has one target and one workspace without placeholder GUIDs.

### Removed

- Cursor plugin manifests; the toolpack targets GitHub Copilot and Claude Code, which both read `.claude-plugin/`.
- `push_toolbelt_wheel.sh` (its version check accepted 1.0.0-1.0.6); publish private toolbelt builds in an
  Environment instead.
- The migration error for the retired `target_workspace.json` format and the template-placeholder check.

## [1.0.17] - 2026-11-16

### Added

- `nor-lakehouse-query`: read-only T-SQL over a product lakehouse's Delta tables through the hosted Fabric SQL
  endpoint MCP server (`execute_query`). Covers target resolution with `fab`, discovery queries, current versus
  historical change-history rows, endpoint error handling, and a `nor-livy-session` fallback. The plugin now ships
  the `fabric-sqlendpoint` MCP server in `.mcp.json` and `.claude-plugin/plugin.json`.
- `nor-pipeline-author`: renders native `pl_<id>` definitions (`nb_extract_<id>` → `nb_cdc_<id>` on `Succeeded`)
  using notebook `.platform` logical IDs, checks their structure, and delegates publishing to `fab deploy` /
  `fabric-cicd`. Notebook activities default to a 2-hour timeout, 1 retry, and the shared
  session tag `pl_<id>`. `run_notebook_job.sh` publishes and runs `pl_*` names as DataPipelines.
- `nor-environment-check` compares workspace Spark settings with `recommended_workspace_settings.json` and prints
  each difference as a non-blocking recommendation with a short click path and reason. It starts with high
  concurrency for pipelines (needed for the shared session tag) and for notebooks.
- Architecture §8 Orchestration: pipelines own orchestration and scheduling, more than one notebook or activity
  means one pipeline, master pipelines invoke product pipelines, and failures must fail the pipeline so external
  monitoring can alert. The builder accepts a build with one `pl_<id>` run.
- `run_notebook_job.sh start`, `wait`, and `status`. `start` reads the job instance id from
  `fab job start --json`. `run` and `wait` poll `fab job run-status --json`, print a heartbeat line per poll, and
  print the `failureReason` and the diagnostics next step as soon as a job fails. A `--timeout` returns exit 124
  and leaves the Fabric job running, resumable with `wait`. `fab job start --wait` is not used because it
  cancels the job on timeout by default. `status` reads the latest job per notebook from Fabric, and `runs`
  delegates to `fab job run-list`.
- `job_started` (with the item path), `job_status`, and `job_wait_timeout` manifest events, and
  `run_manifest.py --latest-jobs`.
- A builder "Progress and feedback" contract: per-phase status lines, bounded waits with status between them,
  immediate failure reporting, concurrent independent chains, and a Done/Running/Blocked/Next block at the end of
  every turn so invoking sessions can follow a background build.

### Changed

- Published the marketplace at `patricks-norrin/fabric-data-product-builder` on GitHub and updated the installation
  instructions so customer environments do not need Azure DevOps repository access.
- Raised the minimum `fab` version to 1.9.0, which the job runner relies on for `--json`.
- Generated extract and CDC notebooks install `lakehouse-toolbelt>=1.0.7` from the hosted wheel feed in a
  dedicated `%pip` cell instead of locating a wheel in shared OneLake.
- Removed local-wheel upload and Environment-published toolbelt requirements from the normal builder workflow
  and preflight; retained the wheel-upload helper for explicitly selected compatibility workflows.
- Switched the Livy driver bootstrap to the hosted feed, surfaced bootstrap failures as command failures, and
  handled dedicated `%pip` cells through explicit driver-only pip execution. Documented the distinction from
  notebook `%pip`, the unverified native Livy magic support, and Environment-based alternatives.

### Fixed

- Pipeline failures now hand their exact workspace/item/job IDs to `nor-spark-diagnostics`. A compact read-only
  activity-query recipe covers retries, pagination, notebook/session mapping and non-Spark/pre-session errors;
  deployment failures remain separate from run diagnostics. No additional diagnostic scripts or dependencies.
- Pipeline publishing uses the upstream `fabric-cicd` binding and deployment implementation through `fab deploy`,
  rather than custom placeholder resolution. Only the selected pipeline is published; orphan deletion is disabled.
- `nor-spark-diagnostics` reads driver stdout before stderr, because notebook cell tracebacks are written there.
  Log content is downloaded with `curl` and an `az` token, because `fab api` cannot parse the
  `application/octet-stream` log response. Downloads are bounded tail ranges written to a temporary file and searched.

## [1.0.16] - 2026-10-08

### Added

- `nor-data-product-modelling`, a Foundational and Business modelling standard covering notebook structure,
  documented business rules, business grain and `dpmeta_uid`, deterministic DataFrame transformations,
  monetary datatypes, Delta descriptions, and cross-product relationships.
- Builder routing between Source-aligned, Foundational, Business, Analytical, and undetermined requests.
- Structural tests for modelling-skill discovery and synchronized plugin versions.
- GitHub Copilot CLI marketplace installation instructions.
- Project changelog reconstructed from manifest versions and Git history, with release bookkeeping guidance.

### Changed

- Expanded package and architecture documentation from source-aligned-only scope to include consumer-aligned
  modelling guidance without claiming an end-to-end modelling workflow.
- Made Fabric preflight connection-gated: local notebook review, editing, and local checks work without Fabric
  authentication, while remote inspection, execution, publication, provisioning, and cleanup still require
  the full environment check.

## [1.0.15] - 2026-10-07

### Changed

- Made source-side incremental extraction the default whenever the source provides a reliable delta mechanism.
- Standardized initial loads as the same request without a delta predicate instead of separate first-run or
  load-mode branches.
- Limited full snapshots to explicit requests, closed timeframes, or sources proven to lack incremental filters.

## [1.0.14] - 2026-09-18

### Changed

- Required source-aligned product identifiers to name the actual source provider or system rather than a
  business subject or dataset.

## [1.0.13] - 2026-09-18

### Added

- `nor-rest-extraction` for source-specific HTTP requests, pagination, raw response formats, and native Spark
  reader decisions.

### Changed

- Generalized extraction templates and guidance beyond the original sample API.
- Kept the shared data-product configuration minimal while moving operational extraction behavior into the
  source-specific notebook cell.
- Clarified the one-time workspace-discovery approval boundary.

## [1.0.12] - 2026-09-17

### Changed

- Clarified host command approval prompts and bounded command, project-write, and Fabric-write scopes.

## [1.0.11] - 2026-09-17

### Added

- Preflight workspace permission checks before provisioning or running data-product workloads.

## [1.0.10] - 2026-09-17

### Added

- First-run target bootstrap guardrails and placeholder rejection.
- `nor-spark-diagnostics` with a read-only evidence ladder for failed or slow Spark runs.
- Small-sample-first development guidance and append-only operational run manifests.
- Tests for environment checks, project context, notebook rendering, and run manifests.

### Changed

- Made the environment check the first builder procedure step.
- Reused one Livy session per development phase and separated sample proof from the final intended load.

## [1.0.9] - 2026-09-17

### Changed

- Simplified generated notebook patterns and removed unnecessary workspace configuration.
- Added repository line-ending rules for consistent cross-platform checkouts.

## [1.0.8] - 2026-09-17

### Fixed

- Corrected schema-enabled Lakehouse provisioning and OneLake path handling.

## [1.0.7] - 2026-09-17

### Changed

- Simplified data-product configuration guidance and retained only the minimal shared toolbelt contract.

## [1.0.6] - 2026-09-17

### Fixed

- Recognized a valid `fab auth status` response even when the CLI exits non-zero.

## [1.0.5] - 2026-09-17

### Added

- Fail-closed minimum-version checks for `fab` and Azure CLI.

### Changed

- Required scripts to be invoked from the directory of the skill that owns them.

## [1.0.4] - 2026-09-17

### Fixed

- Resolved consuming-project and installed-toolpack paths without broad filesystem searches.

## [1.0.3] - 2026-09-16

### Fixed

- Repaired architecture-skill YAML frontmatter so plugin hosts can discover it reliably.

## [1.0.2] - 2026-09-16

### Fixed

- Corrected architecture-skill metadata after the host-portable plugin restructure.

## [1.0.1] - 2026-09-16

### Added

- Packaging and distribution documentation for Azure DevOps marketplace installation.
- Shared OneLake wheel bootstrap for generated notebooks.

### Changed

- Constrained project discovery to the consuming solution root.
- Standardized the prescribed `fab auth status` check.

## [1.0.0] - 2026-09-16

### Added

- Initial Norrin source-aligned data-product architecture, builder agent, skills, scripts, and notebook
  templates.
- End-to-end configuration, extraction, raw landing, CDC, Livy development, environment checking, notebook
  publishing, and headless execution workflow.
- Vendored `lakehouse_toolbelt` documentation and examples as the runtime implementation contract.
- Harness-neutral plugin packaging for GitHub Copilot CLI, Claude Code, and Cursor.
- System overview, skills reference, conventions, and decision history.

### Verified

- Proved the sample extract and CDC flow through Livy and `fab job run` with `lakehouse_toolbelt` 1.0.7 before
  the host-portable plugin restructure.