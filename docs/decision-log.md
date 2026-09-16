# Decision log

Chronological record of decisions made while scoping and building iteration 1, and why. Earlier entries are
the framing decisions that shaped everything after; later entries are what was learned by actually running it.
All dated entries are 2026-09-11 (commit timestamps) unless noted.

This is retained as development history because it records verified platform behavior and rejected design
alternatives. Customer-specific workspace, capacity, Environment, and repository names are intentionally
generalized.

## Framing (before any code was written)

1. **Scope of "source-aligned data product"** — config, lakehouse, both notebooks (extract + CDC), raw files,
   change-history tables, all inside one workspace folder. Decided explicitly to fix scope creep from an
   earlier, broader "build a full agentic Fabric platform" framing.
2. **Iteration 1 is self-contained** — architecture reference, skills, agent, templates all live inside one
   toolpack repo. A separate standards repo (so multiple toolpacks/consumers could share the architecture
   docs) and a validation skill were both proposed and explicitly deferred: *"we'll do the first iteration
   with everything under this agent. When the extract and source aligned data products work reliably, we'll
   think about next steps."*
3. **Optimize for few dependencies and one auth mechanism.** Explicit constraint: this is used across
   multiple customer engagements in consulting; every extra tool with its own auth flow is a support burden
   multiplied by tenant count. This directly killed two options that were otherwise technically fine:
   - The Fabric MCP server (Node dependency, `az login`-based auth, would have been a *third* login).
   - `notebookutils.fs.put()` / the Azure Storage SDK for config upload, once it was noticed `fab` already had
     an equivalent OneLake `cp` path (an MCP OneLake-upload tool was also considered and dropped for the same
     reason — `fab cp` already did it with the login already in place).
4. **Naming: no abbreviations, `nor-` prefix, kebab-case** — e.g. `nor-environment-check`, not `nor-env-check`.
   Explicit user correction after an earlier proposal shortened names.
5. **Devcontainer as distribution vehicle** — evaluated and kept: Docker is available, both `fabric-cli` and
   `lakehouse_toolbelt` already ship devcontainers to copy conventions from, and `fab`'s token cache is a fixed
   path (`~/.config/fab/`), so one container/volume per customer tenant gives clean credential isolation.
6. **Notebooks must be single-responsibility.** Explicit instruction: `nb_extract_<id>` and `nb_cdc_<id>` only
   import config, do the work, exit — no validation or exploration inside them, so they stay human-readable and
   independently rerunnable. Validation was designated to live "somewhere else" (the deferred
   `nor-data-product-validation` skill).
7. **Local git only** for this iteration — no remote configured.

## Design decisions made while building

8. **Config location is the shared-resources lakehouse, not the product lakehouse** — corrected after an
   initial draft assumed the config lived next to the data it describes. Verified against the actual
   `lakehouse_toolbelt` source (`_data_product_class._return_path_prefix`) and a real example notebook/config
   from an internal reference implementation before trusting the location.
9. **Raw vs. Tables split** — raw lands in `Files/`, change history is a Delta table under `Tables/` on a
   schema-enabled lakehouse (not `Files/.../change_history/`, which is only the fallback path for
   non-schema-enabled lakehouses). Also verified against toolbelt source and a real run's printed paths, not
   assumed from the docs alone.
10. **JSON, not YAML, for config** — explicit requirement: Azure Data Factory reads JSON natively but not YAML
    well, and ADF integration is a stated future consumer of these configs.
