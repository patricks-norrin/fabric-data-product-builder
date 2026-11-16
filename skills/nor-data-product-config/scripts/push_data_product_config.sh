#!/usr/bin/env bash
# Validate, push config (+ project_configuration.json) to lh_workspace_shared_resources, provision folder + lh_<id>.
# Usage: push_data_product_config.sh <data_product_identifier> [--no-provision] [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]//\\//}")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
DP="${1:?data_product_identifier required}"; PROVISION=1; [ "${2:-}" = "--no-provision" ] && PROVISION=0
resolve_context
CFG="$PROJECT_ROOT/configuration/data_product/$DP/$DP.json"; PROJ="$PROJECT_ROOT/configuration/data_product/project_configuration/project_configuration.json"
[ -f "$CFG" ] || die "missing $CFG"
(cd "$PROJECT_ROOT" && python3 "$SCRIPT_DIR/validate_data_product_config.py" "$CFG") || die "config invalid"
need_target
SHARED="$WORKSPACE_PATH/lh_workspace_shared_resources.Lakehouse"
if ! fab exists "$SHARED" 2>/dev/null | strip_cr | grep -qi true; then
  info "creating lh_workspace_shared_resources at workspace root"
  CREATE_OUTPUT=$(fab mkdir "$SHARED" -P enableSchemas=true 2>&1 | strip_cr)
  [ "$?" -eq 0 ] || die "mkdir shared lakehouse failed: $CREATE_OUTPUT"
  for i in $(seq 1 12); do
    fab exists "$SHARED" 2>/dev/null | strip_cr | grep -qi true && break
    sleep 5
  done
fi
fab exists "$SHARED" 2>/dev/null | strip_cr | grep -qi true || die "lh_workspace_shared_resources was not visible after creation"

info "pushing configuration"
onelake_mkdir_p "$SHARED" "Files/configuration/data_product/$DP"
fab cp "$CFG" "$SHARED/Files/configuration/data_product/$DP/" -f >/dev/null 2>&1 || die "cp config failed"
fab exists "$SHARED/Files/configuration/data_product/$DP/$DP.json" 2>/dev/null | strip_cr | grep -qi true || die "config not found after cp"
pass "config: $SHARED/Files/configuration/data_product/$DP/$DP.json"
if [ -f "$PROJ" ]; then
  onelake_mkdir_p "$SHARED" "Files/configuration/data_product/project_configuration"
  fab cp "$PROJ" "$SHARED/Files/configuration/data_product/project_configuration/" -f >/dev/null 2>&1 || die "cp project_configuration failed"
  pass "project_configuration.json pushed"
fi

if [ "$PROVISION" -eq 1 ]; then
  info "provisioning folder and lakehouse"
  FOLDER="$WORKSPACE_PATH/$DP.Folder"
  if fab exists "$FOLDER" 2>/dev/null | strip_cr | grep -qi true; then pass "folder $DP exists"; else CREATE_OUTPUT=$(fab mkdir "$FOLDER" 2>&1 | strip_cr); [ "$?" -eq 0 ] || die "mkdir folder failed: $CREATE_OUTPUT"; pass "folder $DP created"; fi
  LH_ID=$(item_id "lh_$DP" Lakehouse)
  if [ -n "$LH_ID" ]; then pass "lakehouse lh_$DP exists ($LH_ID)"; else
    CREATE_OUTPUT=$(fab mkdir "$FOLDER/lh_$DP.Lakehouse" -P enableSchemas=true 2>&1 | strip_cr)
    [ "$?" -eq 0 ] || die "mkdir lakehouse failed: $CREATE_OUTPUT"
    for i in $(seq 1 12); do LH_ID=$(item_id "lh_$DP" Lakehouse); [ -n "$LH_ID" ] && break; sleep 5; done
    pass "lakehouse lh_$DP created in folder $DP ($LH_ID)"
  fi
  fab exists "$WORKSPACE_PATH/lh_$DP.Lakehouse/Tables/dbo" 2>/dev/null | strip_cr | grep -qi true && pass "lh_$DP schema-enabled" || warn "lh_$DP: Tables/dbo not visible yet (schema enablement pending?)"
  echo "LAKEHOUSE_ID=$LH_ID"; echo "WORKSPACE_ID=$WORKSPACE_ID"
fi
