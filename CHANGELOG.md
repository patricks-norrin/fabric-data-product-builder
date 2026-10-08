# Changelog

All notable changes to `norrin-fabric-data-product-toolpack` are documented here.

The history through version 1.0.16 was reconstructed from plugin manifest changes and the main Git history
because earlier releases were not tagged and the project did not yet have a changelog.

## [Unreleased]

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