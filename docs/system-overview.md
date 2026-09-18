# System overview

## What this repo is

A self-contained, harness-neutral kit that lets a coding agent build a **Norrin source-aligned data product**
in Microsoft Fabric: one source system landed as
raw files plus SCD2 change-history tables, using `lakehouse_toolbelt` as the processing contract and `fab`
(Microsoft Fabric CLI) as the only execution surface.

It is an installable, harness-neutral toolpack. A consuming solution repository owns configuration, deployable
Fabric workspace packages, and transient state; the installed toolpack owns only reusable agent instructions,
skills, scripts, templates, schemas, and reference material.

## Directory tree and what each part is for

```
norrin-fabric-data-product-toolpack/
├── README.md                      # Human-facing intro and quick start
├── .devcontainer/devcontainer.json# Harness-neutral Python 3.12 + fab + Azure CLI development environment
├── agents/
│   └── nor-data-product-builder.agent.md   # Canonical orchestrator
├── skills/                            # Canonical, harness-neutral skills
│   ├── nor-data-product-architecture/
│   ├── nor-environment-check/
│   ├── nor-data-product-config/
│   ├── nor-rest-extraction/
│   ├── nor-notebook-author/
│   ├── nor-livy-session/
│   └── nor-notebook-publish-and-run/
├── .claude-plugin/                 # Claude registration metadata
├── .cursor-plugin/                 # Cursor registration metadata
├── reference/
│   ├── architecture/              # The WHY, distilled from existing Norrin sources (see decision-log)
│   │   ├── data-product-architecture.md
│   │   ├── workspace-and-lakehouse-responsibilities.md
│   │   ├── naming-and-folder-conventions.md
│   │   ├── conventions.json               # machine-readable twin of the naming table
│   │   └── notebook-conventions-source.md # raw import, not yet curated
│   └── lakehouse_toolbelt/        # Vendored copy of the toolbelt's docs/ and examples/ (runtime contract)
├── templates/project/
│   └── configuration/
│       ├── fabric_targets.json    # Generic multi-environment target template
│       └── fabric_targets.schema.json
├── scripts/
│   ├── fab_common.sh              # Shared bash helpers
│   └── norrin_context.py          # Project/workspace/target resolver
└── tests/                          # Temporary consuming-project fixtures; no checked-in generated items
```

Active `configuration/`, `ws_<name>/`, generated notebooks, and `.scratch/` belong only to a separate consuming
Fabric solution repository.

## Relationships: who calls whom

```
User
 └─> agent: nor-data-product-builder          (loaded by the active plugin manifest; orchestrates and does
     │                                         not itself touch Fabric except via the skills below)
      │
      ├─ 1. skill: nor-data-product-architecture   (read-only reasoning; no scripts — answers "what/why")
      │
      ├─ 2. skill: nor-environment-check
      │      └─ scripts/check_environment.sh  ──sources──> scripts/fab_common.sh ──calls──> fab, az
      │
      ├─ 3. skill: nor-data-product-config
      │      ├─ scripts/validate_data_product_config.py   (stdlib only, reads toolpack conventions and the
      │      │                                              consuming project's data-product configuration)
      │      └─ scripts/push_data_product_config.sh  ──sources──> fab_common.sh ──calls──> fab
      │
      ├─ 4. skill: nor-notebook-author
      │      └─ scripts/render_notebook.py  (reads project config + target matrix, resolves ids via `fab`,
      │                                       fills templates/*, writes ws_<name>/<id>/...)
      ├─ source-specific skill: nor-rest-extraction
      │      └─ REST documentation + direct `requests` extraction cell + native Spark JSON reader choice
      │
      ├─ 5. skill: nor-livy-session
      │      ├─ scripts/livy_session.sh  ──sources──> fab_common.sh (ids only) ──calls──> az (token) + curl (Livy REST)
      │      ├─ scripts/notebook_cells.py    (parses a notebook-content.py into cells)
      │      ├─ scripts/format_statement_output.py
      │      └─ preamble/livy_preamble.py    (injected as statement 0 of every session — see conventions doc)
      │
      └─ 6. skill: nor-notebook-publish-and-run
             └─ scripts/run_notebook_job.sh  ──sources──> fab_common.sh ──calls──> fab (import/job run/export)

reference/lakehouse_toolbelt/   <-- read by: nor-data-product-architecture, nor-data-product-config,
                                              nor-notebook-author (never executed; it's documentation)
```

`scripts/norrin_context.py` resolves the consuming project independently of the installed toolpack, then selects
the logical workspace and physical target from `configuration/fabric_targets.json`. `scripts/fab_common.sh`
exposes that context to shell skills and resolves `$WORKSPACE_ID`/`$ENVIRONMENT_ID` via `fab`,
`item_id`, `onelake_mkdir_p`, `fab_api`/`fab_api_q` (CRLF-stripped, JMESPath-scoped to `text.`), and the
`pass/warn/fail/die` logging convention used by every script's output.

## Responsibilities at a glance

| Component | Responsibility | Why it's separate |
|---|---|---|
| `nor-data-product-builder` | Canonical non-negotiable rules and orchestration | Loaded identically by each plugin harness |
| `nor-data-product-architecture` | Decision rules (boundaries, keys, CDC-vs-exception) | Pure reasoning, no side effects, reused by every other skill's judgment calls |
| `nor-environment-check` | Prerequisite verification and shared-resource bootstrap | Must run before anything else; isolates "is the platform ready" from "build the thing" |
| `nor-data-product-config` | Author/validate/push config, provision folder + lakehouse | The only place that touches the shared-resources lakehouse and creates the product's Fabric container |
| `nor-rest-extraction` | REST-specific request and raw-format decisions | Keeps HTTP authentication, pagination, and JSON choices out of shared notebook/config contracts |
| `nor-notebook-author` | Turn config + API knowledge into the two notebooks | Templating is mechanical and reusable across data products; only the source-specific cells differ |
| `nor-livy-session` | Cell-by-cell dev loop with real output | The only way to see what a cell produces without VS Code; isolates the auth complexity (az vs fab tokens) |
| `nor-notebook-publish-and-run` | Ship the proven notebook and prove it runs unattended | Separates "I saw it work interactively" from "it works headless, which is how it will actually run" |
| `nor-data-product-builder` (agent) | Sequence the above, enforce retry/safety rules, report with evidence | Only the agent needs judgment (when to stop, when to ask); everything else is a deterministic procedure |

## What's deliberately absent (iteration-1 scope)

- **`nor-data-product-validation`** — no skill exists yet. Validation (UID uniqueness, duplicate detection,
  schema checks against the source) was explicitly deferred until extract + CDC are proven reliable.
- **Pipeline items** (`pl_<id>`) — folder convention reserves the name; nothing renders or publishes one yet.
- **A separate standards repo** — `reference/architecture/` lives inside this toolpack for iteration 1; splitting
  it out is deferred until a second consumer needs the same architecture docs.
- **Fabric MCP server** — deliberately not used for agent operations (see conventions doc); optional for humans only.
