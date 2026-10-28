# Plugin packaging and local development

The plugin manifests in `.claude-plugin/` and `.cursor-plugin/` register this toolpack with their respective
hosts. The package keeps agent and skill source in the shared top-level `agents/` and `skills/` directories.
The host manifests and marketplace entries are hand-maintained; the version synchronization test checks that
their versions agree.

## Copilot CLI

For installation and authentication prerequisites, use the commands in the root [README](../README.md).

For local development, point Copilot CLI at the working tree:

```bash
copilot --plugin-dir /path/to/norrin-fabric-data-product-toolpack
```

`--plugin-dir` precedes the subcommand because it is a global CLI option. This loads the local plugin without
installing it.

## Release checks

Before publication, follow the version-bump and validation steps in [AGENTS.md](../AGENTS.md), then run the
test suite. The plugin version test verifies that both manifests and marketplace entries stay synchronized.
