# Agent and skills reference

This is an index, not a second copy of the skill procedures. The linked `SKILL.md` files are canonical.

## Agent

- [`nor-data-product-builder`](../agents/nor-data-product-builder.agent.md) — routes source-aligned builds,
  consumer-aligned modelling, and supporting Fabric workflows.

## Skills

| Skill | Responsibility |
|---|---|
| [`nor-data-product-architecture`](../skills/nor-data-product-architecture/SKILL.md) | Product boundaries, workspace and lakehouse roles, naming, and CDC decisions |
| [`nor-data-product-modelling`](../skills/nor-data-product-modelling/SKILL.md) | Foundational and Business modelling standards |
| [`nor-environment-check`](../skills/nor-environment-check/SKILL.md) | Fabric prerequisites and target checks |
| [`nor-data-product-config`](../skills/nor-data-product-config/SKILL.md) | Configuration authoring, validation, push, and product provisioning |
| [`nor-rest-extraction`](../skills/nor-rest-extraction/SKILL.md) | REST API discovery and source-specific extraction implementation |
| [`nor-notebook-author`](../skills/nor-notebook-author/SKILL.md) | Render extract and CDC notebooks from the packaged templates |
| [`nor-pipeline-author`](../skills/nor-pipeline-author/SKILL.md) | Render and check the `pl_<id>` orchestration pipeline with portable item references |
| [`nor-livy-session`](../skills/nor-livy-session/SKILL.md) | Cell-by-cell notebook development through Livy |
| [`nor-lakehouse-query`](../skills/nor-lakehouse-query/SKILL.md) | Read-only T-SQL over lakehouse Delta tables through the Fabric SQL endpoint MCP server |
| [`nor-notebook-publish-and-run`](../skills/nor-notebook-publish-and-run/SKILL.md) | Publish notebook and pipeline definitions and run them headlessly |
| [`nor-spark-diagnostics`](../skills/nor-spark-diagnostics/SKILL.md) | Read-only evidence collection for failed, slow, or stuck Spark runs |
