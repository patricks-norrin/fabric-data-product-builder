---
name: nor-environment-check
description: Read-only prerequisite check of the target Fabric workspace before building a data product - fab login, workspace, capacity state and SKU vs default Spark pool, lh_workspace_shared_resources, project_configuration.json, the Environment carrying lakehouse_toolbelt, Livy API reachability, and (optionally) an existing data product's lakehouse and config. Creates nothing.
---

# nor-environment-check

Run first in every session and whenever a `fab` command fails unexpectedly.

```bash
bash .claude/skills/nor-environment-check/scripts/check_environment.sh                # environment only
bash .claude/skills/nor-environment-check/scripts/check_environment.sh frankfurter_api  # + product lakehouse/config
```

Reads `configuration/target_workspace.json`. Prints `PASS/WARN/FAIL` lines and exits non-zero on any FAIL.

## Interpreting results
- `FAIL auth` → ask the user to run `fab auth login --tenant <id>` (browser); never handle secrets.
- `FAIL capacity` (Paused) → stop; the user must resume the capacity. Never start/stop capacities yourself.
- `WARN pool` (SKU ≤ F4 with Starter Pool) → default pool needs Small nodes or jobs fail with `SparkSettingsComputeExceedsPoolLimit`; ask the user to adjust workspace Spark settings.
- `FAIL shared lakehouse` → `lh_workspace_shared_resources` is a prerequisite owned by the platform team; do not create it silently — ask.
- `WARN project_configuration` → push it with `nor-data-product-config` (needed when configs use extra `source_configuration` attributes).
- `FAIL environment` → the Environment (from `target_workspace.json`) must exist on the same capacity and publish a `lakehouse_toolbelt-*.whl`.
- `FAIL livy` → tenant setting "Livy API" disabled or capacity paused; the Livy dev loop is unavailable, fall back to `fab job run` only.
