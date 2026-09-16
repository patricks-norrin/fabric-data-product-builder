#!/usr/bin/env python3
"""Render nb_extract_<id> / nb_cdc_<id> from templates.
Usage: render_notebook.py extract|cdc <data_product_identifier> [--force] [--workspace ws_name] [--target profile]
Resolves workspace, lakehouse and environment ids with fab; writes into the selected ws_<name> package."""
import argparse, json, pathlib, subprocess, sys, re, uuid

HERE = pathlib.Path(__file__).resolve().parent
TOOLPACK_ROOT = HERE.parents[2]
sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))
from norrin_context import resolve_context

TPL = HERE.parent / "templates"

def fab_q(query, *args):
    out = subprocess.run(["fab", *args, "-q", query], capture_output=True, text=True).stdout
    return out.replace("\r", "").strip().strip('"')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("extract", "cdc"))
    parser.add_argument("data_product_identifier")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workspace")
    parser.add_argument("--target")
    parser.add_argument("--project-root", type=pathlib.Path)
    args = parser.parse_args()
    kind, dpid, force = args.kind, args.data_product_identifier, args.force
    context = resolve_context(
        project_root=args.project_root,
        workspace=args.workspace,
        target=args.target,
    )
    cfg = json.load(open(context.project_root / f"configuration/data_product/{dpid}/{dpid}.json"))
    ws_id = fab_q("id", "get", f"{context.workspace_name}.Workspace")
    lh_id = fab_q(f"text.value[?displayName=='lh_{dpid}'].id | [0]", "api", f"workspaces/{ws_id}/items", "-P", "type=Lakehouse")
    if not re.match(r"^[0-9a-f-]{36}$", lh_id): sys.exit(f"lakehouse lh_{dpid} not found in {context.workspace_name} (run nor-data-product-config first)")
    name = f"nb_{kind}_{dpid}"
    logical_id = uuid.uuid5(
        uuid.UUID("c4f81ac2-0cf0-4a55-b272-e863f04ac868"),
        f"{context.workspace_key}/{dpid}/{name}.Notebook",
    )
    values = {"DATA_PRODUCT_IDENTIFIER": dpid, "WORKSPACE_ID": ws_id, "LAKEHOUSE_ID": lh_id,
              "ENVIRONMENT_ID": context.environment_id, "ENVIRONMENT_WORKSPACE_ID": context.environment_workspace_id,
              "LOGICAL_ID": str(logical_id)}
    out_dir = context.workspace_dir / dpid / f"{name}.Notebook"
    if out_dir.exists() and not force: sys.exit(f"{out_dir} exists (use --force to overwrite; source-specific cells would be lost)")
    out_dir.mkdir(parents=True, exist_ok=True)
    content = (TPL / f"nb_{kind}.Notebook/notebook-content.py").read_text()
    if kind == "extract":
        cell_tpl = (TPL / "nb_extract.Notebook/source_specific_cell.py").read_text()
        cells = []
        for ds in cfg["datasets"]:
            src = ds.get("source_configuration", {}) or {}
            cells.append(cell_tpl.replace("{{DATASET_NAME}}", ds["dataset_name"]).replace("{{BASE_URL}}", src.get("base_url", ""))
                         .replace("{{RELATIVE_URL_TEMPLATE}}", src.get("relative_url_template", "")).replace("{{NOTES}}", src.get("notes", "")))
        content = content.replace("{{SOURCE_SPECIFIC_CELLS}}\n", "".join(cells))
    for k, v in values.items(): content = content.replace("{{" + k + "}}", v)
    (out_dir / "notebook-content.py").write_text(content)
    platform = (TPL / "platform.json").read_text()
    for key, value in values.items(): platform = platform.replace("{{" + key + "}}", value)
    (out_dir / ".platform").write_text(platform)
    print(f"rendered {out_dir} (workspace {ws_id}, lakehouse {lh_id}, environment {context.environment_id or '-'})")
    if kind == "extract": print("next: implement the '# --- SOURCE SPECIFIC' cells, then run them with nor-livy-session")

if __name__ == "__main__": main()
