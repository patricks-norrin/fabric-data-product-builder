# TODO

Running backlog of things raised in conversation but not yet acted on. Not a sprint board — just a place so
decisions and findings stop living only in chat history. Update this file whenever something gets deferred or
resolved; move resolved items to `decision-log.md` instead of deleting them outright.

## Small, low-risk — do next session

- [ ] Add the `fab cp <item> <folder> -f` then `fab rm <original> -f` workaround (moving an **already-existing**
  item into a folder — `fab mv` same-workspace is unsupported) to `nor-notebook-publish-and-run/SKILL.md`'s
  gotchas. The original internal source path is intentionally omitted.
- [ ] Log the `fab-deploy` (skill) vs. `fab deploy` (native command) mix-up in `decision-log.md`: the fab-cli-skills
  `fab-deploy` skill is plain `export`/`import`, no parameterization; the **native** `fab deploy --config
  ... --target_env ...` is `fabric-cicd` wrapped directly into `fab` (same `find_replace`/`$workspace.$id`/
  `$items.<Type>.<Name>.$id` model). No new pip dependency needed for future promotion work.

## Architecture docs — needs a decision first

- [ ] **Local vs. Global scoping.** `center_of_exellence/.../Data-Management/Data-Products.md` describes a
  scoping dimension orthogonal to the Source-Aligned/Foundational/Business/Analytical tiers: Local (site/segment
  data product) vs. Local Harmonized vs. Global Harmonized (org-wide baseline, owned by a Global Process Owner,
  that local products must stay compatible with). Not currently in our docs. Decide: adopt as-is, adapt, or
  explicitly out of scope for this toolpack?
- [ ] **Classification/sensitivity taxonomy** for source data (deferred by user 2026-09-14). Real precedent
  exists but is stale: `wikis/fabric_wiki/Fabric-Data-Platform/Architecture/Data-Access-Management.md` is marked
  "Pending Fabric specific rewrite" (currently describes the old Databricks/Unity-Catalog Entra-group model).

## Toolpack scope — deferred until now, may be ready to pick up

- [ ] **`nor-data-product-validation` skill.** Was gated on "extract + CDC proven reliable" — now proven with
  two public APIs, both via Livy and headless `fab job run`. Candidate content: UID
  uniqueness, duplicate detection, schema-vs-source checks. Read
  `wikis/fabric_wiki/Fabric-Data-Platform/Architecture/Report-and-data-testing-architecture.md` (108 lines,
  unread beyond title) before scoping it.
- [ ] **`pl_<data_product_identifier>` pipeline** — naming reserved, never built. Read
  `fabric-toolbox/accelerators/CICD/Branch-out-to-new-workspace` in full first if the pipeline is meant to
  support the branch-workspace exploratory pattern.
- [ ] **Future promotion skill** (`ws_extract_dev` → `test`/`prod`): use native `fab deploy --config config.yml
  --target_env <env>` + a `parameter.yml` for the four GUID fields `render_notebook.py` currently bakes in for
  one workspace (`default_lakehouse`, `default_lakehouse_workspace_id`, `environmentId`, `workspaceId`). Verify
  whether `fab deploy` skips Lakehouse `find_replace` the same way the standalone `fabric-cicd` library does
  (division of labor: `nor-data-product-config`'s `fab mkdir -P enableSchemas=true` would keep owning lakehouse
  creation either way).

## First-run bootstrap — no `fabric_targets.json` yet

Resolved 2026-09-17; see `decision-log.md` #27–29. A live agent run cleared this case on its own by writing
the file, so the risk was improvised contents, not a hard stop. `resolve_context` now names the template and
forbids invented workspace names and GUIDs, rejects the unedited `<environment-id>` / `<workspace-id>`
placeholders, and `nor-environment-check/SKILL.md` documents the ask-offer-verify-derive bootstrap. The
guardrail is deliberately documentation plus validation — no prompt-flow script was built.

Still open:

- [ ] `need_target` cannot distinguish "workspace does not exist" from "no access" from "expired token" — the
  `fab get` failure is identical in all three, which is why the message hedges with `(fab auth status?)`.
  Decide whether that is good enough before building a prompt flow on top of it.

## Distribution / install — partly done 2026-09-16

Published to `dev.azure.com/naksfi/Fabric/_git/nor-data-product-builder` and installed end to end via Copilot
CLI. Mechanics and verified-vs-assumed status are written up in `packaging-and-distribution.md`.