11. **Exit value rejected as the feedback channel** — tried (`notebookutils.notebook.exit(json...)` +
    `fab api .../jobs/instances/<id>?beta=true`); the field came back `null` in this tenant even with the beta
    flag confirmed sent (checked in `fab`'s own debug log). Persisting a report file to `Files/` was also
    proposed and explicitly rejected by the user in favor of getting real cell output — which led directly to
    building the Livy dev loop instead.
12. **Livy over VFS/VS Code for the dev loop** — VFS mode (the pre-existing `norrin_fabric_data_engineering`
    Copilot agent) cannot run a terminal or `fab`, and is VS Code-only. Livy sessions via REST give the same
    cell-by-cell feedback loop from any agent/terminal, which is the actual requirement (autonomous, VFS-mode
    independence).
13. **`fab`'s token cannot drive a Livy Spark session; `az`'s can** — discovered by direct experimentation
    (create identical sessions with each token, run the same diagnostic statement) after `fab job run` failed
    on an F2 capacity with a pool-size error that had nothing to do with auth, which prompted checking auth
    itself as a separate variable. Recorded as a fixed rule (`nor-livy-session`), not re-derived per session.
14. **Diagnostics must be assertion-style, never token-introspection-style** — a script that base64-decoded a
    JWT's `aud`/`scp`/`roles` to explain the difference between the two tokens triggered a model-safety
    classifier false positive (credential-extraction shape) that silently swapped the running model mid-turn.
    Rewritten to report pass/fail of an actual operation instead. See `conventions-and-dependencies.md`.
15. **Environment must live in the same workspace as the notebook/session** — discovered when attaching
    an Environment in a different workspace, sharing the same capacity, killed Spark session acquisition on
    *both* the Livy path and headless `fab job run`, on two different Spark runtime versions. Ruled out runtime
    mismatch as the cause before accepting workspace-locality as the actual constraint. Fixed by `fab cp`-ing
    the Environment into the target workspace and republishing.
16. **Toolbelt wheel version pinned to ≥ 1.0.7** — 1.0.6 (what the test Environment shipped) threw an `AttributeError`
    inside `SourceConfiguration.__init__` on any config that didn't set a now-deprecated key. Found by reading
    the actual traceback against the actual source across wheel versions, not by guessing at a version bump.
    `nor-environment-check` now asserts this as a FAIL condition.

## Explicit operational instructions given during the build

17. Standing scope limit: only the explicitly assigned isolated test workspace could be changed. Its shared
    capacity could be consumed but never started or stopped without an explicit instruction.
18. Capacity cleanup instructions were followed whenever a work session ended; no customer-specific capacity
    names are retained here.
19. Ultimate-goal framing for `nor-notebook-author`/the agent: given only a source's API documentation, the
    agent should be able to propose config + extract/CDC notebooks independently. An existing internal
    implementation may be used as a **sanity check and model**, but the toolpack's
    output must be able to reproduce an equivalent solution **without copying it** — this is why
    `render_notebook.py` generates from templates + live API sampling rather than adapting the lab-5 notebook.
20. If the Livy path does not "unfold" within reasonable effort, **note findings and abort — do not spend
    extended effort working around a possible platform limitation.** Explicitly framed as a real open
    question ("it's possible Fabric is just not mature enough for this workflow") rather than a problem to be
    solved at any cost. In the event, the path did unfold (see result below), so this instruction was not
    invoked, but it remains the standing rule for future platform obstacles.

## Result as of the last verified run (2026-09-11, evening)

The full extract → Livy dev loop → CDC → headless-run cycle was proven for a public exchange-rate API in an
isolated test workspace. Both notebooks ran clean cell-by-cell over Livy and completed through `fab job run`
after the Environment was copied into the target workspace and republished with toolbelt 1.0.7. The resulting
change-history tables had the expected row counts and complete `dpmeta_*` schema. The test capacity was paused
at the end of the session per instruction #18.

## Packaging and first publish (2026-09-16)

21. **Agent file renamed to `nor-data-product-builder.agent.md`.** GitHub's plugin documentation requires
    custom agents to match `agents/*.agent.md`; a plain `.md` is skipped. Nothing errors when it is skipped —
    the plugin installs and reports its skill count normally — so this would have been an invisible failure.
22. **Stayed on the legacy plugin format.** Agent Plugins 1.0 (opt-in via `$schema` in `plugin.json`) makes
    skills and MCP servers portable across clients but relocates agents, hooks and commands under
    `com.github.copilot/`, which Claude Code and Cursor ignore. Since the agent is the part carrying Norrin's
    conventions, hiding it in a Copilot-branded directory defeats the multi-harness goal.
23. **No `.github/plugin/marketplace.json`.** Assumed necessary because Microsoft's `skills-for-fabric` ships
    one; disproven by running `copilot plugin marketplace add` against the repo, which read the existing
    `.claude-plugin/marketplace.json`. One fewer duplicated manifest to maintain.
24. **Marketplace install, not direct URL install.** Both work against Azure DevOps, but direct installs from
    repos, URLs and local paths emit a deprecation warning stating that only `plugin@marketplace` will be
    supported in future. Engagement onboarding instructions must therefore use `marketplace add` + install.
    `copilot plugin install owner/repo` is GitHub-only and cannot reach Azure DevOps at all.
25. **Local branch renamed `master` → `main` before the first force push.** The remote's only branch was
    `main`. Pushing `master` as-is would have left two branches, and `git clone` on a fresh machine checks out
    the remote default — landing it on the pre-existing unrelated content instead of the toolpack.
26. **Published state is explicitly unproven.** The pack installs correctly, but agent invocation, the test
    suite, and the extract + CDC loop have all not been exercised since the restructure. Recorded here so the
    publish is not mistaken for a validation. See `packaging-and-distribution.md` § Not verified.
