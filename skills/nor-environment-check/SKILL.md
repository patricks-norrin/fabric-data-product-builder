---
name: nor-environment-check
description: Prerequisite check of the target Fabric workspace before building a data product - fab login, workspace, capacity state and SKU vs default Spark pool, shared resources lakehouse, project_configuration.json, optional Environment, and Livy API reachability.
---

# nor-environment-check

Run first in every session and whenever a `fab` command fails unexpectedly.
Set `TOOLPACK_ROOT` to the directory containing this installed toolpack. Scripts resolve the consuming project
from its Git root, falling back to the current directory outside Git.

```bash
bash "$TOOLPACK_ROOT/skills/nor-environment-check/scripts/check_environment.sh"
bash "$TOOLPACK_ROOT/skills/nor-environment-check/scripts/check_environment.sh" sample_api --workspace ws_example --target dev
```

Run the script directly; do not inspect `fab --help` or substitute a `whoami` command. Its first
authentication probe is `fab auth status`, and it stops before workspace calls when that probe reports no login.
If `lh_workspace_shared_resources` is missing, the script creates it at the target workspace root.

Reads `configuration/fabric_targets.json`, using its active target and default logical workspace unless
overridden. Prints `PASS/WARN/FAIL` lines and exits non-zero on any FAIL.

## Interpreting results
- `FAIL auth` → ask the user to run `fab auth login --tenant <id>` (browser); never handle secrets.
- `FAIL capacity` (Paused) → stop; the user must resume the capacity. Never start/stop capacities yourself.
- `WARN pool` (SKU ≤ F4 with Starter Pool) → default pool needs Small nodes or jobs fail with `SparkSettingsComputeExceedsPoolLimit`; ask the user to adjust workspace Spark settings.
- `FAIL shared lakehouse` → the shared lakehouse could not be created or verified; stop and report the Fabric error.
- `WARN project_configuration` → push it with `nor-data-product-config` (needed when configs use extra `source_configuration` attributes).
- `WARN environment` → no Environment is configured; generated notebooks install the verified wheel from shared OneLake.
- `FAIL environment` → a configured Environment is on the wrong capacity or does not publish its wheel; remove the stale binding or repair it.
- `FAIL livy` → tenant setting "Livy API" disabled or capacity paused; the Livy dev loop is unavailable, fall back to `fab job run` only.
