# Toolpack architecture and scope

The toolpack packages the `nor-data-product-builder` agent, its `nor-*` skills, and the scripts and templates
those skills use. It supports:

- End-to-end source-aligned data products for REST APIs: configuration, raw landing, and `lakehouse_toolbelt`
  change history.
- Foundational and Business product modelling as an authoring and review standard, not an automated build
  workflow.
- Supporting workflows for environment checks, Livy notebook development, publication, execution, and Spark
  diagnostics.

The consuming Fabric solution owns its configuration, deployable workspace packages, and temporary run state.
The installed toolpack provides reusable instructions and implementation resources; it does not own generated
customer projects.

## Request routing

`nor-data-product-builder` classifies the requested product role before acting:

| Request | Route |
|---|---|
| Faithfully introduce one external source | Source-aligned build via architecture, environment, config, extraction, notebook, Livy, and publish/run skills |
| Model a reusable business concept or combine concepts for a business need | `nor-data-product-modelling` |
| Create a specialized Analytical representation | Report that implementation is not supported |
| Unclear ownership or transformation intent | Ask the user to clarify |

`nor-spark-diagnostics` supports evidence-led investigation after or during Spark runs. It is read-only and
does not replace the publish/run or Livy workflows.

## Component map

| Component | Role |
|---|---|
| `agents/nor-data-product-builder.agent.md` | Classifies requests, routes to skills, applies safety and evidence rules |
| `skills/*/SKILL.md` | Canonical procedures and standards; see the [skills index](skills-reference.md) |
| Skill-local `scripts/`, templates, schemas, and preamble | Executable support for the procedures that own them |
| `reference/architecture/` | Norrin product, workspace, naming, and notebook conventions |
| `reference/lakehouse_toolbelt/` | Vendored toolbelt documentation and examples used as the CDC implementation contract |
| `templates/project/` | Generic project configuration templates |
| `tests/` | Structural and behavior checks for scripts, templates, skills, and plugin metadata |
| `.claude-plugin/`, `.cursor-plugin/` | Host plugin and marketplace metadata |

The toolpack contains nine skills. The skills and their resources are the implementation source of truth;
this overview and the skills index summarize and link to them rather than restating their detailed procedures.

## Boundaries

- REST is the currently supported source-extraction type. Do not imply JDBC or file extraction workflows exist
  until they are implemented and proven.
- Foundational and Business modelling guidance does not generate, publish, execute, or test notebooks as an
  orchestrated workflow.
- Analytical implementation and pipeline generation are not supported workflows.
- Generated project configuration and notebook items belong in the consuming solution, not in the installed
  toolpack.

For the user-facing capabilities and installation entry point, see the [README](../README.md). For exact
procedures, follow the owning skill rather than copying implementation details into this overview.
