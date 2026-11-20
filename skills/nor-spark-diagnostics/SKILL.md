---
name: nor-spark-diagnostics
description: Diagnose a failed, slow, or stuck Fabric pipeline, notebook, or Livy Spark run with read-only fab api calls. For pipelines, query activity runs to obtain errors and exact notebook/run/session IDs before Spark diagnostics. Use after nor-notebook-publish-and-run reports a failureReason or when investigating Spark logs, Advisor, stages, or executors.
---

# nor-spark-diagnostics

Use this skill only to diagnose a failed, slow, or stuck pipeline or Spark run. It is read-only: never create,
restart, or delete a session, and never republish or change an item before reporting the evidence.

For a pipeline, start with **Pipeline run** below. A pipeline job instance ID is not a notebook job instance ID.
Deployment failures before a job exists belong to `nor-pipeline-author`, not Spark diagnostics.

Start from the job instance ID and `failureReason` printed by `nor-notebook-publish-and-run`. Resolve the
workspace and notebook IDs from the selected project target; never guess them. The recipes below are shell-neutral
`fab` commands: substitute `<workspace-id>`, `<notebook-id>`, `<job-instance-id>`, `<livy-id>` (the Livy session of
the job instance) and `<app-id>` (its Spark application) with resolved values.

## Evidence order

1. Start with the existing job-instance `failureReason`. If it names a specific root cause, report it and stop.
2. Resolve the Livy session and Spark application IDs. Check Spark Advisor before any log download.
3. Only when Advisor is empty or generic, read driver logs. Check **stdout first**: a notebook cell's Python
   traceback (`AnalysisException`, `KeyError`, `Cell In[n], line m`) is written to driver stdout, which is
   small. `System_Cancelled_Session_Statements_Failed` almost always means such a cell exception. Read
   driver stderr only for JVM-side failures (OOM, lost executors, task failures) and only as a bounded range.
4. For a slow or still-running job, inspect stages, executors, and resource usage with compact projections.
5. When monitoring data has expired, report the retained job `failureReason` and construct a Notebook Snapshot
   URL for manual cell-level inspection. Do not rerun the original notebook merely to obtain diagnostics.

Spark Monitoring data (Advisor, logs, stages, executors) can expire within hours. Diagnose promptly. Job
instance failure reasons last longer but are less detailed.

## Cookbook

### Pipeline run

Use the pipeline item ID and job instance ID retained by the runner. Resolve the item ID from the selected
target if only the pipeline name/path was supplied. Do not infer a notebook run from its name or timestamps.

```text
fab api "workspaces/<workspace-id>/items/<pipeline-id>/jobs/instances/<pipeline-job-id>" -X get
```

Write this JSON to `<project>/.scratch/<ws_name>/diagnostics/activity-query.json`, replacing the time placeholders with ISO 8601 UTC bounds enclosing the recorded
run: start minus one hour through end plus one hour (use current UTC time if still running). Keep the query
scoped to this job; the job ID is the same ID used by the Job Scheduler.

```json
{
  "filters": [],
  "orderBy": [{"orderBy": "ActivityRunStart", "order": "DESC"}],
  "lastUpdatedAfter": "<run start UTC minus one hour>",
  "lastUpdatedBefore": "<run end or current UTC plus one hour>",
  "continuationToken": null
}
```

```text
fab api "workspaces/<workspace-id>/datapipelines/pipelineruns/<pipeline-job-id>/queryactivityruns" -X post -i "<activity-query.json path>" \
  -q "{status_code:status_code,message:text.message,continuationToken:text.continuationToken,activities:text.value[].{name:activityName,type:activityType,status:status,iteration:iterationHash,retry:retryAttempt,notebook:input.notebookId,workspace:input.workspaceId,job:output.result.runId,session:output.result.sessionId,exception:output.result.error,error:error}}"
```

Check `status_code`, not the CLI exit code: `fab api` can exit zero on HTTP errors. On `200`, inspect the projected
activities. Repeat with the full returned `continuationToken` string in the request body until it is null, even
if a page has no activities. Never parse or truncate the token. If the projection lacks errors/IDs, capture the
raw response once under `.scratch/` and decode `text.value[].input`/`output` with a JSON parser if they are JSON
strings; do not print full parameter/output payloads. On HTTP failure, preserve the response and request ID and stop.

For each activity, retain name, type, status, iteration and retry attempt. Group retries by activity name plus
`iterationHash`; inspect the highest `retryAttempt` in each group and mention recovered earlier failures.

