#!/usr/bin/env bash
# Shared helpers for fab-based scripts. Source this file.
set -o pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_FILE="$REPO_ROOT/configuration/target_workspace.json"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "• $*"; }
pass() { echo "PASS  $*"; }
warn() { echo "WARN  $*"; }
fail() { echo "FAIL  $*"; FAILURES=$((FAILURES+1)); }
FAILURES=0

strip_cr() { tr -d '\r'; }

# fab api wrapper: fab_api <endpoint> [fab api args...]  -> stdout without CR
fab_api() { fab api "$@" 2>/dev/null | strip_cr; }

# JMESPath on fab api: fab_api_q <query> <endpoint> [args...]
fab_api_q() { local q="$1"; shift; fab api "$@" -q "$q" 2>/dev/null | strip_cr | sed 's/^"//;s/"$//'; }

need_target() {
  [ -f "$TARGET_FILE" ] || die "missing $TARGET_FILE"
  WORKSPACE_NAME=$(python3 -c "import json;print(json.load(open('$TARGET_FILE'))['workspace_name'])")
  ENVIRONMENT_ID=$(python3 -c "import json;print(json.load(open('$TARGET_FILE')).get('environment',{}).get('id',''))")
  ENVIRONMENT_WORKSPACE_ID=$(python3 -c "import json;print(json.load(open('$TARGET_FILE')).get('environment',{}).get('workspace_id',''))")
  ENVIRONMENT_NAME=$(python3 -c "import json;print(json.load(open('$TARGET_FILE')).get('environment',{}).get('name',''))")
  WORKSPACE_PATH="$WORKSPACE_NAME.Workspace"
  WORKSPACE_ID=$(fab get "$WORKSPACE_PATH" -q id 2>/dev/null | strip_cr | tr -d '" ')
  [[ "$WORKSPACE_ID" =~ ^[0-9a-f-]{36}$ ]] || die "workspace '$WORKSPACE_NAME' not found (fab auth status?)"
}

# item id by display name and type inside the target workspace (folders are transparent to the API)
item_id() { # item_id <displayName> <Type>
  fab_api_q "text.value[?displayName=='$1'].id | [0]" "workspaces/$WORKSPACE_ID/items" -P "type=$2" | sed 's/^None$//'
}

# ensure one OneLake directory level exists: onelake_mkdir_p <lakehouse item path> <Files/a/b/c>
onelake_mkdir_p() {
  local lh="$1" rel="$2" acc=""
  IFS='/' read -ra parts <<< "$rel"
  for p in "${parts[@]}"; do
    acc="${acc:+$acc/}$p"
    [ "$acc" = "Files" ] && continue
    if ! fab exists "$lh/$acc" 2>/dev/null | strip_cr | grep -qi true; then
      fab mkdir "$lh/$acc" >/dev/null 2>&1 || die "mkdir failed: $lh/$acc"
      info "created $lh/$acc"
    fi
  done
}
