# Consuming project layout

The installed toolpack is read-only. A Fabric solution repository owns all configuration, deployable item
definitions, and temporary execution state.

```text
project/
├── configuration/
│   ├── fabric_targets.json
│   └── data_product/
│       ├── project_configuration/project_configuration.json
│       └── <data_product>/<data_product>.json
├── ws_<name>/
│   └── <data_product>/
│       ├── nb_extract_<data_product>.Notebook/
│       │   ├── .platform
│       │   └── notebook-content.py
│       └── nb_cdc_<data_product>.Notebook/
│           ├── .platform
│           └── notebook-content.py
└── .scratch/
    └── ws_<name>/
        ├── export/
        └── livy/
```

## Logical workspace packages

Every top-level `ws_<name>/` directory is an environment-neutral package for one Fabric workspace. The suffix
is user-defined; `ws_extract`, `ws_procurement`, and `ws_finance` are examples rather than reserved names. A
single repository can contain any number of these packages.

Connect Fabric Git integration to the selected `ws_<name>/` directory, not to the repository root. Fabric
retains ordinary Git subdirectories as workspace folders, so `<data_product>/` maps to the remote product
folder while `<item-name>.<ItemType>/` remains the Fabric item directory. The `.platform` file uses Fabric's
version 2 format and a stable logical ID.

For `fabric-cicd`, pass the same `ws_<name>/` directory as `repository_directory`. The package contains only
Fabric item definitions; project configuration and `.scratch` are intentionally outside it.

## Target matrix

`configuration/fabric_targets.json` separates environment-neutral source paths from physical Fabric
workspaces. Copy the generic template and schema from the installed toolpack's
`templates/project/configuration/` directory when initializing a consuming project.

- `active_target` selects a target profile such as `dev`, `test`, `prod`, or a feature deployment.
- `default_workspace` selects the logical package when a command has no override.
- `targets.<profile>.workspaces.<ws_name>` maps a logical package to a physical Fabric workspace and its
  Environment.
- `--workspace ws_<name>` overrides the logical package.
- `--target <profile>` overrides the target profile.
- Harness-neutral environment overrides `NORRIN_WORKSPACE` and `NORRIN_TARGET` are also supported.

## Root resolution

Scripts resolve the consuming project with `git rev-parse --show-toplevel`. Outside Git, the current directory
is the project root. Toolpack resources are resolved from each script's installed location. No host-specific
plugin-root variable is used, and no project output is written beneath the installed toolpack.
