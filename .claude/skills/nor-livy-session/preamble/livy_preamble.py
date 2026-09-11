# Livy preamble — executed once per session by livy_session.sh (never part of a notebook).
# 1) shim: lakehouse_toolbelt reads notebookutils.runtime.context["currentWorkspaceName"], which is None in Livy.
import json, os
import notebookutils

WORKSPACE_NAME = "__WORKSPACE_NAME__"
_ctx = dict(notebookutils.runtime.context)
_ctx["currentWorkspaceName"] = _ctx.get("currentWorkspaceName") or WORKSPACE_NAME

class _Runtime:
    context = _ctx

class _NotebookutilsShim:
    runtime = _Runtime
    def __getattr__(self, name):
        return getattr(notebookutils, name)

_shim = _NotebookutilsShim()
_report = {"workspace_name": _ctx["currentWorkspaceName"], "workspace_id": _ctx.get("currentWorkspaceId"),
           "spark": spark.version, "AZURE_SERVICE": "AZURE_SERVICE" in os.environ}
def _install_toolbelt_from_shared_resources():
    """Fallback when no Environment is attached: install the wheel staged in lh_workspace_shared_resources/Files/libraries."""
    import subprocess, sys
    libraries = f"abfss://{_ctx['currentWorkspaceName']}@onelake.dfs.fabric.microsoft.com/lh_workspace_shared_resources.Lakehouse/Files/libraries"
    wheels = [f for f in notebookutils.fs.ls(libraries) if f.name.startswith("lakehouse_toolbelt") and f.name.endswith(".whl")]
    if not wheels:
        raise RuntimeError(f"no lakehouse_toolbelt wheel under {libraries}")
    local = f"/tmp/{wheels[-1].name}"
    notebookutils.fs.cp(wheels[-1].path, f"file:{local}")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", local], check=True)
    return wheels[-1].name

try:
    try:
        import lakehouse_toolbelt
    except ImportError:
        _report["wheel_installed"] = _install_toolbelt_from_shared_resources()
        import lakehouse_toolbelt
    import lakehouse_toolbelt._env_helper as _env
    import lakehouse_toolbelt._data_product_class as _dpc
    import lakehouse_toolbelt._configuration_helpers as _cfg
    import lakehouse_toolbelt._dataset_class as _ds
    import lakehouse_toolbelt._source_configuration_class as _src
    import lakehouse_toolbelt._publish_configuration_class as _pub
    for _m in (_env, _dpc, _cfg, _ds, _src, _pub):
        if hasattr(_m, "notebookutils"):
            _m.notebookutils = _shim
    _report["lakehouse_toolbelt"] = getattr(lakehouse_toolbelt, "__version__", "imported")
except Exception as e:  # environment not attached or wheel missing
    _report["lakehouse_toolbelt"] = f"IMPORT FAILED: {e!r}"
print("PREAMBLE " + json.dumps(_report))
