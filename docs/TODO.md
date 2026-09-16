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

## Distribution / install — explicitly deferred to the "publish" phase

- [x] Make `.devcontainer/devcontainer.json` harness-neutral and include Azure CLI for `nor-livy-session`.
- [ ] No documented bare-metal prerequisite list (`fab`, `az`, `python3`, `git`) for engagements that won't use
  the devcontainer.
- [ ] `fab-bootstrap` skill (fab-cli-skills) has a working pattern for install + PATH + login on Windows/macOS —
  reference when writing the above.

## Candidates noted, not evaluated in depth

- [ ] `fab-workspace-organize` skill (fab-cli-skills) — same-workspace folder reorganization; possible source
  for a future workspace-tidy skill.
- [ ] `fab-conventions` skill (fab-cli-skills) — table/view/measure/column naming governance; relevant once
  Foundational/Business modeling exists.
- [ ] `Implementation-Patterns/*-Basic-Full-Load.md` (DEG guild, Azure + Fabric versions) — detail for the
  snapshot-fallback pattern our architecture doc currently only stubs.
- [ ] `Governance-Model/Operating-Model.md` + `Operating-Parties.md` (wiki, 103+110 lines, unread beyond title) —
  likely substantiates the IT-vs-business ownership split already written into `data-product-architecture.md`.
