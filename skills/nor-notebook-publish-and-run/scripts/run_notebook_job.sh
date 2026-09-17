#!/usr/bin/env bash
# Usage: run_notebook_job.sh publish|run|export|runs <data_product_identifier> <notebook_name> [args] [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
CMD="${1:?}"; DP="${2:?}"; NB="${3:?}"; shift 3; need_target
LOCAL="$WORKSPACE_DIR/$DP/$NB.Notebook"; FOLDER="$WORKSPACE_PATH/$DP.Folder"; ITEM="$FOLDER/$NB.Notebook"
nb_id() { item_id "$NB" Notebook; }
case "$CMD" in
  publish)
    [ -f "$LOCAL/notebook-content.py" ] || die "missing $LOCAL/notebook-content.py"
    fab exists "$FOLDER" 2>/dev/null | strip_cr | grep -qi true || die "folder $DP missing (run nor-data-product-config)"
    fab import "$ITEM" -i "$LOCAL" --format .py -f 2>&1 | strip_cr | grep -v '^\s*$' | tail -2
    for i in $(seq 1 12); do ID=$(nb_id); [ -n "$ID" ] && break; sleep 5; done; [ -n "$ID" ] || die "notebook not found after import"
    pass "published $NB ($ID) in folder $DP" ;;
  run)
    ID=$(nb_id); [ -n "$ID" ] || die "notebook $NB not published"
    record_run_event job_requested "notebook_id=$ID" "notebook=$NB" "data_product=$DP"
    info "running $NB (sync)"; set +e; fab job run "$ITEM" "$@" 2>&1 | strip_cr | grep -v '^\s*$' | tail -3; RC=${PIPESTATUS[0]}; set -e
    JID=$(fab_api_q "text.value[0].id" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances")
    fab_api "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID" -q "text.{status:status,start:startTimeUtc,end:endTimeUtc,failureReason:failureReason.message}"
    STATUS=$(fab_api_q "text.status" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID")
    START=$(fab_api_q "text.startTimeUtc" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID")
    END=$(fab_api_q "text.endTimeUtc" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID")
    FAILURE=$(fab_api_q "text.failureReason.message" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID")
    record_run_event job_finished "job_id=$JID" "notebook_id=$ID" "notebook=$NB" "status=$STATUS" "start_utc=$START" "end_utc=$END" "failure_reason=$FAILURE" "command_exit_code=$RC"
    [ "$STATUS" = "Completed" ] ;;
  runs) ID=$(nb_id); fab_api "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances" -q "text.value[:5].{id:id,status:status,start:startTimeUtc,end:endTimeUtc}" ;;
  export)
    OUT="$SCRATCH_DIR/export/$DP"; rm -rf "$OUT"; mkdir -p "$OUT"; fab export "$ITEM" -o "$OUT" --format .py -f >/dev/null 2>&1 || die "export failed"
    diff <(grep -v '^$' "$LOCAL/notebook-content.py") <(grep -v '^$' "$OUT/$NB.Notebook/notebook-content.py") && pass "remote definition identical to local" || warn "remote differs from local (see above)" ;;
  *) die "usage: publish|run|export|runs <dp> <notebook> [args]" ;;
esac
