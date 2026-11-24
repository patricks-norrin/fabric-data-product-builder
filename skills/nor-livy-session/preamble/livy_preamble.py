# Livy preamble — executed once per session by livy_session.py (never part of a notebook).
# 1) shim: currentWorkspaceName is None in Livy for notebooks and lakehouse_toolbelt.
import json, os, sys, types
import notebookutils

WORKSPACE_NAME = "__WORKSPACE_NAME__"
_original_notebookutils = notebookutils
_ctx = dict(_original_notebookutils.runtime.context)
_ctx["currentWorkspaceName"] = _ctx.get("currentWorkspaceName") or WORKSPACE_NAME

class _Runtime:
    context = _ctx

    def __getattr__(self, name):
        return getattr(_original_notebookutils.runtime, name)

class _NotebookutilsShim(types.ModuleType):
    def __getattr__(self, name):
        return getattr(_original_notebookutils, name)

_shim = _NotebookutilsShim("notebookutils")
_shim.runtime = _Runtime()
sys.modules["notebookutils"] = _shim
notebookutils = _shim
_report = {"workspace_name": _ctx["currentWorkspaceName"], "workspace_id": _ctx.get("currentWorkspaceId"),
           "spark": spark.version, "AZURE_SERVICE": "AZURE_SERVICE" in os.environ}
try:  # assertion-style: does this session have a delegated OneLake identity?
    notebookutils.fs.ls("Files"); _report["onelake_access"] = True
except Exception as e:
    _report["onelake_access"] = f"FAILED: {str(e).splitlines()[0][:120]}"
def _install_toolbelt():
    """Resolve the minimum runtime requirement without upgrading a compatible installation."""
    import subprocess, sys
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-index", "-f", "https://nrnctopublishpip.z6.web.core.windows.net/pip/",
        "lakehouse-toolbelt>=1.0.7",
    ], check=True)
    import importlib
    importlib.invalidate_caches()

try:
    _install_toolbelt()
    import lakehouse_toolbelt
    # Internal module names vary across toolbelt versions; patch whichever exist, skip the rest.
    import importlib
    _submodule_names = [
        "_env_helper", "_data_product_class", "_configuration_helpers", "_dataset_class",
        "_source_configuration_class", "_publish_configuration_class",
    ]
    _patched, _missing = [], []
    for _name in _submodule_names:
        try:
            _m = importlib.import_module(f"lakehouse_toolbelt.{_name}")
        except ModuleNotFoundError:
            _missing.append(_name)
            continue
        if hasattr(_m, "notebookutils"):
            _m.notebookutils = _shim
        _patched.append(_name)
    from importlib.metadata import version
    _report["lakehouse_toolbelt"] = version("lakehouse-toolbelt")
    if _missing:
        _report["lakehouse_toolbelt_missing_submodules"] = _missing
except Exception as e:
    _report["lakehouse_toolbelt"] = f"IMPORT FAILED: {e!r}"
    print("PREAMBLE " + json.dumps(_report))
    raise
print("PREAMBLE " + json.dumps(_report))
