# Developing lakehouse-toolbelt

This page covers everything needed to work on the library itself: dev container setup, building, versioning, and the repository folder map.

---

## Prerequisites

| Requirement | Why |
| --- | --- |
| Docker | The dev container runs in a Docker container |
| VS Code with the Dev Containers extension | Opens the repository inside the container with all tooling pre-configured |

No other local installation is needed. Python, Hatch, and VS Code extensions are provided by the dev container.

### Install Docker

Install Docker Desktop or Docker Engine before opening the dev container.

- Windows and macOS: use Docker Desktop
- Linux: use Docker Engine and Docker Compose plugin

Official install guides:

- Docker Desktop: https://docs.docker.com/desktop/
- Docker Engine: https://docs.docker.com/engine/install/

After installation, verify Docker is available:

```bash
docker --version
```

## Dev Container

The dev container is defined in `.devcontainer/devcontainer.json`:

| Setting | Value |
| --- | --- |
| Base image | `mcr.microsoft.com/devcontainers/base:noble` (Ubuntu) |
| Python | 3.11, installed via the `python` dev container feature |
| Java | 17, installed via the `java` dev container feature for local Spark |
| Hatch | Installed via the `hatch` dev container feature |
| VS Code extensions | GitHub Copilot, Copilot Chat, Pylance, Python, debugpy |

The container also sets `SPARK_LOCAL_IP=127.0.0.1` and installs the editable test stack with `python -m pip install -e .[test]` during `postCreateCommand`.

### Opening The Dev Container

1. Clone the repository.
2. Open the folder in VS Code.
3. When prompted, click **Reopen in Container** (or run the command **Dev Containers: Reopen in Container** from the command palette).
4. VS Code builds and starts the container. Once ready, a terminal inside the container is available.

## Running Tests

For fast local development, dataframe tests should run in a plain local Spark session inside the dev container rather than through notebook-style `unittest` files.

Recommended approach:

- `pytest` for discovery and fast iteration
- `pyspark.testing.assertDataFrameEqual` for dataframe diffs
- `pyspark.testing.assertSchemaEqual` for schema-only assertions
- a shared session-scoped Spark fixture in `tests/conftest.py`

### Spark Session Convention

Library modules must obtain Spark through `get_spark()` in `_spark_handler.py`; they must not create their own `SparkSession`. Spark reuses one underlying context, so a later session cannot add startup configuration such as the Delta extensions and JAR packages configured by the local test fixture. In Fabric and Databricks, `get_spark()` reuses the notebook's configured session.

Run all tests with:

```bash
pytest
```

Run a single test file with:

```bash
pytest tests/test_dpmeta_payload_hash.py
```

Notes:
- If you prefer more verbose output, add -v or -vv argument for pytest
- `pyproject.toml` limits pytest discovery to the `tests/` folder so the legacy notebook-style files under `src/` are not collected.
- The old `*_test.py` files remain as historical Databricks tests, but the preferred local workflow is now `pytest` plus native Spark asserts.

---

## Building

The project uses [Hatch](https://hatch.pypa.io/) as the build tool. The build configuration is in `pyproject.toml`.

### Build Artifacts

| Command | Artifacts | Output folder |
| --- | --- | --- |
| `hatch build` | `.whl` + `.tar.gz` | `dist/` |
| `hatch build -t wheel` | `.whl` only | `dist/` |

### Download The Wheel

After building, the wheel file is at:

```
dist/lakehouse_toolbelt-<version>-py3-none-any.whl
```

Download or copy this file to install the library in a Fabric or Databricks environment:

```bash
# Install in notebook
%pip install /path/to/lakehouse_toolbelt-<version>-py3-none-any.whl
```

### Versioning

The current version is defined in `src/lakehouse_toolbelt/__about__.py`.

| Command | Effect | Example |
| --- | --- | --- |
| `hatch version micro` | Patch bump | `1.0.5` → `1.0.6` |
| `hatch version minor` | Minor bump | `1.0.5` → `1.1.0` |
| `hatch version major,rc` | Major bump with release candidate | `1.0.5` → `2.0.0rc0` |
| `hatch version release` | Promote release candidate | `2.0.0rc0` → `2.0.0` |

Run the version command **before** `hatch build` or `hatch build -t wheel` to update the version in the next build artifact.

### Typical Build Workflows

Build both artifact types:

```bash
# 1. Bump the version
hatch version micro

# 2. Build both artifacts
hatch build

# 3. The new .whl and .tar.gz are in dist/
ls dist/
```

Build only the wheel:

```bash
# 1. Bump the version
hatch version micro

# 2. Build only the wheel
hatch build -t wheel

# 3. The new .whl is in dist/
ls dist/
```

---

## Repository Folder Map

```
lakehouse_toolbelt/
├── .devcontainer/
│   └── devcontainer.json          # Dev container definition (Docker image, Python, Hatch, extensions)
├── dist/                          # Build output (wheels and sdists produced by hatch build)
├── docs/                          # Documentation (Markdown pages)
│   ├── environment-prerequisites-and-conventions.md
│   ├── quickstart-cdc-upsert.md
│   ├── configuration-reference.md
│   ├── function-reference.md      # API Reference
│   ├── schema-compatibility.md
│   └── developing.md              # This page
├── examples/                      # Example data product config and notebook
│   ├── mdm_extract_dat1.json
│   └── nb_mdm_extract_cdc_dat1.ipynb
├── src/
│   └── lakehouse_toolbelt/        # Package source
│       ├── __about__.py           # Version string
│       ├── __init__.py            # Public API exports
│       ├── _data_product_class.py # DataProduct class
│       ├── _dataset_class.py      # DataSet class
│       ├── _dpmeta_functions.py   # Metadata column functions (add_dpmeta_*)
│       ├── _env_helper.py         # Fabric / Databricks runtime detection
│       ├── _publish_configuration_class.py
│       ├── _schema_compatibility.py  # Schema alignment before upsert
│       ├── _source_configuration_class.py
│       ├── _spark_handler.py      # Spark session acquisition
│       ├── _upsert_delta_change_history.py  # Change-history merge logic
│       └── _upsert_delta_change_history_test.py
├── tests/                         # Local pytest suite for devcontainer-based development
│   ├── conftest.py                # Shared local Spark fixture
│   ├── test_convert_timestamps.py
│   ├── test_dpmeta_columns.py
│   └── test_dpmeta_payload_hash.py
├── pyproject.toml                 # Build config, dependencies, Hatch settings
├── lakehouse_toolbelt.code-workspace  # VS Code workspace file
├── README.md                      # Project entry point
├── build_and_upload_wheel_for_databricks.yml  # CI pipeline (Databricks)
└── build_and_upload_wheel_for_fabric.yml      # CI pipeline (Fabric)
```

### Key Conventions

- All package source lives under `src/lakehouse_toolbelt/`.
- Files prefixed with `_` are internal modules. The public API is re-exported through `__init__.py`.
- The supported local test suite lives under `tests/` and runs with `pytest` inside the devcontainer.
- The remaining `*_test.py` file under `src/` is a legacy Databricks notebook-style test and is not part of local pytest discovery.
- Build artifacts go to `dist/` and are `.gitignore`-managed.
