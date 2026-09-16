#!/usr/bin/env bash
# Livy session driver. Control plane (ids) via fab; the Spark session itself is created with an Azure CLI user token,
# because Fabric's Spark runtime only receives a delegated OneLake identity from that token (see SKILL.md).
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOLPACK_ROOT="$(cd "$HERE/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
resolve_context
STATE_DIR="$SCRATCH_DIR/livy"; STATE="$STATE_DIR/livy_session.json"; mkdir -p "$STATE_DIR"
API="https://api.fabric.microsoft.com/v1"; CMD="${1:-}"; shift || true

token() { az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv 2>/dev/null || die "no Azure CLI token: run 'az login --tenant <tenant-id> --allow-no-subscriptions --use-device-code'"; }
livy() { # livy <METHOD> <path-after-/v1/> [bodyfile]
  local m="$1" p="$2" b="${3:-}"; local t; t=$(token)
  if [ -n "$b" ]; then curl -sS -X "$m" -H "Authorization: Bearer $t" -H "Content-Type: application/json" --data-binary "@$b" "$API/$p"; else curl -sS -X "$m" -H "Authorization: Bearer $t" "$API/$p"; fi
}
jq_() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1" 2>/dev/null; }
load_state() { [ -f "$STATE" ] || die "no session (run: livy_session.sh create <lakehouse_name>)"; BASE=$(python3 -c "import json;print(json.load(open('$STATE'))['base'])"); SID=$(python3 -c "import json;print(json.load(open('$STATE'))['session_id'])"); }
session_json() { livy GET "$BASE/$SID"; }
wait_idle() {
  local t0=$(date +%s)
  while :; do
    local j; j=$(session_json); local st inner msg
    st=$(echo "$j" | jq_ "d.get('state')"); inner=$(echo "$j" | jq_ "(d.get('fabricSessionStateInfo') or {}).get('state')"); msg=$(echo "$j" | jq_ "(d.get('fabricSessionStateInfo') or {}).get('errorMessage','')")
    case "$st" in idle) echo "session idle after $(( $(date +%s)-t0 ))s"; return 0;; dead|error|killed|shutting_down|success) die "session state $st: $msg";; esac
    case "$inner" in error|dead) die "session failed while starting: $msg";; esac
    echo "  $(( $(date +%s)-t0 ))s $st ${inner:-}"; sleep 10
    [ $(( $(date +%s)-t0 )) -gt 900 ] && die "timeout waiting for idle"
  done
}
submit() { # submit <kind> <codefile>
  local body="$STATE_DIR/stmt_body.json"
  python3 -c "import json,sys; json.dump({'kind':sys.argv[1],'code':open(sys.argv[2],encoding='utf-8').read()}, open(sys.argv[3],'w'))" "$1" "$2" "$body"
  local stid; stid=$(livy POST "$BASE/$SID/statements" "$body" | jq_ "d['id']"); [[ "$stid" =~ ^[0-9]+$ ]] || die "statement submit failed"
  local st; while :; do st=$(livy GET "$BASE/$SID/statements/$stid" | jq_ "d.get('state')"); case "$st" in available|error|cancelled) break;; esac; sleep 3; done
  livy GET "$BASE/$SID/statements/$stid" | python3 "$HERE/format_statement_output.py"
}

case "$CMD" in
  create)
    LH="${1:?lakehouse_name required}"; need_target; [ "${2:-}" = "--no-environment" ] && ENVIRONMENT_ID="" && ENVIRONMENT_NAME="none (wheel installed in-session)"
    LH_ID=$(item_id "$LH" Lakehouse); [ -n "$LH_ID" ] || die "lakehouse $LH not found in $WORKSPACE_NAME"
    BASE="workspaces/$WORKSPACE_ID/lakehouses/$LH_ID/livyapi/versions/2023-12-01/sessions"; BODY="$STATE_DIR/session_body.json"
    python3 - "$BODY" "$ENVIRONMENT_ID" "$LH" <<'PY'
import json,sys,time
body={"name":f"nor-{sys.argv[3]}-{time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())}"}
if sys.argv[2]: body["conf"]={"spark.fabric.environmentDetails": json.dumps({"id": sys.argv[2]})}
json.dump(body,open(sys.argv[1],"w"))
PY
    SID=$(livy POST "$BASE" "$BODY" | jq_ "d['id']"); [[ "$SID" =~ ^[0-9a-f-]{36}$ ]] || die "session create failed"
    python3 -c "import json;json.dump({'base':'$BASE','session_id':'$SID','lakehouse':'$LH','workspace_name':'$WORKSPACE_NAME','environment':'$ENVIRONMENT_ID'},open('$STATE','w'))"
    info "session $SID on $LH (environment ${ENVIRONMENT_NAME:-none})"; wait_idle
    sed "s/__WORKSPACE_NAME__/$WORKSPACE_NAME/" "$HERE/../preamble/livy_preamble.py" > "$STATE_DIR/preamble.py"; submit pyspark "$STATE_DIR/preamble.py" ;;
  status) load_state; session_json | jq_ "{'state': d.get('state'), 'inner': (d.get('fabricSessionStateInfo') or {}).get('state')}" ;;
  statement) load_state; if [ "${1:-}" = "-f" ]; then submit pyspark "$2"; else printf '%s' "$1" > "$STATE_DIR/adhoc.py"; submit pyspark "$STATE_DIR/adhoc.py"; fi ;;
  run-cells)
    load_state; NB="${1:?notebook-content.py required}"; SEL="${2:-all}"; KEEP=0; [ "${3:-}" = "--keep-going" ] && KEEP=1
    python3 "$HERE/notebook_cells.py" "$NB" --json > "$STATE_DIR/cells.json"
    mapfile -t IDX < <(python3 -c "
import json,sys; cells=json.load(open('$STATE_DIR/cells.json')); sel='$SEL'
want=[c['index'] for c in cells if c['type']!='markdown'] if sel=='all' else [int(x) for x in sel.split(',')]
print('\n'.join(str(i) for i in want))")
    RC=0; for i in "${IDX[@]}"; do
      python3 -c "
import json; c=next(c for c in json.load(open('$STATE_DIR/cells.json')) if c['index']==$i); open('$STATE_DIR/cell.py','w',encoding='utf-8').write(c['source']); open('$STATE_DIR/cell.kind','w').write(c['kind']); print(f\"\n=== cell {c['index']} [{c['type']}/{c['kind']}] {c['title']}\")"
      if ! submit "$(cat "$STATE_DIR/cell.kind")" "$STATE_DIR/cell.py"; then RC=1; [ "$KEEP" -eq 1 ] || { echo "stopped at cell $i"; break; }; fi
    done; exit $RC ;;
  delete) load_state; livy DELETE "$BASE/$SID" >/dev/null; rm -f "$STATE"; echo "session $SID deleted" ;;
  *) echo "usage: livy_session.sh create <lakehouse> [--no-environment]|status|statement <code>|-f file|run-cells <nb.py> [all|N,M] [--keep-going]|delete"; exit 2 ;;
esac
