#!/usr/bin/env bash
# Shared helpers for fab-based scripts. Source this file.
set -o pipefail

TOOLPACK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT_SCRIPT="$TOOLPACK_ROOT/scripts/norrin_context.py"
CONTEXT_WORKSPACE=""
CONTEXT_TARGET=""
CONTEXT_PROJECT_ROOT=""
CONTEXT_ARGS=()

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "• $*"; }
pass() { echo "PASS  $*"; }
warn() { echo "WARN  $*"; }
fail() { echo "FAIL  $*"; FAILURES=$((FAILURES+1)); }
FAILURES=0

strip_cr() { tr -d '\r'; }

parse_context_args() {
  CONTEXT_ARGS=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --workspace|-w)
        [ "$#" -ge 2 ] || die "$1 requires a logical ws_<name>"
        CONTEXT_WORKSPACE="$2"; shift 2 ;;
      --target|-t)
        [ "$#" -ge 2 ] || die "$1 requires a target profile"
        CONTEXT_TARGET="$2"; shift 2 ;;
      --project-root)
        [ "$#" -ge 2 ] || die "$1 requires a directory"
        CONTEXT_PROJECT_ROOT="$2"; shift 2 ;;
      *)
        CONTEXT_ARGS+=("$1"); shift ;;
    esac
  done
}

resolve_context() {
  local args=(resolve --format shell)
  [ -n "$CONTEXT_WORKSPACE" ] && args+=(--workspace "$CONTEXT_WORKSPACE")
  [ -n "$CONTEXT_TARGET" ] && args+=(--target "$CONTEXT_TARGET")
  [ -n "$CONTEXT_PROJECT_ROOT" ] && args+=(--project-root "$CONTEXT_PROJECT_ROOT")
  local resolved
  resolved=$(python3 "$CONTEXT_SCRIPT" "${args[@]}") || exit 1
  eval "$resolved"
  REPO_ROOT="$PROJECT_ROOT"
  WORKSPACE_PATH="/$WORKSPACE_NAME.Workspace"
  mkdir -p "$SCRATCH_DIR"
}

# fab api wrapper: fab_api <endpoint> [fab api args...]  -> stdout without CR
fab_api() { fab api "$@" 2>/dev/null | strip_cr; }

# JMESPath on fab api: fab_api_q <query> <endpoint> [args...]
fab_api_q() { local q="$1"; shift; fab api "$@" -q "$q" 2>/dev/null | strip_cr | sed 's/^"//;s/"$//'; }

need_target() {
  resolve_context
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
