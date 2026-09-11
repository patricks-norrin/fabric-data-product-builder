#!/usr/bin/env bash
# Usage: run_notebook_job.sh publish|run|export|runs <data_product_identifier> <notebook_name> [fab job run args...]
source "$(dirname "$0")/../../../../scripts/fab_common.sh"
CMD="${1:?}"; DP="${2:?}"; NB="${3:?}"; shift 3; need_target
LOCAL="$REPO_ROOT/notebooks/$DP/$NB.Notebook"; FOLDER="$WORKSPACE_PATH/$DP.Folder"; ITEM="$FOLDER/$NB.Notebook"
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
    info "running $NB (sync)"; set +e; fab job run "$ITEM" "$@" 2>&1 | strip_cr | grep -v '^\s*$' | tail -3; RC=${PIPESTATUS[0]}; set -e
    JID=$(fab_api_q "text.value[0].id" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances")
    fab_api "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID" -q "text.{status:status,start:startTimeUtc,end:endTimeUtc,failureReason:failureReason.message}"
    STATUS=$(fab_api_q "text.status" "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances/$JID"); [ "$STATUS" = "Completed" ] ;;
  runs) ID=$(nb_id); fab_api "workspaces/$WORKSPACE_ID/items/$ID/jobs/instances" -q "text.value[:5].{id:id,status:status,start:startTimeUtc,end:endTimeUtc}" ;;
  export)
    OUT="$REPO_ROOT/.scratch/export/$DP"; rm -rf "$OUT"; mkdir -p "$OUT"; fab export "$ITEM" -o "$OUT" --format .py -f >/dev/null 2>&1 || die "export failed"
    diff <(grep -v '^$' "$LOCAL/notebook-content.py") <(grep -v '^$' "$OUT/$NB.Notebook/notebook-content.py") && pass "remote definition identical to local" || warn "remote differs from local (see above)" ;;
  *) die "usage: publish|run|export|runs <dp> <notebook> [args]" ;;
esac
