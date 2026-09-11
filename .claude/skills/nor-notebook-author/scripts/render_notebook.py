#!/usr/bin/env python3
"""Render nb_extract_<id> / nb_cdc_<id> from templates.
Usage: render_notebook.py extract|cdc <data_product_identifier> [--force]
Resolves workspace, lakehouse and environment ids with fab; writes notebooks/<id>/nb_<kind>_<id>.Notebook/."""
import json, pathlib, subprocess, sys, re

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
TPL = HERE.parent / "templates"

def fab_q(query, *args):
    out = subprocess.run(["fab", *args, "-q", query], capture_output=True, text=True).stdout
    return out.replace("\r", "").strip().strip('"')

def main():
    kind, dpid = sys.argv[1], sys.argv[2]; force = "--force" in sys.argv
    assert kind in ("extract", "cdc")
    cfg = json.load(open(REPO / f"configuration/data_product/{dpid}/{dpid}.json"))
    target = json.load(open(REPO / "configuration/target_workspace.json"))
    ws_id = fab_q("id", "get", f"{target['workspace_name']}.Workspace")
    lh_id = fab_q(f"text.value[?displayName=='lh_{dpid}'].id | [0]", "api", f"workspaces/{ws_id}/items", "-P", "type=Lakehouse")
    if not re.match(r"^[0-9a-f-]{36}$", lh_id): sys.exit(f"lakehouse lh_{dpid} not found in {target['workspace_name']} (run nor-data-product-config first)")
    env = target.get("environment", {})
    values = {"DATA_PRODUCT_IDENTIFIER": dpid, "WORKSPACE_ID": ws_id, "LAKEHOUSE_ID": lh_id,
              "ENVIRONMENT_ID": env.get("id", ""), "ENVIRONMENT_WORKSPACE_ID": env.get("workspace_id", "")}
    name = f"nb_{kind}_{dpid}"
    out_dir = REPO / "notebooks" / dpid / f"{name}.Notebook"
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
    (out_dir / ".platform").write_text((TPL / "platform.json").read_text().replace("{{NOTEBOOK_NAME}}", name))
    print(f"rendered {out_dir} (workspace {ws_id}, lakehouse {lh_id}, environment {env.get('id','-')})")
    if kind == "extract": print("next: implement the '# --- SOURCE SPECIFIC' cells, then run them with nor-livy-session")

if __name__ == "__main__": main()
