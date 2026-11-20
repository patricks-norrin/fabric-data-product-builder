# Norrin Data Product Builder

Build source-aligned data products, model consumer-aligned products, and develop and troubleshoot Spark
notebooks in **Microsoft Fabric** with the `nor-data-product-builder` agent.

Use it from GitHub Copilot or Claude Code, in VS Code or the CLI, on Linux, WSL, or Windows, in your own project.

## What You Can Do

The two main use cases are **sourcing data** and **modelling products on top of that data**.

### Source-Aligned Products: Sourcing and Technical Implementation

Introduce data from one external source system without adding business meaning. Source entities are datasets
inside that product, with unchanged raw landing and source-faithful change history.

The agent builds, extends, or repairs the technical implementation: product configuration, a schema-enabled
lakehouse, separate extract and CDC notebooks, and `lakehouse_toolbelt` change-history tables. It runs the
workflow and verifies raw batches, table schemas, and row counts.

**Currently supported source type: REST APIs.** The agent reads API documentation, identifies datasets and
keys, implements authentication and pagination, and uses incremental extraction where the source supports
it. REST extraction is part of the source-aligned workflow, not a separate product use case.

Example: `frankfurter_api` is the source-aligned product; `exchange_rates` is a dataset inside it.

### Consumer-Aligned Products: Modelling and Business Meaning

Build modelled products on top of source-aligned data. The agent helps design, edit, or review modelling
notebooks: grain, identifiers, joins, business rules, output contracts, monetary types, Delta descriptions,
and relationships between products.

| Product role | Purpose | Example |
|---|---|---|
| **Foundational** | Model one reusable business concept with agreed attributes, identifiers, and business rules. | `purchase_invoice`, `supplier`, or `exchange_rate`. |
| **Business** | Combine Foundational products to answer a business need. | Spend analysis built from invoices, suppliers, and exchange rates. |

The agent chooses the workflow from the requested outcome. Modelling a business concept does not trigger
source extraction or CDC. Consumer-aligned modelling currently provides authoring and review standards,
not automated notebook scaffolding or generated tests. Specialized
**Analytical** products, such as graphs or application-serving indexes, do not yet have an implementation workflow.

### Utilities: Develop, Diagnose, and Execute

Use these supporting workflows during product development or on an existing notebook:

| Utility | How the agent helps |
|---|---|
| **Notebook development with Livy** | Run PySpark or SQL cell by cell in a Fabric Spark session, inspect outputs and tracebacks, and fix and rerun the failing cell without rerunning the whole notebook. |
| **Spark troubleshooting** | Investigate failed, slow, or stuck notebook and Livy runs using failure reasons, Spark Advisor, bounded logs, stages, and executors. |
| **Publish and run** | Publish notebook definitions to the selected Fabric workspace, execute them headlessly, and report run status and failure evidence. |

## Try These Requests

Select `nor-data-product-builder` in your coding assistant and describe the outcome you need:

### Source-Aligned Products

- "Build a source-aligned product for this REST API. Use its documentation to identify datasets, keys, and incremental extraction options: <documentation URL>."

### Consumer-Aligned Products

- **Foundational modelling:** "Model the purchase_invoice Foundational product from our source-aligned invoice data. Make the grain, business rules, and output contract explicit."
- **Business modelling:** "Model a spend analysis Business product using our purchase_invoice, supplier, and exchange_rate products."
- **Modelling review:** "Review this modelling notebook against the Norrin standard. Report the findings before making changes."

### Utilities

- **Livy development:** "Run this notebook cell by cell through Livy, inspect the outputs, and help fix the failing cell."
- **Troubleshooting:** "Investigate this failed Fabric notebook run: <job instance ID>. Report the evidence before changing or rerunning it."
- **Publish and run:** "Publish this notebook to the selected Fabric workspace, run it headlessly, and report the result."

## Get Started

Open the project where your data products belong. Generated configuration and notebooks stay in that
project, not in the installed plugin.

Local notebook editing and reviews need no Fabric connection. For live builds, execution, or diagnostics,
you need access to a Fabric workspace, the Microsoft Fabric CLI (`fab` 1.9.0 or later), Azure CLI (`az`), and
Python 3.10+ (already present with `fab`). The same commands work on Linux, WSL, and native Windows; on Windows,
install and sign in to `fab` and `az` on the side (Windows or WSL) where your assistant runs. Sign in to the
customer tenant:

```bash
fab auth login --tenant <tenant-id>
az login --tenant <tenant-id> --allow-no-subscriptions --use-device-code
```

The agent checks the environment before connecting to Fabric. It uses your project's
`configuration/fabric_targets.json` to select the workspace and target; when the file is missing, it helps
you select a workspace and create the mapping. Livy uses Azure CLI sign-in for delegated OneLake access.

### Install with GitHub Copilot CLI

Already installed in VS Code? Start with a request above. For a new CLI installation, register the marketplace
and install the plugin:

```bash
copilot plugin marketplace add https://github.com/patricks-norrin/fabric-data-product-builder.git
copilot plugin install norrin-fabric-data-product-toolpack@norrin-fabric-plugins
```

### Install with Claude Code

In Claude Code (CLI or VS Code extension), register the marketplace and install the plugin:

```text
/plugin marketplace add https://github.com/patricks-norrin/fabric-data-product-builder.git
/plugin install norrin-fabric-data-product-toolpack@norrin-fabric-plugins
```

The marketplace is public; no Azure DevOps repository access is required.

### Follow a Running Build

The agent posts a status line at each phase and polls headless notebook jobs with a heartbeat, so a long
Fabric run never looks silent. When the agent runs as a background subagent, ask it for a status, or run the
job table directly from the project:

```bash
python3 <installed toolpack>/skills/nor-notebook-publish-and-run/scripts/run_notebook_job.py status
```

It reads the current state of the latest job of each notebook from Fabric and prints its status, start/end
times, job id, and failure reason.

## Further Reading

- [Skills reference](docs/skills-reference.md): index of the packaged agent and skills.
- [Project layout](docs/project-layout.md): where configuration, notebooks, and temporary state belong.
- [Architecture and dependencies](docs/conventions-and-dependencies.md): conventions and runtime requirements.
- [Maintainer documentation](docs/README.md): current repository and plugin maintenance references.
- [Changelog](CHANGELOG.md): release history.
