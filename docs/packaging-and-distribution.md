# Packaging and distribution

How the toolpack is packaged as a host plugin, how it gets installed on a clean machine, and which of those
mechanics are **verified against a real CLI** versus taken from vendor documentation. Written 2026-09-16, when
the pack was first pushed to a remote and installed end to end.

Companion to [system-overview.md](system-overview.md) (what the pack contains) and
[ms-skills-fit-for-norrin.md](ms-skills-fit-for-norrin.md) (whether Microsoft's `skills-for-fabric` can sit
underneath the Norrin agent).

## Remote

`https://naksfi@dev.azure.com/naksfi/Fabric/_git/nor-data-product-builder`, default branch `main`.

The repo predates the toolpack and held unrelated content, so the first publish was a force push. The local
branch was `master` while the remote's only branch was `main`; local was renamed to `main` rather than pushing
a second branch, because a plain `git clone` checks out the remote default and would otherwise land a fresh
machine on the old content.

Note that the repository name (`nor-data-product-builder`) is the *agent* name, not the pack name
(`norrin-fabric-data-product-toolpack`). Harmless, but it means the clone directory and the installed plugin
name differ.

## Plugin layout

Component discovery is by convention, not by manifest declaration. Per GitHub's
[plugin documentation](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins),
a legacy-format plugin exposes:

| Component | Required location |
|---|---|
| Custom agents | `agents/*.agent.md` — **the `.agent.md` suffix is mandatory** |
| Skills | `skills/<name>/SKILL.md` |
| Hooks | `hooks.json` at plugin root, or `hooks/` |
| MCP servers | `.mcp.json`, `.github/mcp.json`, or the `mcpServers` manifest field |

The agent was `agents/nor-data-product-builder.md` until 2026-09-16 and would have been silently skipped — the
plugin still installs and reports its skills, so there is no error to notice. Renamed to
`nor-data-product-builder.agent.md`; the `name:` frontmatter field (`nor-data-product-builder`) is what the
user types to invoke it.

There is also an Agent Plugins 1.0 format, selected by setting `$schema` in `plugin.json`, which moves
Copilot-specific components under `com.github.copilot/` and fixes the component paths. This pack deliberately
stays on the legacy format: the 1.0 format's portability benefit only covers skills and MCP servers, and it
would put the agent in a Copilot-branded directory that Claude Code and Cursor ignore.

### Verified facts about manifest locations

Both established by running the CLI, not by reading docs:

- `.claude-plugin/plugin.json` is accepted as a legacy manifest location. No root `plugin.json` is needed.
- `copilot plugin marketplace add` reads `.claude-plugin/marketplace.json`. **No `.github/plugin/marketplace.json`
  is required**, even though Microsoft's `skills-for-fabric` maintains one. An earlier assumption that Copilot
  needed its own marketplace file was wrong.

The pack carries a near-duplicate `.cursor-plugin/` pair alongside `.claude-plugin/`. These are hand-maintained
and will drift.

## Installing

### On a clean machine (preferred)

```bash
copilot plugin marketplace add https://naksfi@dev.azure.com/naksfi/Fabric/_git/nor-data-product-builder
copilot plugin install norrin-fabric-data-product-toolpack@norrin-fabric-plugins
```

The marketplace name (`norrin-fabric-plugins`) comes from `marketplace.json`, not from the repo name. Verified
working against Azure DevOps over HTTPS; the plugin landed at
`~/.copilot/installed-plugins/norrin-fabric-plugins/norrin-fabric-data-product-toolpack/` with the agent file
present.

Install reports `Installed 6 skills` and says nothing about agents. The count excludes agents — absence of a
mention is not evidence the agent was skipped, so check the file on disk if in doubt.

### Local development loop

```bash
copilot --plugin-dir /path/to/norrin-fabric-data-product-toolpack
```

`--plugin-dir` is a global flag on `copilot`, not an option of the `plugin` subcommand, so it must precede the
subcommand. It loads the pack straight from a working tree with no install step and no write to
`~/.copilot/settings.json`, which makes it the right loop for editing skills. `copilot --plugin-dir <dir> plugin
list` shows it under an "External Plugins" heading.

### Deprecated

Direct installs from a repo, URL, or local path work today but emit:

> Direct plugin installs (repos, URLs, local paths) are deprecated. Only `plugin@marketplace` installs will be
> supported in a future release.

Do not build the engagement onboarding instructions around `copilot plugin install <url>`. Note that
`copilot plugin install owner/repo` is GitHub-only and cannot address Azure DevOps.

### Authentication caveat

The development machine resolves Azure DevOps credentials through
`/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe` — the Windows Git Credential Manager reached
over the WSL interop mount. A fresh WSL image has no such configuration, so both the clone and
`marketplace add` will fail to authenticate until either the interop helper is configured or a PAT is issued.
This is the most likely first failure on a new engagement machine.

## Ambient context collisions

Installing the pack does not give the Norrin agent exclusive control of a session. On the development machine,
three sources of Fabric guidance load simultaneously:

1. `fabric-skills@fabric-collection` — Microsoft's pack, enabled in `~/.copilot/settings.json`, bringing four
   agents (`FabricDataEngineer`, `FabricIQ`, `FabricAdmin`, `FabricAppDev`) and its own always-applied rules
   asserting `az rest` as the control plane and Bronze/Silver/Gold as the architecture.
2. `~/.copilot/agents/norrin_fabric_data_engineering.agent.md` — a stale user-level Norrin agent from
   2026-05-15, predating this toolpack, loaded in every session regardless of plugin state.
3. This pack's `nor-data-product-builder`.

The toolpack has no ambient rules of its own: the restructure deleted the root `AGENTS.md` and `CLAUDE.md`, so
Norrin's conventions are only in effect once its agent or skills are explicitly invoked, while Microsoft's are
in effect from the first token. That asymmetry is the practical form of the precedence problem described in
[ms-skills-fit-for-norrin.md](ms-skills-fit-for-norrin.md).

## Not verified

- **Agent invocation.** That `nor-data-product-builder` actually appears in `/agents` and can be selected has
  never been observed. There is no offline agent-listing command; it needs a live session, ideally on a clean
  machine where the stale user-level agent cannot mask the result.
- **Claude Code and Cursor.** Only Copilot CLI was exercised. The `.claude-plugin/` and `.cursor-plugin/`
  manifests are untested.
- **`tests/`.** `pytest` is not importable in the development environment, so `tests/test_project_context.py`
  and `tests/test_render_notebook.py` have never been run. The restructure that moved every path is exactly
  the change those tests exist to catch.
- **The restructured pack end to end.** The extract + CDC loop was last proven on 2026-09-11, before the
  worktree restructure and the multi-harness path abstraction.
