#!/usr/bin/env bash
# Livy session driver over `fab api`. See SKILL.md. State file: .scratch/livy_session.json
source "$(dirname "$0")/../../../../scripts/fab_common.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"; STATE_DIR="$REPO_ROOT/.scratch"; STATE="$STATE_DIR/livy_session.json"; mkdir -p "$STATE_DIR"
CMD="${1:-}"; shift || true

load_state() { [ -f "$STATE" ] || die "no session (run: livy_session.sh create <lakehouse_name>)"; BASE=$(python3 -c "import json;print(json.load(open('$STATE'))['base'])"); SID=$(python3 -c "import json;print(json.load(open('$STATE'))['session_id'])"); }
session_state() { fab_api_q "text.state" "$BASE/$SID"; }
wait_idle() { local t0=$(date +%s); while :; do local st=$(session_state); local inner=$(fab_api_q "text.fabricSessionStateInfo.state" "$BASE/$SID"); case "$st" in idle) echo "session idle after $(( $(date +%s)-t0 ))s"; return 0;; dead|error|killed|shutting_down|success) fab_api "$BASE/$SID" -q "text" | head -40; die "session state $st";; esac; case "$inner" in error|dead) fab_api "$BASE/$SID" -q "text.fabricSessionStateInfo"; die "session failed while starting (fabricSessionStateInfo=$inner)";; esac; sleep 10; echo "  $(( $(date +%s)-t0 ))s $st"; [ $(( $(date +%s)-t0 )) -gt 900 ] && die "timeout waiting for idle"; done; }

# submit <kind> <codefile> -> prints output, returns 0 ok / 1 error
submit() {
  local kind="$1" codefile="$2" body="$STATE_DIR/stmt_body.json"
  python3 - "$kind" "$codefile" "$body" <<'PY'
import json,sys; json.dump({"kind":sys.argv[1],"code":open(sys.argv[2],encoding="utf-8").read()}, open(sys.argv[3],"w"))
PY
  local stid; stid=$(fab_api_q "text.id" "$BASE/$SID/statements" -X post -i "$body"); [[ "$stid" =~ ^[0-9]+$ ]] || { fab_api "$BASE/$SID/statements" -X post -i "$body" | head -20; die "statement submit failed"; }
  local st; while :; do st=$(fab_api_q "text.state" "$BASE/$SID/statements/$stid"); case "$st" in available|error|cancelled) break;; esac; sleep 3; done
  fab_api "$BASE/$SID/statements/$stid" -q "text.output" > "$STATE_DIR/stmt_out.json"
  python3 - "$STATE_DIR/stmt_out.json" <<'PY'
import json,sys; o=json.load(open(sys.argv[1])) or {}
txt=(o.get("data") or {}).get("text/plain","")
if txt: print(txt)
if o.get("status")=="error":
    print(f"ERROR {o.get('ename')}: {o.get('evalue')}"); print("".join(o.get("traceback") or [])[-3000:]); sys.exit(1)
print(f"[statement ok, execution_count={o.get('execution_count')}]")
PY
}

case "$CMD" in
  create)
    LH="${1:?lakehouse_name required}"; need_target; [ "${2:-}" = "--no-environment" ] && ENVIRONMENT_ID="" && ENVIRONMENT_NAME="none (wheel installed in-session)"
    LH_ID=$(item_id "$LH" Lakehouse); [ -n "$LH_ID" ] || die "lakehouse $LH not found in $WORKSPACE_NAME"
    BASE="workspaces/$WORKSPACE_ID/lakehouses/$LH_ID/livyapi/versions/2023-12-01/sessions"
    BODY="$STATE_DIR/session_body.json"
    python3 - "$BODY" "$ENVIRONMENT_ID" "$LH" <<'PY'
import json,sys,time
body={"name":f"nor-{sys.argv[3]}-{time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())}"}
if sys.argv[2]: body["conf"]={"spark.fabric.environmentDetails": json.dumps({"id": sys.argv[2]})}
json.dump(body,open(sys.argv[1],"w"))
PY
    SID=$(fab_api_q "text.id" "$BASE" -X post -i "$BODY"); [[ "$SID" =~ ^[0-9a-f-]{36}$ ]] || { fab_api "$BASE" -X post -i "$BODY" | head -20; die "session create failed"; }
    python3 -c "import json;json.dump({'base':'$BASE','session_id':'$SID','lakehouse':'$LH','workspace_name':'$WORKSPACE_NAME'},open('$STATE','w'))"
    info "session $SID on $LH (environment ${ENVIRONMENT_NAME:-none})"; wait_idle
    sed "s/__WORKSPACE_NAME__/$WORKSPACE_NAME/" "$HERE/../preamble/livy_preamble.py" > "$STATE_DIR/preamble.py"; python3 -c "import json;d=json.load(open('$STATE'));d['environment']='$ENVIRONMENT_ID';json.dump(d,open('$STATE','w'))"; submit pyspark "$STATE_DIR/preamble.py" ;;
  status) load_state; echo "session $SID: $(session_state)" ;;
  statement) load_state; if [ "${1:-}" = "-f" ]; then submit pyspark "$2"; else printf '%s' "$1" > "$STATE_DIR/adhoc.py"; submit pyspark "$STATE_DIR/adhoc.py"; fi ;;
  run-cells)
    load_state; NB="${1:?notebook-content.py required}"; SEL="${2:-all}"; KEEP=0; [ "${3:-}" = "--keep-going" ] && KEEP=1
    python3 "$HERE/notebook_cells.py" "$NB" --json > "$STATE_DIR/cells.json"
    mapfile -t IDX < <(python3 - "$STATE_DIR/cells.json" "$SEL" <<'PY'
import json,sys; cells=json.load(open(sys.argv[1])); sel=sys.argv[2]
want=[c["index"] for c in cells if c["type"]!="markdown"] if sel=="all" else [int(x) for x in sel.split(",")]
print("\n".join(str(i) for i in want))
PY
)
    RC=0; for i in "${IDX[@]}"; do
      python3 - "$STATE_DIR/cells.json" "$i" "$STATE_DIR/cell.py" <<'PY'
import json,sys; c=next(c for c in json.load(open(sys.argv[1])) if c["index"]==int(sys.argv[2])); open(sys.argv[3],"w",encoding="utf-8").write(c["source"]); print(f"\n=== cell {c['index']} [{c['type']}/{c['kind']}] {c['title']}")
PY
      KIND=$(python3 -c "import json;print(next(c for c in json.load(open('$STATE_DIR/cells.json')) if c['index']==$i)['kind'])")
      if ! submit "$KIND" "$STATE_DIR/cell.py"; then RC=1; [ "$KEEP" -eq 1 ] || { echo "stopped at cell $i"; break; }; fi
    done; exit $RC ;;
  delete) load_state; fab_api "$BASE/$SID" -X delete >/dev/null; rm -f "$STATE"; echo "session $SID deleted" ;;
  *) echo "usage: livy_session.sh create <lakehouse> [--no-environment]|status|statement <code>|-f file|run-cells <nb.py> [all|N,M] [--keep-going]|delete"; exit 2 ;;
esac
