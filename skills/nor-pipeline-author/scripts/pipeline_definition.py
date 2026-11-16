#!/usr/bin/env python3
"""Render and check native Fabric pipelines; configure publishing through fab deploy.

Usage:
  pipeline_definition.py render source <data_product_identifier> [--force] [--workspace ws_name] [--target profile]
  pipeline_definition.py check <pipeline dir>
    pipeline_definition.py deploy-config <pipeline dir> <output.yml> --workspace-dir <dir> --workspace-id <id>
"""
import argparse
import json
import pathlib
import re
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
TOOLPACK_ROOT = HERE.parents[2]
TEMPLATES = HERE.parent / "templates"
CONTENT = "pipeline-content.json"


def render(kind: str, dpid: str, force: bool, workspace: str | None, target: str | None,
           project_root: pathlib.Path | None) -> pathlib.Path:
    sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))
    from norrin_context import resolve_context

    context = resolve_context(project_root=project_root, workspace=workspace, target=target)
    name = f"pl_{dpid}"
    out_dir = context.workspace_dir / dpid / f"{name}.DataPipeline"
    if out_dir.exists() and not force:
        sys.exit(f"{out_dir} exists (use --force to overwrite)")
    logical_id = uuid.uuid5(uuid.UUID("c4f81ac2-0cf0-4a55-b272-e863f04ac868"),
                            f"{context.workspace_key}/{dpid}/{name}.DataPipeline")
    values = {"DATA_PRODUCT_IDENTIFIER": dpid, "PIPELINE_NAME": name, "LOGICAL_ID": str(logical_id)}
    for role in ("extract", "cdc"):
        notebook = context.workspace_dir / dpid / f"nb_{role}_{dpid}.Notebook" / ".platform"
        try:
            values[f"{role.upper()}_NOTEBOOK_LOGICAL_ID"] = json.loads(notebook.read_text(encoding="utf-8"))["config"]["logicalId"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            sys.exit(f"render the notebooks first; cannot read {notebook}: {exc}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for source, target_name in ((TEMPLATES / f"pl_{kind}.DataPipeline" / CONTENT, CONTENT),
                                (TEMPLATES / "platform.json", ".platform")):
        text = source.read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        with open(out_dir / target_name, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return out_dir


def load(pipeline_dir: pathlib.Path) -> dict:
    return json.loads((pipeline_dir / CONTENT).read_text(encoding="utf-8"))


def deploy_config(pipeline_dir: pathlib.Path, output: pathlib.Path, workspace_dir: pathlib.Path,
                  workspace_id: str) -> None:
    config = {
        "core": {"workspace_id": workspace_id, "repository_directory": str(workspace_dir.resolve()),
                 "item_types_in_scope": ["Notebook", "DataPipeline"]},
        "publish": {"exclude_regex": f"^(?!{re.escape(pipeline_dir.stem)}$)"},
        "unpublish": {"skip": True},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(config, indent=2) + "\n")


def check(pipeline_dir: pathlib.Path) -> list[str]:
    """Structural problems only: shape, unique activity names, dependsOn targets, reference syntax."""
    try:
        definition = load(pipeline_dir)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{CONTENT}: {exc}"]
    activities = definition.get("properties", {}).get("activities")
    if not isinstance(activities, list) or not activities:
        return ["properties.activities must be a non-empty list"]
    errors, names = [], [activity.get("name") for activity in activities]
    for name in {name for name in names if names.count(name) > 1}:
        errors.append(f"duplicate activity name: {name}")
    for activity in activities:
        if not activity.get("name") or not activity.get("type"):
            errors.append(f"activity without name or type: {json.dumps(activity)[:80]}")
        for dependency in activity.get("dependsOn", []):
            if dependency.get("activity") not in names:
                errors.append(f"{activity.get('name')}: dependsOn unknown activity {dependency.get('activity')!r}")
            if not dependency.get("dependencyConditions"):
                errors.append(f"{activity.get('name')}: dependsOn {dependency.get('activity')!r} has no dependencyConditions")
    leftover = re.findall(r"\{\{[^{}]*\}\}", json.dumps(definition))
    errors += [f"unresolved placeholder {placeholder}; use native Fabric logical IDs" for placeholder in sorted(set(leftover))]
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("kind", choices=("source",))
    render_parser.add_argument("data_product_identifier")
    render_parser.add_argument("--force", action="store_true")
    render_parser.add_argument("--workspace")
    render_parser.add_argument("--target")
    render_parser.add_argument("--project-root", type=pathlib.Path)
    commands.add_parser("check").add_argument("pipeline_dir", type=pathlib.Path)
    deploy_parser = commands.add_parser("deploy-config")
    deploy_parser.add_argument("pipeline_dir", type=pathlib.Path)
    deploy_parser.add_argument("output", type=pathlib.Path)
    deploy_parser.add_argument("--workspace-dir", type=pathlib.Path, required=True)
    deploy_parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args()

    if args.command == "render":
        out_dir = render(args.kind, args.data_product_identifier, args.force, args.workspace, args.target,
                         args.project_root)
        errors = check(out_dir)
        print(f"rendered {out_dir}")
    elif args.command == "check":
        errors = check(args.pipeline_dir)
        if not errors:
            print(f"PASS  {args.pipeline_dir}")
    else:
        errors = check(args.pipeline_dir)
        if not errors:
            deploy_config(args.pipeline_dir, args.output, args.workspace_dir, args.workspace_id)
    for error in errors:
        print(f"ERROR {error}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
