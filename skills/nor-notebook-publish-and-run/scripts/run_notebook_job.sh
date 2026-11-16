#!/usr/bin/env bash
# Usage:
#   run_notebook_job.sh publish|export|runs <data_product_identifier> <nb_* or pl_* name> [--workspace ws_name] [--target profile]
#   run_notebook_job.sh run|start <data_product_identifier> <nb_* or pl_* name> [-P|-C|-i fab job args] [--timeout s] [--poll s]
#   run_notebook_job.sh wait <data_product_identifier> <nb_* or pl_* name> [--job-id id] [--timeout s] [--poll s]
# Names starting with pl_ are DataPipelines; everything else is a Notebook.
#   run_notebook_job.sh status [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]//\\//}")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
CMD="${1:?usage: publish|run|start|wait|status|export|runs <dp> <notebook> [args]}"
TERMINAL_STATUSES=" Completed Failed Cancelled Deduped "

manifest() { python3 "$TOOLPACK_ROOT/scripts/run_manifest.py" "$SCRATCH_DIR/operational_manifest.jsonl" "$@"; }
now_utc() { date -u +%H:%M:%SZ; }

# Reads `fab job ... --json` and prints id, status, start, end and failure message, one line each.
job_fields() {
  python3 -c 'import json, sys
job = json.load(sys.stdin)["result"]["data"][0]
failure = job.get("failureReason") or {}
failure = failure.get("message") if isinstance(failure, dict) else failure
for value in (job.get("id"), job.get("status"), job.get("startTimeUtc"), job.get("endTimeUtc"), failure):
    print(" ".join(str(value or "").split()))'
}

# job_status <item path> <job id> -> J=(id status start end failure); returns 1 and sets FAB_OUT when unreadable
job_status() {
  local fields
  FAB_OUT=$(fab job run-status "$1" --id "$2" --json 2>/dev/null | strip_cr)
  fields=$(printf '%s' "$FAB_OUT" | job_fields 2>/dev/null) || return 1
  mapfile -t J <<< "$fields"
  [ -n "${J[1]}" ]
}

TIMEOUT=3600; POLL=30; JOB_ID=""; FAB_ARGS=()
parse_poll_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --timeout) TIMEOUT="${2:?--timeout requires seconds}"; shift 2 ;;
      --poll|--polling_interval) POLL="${2:?--poll requires seconds}"; shift 2 ;;
      --job-id) JOB_ID="${2:?--job-id requires an id}"; shift 2 ;;
      *) FAB_ARGS+=("$1"); shift ;;
    esac
  done
  [[ "$TIMEOUT" =~ ^[0-9]+$ && "$POLL" =~ ^[0-9]+$ && "$POLL" -gt 0 ]] || die "--timeout and --poll must be positive integers"
}

start_job() { # sets JOB_ID from the structured output of fab job start
  local out
  record_run_event job_requested "item=$ITEM" "notebook=$NB" "data_product=$DP"
  info "[$(now_utc)] starting $NB in $WORKSPACE_NAME"
  out=$(fab job start "$ITEM" "${FAB_ARGS[@]}" --json 2>/dev/null | strip_cr)
  JOB_ID=$(printf '%s' "$out" | job_fields 2>/dev/null | head -1)
  [ -n "$JOB_ID" ] || { echo "$out" | tail -8; die "fab job start returned no job instance id for $NB"; }
  record_run_event job_started "item=$ITEM" "job_id=$JOB_ID" "notebook=$NB" "data_product=$DP" "workspace=$WORKSPACE_NAME"
  pass "started $NB (job $JOB_ID)"
}

wait_job() { # 0 Completed, 1 any other terminal status, 124 still running at timeout
  local jid="$1" last="" errors=0
  SECONDS=0
  info "waiting for $NB (job $jid): polling every ${POLL}s, timeout ${TIMEOUT}s"
  while :; do
    if job_status "$ITEM" "$jid"; then
      errors=0
      echo "[$(now_utc)] $NB ${J[1]} ${SECONDS}s (job $jid)"
      if [ "${J[1]}" != "$last" ]; then
        record_run_event job_status "item=$ITEM" "job_id=$jid" "notebook=$NB" "status=${J[1]}"
        last="${J[1]}"
      fi
      [[ "$TERMINAL_STATUSES" == *" $last "* ]] && { finish_job "$jid"; return; }
    else
      errors=$((errors+1))
      warn "[$(now_utc)] $NB status unreadable ($errors/5): $(echo "$FAB_OUT" | tr -s ' \n' ' ' | tail -c 200)"
      [ "$errors" -ge 5 ] && die "could not read status of job $jid five times in a row"
    fi
    if [ "$SECONDS" -ge "$TIMEOUT" ]; then
      record_run_event job_wait_timeout "item=$ITEM" "job_id=$jid" "notebook=$NB" "status=$last" "waited_s=$SECONDS"
      warn "$NB still ${last:-unknown} after ${SECONDS}s; the Fabric job keeps running. Resume with: wait $DP $NB --job-id $jid"
      return 124
    fi
    sleep "$POLL"
  done
}

finish_job() { # uses J from the last successful poll
  record_run_event job_finished "item=$ITEM" "job_id=$1" "notebook=$NB" "data_product=$DP" "status=${J[1]}" \
    "start_utc=${J[2]}" "end_utc=${J[3]}" "failure_reason=${J[4]}"
  if [ "${J[1]}" = "Completed" ]; then
    pass "$NB Completed (job $1, ${J[2]} -> ${J[3]})"; return 0
  fi
  fail "$NB ${J[1]} (job $1, ${J[2]} -> ${J[3]})"
  [ -n "${J[4]}" ] && echo "failureReason: ${J[4]}"
  if [ "$TYPE" = DataPipeline ]; then
    echo "next: load nor-spark-diagnostics for pipeline $ITEM, workspace $WORKSPACE_ID, job instance $1 before changing or rerunning it"
  else
    echo "next: load nor-spark-diagnostics with job instance $1 before changing or rerunning $NB"
  fi
  return 1
}

