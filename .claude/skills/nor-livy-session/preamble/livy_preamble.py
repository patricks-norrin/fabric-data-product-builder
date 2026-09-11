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
try:
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