- [x] Make `.devcontainer/devcontainer.json` harness-neutral and include Azure CLI for `nor-livy-session`.
- [x] Push to a remote and prove a marketplace install works from Azure DevOps.
- [x] Rename the agent to `*.agent.md` so Copilot CLI discovers it.
- [ ] **Confirm the agent is actually invocable.** Run a live session on a clean machine and check `/agents`
  lists `nor-data-product-builder`. Everything so far only proves the *file* installs to the right path. Do
  this before the stale `~/.copilot/agents/norrin_fabric_data_engineering.agent.md` is allowed to confuse the
  result — or delete that file first.
- [ ] **Run `tests/` for the first time.** `pytest` is not importable in the dev environment, so
  `test_project_context.py` and `test_render_notebook.py` have never executed. The restructure moved every
  path these tests cover.
- [ ] **Re-prove extract + CDC after the restructure.** Last verified 2026-09-11, before the worktree
  restructure and multi-harness path abstraction. Until this is re-run, the pack is published but unproven.
- [ ] **Enforce synchronized versions at release time.** Both plugin manifests and both marketplace entries
  currently agree on `1.0.10`. Add one focused check that fails when they
  differ, plus a documented bump-before-publish step; current correctness is manual, not enforced.
- [ ] **Generate `.cursor-plugin/` from `.claude-plugin/`** (or the reverse) in a script. They are
  hand-maintained near-duplicates today and will diverge.
- [ ] Test the `.claude-plugin/` and `.cursor-plugin/` manifests in Claude Code and Cursor. Only Copilot CLI
  has been exercised.
- [ ] Document the Azure DevOps credential prerequisite. The dev machine authenticates through the Windows
  Git Credential Manager over the WSL interop mount; a fresh image has nothing equivalent and will fail at
  `marketplace add`. Decide between PAT and interop-helper setup and write it down.
- [ ] No documented bare-metal prerequisite list (`fab`, `az`, `python3`, `git`) for engagements that won't use
  the devcontainer.
- [ ] `fab-bootstrap` skill (fab-cli-skills) has a working pattern for install + PATH + login on Windows/macOS —
  reference when writing the above.

## Plugin self-containment

Microsoft Fabric skills are available only on the development machine. The runner image receives this entire
Norrin toolpack through `plugin install`; `fab`, `az`, Python, and Git remain external runtime prerequisites and
will eventually be managed by the devcontainer. Generated ambient precedence files and Microsoft-skill routing
rules are therefore not production requirements.

- [ ] **Add a clean-runner acceptance check for the installed plugin.** Verify that `plugin install` exposes
  `nor-data-product-builder` and every referenced `nor-*` skill without Microsoft skills present, then run the
  small-sample extract + CDC workflow. Treat any undeclared Microsoft-skill dependency as a packaging defect.

## Notebook and Spark troubleshooting — implemented, needs live proof

`nor-spark-diagnostics` is committed and the builder loads it after a failed headless run. It provides a
read-only evidence ladder from retained `failureReason` through Spark Advisor, bounded driver stderr, stages,
executors, resource usage, and the Notebook Snapshot fallback. Automatic stderr retrieval was deliberately
not added: Advisor or the retained failure can already identify the cause, and unconditional logs increase
context.

- [ ] **Live-test `nor-spark-diagnostics` on one deliberately failed headless run.** Verify job-to-Livy/app ID
  resolution, Advisor, driver-log metadata and bounded partial stderr while monitoring data is retained, plus
  the Snapshot fallback after expiry. Only automate a proven stable subset afterward.
- [ ] Add source-independent failure categories (infrastructure, runtime, data contract) to the diagnostic
  report after the live test establishes which evidence is reliably available.

## Run evidence — minimal lifecycle manifest implemented 2026-09-17

Livy and headless job drivers now append their existing lifecycle facts to
`.scratch/<ws_name>/operational_manifest.jsonl`. Keep it minimal. Add notebook-produced batch IDs, row counts,
or payload sizes only when a concrete consumer needs them; do not parse notebook output or duplicate toolbelt
lineage merely to enrich the manifest.

## Candidates noted, not evaluated in depth

- [ ] `fab-workspace-organize` skill (fab-cli-skills) — same-workspace folder reorganization; possible source
  for a future workspace-tidy skill.
- [ ] `fab-conventions` skill (fab-cli-skills) — table/view/measure/column naming governance; relevant once
  Foundational/Business modeling exists.
- [ ] `Implementation-Patterns/*-Basic-Full-Load.md` (DEG guild, Azure + Fabric versions) — detail for the
  snapshot-fallback pattern our architecture doc currently only stubs.
- [ ] `Governance-Model/Operating-Model.md` + `Operating-Parties.md` (wiki, 103+110 lines, unread beyond title) —
  likely substantiates the IT-vs-business ownership split already written into `data-product-architecture.md`.
