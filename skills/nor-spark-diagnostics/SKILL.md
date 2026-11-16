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

```bash
PIPELINE_ID="<resolved pipeline item ID>"
PIPELINE_JOB_ID="<recorded pipeline job instance ID>"
QUERY_BODY="<absolute path under the selected project's .scratch/ to activity-query.json>"
fab api "workspaces/$WORKSPACE_ID/items/$PIPELINE_ID/jobs/instances/$PIPELINE_JOB_ID" -X get
```

Write this JSON to `QUERY_BODY`, replacing the time placeholders with ISO 8601 UTC bounds enclosing the recorded
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

```bash
fab api "workspaces/$WORKSPACE_ID/datapipelines/pipelineruns/$PIPELINE_JOB_ID/queryactivityruns" -X post -i "$QUERY_BODY" \
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
| `input.notebookId`, `input.workspaceId` | Set `NOTEBOOK_ID` and `WORKSPACE_ID` for the notebook; respect cross-workspace references. |
| `output.result.runId`, `output.result.sessionId` | When present, set notebook `JOB_INSTANCE_ID` and `LIVY_ID`, then use the existing session/Advisor/log recipes only if the error remains unclear. |

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

### Read driver logs without flooding context

Check log metadata with `fab api` (JSON). `LOG` is `stdout` first, then `stderr` only if needed:

```bash
APP_PATH="workspaces/$WORKSPACE_ID/notebooks/$NOTEBOOK_ID/livySessions/$LIVY_ID/applications/$APP_ID"
LOG=stdout
LEN=$(fab api "$APP_PATH/logs?type=driver&meta=true&fileName=$LOG" -X get -q "text.containerLogMeta.length" | tr -d '[:space:]')
case "$LEN" in ''|*[!0-9]*) echo "unexpected $LOG length '$LEN'" ;; *) echo "$LOG length: $LEN" ;; esac
```

Only strip whitespace (`fab` can end lines with `\r`); never extract digits from arbitrary output. `fab api`
exits `0` even on HTTP errors and prints `None` when the projection matches nothing, so a non-integer value is
ambiguous. Inspect the raw response once without `-q`: `status_code` `404` means the log is not retained (use
the Snapshot fallback); any other shape means Fabric or `fab` changed, so adjust the projection to what the
response actually contains instead of guessing.

Log content is returned as `application/octet-stream`, which `fab api` cannot parse (`[UnexpectedError]
Expecting value: line 1 column 1`). Do not retry it with other `fab` flags; download a bounded range with
`curl` and an `az` token into a temporary file, then search the file instead of printing it:

```bash
SIZE=16384; OFFSET=$(( LEN > SIZE ? LEN - SIZE : 0 ))
TOKEN=$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)
curl -sS -H "Authorization: Bearer $TOKEN" -o "/tmp/${LIVY_ID}_$LOG.log" \
  "https://api.fabric.microsoft.com/v1/$APP_PATH/logs?type=driver&fileName=$LOG&isDownload=true&isPartial=true&offset=$OFFSET&size=$SIZE"
grep -nE "Traceback|Exception|Error" "/tmp/${LIVY_ID}_$LOG.log" | head -20
```

Read the tail (the failure is at the end), then `view` only the lines around the first traceback. Stdout is
usually small enough to read whole. Never print a full driver or executor stderr log, which can be megabytes,
and delete the temporary files after reporting.

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

Report the job instance, notebook, Livy/application IDs, evidence checked, root cause if specific (failing
cell, line, and exception message), and the smallest next action. If no specific cause was found, state which evidence was unavailable and stop. Do not
suggest tuning Spark settings for a successful, healthy run.