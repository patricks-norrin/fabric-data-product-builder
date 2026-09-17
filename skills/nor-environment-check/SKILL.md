---
name: nor-environment-check
description: Prerequisite check of the target Fabric workspace before building a data product - fab and az minimum CLI versions, fab login, workspace, capacity state and SKU vs default Spark pool, shared resources lakehouse, project_configuration.json, optional Environment, and Livy API reachability.
---

# nor-environment-check

Run first in every session and whenever a `fab` command fails unexpectedly.
Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`; the script locates the toolpack from its own
path. The consuming project is the Git root of the current directory (cwd outside Git).

```bash
bash "<directory of this SKILL.md>/scripts/check_environment.sh"
bash "<directory of this SKILL.md>/scripts/check_environment.sh" sample_api --workspace ws_example --target dev
```

Run this installed script as-is. Do not copy it to `/tmp`, `sed` it, or substitute `fab --help` /
`whoami`. It checks `fab >= 1.7.0` and `az >= 2.50.0` first, then `fab auth status` and a reversible
local-workspace create/modify/delete probe. It continues with every independent check whose dependencies
are available and records dependent checks as `SKIPPED`.
If `lh_workspace_shared_resources` is missing, the script creates it at the target workspace root.

The local probe verifies the process executing the preflight can read and write the consuming project; it
cannot inspect VS Code/Copilot tool-approval policy. A host may still ask the user to approve an individual
terminal or file-edit action. Before the first mutation, the builder requests approval for only the planned
command families and project directories; that explanation is not an approval grant. When the host presents
a repo-scoped persistent option for the command family, the user must choose it themselves. The builder must
not request unrestricted shell, home-directory, toolpack, or tenant-wide access. Treat a denied approval as
a blocker and report it rather than retrying.

Reads `configuration/fabric_targets.json`, using its active target and default logical workspace unless
overridden. A clean run prints one summary line. A run needing review prints one consolidated report with
`BLOCKERS`, `ACKNOWLEDGMENTS`, `RECOMMENDATIONS`, `SKIPPED`, and `PASSED`; it exits non-zero only when blockers
exist. Present all blockers and acknowledgments to the user together and ask once for all required decisions
or actions. After those are resolved, rerun the complete preflight because changed capacity, authentication,
or target settings can affect later checks.

## Interpreting results
- `ERROR missing project target configuration` → the project has no `configuration/fabric_targets.json`.
  Do **not** write one from assumptions. Offer the workspaces the signed-in identity can actually see
  (`fab ls`), ask which physical workspace to target and which logical `ws_<name>` key it maps to, then
  verify the choice with `fab get "<name>.Workspace" -q id` before writing anything. Copy the template named
  in the error, set `active_target` to `dev` with that single entry, and **derive** the Environment GUIDs from
  `fab api workspaces/<ws-id>/environments` — never ask for them and never invent them. With no Environment,
  omit the block entirely and let `WARN environment` stand. Write the file into the consuming project only.
- `ERROR ... is still the template placeholder` → a copied template kept `<environment-id>` /
  `<workspace-id>`. Derive the real GUIDs as above, or remove the `environment` block; never leave the
  placeholder in place, because it is truthy and would otherwise be baked into the generated notebooks.
- `FAIL fab` (missing or `< 1.7.0`) → stop; ask the user to `pip install -U 'ms-fabric-cli>=1.7.0'`. The
  0.1.x `fab` on some PATHs is not this CLI. Never patch the check script to match another tool's output.
- `FAIL az` (missing or `< 2.50.0`) → Livy cannot be trusted; ask the user to upgrade Azure CLI
  (`https://aka.ms/install-azure-cli`). Continue only if they explicitly accept no Livy loop.
- `FAIL auth` → ask the user to run `fab auth login --tenant <id>` (browser); never handle secrets.
  Do **not** run `fab auth status` yourself — it prints tokens. Trust this script's PASS/FAIL line.
- `FAIL local workspace` → the agent process cannot safely create or modify the consuming project's files.
  Stop and ask the user to grant workspace write access or select a writable project directory.
- `FAIL capacity` (Paused) → stop; the user must resume the capacity. Never start/stop capacities yourself.
- `ACKNOWLEDGMENT capacity` (F2 or F4) → **stop and ask before any Spark work.** This workflow is verified on F8; on F2/F4
  sessions and jobs may fail or queue. Present the SKU and the risk, then continue only once the user either
  acknowledges proceeding on the current capacity or scales it to F8. Never scale, start, or stop a capacity
  yourself. Repeat the acknowledgment in the final report.
- `WARN pool` (F2/F4 with Starter Pool) → default pool needs Small nodes or jobs fail with
  `SparkSettingsComputeExceedsPoolLimit`; ask the user to set a Small custom pool as the workspace default, or
  to scale to F8. The error is deterministic — do not retry a session that failed this way.
- `FAIL shared lakehouse` → the shared lakehouse could not be created or verified; stop and report the Fabric error.
- `WARN project_configuration` → push it with `nor-data-product-config` (needed when configs use extra `source_configuration` attributes).
- `WARN environment` → no Environment is configured; generated notebooks install the verified wheel from shared OneLake.
- `FAIL environment` → a configured Environment is on the wrong capacity or does not publish its wheel; remove the stale binding or repair it.
- `FAIL livy` → tenant setting "Livy API" disabled or capacity paused; the Livy dev loop is unavailable, fall back to `fab job run` only.
