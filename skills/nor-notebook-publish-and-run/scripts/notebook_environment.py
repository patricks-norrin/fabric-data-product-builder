#!/usr/bin/env python3
"""Resolve a notebook's Git-sync Environment binding for `fab import`.

Git integration writes `dependencies.environment` with an all-zero `workspaceId` and the Environment's
`logicalId` as `environmentId`. Only Git sync translates that form; `fab import` uploads it unchanged and the
notebook then fails with InvalidEnvironmentArtifact. `ref` names the Environment to look up in the target
workspace, `resolve` writes a copy of the notebook bound to the target Environment id.
"""
import argparse
import json
import pathlib
import shutil
import sys

CONTENT = "notebook-content.py"
GIT_SYNC_WORKSPACE = "00000000-0000-0000-0000-000000000000"
META = "# META"


def is_meta(line: str) -> bool:
    return line == META or line.startswith(META + " ")


def header(text: str) -> tuple[int, int, dict]:
    """Return start/end line indexes and the parsed first METADATA block."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if is_meta(line)), None)
    if start is None:
        return 0, 0, {}
    end = start
    while end < len(lines) and is_meta(lines[end]):
        end += 1
    return start, end, json.loads("\n".join(line[len(META):] for line in lines[start:end]))


def binding(notebook_dir: pathlib.Path) -> dict:
    return header((notebook_dir / CONTENT).read_text(encoding="utf-8"))[2].get("dependencies", {}).get("environment") or {}


def environment_names(workspace_dir: pathlib.Path) -> dict[str, str]:
    names = {}
    for platform in workspace_dir.rglob("*.Environment/.platform"):
        data = json.loads(platform.read_text(encoding="utf-8"))
        logical_id = data.get("config", {}).get("logicalId")
        if logical_id:
            names[logical_id] = data.get("metadata", {}).get("displayName") or platform.parent.name.removesuffix(".Environment")
    return names


def ref(notebook_dir: pathlib.Path, workspace_dir: pathlib.Path) -> str:
    environment = binding(notebook_dir)
    if environment.get("workspaceId") != GIT_SYNC_WORKSPACE:
        return ""
    logical_id = environment.get("environmentId", "")
    name = environment_names(workspace_dir).get(logical_id)
    if not name:
        sys.exit(f"{notebook_dir.name} binds Environment logicalId {logical_id!r} (Git-sync form), but no "
                 f"*.Environment/.platform under {workspace_dir} has that logicalId")
    return name


def resolve(notebook_dir: pathlib.Path, out_dir: pathlib.Path, environment_id: str, workspace_id: str) -> None:
    text = (notebook_dir / CONTENT).read_text(encoding="utf-8")
    start, end, metadata = header(text)
    metadata["dependencies"]["environment"] = {"environmentId": environment_id, "workspaceId": workspace_id}
    lines = text.splitlines()
    block = [f"{META} {line}" for line in json.dumps(metadata, indent=2).splitlines()]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(notebook_dir, out_dir, ignore=shutil.ignore_patterns("__pycache__"))
    with open(out_dir / CONTENT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines[:start] + block + lines[end:]) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    ref_parser = commands.add_parser("ref")
    ref_parser.add_argument("notebook_dir", type=pathlib.Path)
    ref_parser.add_argument("workspace_dir", type=pathlib.Path)
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("notebook_dir", type=pathlib.Path)
    resolve_parser.add_argument("out_dir", type=pathlib.Path)
    resolve_parser.add_argument("--environment-id", required=True)
    resolve_parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args()
    if args.command == "ref":
        print(ref(args.notebook_dir, args.workspace_dir))
    else:
        resolve(args.notebook_dir, args.out_dir, args.environment_id, args.workspace_id)


if __name__ == "__main__":
    main()
