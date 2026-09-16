#!/usr/bin/env bash
# Read-only environment check. Usage: check_environment.sh [data_product_identifier] [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
DP="${1:-}"

echo "== fab"
if fab auth status 2>/dev/null | strip_cr | grep -q "Logged In: True"; then pass "auth: $(fab auth status 2>/dev/null | strip_cr | grep -E 'Account|Tenant' | tr '\n' ' ')"; else fail "auth: not logged in (fab auth login --tenant <id>)"; exit 1; fi
need_target
pass "workspace: $WORKSPACE_NAME ($WORKSPACE_ID)"

echo "== capacity and Spark"
CAP_ID=$(fab_api_q "text.capacityId" "workspaces/$WORKSPACE_ID")
CAP_JSON=$(fab_api "capacities" -q "text.value[?id=='$CAP_ID'] | [0]")
CAP_STATE=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('state',''))" 2>/dev/null)
CAP_SKU=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('sku',''))" 2>/dev/null)
CAP_NAME=$(echo "$CAP_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin) or {};print(d.get('displayName',''))" 2>/dev/null)
if [ "$CAP_STATE" = "Active" ]; then pass "capacity: $CAP_NAME $CAP_SKU Active"; else fail "capacity: $CAP_NAME $CAP_SKU state='$CAP_STATE'"; fi
POOL=$(fab_api_q "text.pool.defaultPool.name" "workspaces/$WORKSPACE_ID/spark/settings")
RUNTIME=$(fab_api_q "text.environment.runtimeVersion" "workspaces/$WORKSPACE_ID/spark/settings")
case "$CAP_SKU" in F2|F4) [ "$POOL" = "Starter Pool" ] && warn "pool: '$POOL' on $CAP_SKU exceeds capacity (needs Small custom pool as default)" || pass "pool: $POOL on $CAP_SKU";; *) pass "pool: $POOL (runtime $RUNTIME) on $CAP_SKU";; esac

echo "== shared resources"
SHARED_ID=$(item_id lh_workspace_shared_resources Lakehouse)
if [ -n "$SHARED_ID" ]; then pass "lh_workspace_shared_resources ($SHARED_ID)"; else fail "lh_workspace_shared_resources missing"; fi
SHARED_PATH="$WORKSPACE_PATH/lh_workspace_shared_resources.Lakehouse"
if [ -n "$SHARED_ID" ]; then
  if fab exists "$SHARED_PATH/Files/configuration/data_product/project_configuration/project_configuration.json" 2>/dev/null | strip_cr | grep -qi true; then pass "project_configuration.json present"; else warn "project_configuration.json missing (push with nor-data-product-config if configs use extra source attributes)"; fi
fi

echo "== environment (lakehouse_toolbelt)"
if [ -n "$ENVIRONMENT_ID" ]; then
  ENV_CAP=$(fab_api_q "text.capacityId" "workspaces/$ENVIRONMENT_WORKSPACE_ID")
  [ "$ENV_CAP" = "$CAP_ID" ] && pass "environment workspace on same capacity" || fail "environment workspace capacity $ENV_CAP != $CAP_ID"
  WHEELS=$(fab_api_q "text.customLibraries.wheelFiles | join(',', @)" "workspaces/$ENVIRONMENT_WORKSPACE_ID/environments/$ENVIRONMENT_ID/libraries")
  case "$WHEELS" in *lakehouse_toolbelt*) pass "environment $ENVIRONMENT_NAME publishes $WHEELS";; *) fail "environment $ENVIRONMENT_NAME: no lakehouse_toolbelt wheel (got '$WHEELS')";; esac
  VER=$(echo "$WHEELS" | grep -o 'lakehouse_toolbelt-[0-9.]*[0-9]' | head -1 | sed 's/lakehouse_toolbelt-//')
  python3 -c "import sys; v=tuple(int(x) for x in '$VER'.split('.')); sys.exit(0 if v>=(1,0,7) else 1)" 2>/dev/null && pass "toolbelt wheel $VER >= 1.0.7 (project_configuration support)" || fail "toolbelt wheel '$VER' < 1.0.7: configs with extra source_configuration attributes will fail (SourceConfiguration/filter_string bug)"
  [ "$ENVIRONMENT_WORKSPACE_ID" = "$WORKSPACE_ID" ] && pass "environment lives in the target workspace" || fail "environment is in another workspace: Spark session acquisition fails for notebooks and Livy (copy it with fab cp)"
else fail "no environment configured for $WORKSPACE_KEY in $TARGET_FILE"; fi

echo "== Azure CLI token (Livy Spark sessions)"
if az account get-access-token --resource https://api.fabric.microsoft.com --query expiresOn -o tsv >/dev/null 2>&1; then pass "az token for api.fabric.microsoft.com available"; else warn "no az token: Livy dev loop unavailable until 'az login --tenant <id> --allow-no-subscriptions --use-device-code'"; fi
echo "== Livy API"
if [ -n "$SHARED_ID" ]; then
  LIVY=$(fab_api "workspaces/$WORKSPACE_ID/lakehouses/$SHARED_ID/livyapi/versions/2023-12-01/sessions" -q "text.pageSize")
  [[ "$LIVY" =~ ^[0-9]+$ ]] && pass "livy: sessions endpoint reachable" || fail "livy: endpoint not reachable (tenant setting or capacity)"
fi

if [ -n "$DP" ]; then
  echo "== data product $DP"
  LH_ID=$(item_id "lh_$DP" Lakehouse)
  if [ -n "$LH_ID" ]; then
    pass "lh_$DP ($LH_ID)"
    fab exists "$WORKSPACE_PATH/lh_$DP.Lakehouse/Tables/dbo" 2>/dev/null | strip_cr | grep -qi true && pass "lh_$DP is schema-enabled" || fail "lh_$DP is not schema-enabled (Tables/dbo missing)"
  else fail "lh_$DP missing (provision with nor-data-product-config)"; fi
  fab exists "$SHARED_PATH/Files/configuration/data_product/$DP/$DP.json" 2>/dev/null | strip_cr | grep -qi true && pass "config $DP.json present in shared resources" || fail "config $DP.json missing in shared resources"
  FOLDER_ID=$(fab_api_q "text.value[?displayName=='$DP'].id | [0]" "workspaces/$WORKSPACE_ID/folders" | sed 's/^None$//')
  [ -n "$FOLDER_ID" ] && pass "folder $DP ($FOLDER_ID)" || warn "folder $DP missing"
fi

echo "== result: $FAILURES failure(s)"; [ "$FAILURES" -eq 0 ]
