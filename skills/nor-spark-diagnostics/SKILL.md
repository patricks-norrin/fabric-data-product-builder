---
name: nor-spark-diagnostics
description: Diagnose a failed, slow, or stuck Fabric notebook or Livy Spark run with read-only fab api calls. Use after nor-notebook-publish-and-run reports a failureReason, or when the user asks to investigate Spark logs, Spark Advisor findings, stages, executors, or a headless notebook run.
---

# nor-spark-diagnostics

Use this skill only to diagnose a failed, slow, or stuck Spark run. It is read-only: never create, restart,
or delete a session, and never republish or change a notebook before reporting the evidence.

Start from the job instance ID and `failureReason` printed by `nor-notebook-publish-and-run`. Resolve the
workspace and notebook IDs from the selected project target; never guess them. Set these values before using
the recipes below:

```bash
WORKSPACE_ID=<resolved target workspace id>
NOTEBOOK_ID=<resolved notebook item id>
JOB_INSTANCE_ID=<failed job instance id>
LIVY_ID=<livyId associated with the job instance>
APP_ID=<sparkApplicationId associated with the Livy session>
```

## Evidence order

1. Start with the existing job-instance `failureReason`. If it names a specific root cause, report it and stop.
2. Resolve the Livy session and Spark application IDs. Check Spark Advisor before any log download.
3. Only when Advisor is empty or generic, check driver stderr metadata. Read a bounded partial log only when
   its metadata is available and more evidence is needed.
4. For a slow or still-running job, inspect stages, executors, and resource usage with compact projections.
5. When monitoring data has expired, report the retained job `failureReason` and construct a Notebook Snapshot
   URL for manual cell-level inspection. Do not rerun the original notebook merely to obtain diagnostics.

Spark Monitoring data (Advisor, logs, stages, executors) can expire within hours. Diagnose promptly. Job
instance failure reasons last longer but are less detailed.

## Cookbook

### Resolve the job and session

List recent instances when the job instance ID was not retained. Select a failed instance explicitly; do not
assume the most recent run failed.

```bash
fab api "workspaces/$WORKSPACE_ID/items/$NOTEBOOK_ID/jobs/instances" -X get \
  -q "text.value[:5].{id:id,status:status,start:startTimeUtc,end:endTimeUtc,failure:failureReason.message}"
```

For a known Livy ID, retrieve the Spark application ID and confirm state:

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID" -X get \
  -q "text.{app:sparkApplicationId,state:state,job:jobInstanceId}"
```

If the session is no longer listed or this call returns `404`, monitoring retention has expired. Do not probe
alternate paths; use the job instance result and the Snapshot fallback below.

### Ask Spark Advisor first

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/advice" \
  -X get -q "text"
```

An empty array is valid for a healthy run. A nonempty response can identify task errors, data skew, or time
skew. Report the first actionable error or warning and its recommended fix before collecting lower-level data.

### Check driver stderr without flooding context

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/logs?type=driver&meta=true&fileName=stderr" \
  -X get -q "text.{containerId:containerId,nodeId:nodeId,log:containerLogMeta}"
```

Only when the metadata proves a log exists and Advisor did not identify the problem, fetch a bounded range:

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/logs?type=driver&fileName=stderr&isDownload=true&isPartial=true&offset=0&size=10240" \
  -X get
```

Never download the full driver or executor log by default.

### Inspect a slow or running application

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/jobs" \
  -X get -q "text[:5].{id:jobId,status:status,tasks:numTasks,failed:numFailedTasks}"

fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/stages" \
  -X get -q "text[].{id:stageId,status:status,tasks:numTasks,completed:numCompleteTasks,failed:numFailedTasks,input:inputBytes,shuffleRead:shuffleReadBytes,shuffleWrite:shuffleWriteBytes}"

fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/allexecutors" \
  -X get -q "text[].{id:id,active:isActive,completed:completedTasks,failed:failedTasks,duration:totalDuration,gc:totalGCTime,shuffleRead:totalShuffleRead,shuffleWrite:totalShuffleWrite}"
```

Use the resource-usage endpoint only when stages and executors do not explain the slowdown; inspect the raw
response once before writing a projection because Fabric can vary its timeline shape:

```bash
fab api "workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID/resourceUsage" -X get
```

## Snapshot fallback

When monitoring data is expired, construct this URL after resolving the tenant ID by an approved local method:

```text
https://app.powerbi.com/workloads/de-ds/sparkmonitor/<NOTEBOOK_ID>/<LIVY_ID>?trident=1&experience=power-bi&ctid=<TENANT_ID>&tab=related
```

It retains cell-level failure evidence longer than the monitoring APIs. Report the URL with the retained
`failureReason`; do not claim the failed cell or root cause without evidence.

## Report

Report the job instance, notebook, Livy/application IDs, evidence checked, root cause if specific, and the
smallest next action. If no specific cause was found, state which evidence was unavailable and stop. Do not
suggest tuning Spark settings for a successful, healthy run.