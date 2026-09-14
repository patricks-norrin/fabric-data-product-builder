# System overview

## Repository location

```
/home/jpps/code/playground/norrin-fabric-data-product-toolpack/    (git, local only, 7 commits)
```

Not yet moved to `/home/jpps/projects/data_product_agent` (created but empty as of 2026-09-14) — pending
user decision on whether the toolpack relocates there.

## What this repo is

A self-contained kit that lets a coding agent (Claude Code today; GitHub Copilot CLI / Codex compatible by
convention) build a **Norrin source-aligned data product** in Microsoft Fabric: one source system landed as
raw files plus SCD2 change-history tables, using `lakehouse_toolbelt` as the processing contract and `fab`
(Microsoft Fabric CLI) as the only execution surface.

It is a **template repo**, not a service: it gets cloned per customer engagement, `fab auth login`'d once, and
pointed at a target workspace via one config file. Everything an agent needs — rules, architecture reasoning,
procedures, scripts, templates — travels inside it so it is reviewable and versioned like code.

## Directory tree and what each part is for

```
norrin-fabric-data-product-toolpack/
├── CLAUDE.md                      # Always-loaded rules: non-negotiables, tools, safety, workflow, fab gotchas
├── AGENTS.md -> CLAUDE.md         # Symlink: same rules for Copilot CLI / Codex-style tools
├── README.md                      # Human-facing intro and quick start
├── .mcp.json                      # Registers the microsoft-learn remote MCP server (no auth) as project-scoped
├── .devcontainer/devcontainer.json# Python 3.12 + ms-fabric-cli + node/Claude Code — distribution unit
├── .claude/
│   ├── settings.json              # Permission allowlist (fab, skill scripts, read-only git) — fewer prompts
│   ├── agents/
│   │   └── nor-data-product-builder.md   # The orchestrator (see below)
│   └── skills/                    # One folder per skill; see skills-reference.md
│       ├── nor-data-product-architecture/
│       ├── nor-environment-check/
│       ├── nor-data-product-config/
│       ├── nor-notebook-author/
│       ├── nor-livy-session/
│       └── nor-notebook-publish-and-run/
├── reference/
│   ├── architecture/              # The WHY, distilled from existing Norrin sources (see decision-log)
│   │   ├── data-product-architecture.md
│   │   ├── workspace-and-lakehouse-responsibilities.md
│   │   ├── naming-and-folder-conventions.md
│   │   ├── conventions.json               # machine-readable twin of the naming table
│   │   └── notebook-conventions-source.md # raw import, not yet curated
│   └── lakehouse_toolbelt/        # Vendored copy of the toolbelt's docs/ and examples/ (runtime contract)
├── configuration/
│   ├── target_workspace.json      # THE pointer: which workspace + which Environment this repo currently targets
│   └── data_product/
│       ├── project_configuration/project_configuration.json   # allow-list of extra config attributes
│       └── frankfurter_api/frankfurter_api.json                # the one data product built so far
├── notebooks/frankfurter_api/
│   ├── nb_extract_frankfurter_api.Notebook/  {notebook-content.py, .platform}
│   └── nb_cdc_frankfurter_api.Notebook/      {notebook-content.py, .platform}
├── scripts/fab_common.sh          # Shared bash helpers every skill script sources
└── .scratch/                      # Gitignored working area: Livy session state, exports, diagnostics
```

## Relationships: who calls whom

```
User
 └─> agent: nor-data-product-builder          (reads CLAUDE.md automatically; orchestrates, does not itself
      │                                         touch Fabric except via the skills below)
      │
      ├─ 1. skill: nor-data-product-architecture   (read-only reasoning; no scripts — answers "what/why")
      │
      ├─ 2. skill: nor-environment-check
      │      └─ scripts/check_environment.sh  ──sources──> scripts/fab_common.sh ──calls──> fab, az
      │
      ├─ 3. skill: nor-data-product-config
      │      ├─ scripts/validate_data_product_config.py   (stdlib only, reads reference/architecture/conventions.json
      │      │                                              and configuration/data_product/project_configuration/*)
      │      └─ scripts/push_data_product_config.sh  ──sources──> fab_common.sh ──calls──> fab
      │
      ├─ 4. skill: nor-notebook-author
      │      └─ scripts/render_notebook.py  (reads configuration/data_product/<id>/<id>.json + target_workspace.json,
      │                                       resolves ids via `fab`, fills templates/*, writes notebooks/<id>/...)
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

`scripts/fab_common.sh` is the one piece of shared code: every skill script `source`s it for `need_target`
(reads `configuration/target_workspace.json`, resolves `$WORKSPACE_ID`/`$ENVIRONMENT_ID` via `fab`),
`item_id`, `onelake_mkdir_p`, `fab_api`/`fab_api_q` (CRLF-stripped, JMESPath-scoped to `text.`), and the
`pass/warn/fail/die` logging convention used by every script's output.

## Responsibilities at a glance

| Component | Responsibility | Why it's separate |
|---|---|---|
| `CLAUDE.md` | Non-negotiable rules always in context | Cheapest, always-on guardrail; everything else is loaded on demand |
| `nor-data-product-architecture` | Decision rules (boundaries, keys, CDC-vs-exception) | Pure reasoning, no side effects, reused by every other skill's judgment calls |
| `nor-environment-check` | Read-only prerequisite verification | Must run before anything else; isolates "is the platform ready" from "build the thing" |
| `nor-data-product-config` | Author/validate/push config, provision folder + lakehouse | The only place that touches the shared-resources lakehouse and creates the product's Fabric container |
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
