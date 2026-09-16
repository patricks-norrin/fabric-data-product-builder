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
try:  # assertion-style: does this session have a delegated OneLake identity?
    notebookutils.fs.ls("Files"); _report["onelake_access"] = True
except Exception as e:
    _report["onelake_access"] = f"FAILED: {str(e).splitlines()[0][:120]}"
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
    try:
        import subprocess as _sp
        _pip_version = _sp.run(["pip", "show", "lakehouse-toolbelt"], capture_output=True, text=True).stdout
        _version = next((l.split(":", 1)[1].strip() for l in _pip_version.splitlines() if l.startswith("Version:")), "unknown")
    except Exception:
        _version = getattr(lakehouse_toolbelt, "__version__", "imported")
    _report["lakehouse_toolbelt"] = _version
    if _missing:
        _report["lakehouse_toolbelt_missing_submodules"] = _missing
except Exception as e:  # environment not attached or wheel missing
    _report["lakehouse_toolbelt"] = f"IMPORT FAILED: {e!r}"
print("PREAMBLE " + json.dumps(_report))
