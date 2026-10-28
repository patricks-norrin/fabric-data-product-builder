# Coexisting with Microsoft Fabric skills

Microsoft's `skills-for-fabric` is useful as a source of Fabric technical references, but it is not a drop-in
extension to the Norrin builder. Its agents and skills may encode different architecture choices, execution
surfaces, and notebook workflows. When both toolsets are present in one session, make the overlap explicit
and keep Norrin's `nor-*` skills authoritative for Norrin work.

## Where guidance can conflict

| Concern | Norrin owner | Potential overlap |
|---|---|---|
| Product architecture and layering | `nor-data-product-architecture` | Microsoft medallion guidance may introduce Bronze/Silver/Gold concepts that do not match Norrin product boundaries |
| Build orchestration | `nor-data-product-builder` | Microsoft Fabric agents may route the same request through different workflows |
| Notebook authoring and publication | `nor-notebook-author`, `nor-notebook-publish-and-run` | `spark-cli` authoring may use different notebook formats or API paths |
| Livy development | `nor-livy-session` | `spark-cli` consumption may not include Norrin's authentication and toolbelt setup |
| Spark diagnostics | `nor-spark-diagnostics` | Microsoft operations material can be useful as technical reference, but Norrin's read-only evidence order governs this workflow |
| Fabric mutations | Norrin skill scripts and `fab` | Microsoft examples may use `az rest`, MCP, or another execution surface |

The overlap warning and routing rule are also in the
[builder agent](../agents/nor-data-product-builder.agent.md), where they apply during execution.

## Safe use

- Do not load or invoke a competing Microsoft orchestrator for a Norrin product request.
- Do not let overlapping Microsoft skills author, publish, or mutate Norrin items or replace the Norrin
  architecture, notebook, or Livy procedures.
- If the user explicitly asks for a Microsoft technical reference, treat it as reference material only;
  reconcile it with the current Norrin skills and vendored `lakehouse_toolbelt` documentation before acting.
- Keep non-overlapping material as an optional reference, not a runtime dependency. The packaged toolpack must
  remain usable without Microsoft's skills installed.

Recheck this guidance when either toolset changes substantially. Do not maintain a full inventory or version-
specific compatibility matrix here; use the skills themselves as the source of truth for current behavior.