if [ "$CMD" = "status" ]; then
  resolve_context
  JOBS=$(manifest --latest-jobs)
  [ -n "$JOBS" ] || { info "no jobs recorded in $SCRATCH_DIR/operational_manifest.jsonl"; exit 0; }
  printf '%-32s %-11s %-28s %-28s %s\n' notebook status start_utc end_utc job_id
  while IFS=$'\t' read -r item jid; do
    nb=${item##*/}; nb=${nb%.*}
    if job_status "$item" "$jid"; then
      printf '%-32s %-11s %-28s %-28s %s\n' "$nb" "${J[1]}" "${J[2]:--}" "${J[3]:--}" "$jid"
      [ -n "${J[4]}" ] && echo "  failureReason: ${J[4]}"
    else
      printf '%-32s %-11s %-28s %-28s %s\n' "$nb" unreadable - - "$jid"
    fi
  done <<< "$JOBS"
  exit 0
fi

DP="${2:?data product identifier required}"; NB="${3:?item name required}"; shift 3; need_target
TYPE=Notebook; [[ "$NB" == pl_* ]] && TYPE=DataPipeline
LOCAL="$WORKSPACE_DIR/$DP/$NB.$TYPE"; FOLDER="$WORKSPACE_PATH/$DP.Folder"; ITEM="$FOLDER/$NB.$TYPE"
PIPELINE_PY="$TOOLPACK_ROOT/skills/nor-pipeline-author/scripts/pipeline_definition.py"

publish_pipeline() {
  local config="$SCRATCH_DIR/publish/$DP/$NB.deploy.yml"
  python3 "$PIPELINE_PY" deploy-config "$LOCAL" "$config" --workspace-dir "$WORKSPACE_DIR" --workspace-id "$WORKSPACE_ID" || die "invalid $NB definition"
  fab deploy --config "$config" -f || die "could not publish $NB"
}

ENV_PY="$SCRIPT_DIR/notebook_environment.py"
publish_notebook() { # a Git-sync Environment binding is rebound to the same-named Environment in the target
  local src="$LOCAL" env_name env_id
  env_name=$(python3 "$ENV_PY" ref "$LOCAL" "$WORKSPACE_DIR") || die "cannot resolve the Environment binding of $NB"
  if [ -n "$env_name" ]; then
    env_id=$(item_id "$env_name" Environment)
    [ -n "$env_id" ] || die "$NB binds Environment $env_name, which is not in $WORKSPACE_NAME; create it first"
    src="$SCRATCH_DIR/publish/$DP/$NB.Notebook"
    python3 "$ENV_PY" resolve "$LOCAL" "$src" --environment-id "$env_id" --workspace-id "$WORKSPACE_ID" || die "could not resolve $NB"
    info "bound $NB to Environment $env_name ($env_id)"
  fi
  fab import "$ITEM" -i "$src" --format .py -f 2>&1 | strip_cr | grep -v '^\s*$' | tail -2
}

case "$CMD" in
  publish)
    if [ "$TYPE" = DataPipeline ]; then
      [ -f "$LOCAL/pipeline-content.json" ] || die "missing $LOCAL/pipeline-content.json (render it with nor-pipeline-author)"
    else
      [ -f "$LOCAL/notebook-content.py" ] || die "missing $LOCAL/notebook-content.py"
    fi
    fab exists "$FOLDER" 2>/dev/null | strip_cr | grep -qi true || die "folder $DP missing (run nor-data-product-config)"
    if [ "$TYPE" = DataPipeline ]; then
      publish_pipeline
    else
      publish_notebook
    fi
    for i in $(seq 1 12); do ID=$(item_id "$NB" "$TYPE"); [ -n "$ID" ] && break; sleep 5; done; [ -n "$ID" ] || die "$NB not found after import"
    pass "published $NB ($ID) in folder $DP" ;;
  start)
    parse_poll_args "$@"; start_job
    echo "next: wait $DP $NB --job-id $JOB_ID   |   status" ;;
  run)
    parse_poll_args "$@"; start_job; wait_job "$JOB_ID" ;;
  wait)
    parse_poll_args "$@"
    [ -n "$JOB_ID" ] || JOB_ID=$(manifest --latest-jobs | awk -F'\t' -v item="$ITEM" '$1 == item { print $2 }')
    [ -n "$JOB_ID" ] || die "no job recorded for $NB; pass --job-id (see: runs $DP $NB)"
    wait_job "$JOB_ID" ;;
  runs) fab job run-list "$ITEM" 2>&1 | strip_cr ;;
  export)
    [ "$TYPE" = Notebook ] || die "export compares notebooks only"
    OUT="$SCRATCH_DIR/export/$DP"; rm -rf "$OUT"; mkdir -p "$OUT"; fab export "$ITEM" -o "$OUT" --format .py -f >/dev/null 2>&1 || die "export failed"
    diff <(grep -v '^$' "$LOCAL/notebook-content.py") <(grep -v '^$' "$OUT/$NB.Notebook/notebook-content.py") && pass "remote definition identical to local" || warn "remote differs from local (see above)" ;;
  *) die "usage: publish|run|start|wait|status|export|runs <dp> <notebook> [args]" ;;
esac
