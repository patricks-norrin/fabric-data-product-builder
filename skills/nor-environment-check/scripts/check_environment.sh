#!/usr/bin/env bash
# Read-only environment check. Usage: check_environment.sh [data_product_identifier] [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
VERSION_HELPER="$TOOLPACK_ROOT/scripts/cli_version.py"
MIN_FAB="1.7.0"
MIN_AZ="2.50.0"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
DP="${1:-}"

PASSES=()
BLOCKERS=()
ACKNOWLEDGMENTS=()
RECOMMENDATIONS=()
SKIPPED=()
pass() { PASSES+=("$*"); }
fail() { BLOCKERS+=("$*"); FAILURES=$((FAILURES+1)); }
acknowledge() { ACKNOWLEDGMENTS+=("$*"); }
warn() { RECOMMENDATIONS+=("$*"); }
skip() { SKIPPED+=("$*"); }

print_list() {
  local heading="$1"; shift
  [ "$#" -eq 0 ] && return
  printf '\n%s\n' "$heading"
  printf -- '- %s\n' "$@"
}

finish() {
  local action_count=$(( ${#BLOCKERS[@]} + ${#ACKNOWLEDGMENTS[@]} + ${#RECOMMENDATIONS[@]} ))
  if [ "$action_count" -eq 0 ]; then
    echo "PASS  preflight complete (${#PASSES[@]} checks)"
  else
    echo "== preflight requires review"
    print_list "BLOCKERS" "${BLOCKERS[@]}"
    print_list "ACKNOWLEDGMENTS" "${ACKNOWLEDGMENTS[@]}"
    print_list "RECOMMENDATIONS" "${RECOMMENDATIONS[@]}"
    print_list "SKIPPED" "${SKIPPED[@]}"
    print_list "PASSED" "${PASSES[@]}"
    printf '\n== result: %d blocker(s), %d acknowledgment(s), %d recommendation(s)\n' \
      "${#BLOCKERS[@]}" "${#ACKNOWLEDGMENTS[@]}" "${#RECOMMENDATIONS[@]}"
  fi
  [ "${#BLOCKERS[@]}" -eq 0 ]
}

require_cli() {
  local label="$1" min="$2" cmd="$3"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    fail "$label: '$cmd' not on PATH (need >= $min)"
    return 1
  fi
  local ver
  ver=$("$cmd" --version 2>&1 | python3 "$VERSION_HELPER" extract "$label") || ver=""
  if [ -z "$ver" ]; then
    fail "$label: could not parse '$cmd --version' (need >= $min)"
    return 1
  fi
  if python3 "$VERSION_HELPER" at_least "$min" "$ver"; then
    pass "$label: $ver (>= $min)"
    return 0
  fi
  fail "$label: $ver < $min (upgrade the CLI; do not copy or patch toolpack scripts)"
  return 1
}

FAB_READY=0
AZ_READY=0
require_cli fab "$MIN_FAB" fab && FAB_READY=1
require_cli az "$MIN_AZ" az && AZ_READY=1

# Capture stdout+stderr; ignore fab's exit code (pipefail would treat a logged-in
# non-zero as failure). Never print Token lines — `fab auth status` includes them.
AUTH_READY=0
if [ "$FAB_READY" -eq 1 ]; then
  AUTH=$(set +o pipefail; fab auth status 2>&1 | strip_cr)
  if printf '%s\n' "$AUTH" | python3 "$VERSION_HELPER" fab_logged_in; then
    pass "auth: $(printf '%s\n' "$AUTH" | grep -E '^(Account|Tenant ID):' | tr '\n' ' ')"
    AUTH_READY=1
  else
    fail "auth: not logged in (fab auth login --tenant <id>)"
  fi
else
  skip "Fabric authentication: fab CLI unavailable"
fi

CONTEXT_READY=0
CONTEXT_ARGS=(resolve --format shell)
[ -n "$CONTEXT_WORKSPACE" ] && CONTEXT_ARGS+=(--workspace "$CONTEXT_WORKSPACE")
[ -n "$CONTEXT_TARGET" ] && CONTEXT_ARGS+=(--target "$CONTEXT_TARGET")
[ -n "$CONTEXT_PROJECT_ROOT" ] && CONTEXT_ARGS+=(--project-root "$CONTEXT_PROJECT_ROOT")
if RESOLVED_CONTEXT=$(python3 "$CONTEXT_SCRIPT" "${CONTEXT_ARGS[@]}" 2>&1); then
  eval "$RESOLVED_CONTEXT"
  REPO_ROOT="$PROJECT_ROOT"
  WORKSPACE_PATH="/$WORKSPACE_NAME.Workspace"
  mkdir -p "$SCRATCH_DIR"
  CONTEXT_READY=1
else
  fail "project target configuration: $RESOLVED_CONTEXT"
fi

if [ "$CONTEXT_READY" -eq 1 ]; then
  LOCAL_PROBE=""
  if [ ! -r "$REPO_ROOT" ] || [ ! -w "$REPO_ROOT" ] || [ ! -x "$REPO_ROOT" ]; then
    fail "local workspace: cannot read or create files in $REPO_ROOT"
  elif [ ! -r "$TARGET_FILE" ] || [ ! -w "$TARGET_FILE" ]; then
    fail "local workspace: target configuration $TARGET_FILE is not readable and writable"
  elif LOCAL_PROBE=$(mktemp "$REPO_ROOT/.norrin-preflight.XXXXXX" 2>/dev/null) \
    && printf 'created\nmodified\n' > "$LOCAL_PROBE" \
    && rm -f "$LOCAL_PROBE"; then
    pass "local workspace: read/create/modify/delete probe passed"
  else
    [ -n "$LOCAL_PROBE" ] && rm -f "$LOCAL_PROBE"
    fail "local workspace: create/modify/delete probe failed in $REPO_ROOT"
  fi
fi

WORKSPACE_READY=0
if [ "$AUTH_READY" -eq 1 ] && [ "$CONTEXT_READY" -eq 1 ]; then
  WORKSPACE_ID=$(fab get "$WORKSPACE_PATH" -q id 2>/dev/null | strip_cr | tr -d '" ')
  if [[ "$WORKSPACE_ID" =~ ^[0-9a-f-]{36}$ ]]; then
    pass "workspace: $WORKSPACE_NAME ($WORKSPACE_ID)"
    WORKSPACE_READY=1
  else
    fail "workspace '$WORKSPACE_NAME' not found or inaccessible"
  fi
else
  skip "Workspace, capacity, Spark, shared resources, Environment, Livy, and product checks: Fabric authentication or project target unavailable"
fi

if [ "$WORKSPACE_READY" -eq 1 ]; then
  CAP_ID=$(fab_api_q "text.capacityId" "workspaces/$WORKSPACE_ID")
  CAP_JSON=$(fab_api "capacities" -q "text.value[?id=='$CAP_ID'] | [0]")
  CAP_STATE=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('state',''))" 2>/dev/null)
  CAP_SKU=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('sku',''))" 2>/dev/null)
  CAP_NAME=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('displayName',''))" 2>/dev/null)
  if [ "$CAP_STATE" = "Active" ]; then pass "capacity: $CAP_NAME $CAP_SKU Active"; else fail "capacity: $CAP_NAME $CAP_SKU state='$CAP_STATE'"; fi
  POOL=$(fab_api_q "text.pool.defaultPool.name" "workspaces/$WORKSPACE_ID/spark/settings")
  RUNTIME=$(fab_api_q "text.environment.runtimeVersion" "workspaces/$WORKSPACE_ID/spark/settings")
  case "$CAP_SKU" in
    F2|F4)
      [ "$POOL" = "Starter Pool" ] && warn "pool: '$POOL' on $CAP_SKU exceeds capacity (set a Small custom pool as default or scale to F8)" || pass "pool: $POOL on $CAP_SKU"
      acknowledge "capacity $CAP_SKU is below the F8 this workflow is verified on: acknowledge continuing with possible Spark queueing/failure, or scale to F8"
      ;;
    *) pass "pool: $POOL (runtime $RUNTIME) on $CAP_SKU";;
  esac

  SHARED_ID=$(item_id lh_workspace_shared_resources Lakehouse)
  SHARED_PATH="$WORKSPACE_PATH/lh_workspace_shared_resources.Lakehouse"
  if [ -n "$SHARED_ID" ]; then
    pass "lh_workspace_shared_resources ($SHARED_ID)"
  else
    CREATE_OUTPUT=$(fab mkdir "$SHARED_PATH" -P enableSchemas=true 2>&1 | strip_cr)
    if [ "$?" -ne 0 ]; then
      fail "could not create lh_workspace_shared_resources: $CREATE_OUTPUT"
    fi
    for i in $(seq 1 12); do
      SHARED_ID=$(item_id lh_workspace_shared_resources Lakehouse)
      [ -n "$SHARED_ID" ] && break
      sleep 5
    done
    if [ -n "$SHARED_ID" ]; then pass "lh_workspace_shared_resources created ($SHARED_ID)"; else fail "lh_workspace_shared_resources was not visible after creation"; fi
  fi
  if [ -n "$SHARED_ID" ]; then
    if fab exists "$SHARED_PATH/Files/configuration/data_product/project_configuration/project_configuration.json" 2>/dev/null | strip_cr | grep -qi true; then pass "project_configuration.json present"; else warn "project_configuration.json missing (push with nor-data-product-config if configs use extra source attributes)"; fi
  fi

  if [ -n "$ENVIRONMENT_ID" ]; then
    ENV_CAP=$(fab_api_q "text.capacityId" "workspaces/$ENVIRONMENT_WORKSPACE_ID")
    [ "$ENV_CAP" = "$CAP_ID" ] && pass "environment workspace on same capacity" || fail "environment workspace capacity $ENV_CAP != $CAP_ID"
    WHEELS=$(fab_api_q "text.customLibraries.wheelFiles | join(',', @)" "workspaces/$ENVIRONMENT_WORKSPACE_ID/environments/$ENVIRONMENT_ID/libraries")
    case "$WHEELS" in *lakehouse_toolbelt*) pass "environment $ENVIRONMENT_NAME publishes $WHEELS";; *) fail "environment $ENVIRONMENT_NAME: no lakehouse_toolbelt wheel (got '$WHEELS')";; esac
    VER=$(echo "$WHEELS" | grep -o 'lakehouse_toolbelt-[0-9.]*[0-9]' | head -1 | sed 's/lakehouse_toolbelt-//')
    python3 -c "import sys; v=tuple(int(x) for x in '$VER'.split('.')); sys.exit(0 if v>=(1,0,7) else 1)" 2>/dev/null && pass "toolbelt wheel $VER >= 1.0.7 (project_configuration support)" || fail "toolbelt wheel '$VER' < 1.0.7: configs with extra source_configuration attributes will fail (SourceConfiguration/filter_string bug)"
    [ "$ENVIRONMENT_WORKSPACE_ID" = "$WORKSPACE_ID" ] && pass "environment lives in the target workspace" || fail "environment is in another workspace: Spark session acquisition fails for notebooks and Livy (copy it with fab cp)"
  else
    warn "no environment configured for $WORKSPACE_KEY; notebooks will install lakehouse_toolbelt from shared resources"
  fi

  if [ -n "$SHARED_ID" ]; then
    LIVY=$(fab_api "workspaces/$WORKSPACE_ID/lakehouses/$SHARED_ID/livyapi/versions/2023-12-01/sessions" -q "text.pageSize")
    [[ "$LIVY" =~ ^[0-9]+$ ]] && pass "livy: sessions endpoint reachable" || fail "livy: endpoint not reachable (tenant setting or capacity)"
  else
    skip "Livy API: shared lakehouse unavailable"
  fi

  if [ -n "$DP" ]; then
    LH_ID=$(item_id "lh_$DP" Lakehouse)
    if [ -n "$LH_ID" ]; then
      pass "lh_$DP ($LH_ID)"
      fab exists "$WORKSPACE_PATH/lh_$DP.Lakehouse/Tables/dbo" 2>/dev/null | strip_cr | grep -qi true && pass "lh_$DP is schema-enabled" || fail "lh_$DP is not schema-enabled (Tables/dbo missing)"
    else fail "lh_$DP missing (provision with nor-data-product-config)"; fi
    fab exists "$SHARED_PATH/Files/configuration/data_product/$DP/$DP.json" 2>/dev/null | strip_cr | grep -qi true && pass "config $DP.json present in shared resources" || fail "config $DP.json missing in shared resources"
    FOLDER_ID=$(fab_api_q "text.value[?displayName=='$DP'].id | [0]" "workspaces/$WORKSPACE_ID/folders" | sed 's/^None$//')
    [ -n "$FOLDER_ID" ] && pass "folder $DP ($FOLDER_ID)" || warn "folder $DP missing"
  fi
fi

if [ "$AZ_READY" -eq 1 ]; then
  if az account get-access-token --resource https://api.fabric.microsoft.com --query expiresOn -o tsv >/dev/null 2>&1; then
    pass "az token for api.fabric.microsoft.com available"
  else
    warn "no az token: Livy dev loop unavailable until 'az login --tenant <id> --allow-no-subscriptions --use-device-code'"
  fi
else
  skip "Azure CLI token: az CLI unavailable"
fi

finish
