---
name: nor-pipeline-author
description: Author the pl_<id> Fabric DataPipeline that orchestrates a data product's notebooks (source-aligned - nb_extract_<id> then nb_cdc_<id> on success). Renders native logical-ID references and publishes through fab deploy backed by fabric-cicd. Use whenever a product has more than one notebook or activity, or must be scheduled.
---

# nor-pipeline-author

Pipelines own orchestration and scheduling (`nor-data-product-architecture` §8). Run `scripts/` next to this file with `python3` (Linux/WSL) or `python` (Windows).

## Render
```bash
python3 "<directory of this SKILL.md>/scripts/pipeline_definition.py" render source sample_api --workspace ws_example --target dev
```
Writes `ws_<name>/<id>/pl_<id>.DataPipeline/{pipeline-content.json,.platform}`: two `TridentNotebook` activities,
`nb_extract_<id>` then `nb_cdc_<id>` with `dependencyConditions: ["Succeeded"]`. Every notebook activity defaults to:
- **Timeout 2 hours** (`0.02:00:00`). Raise it only for a measured run that needs longer (Fabric maximum 12 hours).
- **1 retry** after 30 s. Safe because extract writes a new raw batch per run and CDC upserts idempotently. A failed
  pipeline therefore means the activity failed twice; diagnose the latest attempt.
- **Session tag `pl_<id>`**, so the product's notebooks share one high-concurrency Spark session instead of starting
  one each. This needs the workspace setting *For pipeline running multiple notebooks*;
  `nor-environment-check` reports when it is off. One session holds at most 5 notebooks per tag; Fabric starts another
  beyond that.

Render the notebooks first. The pipeline reads their local `.platform` `config.logicalId` values for `notebookId`
and uses `00000000-0000-0000-0000-000000000000` for same-workspace `workspaceId`. This is the native Git format,
also used by the `fabric-cicd` pipeline sample. Preserve existing logical IDs. Custom `{{Notebook:name}}` or
`{{workspace_id}}` reference syntax is not supported; re-render older placeholder-based definitions.

## Publish

`nor-notebook-publish-and-run publish <id> pl_<id>` checks the definition and calls `fab deploy`, which delegates
to `fabric-cicd` using the existing Fabric CLI authentication. The library owns logical-to-physical ID replacement,
workspace ID replacement, folder handling, and item create/update. Do not copy those internals or add another resolver.

The scratch deployment config uses the entire local workspace as `repository_directory`, includes Notebook and
DataPipeline types for dependency lookup, excludes every item name except the selected pipeline from publishing,
and explicitly sets `unpublish.skip: true`. Publish the referenced notebooks first; they are not redeployed by this
command. Source definitions are not rewritten. `fab import` is a raw single-item import and does not rebind references.

If validation or `fab deploy` fails, retain the command output and any HTTP error/request ID. Diagnose the stated
definition, dependency, permission or capacity error before starting a run; there is no activity run to query yet.
Do not bypass the library with a custom publisher, rewrite logical IDs, reconnect Git, delete items, or change
capacity as speculative fixes. Generic errors remain unproven; report the evidence and the missing check.

Git integration and REST deployment are separate paths: a successful deployment doesn't prove `updateFromGit`
works. An immediate Git `UnknownError` doesn't establish that a pipeline definition is invalid. Get approval before
creating diagnostic branches/workspaces or changing the original workspace connection.

Microsoft Learn: [pipeline CI/CD](https://learn.microsoft.com/fabric/data-factory/cicd-pipelines),
[Git logical references](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd),
[Create Data Pipeline](https://learn.microsoft.com/rest/api/fabric/datapipeline/items/create-data-pipeline).

## Check
```bash
python3 "<directory of this SKILL.md>/scripts/pipeline_definition.py" check <ws_name>/<id>/pl_<id>.DataPipeline
```
Structural only: valid JSON, non-empty activities, unique activity names, every `dependsOn` names an existing
activity and has a condition, and no unresolved `{{...}}` placeholder. `publish` runs it automatically.

## Editing
Keep the rendered pipeline as is for a standard source-aligned product. Add an activity only when the product
genuinely has another step (for example a Copy activity that lands raw files instead of `nb_extract_<id>`), and
connect it with `Succeeded`. Keep the timeout, retry and session-tag defaults on new activities. Do not add parameters, variables or failure
branches unless the source requires them, and never add a path that lets the pipeline succeed after a failed activity.

Good: `nb_extract_x` → (Succeeded) → `nb_cdc_x`.
Bad: `nb_cdc_x` depends on `nb_extract_x` with `Completed` (CDC runs after a failed extract), or a `Failed` branch
ending in a Wait/SetVariable activity (the pipeline reports success and monitoring never alerts).

## Run and schedule
- Headless acceptance: use `nor-notebook-publish-and-run start` + bounded `wait` for `pl_<id>`, then verify
  output tables and row counts. A failed pipeline's job ID goes directly to `nor-spark-diagnostics` for activity
  errors and exact notebook/session IDs. Do not infer the failed notebook from a generic pipeline error.
- Schedule only when the user asks, and only the pipeline, for example daily at 06:00 UTC:
  `fab job run-sch /<ws>.Workspace/<id>.Folder/pl_<id>.DataPipeline --type daily --interval 06:00 --start <UTC> --end <UTC> --enable`.
  Never schedule a notebook.
- Master pipelines for business data products (calling product pipelines with `InvokePipeline`) are not templated
  yet; `InvokePipeline` needs a Fabric connection in `externalReferences.connection`.
