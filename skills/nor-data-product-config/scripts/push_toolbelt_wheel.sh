#!/usr/bin/env bash
# Upload a lakehouse_toolbelt wheel to shared OneLake libraries.
# Usage: push_toolbelt_wheel.sh /path/to/lakehouse_toolbelt-1.0.7-py3-none-any.whl [--workspace ws_name] [--target profile]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLPACK_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$TOOLPACK_ROOT/scripts/fab_common.sh"
parse_context_args "$@"; set -- "${CONTEXT_ARGS[@]}"
WHEEL="${1:?wheel path required}"; shift
[ -f "$WHEEL" ] || die "wheel not found: $WHEEL"
case "$(basename "$WHEEL")" in
  lakehouse_toolbelt-[1-9]*.whl|lakehouse_toolbelt-1.[0-9]*.whl|lakehouse_toolbelt-1.0.[7-9]*.whl) ;;
  *) die "expected lakehouse_toolbelt wheel version >= 1.0.7: $(basename "$WHEEL")" ;;
esac
need_target
SHARED="$WORKSPACE_PATH/lh_workspace_shared_resources.Lakehouse"
if ! fab exists "$SHARED" 2>/dev/null | strip_cr | grep -qi true; then
  fab mkdir "$SHARED" -P enableSchemas=true >/dev/null 2>&1 || die "mkdir shared lakehouse failed"
fi
onelake_mkdir_p "$SHARED" "Files/libraries"
fab cp "$WHEEL" "$SHARED/Files/libraries/" -f >/dev/null 2>&1 || die "wheel upload failed"
NAME="$(basename "$WHEEL")"
fab exists "$SHARED/Files/libraries/$NAME" 2>/dev/null | strip_cr | grep -qi true || die "wheel not found after upload"
pass "wheel: $SHARED/Files/libraries/$NAME"
