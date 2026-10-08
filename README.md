# norrin-fabric-data-product-toolpack

Harness-neutral tooling, instructions and templates that let a coding agent build a
**source-aligned data product** in Microsoft Fabric end to end and apply a shared modelling standard to
Foundational and Business data products. Source-aligned products follow the `lakehouse_toolbelt` contract;
consumer-aligned modelling guidance covers notebook structure, business rules, output contracts, monetary
types, Delta descriptions, and cross-product relationships.

The toolpack can be installed once and used from GitHub Copilot CLI, GitHub Copilot in VS Code, Claude Code,
or Cursor sessions opened in any consuming project. Scripts resolve that project's Git root (or cwd outside
Git); generated files and temporary state never belong to the installed toolpack.

## Install with GitHub Copilot CLI

Register the Azure DevOps repository as a plugin marketplace, then install the toolpack from that marketplace:

```bash
copilot plugin marketplace add https://naksfi@dev.azure.com/naksfi/Fabric/_git/nor-data-product-builder
copilot plugin install norrin-fabric-data-product-toolpack@norrin-fabric-plugins
```

The first command requires Git credentials that can access the Azure DevOps repository.

Single execution surface: the Microsoft Fabric CLI (`fab`). One login per customer tenant.

- `agents/nor-data-product-builder.agent.md` — canonical orchestrating agent
- `skills/nor-*` — canonical procedures and standards (source-aligned operations plus Foundational/Business modelling)
- `.claude-plugin/`, `.cursor-plugin/` — host registration metadata only
- `reference/architecture/` — the Norrin data product architecture (single source of truth)
- `reference/lakehouse_toolbelt/` — vendored toolbelt docs and examples (runtime contract)
- `templates/project/` — generic files a consuming project can copy and customize
- `scripts/` — harness-neutral project/target resolution and Fabric helpers
- `tests/` — fixture-based tests that prove outputs stay outside the installed toolpack
- `docs/` — how this repo is structured, why each piece exists, conventions and decisions made building it
- `CHANGELOG.md` — release history reconstructed from manifest versions and Git history

This repository contains no generated notebooks or deployable workspace package. Those belong in a separate
consuming project, for example:

```text
project/
├── configuration/
│   ├── fabric_targets.json
│   └── data_product/
├── ws_extract/
├── ws_procurement/
└── .scratch/
```

The workspace names are examples, not reserved names. Each `ws_<name>` package can be deployed to the mapped
dev, test, prod, or feature workspace through Fabric Git integration or `fabric-cicd`.

Start: `fab auth login --tenant <tenant-id>`, configure `configuration/fabric_targets.json`, then ask the agent:

- Source-aligned: "Build the source-aligned data product for <source system>."
- Consumer-aligned: "Model the Foundational data product <business concept>."

The builder classifies requests before acting. It runs the end-to-end extract and CDC procedure only for
source-aligned products and routes Foundational or Business modelling to `nor-data-product-modelling`.