| Evidence | Action |
|---|---|
| `output.result.error` | Report exception (`ename`, `evalue`) and relevant `traceback` frames as returned. A specific user-code error needs no Spark tuning or additional logs. |
| `error` | Report `errorCode`, `message`, and `failureType`. For Copy/Web/other non-Spark activities, stop here and use the activity's documented troubleshooting path. |
| `input.notebookId`, `input.workspaceId` | Use them as `<notebook-id>` and `<workspace-id>` for the notebook; respect cross-workspace references. |
| `output.result.runId`, `output.result.sessionId` | When present, use them as `<job-instance-id>` and `<livy-id>`, then use the existing session/Advisor/log recipes only if the error remains unclear. |

If no session ID exists, report the activity error: Spark may never have started, or a downstream activity may
have been cancelled. Do not invent a session or rerun to obtain one. For child-pipeline activities, repeat this
query only with the child workspace/item/run IDs returned by the activity; report missing IDs rather than guess.
Shared high-concurrency session metrics can include other notebooks: attribute activity errors directly, and
do not present shared metrics as proof about one activity. Missing or expired evidence uses the existing Snapshot
fallback only when notebook/session IDs are known; otherwise report the retained pipeline error and stop.

This adapts `skills-for-fabric`'s Spark pipeline-diagnosis recipe without importing its architecture or helpers.
Contracts: [Fabric activity query](https://learn.microsoft.com/fabric/data-factory/pipeline-rest-api-capabilities#query-activity-runs),
[Fabric pagination guidance](https://learn.microsoft.com/fabric/data-factory/pipeline-troubleshoot-guide#general).

### Resolve the job and session

List recent instances when the job instance ID was not retained. Select a failed instance explicitly; do not
assume the most recent run failed.

```text
fab api "workspaces/<workspace-id>/items/<notebook-id>/jobs/instances" -X get \
  -q "text.value[:5].{id:id,status:status,start:startTimeUtc,end:endTimeUtc,failure:failureReason.message}"
```

For a known Livy ID, retrieve the Spark application ID and confirm state:

```text
fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>" -X get \
  -q "text.{app:sparkApplicationId,state:state,job:jobInstanceId}"
```

If the session is no longer listed or this call returns `404`, monitoring retention has expired. Do not probe
alternate paths; use the job instance result and the Snapshot fallback below.

### Ask Spark Advisor first

```text
fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>/applications/<app-id>/advice" \
  -X get -q "text"
```

An empty array is valid for a healthy run. A nonempty response can identify task errors, data skew, or time
skew. Report the first actionable error or warning and its recommended fix before collecting lower-level data.

### Read driver logs without flooding context

Check **stdout first**; read `stderr` only for JVM-side failures. Log content is not JSON, so `fab api` cannot read
it; use the Livy driver from `nor-livy-session`, which saves a bounded tail under the project's `.scratch/` and
prints only the matching failure lines:

```text
python3 "<nor-livy-session directory>/scripts/livy_session.py" download-log <notebook-id> <livy-id> <app-id> --file stdout
```

Add `--workspace-id <workspace-id>` when the notebook is outside the project target, and `--bytes N` to widen the
tail. Then read only the lines around the first traceback in the saved file. An error saying no log length was
returned means monitoring data expired: use the Snapshot fallback. Never print a full driver or executor log.

### Inspect a slow or running application

```text
fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>/applications/<app-id>/jobs" \
  -X get -q "text[:5].{id:jobId,status:status,tasks:numTasks,failed:numFailedTasks}"

fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>/applications/<app-id>/stages" \
  -X get -q "text[].{id:stageId,status:status,tasks:numTasks,completed:numCompleteTasks,failed:numFailedTasks,input:inputBytes,shuffleRead:shuffleReadBytes,shuffleWrite:shuffleWriteBytes}"

fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>/applications/<app-id>/allexecutors" \
  -X get -q "text[].{id:id,active:isActive,completed:completedTasks,failed:failedTasks,duration:totalDuration,gc:totalGCTime,shuffleRead:totalShuffleRead,shuffleWrite:totalShuffleWrite}"
```

Use the resource-usage endpoint only when stages and executors do not explain the slowdown; inspect the raw
response once before writing a projection because Fabric can vary its timeline shape:

```text
fab api "workspaces/<workspace-id>/notebooks/<notebook-id>/livySessions/<livy-id>/applications/<app-id>/resourceUsage" -X get
```

## Snapshot fallback

When monitoring data is expired, construct this URL after resolving the tenant ID by an approved local method:

```text
https://app.powerbi.com/workloads/de-ds/sparkmonitor/<notebook-id>/<livy-id>?trident=1&experience=power-bi&ctid=<TENANT_ID>&tab=related
```

It retains cell-level failure evidence longer than the monitoring APIs. Report the URL with the retained
`failureReason`; do not claim the failed cell or root cause without evidence.

## Report

Report the job instance, notebook, Livy/application IDs, evidence checked, root cause if specific (failing
cell, line, and exception message), and the smallest next action. If no specific cause was found, state which evidence was unavailable and stop. Do not
suggest tuning Spark settings for a successful, healthy run.