# norrin-fabric-data-product-toolpack

Tooling, instructions and templates that let a coding agent (Claude Code, GitHub Copilot CLI) build a
**source-aligned data product** in Microsoft Fabric end to end: data product configuration, lakehouse,
extract and CDC notebooks, raw files and change-history tables — following the Norrin architecture and
the `lakehouse_toolbelt` contract.

Single execution surface: the Microsoft Fabric CLI (`fab`). One login per customer tenant.

- `CLAUDE.md` — non-negotiable rules the agent always sees (also `AGENTS.md`)
- `.claude/agents/nor-data-product-builder.md` — the orchestrating agent
- `.claude/skills/nor-*` — procedures with scripts (environment check, config, notebooks, Livy, publish/run)
- `reference/architecture/` — the Norrin data product architecture (single source of truth)
- `reference/lakehouse_toolbelt/` — vendored toolbelt docs and examples (runtime contract)
- `configuration/` — target workspace and data product configurations (JSON)
- `notebooks/<data_product_identifier>/` — notebook definitions in Fabric `.py` format
- `docs/` — how this repo is structured, why each piece exists, conventions and decisions made building it

Start: `fab auth login --tenant <tenant-id>`, edit `configuration/target_workspace.json`, then ask the agent:
"Build the source-aligned data product for <API>".
