---
name: nor-environment-check
description: Read-only prerequisite check of the target Fabric workspace before building a data product - fab and az minimum CLI versions, sign-in and workspace access, capacity state and SKU vs default Spark pool, workspace Spark settings, shared resources lakehouse, optional Environment, product lakehouse, and Livy API reachability.
---

# nor-environment-check

Run first in every session and whenever a `fab` command fails unexpectedly. Run the script next to this file
with `python3` (Linux/WSL) or `python` (Windows); it locates the toolpack itself. The consuming project is the Git
root of the current directory (cwd outside Git). For a nested project, pass
`--project-root "<directory containing configuration/fabric_targets.json>"` and use the same root for every later
skill command.

```bash
python3 "<directory of this SKILL.md>/scripts/check_environment.py"
python3 "<directory of this SKILL.md>/scripts/check_environment.py" sample_api --workspace ws_example --target dev
```

Run the installed script as-is; do not copy or patch it. It is read-only: it never creates, changes or deletes
anything locally or in Fabric. It checks `fab >= 1.9.0` and `az >= 2.50.0`, then every independent check whose
dependencies are available, and lists dependent checks as `SKIPPED`. Each failure includes the message Fabric
returned.

A clean run prints one summary line. Otherwise it prints one report with `BLOCKERS`, `ACKNOWLEDGMENTS`,
`RECOMMENDATIONS`, `SKIPPED`, and `PASSED`, and exits non-zero only when blockers exist. Present all blockers,
acknowledgments and recommendations to the user together and ask once for the required decisions. Rerun the
complete check after they are resolved.

## Interpreting results
- `project target configuration: missing ...fabric_targets.json` → do **not** write one from assumptions. Run
  `fab ls` once to show the workspaces the signed-in identity can see, ask which physical workspace to target
  and which logical `ws_<name>` key it maps to, and verify the choice with `fab get "<name>.Workspace" -q id`.
  Copy the template named in the error into the consuming project and fill in that single workspace. Add an
  `environment` block only when the user wants an Environment; derive its GUIDs from
  `fab api workspaces/<ws-id>/environments`, never invent them.
- `fab` / `az` below minimum or missing → stop and ask the user to upgrade (`pip install -U 'ms-fabric-cli>=1.9.0'`,
  `https://aka.ms/install-azure-cli`). A 0.1.x `fab` on some PATHs is a different tool. Without `az`, continue
  only if the user accepts no Livy loop.
- `Fabric: ...` → the workspace lookup failed with the quoted Fabric message. When it indicates no sign-in, ask
  the user to run `fab auth login --tenant <id>`; never handle secrets. `fab auth status` is safe for diagnosis.
- `capacity ... state=` not Active → stop; the user must resume it. Never start, stop or scale a capacity.
- `ACKNOWLEDGMENTS capacity` (F2 or F4) → **stop and ask before any Spark work.** This workflow is verified on F8;
  smaller capacities may queue or fail. Continue once the user acknowledges or scales to F8, and repeat the
  acknowledgment in the final report.
- `pool` (F2/F4 with Starter Pool) → jobs fail deterministically with `SparkSettingsComputeExceedsPoolLimit`;
  ask the user to set a Small custom pool as the workspace default or scale to F8. Do not retry.
- `workspace setting: ...` → not a blocker. Relay each as printed: current and recommended value, the `How:`
  click path and the `Why:`. The user or a workspace admin decides. Rules live in
  `recommended_workspace_settings.json` next to this file; add one only with a concrete workflow reason.
- `lh_workspace_shared_resources is missing` → expected in a new workspace; `nor-data-product-config` creates it
  when it pushes the first configuration.
- Environment on another capacity or workspace → Spark sessions fail at startup. Remove the binding from
  `fabric_targets.json` or copy the Environment into the target workspace.
- `livy: endpoint not reachable` → tenant setting "Livy API" disabled or capacity paused; the Livy loop is
  unavailable, fall back to `nor-notebook-publish-and-run`.
- `no az token` → Livy needs `az login --tenant <id> --allow-no-subscriptions --use-device-code`.
