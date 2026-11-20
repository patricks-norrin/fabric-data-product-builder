#!/usr/bin/env python3
"""Resolve the consuming project, logical workspace package, and Fabric target."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


TOOLPACK_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKSPACE_PATTERN = re.compile(r"^ws_[a-z0-9]+(?:_[a-z0-9]+)*$")
TEMPLATE_TARGET_FILE = TOOLPACK_ROOT / "templates/project/configuration/fabric_targets.json"


@dataclass(frozen=True)
class ProjectContext:
    toolpack_root: pathlib.Path
    project_root: pathlib.Path
    target_file: pathlib.Path
    target_profile: str
    workspace_key: str
    workspace_dir: pathlib.Path
    scratch_dir: pathlib.Path
    workspace_name: str
    environment_name: str
    environment_id: str
    environment_workspace_id: str


def find_project_root(start: pathlib.Path | None = None) -> pathlib.Path:
    current = (start or pathlib.Path.cwd()).resolve()
    result = subprocess.run(
        ["git", "-C", str(current), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return pathlib.Path(result.stdout.strip()).resolve()
    return current


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"missing project target configuration: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"target configuration must be a JSON object: {path}")
    return value


def resolve_context(
    *,
    start: pathlib.Path | None = None,
    project_root: pathlib.Path | None = None,
    workspace: str | None = None,
    target: str | None = None,
) -> ProjectContext:
    root = (project_root or find_project_root(start)).resolve()
    target_file = root / "configuration" / "fabric_targets.json"
    if not target_file.exists():
        raise ValueError(
            f"missing project target configuration: {target_file}; ask the user which physical "
            "Fabric workspace to target and verify it before writing anything, then create the "
            f"file from the installed toolpack template at {TEMPLATE_TARGET_FILE}. Never invent "
            "a workspace name or an Environment GUID"
        )
    config = _load_json(target_file)

    target_profile = target or os.environ.get("NORRIN_TARGET") or config.get("active_target")
    workspace_key = workspace or os.environ.get("NORRIN_WORKSPACE") or config.get("default_workspace")
    if not isinstance(target_profile, str) or not target_profile:
        raise ValueError(f"{target_file}: active_target is required")
    if not isinstance(workspace_key, str) or not WORKSPACE_PATTERN.fullmatch(workspace_key):
        raise ValueError(
            f"{target_file}: logical workspace must match ws_<name>; got {workspace_key!r}"
        )

    targets = config.get("targets")
    if not isinstance(targets, dict) or target_profile not in targets:
        available = ", ".join(sorted(targets)) if isinstance(targets, dict) else "none"
        raise ValueError(
            f"{target_file}: target {target_profile!r} not found (available: {available})"
        )
    profile = targets[target_profile]
    workspaces = profile.get("workspaces") if isinstance(profile, dict) else None
    if not isinstance(workspaces, dict) or workspace_key not in workspaces:
        available = ", ".join(sorted(workspaces)) if isinstance(workspaces, dict) else "none"
        raise ValueError(
            f"{target_file}: workspace {workspace_key!r} is not mapped in target "
            f"{target_profile!r} (available: {available})"
        )
    workspace_config = workspaces[workspace_key]
    if not isinstance(workspace_config, dict):
        raise ValueError(
            f"{target_file}: targets.{target_profile}.workspaces.{workspace_key} must be an object"
        )

    workspace_name = workspace_config.get("workspace_name")
    if not isinstance(workspace_name, str) or not workspace_name:
        raise ValueError(
            f"{target_file}: targets.{target_profile}.workspaces.{workspace_key}.workspace_name "
            "is required"
        )
    environment = workspace_config.get("environment") or {}
    if not isinstance(environment, dict):
        raise ValueError(
            f"{target_file}: targets.{target_profile}.workspaces.{workspace_key}.environment "
            "must be an object"
        )

    return ProjectContext(
        toolpack_root=TOOLPACK_ROOT,
        project_root=root,
        target_file=target_file,
        target_profile=target_profile,
        workspace_key=workspace_key,
        workspace_dir=root / workspace_key,
        scratch_dir=root / ".scratch" / workspace_key,
        workspace_name=workspace_name,
        environment_name=str(environment.get("name", "")),
        environment_id=str(environment.get("id", "")),
        environment_workspace_id=str(environment.get("workspace_id", "")),
    )


def _as_dict(context: ProjectContext) -> dict[str, str]:
    return {
        "TOOLPACK_ROOT": str(context.toolpack_root),
        "PROJECT_ROOT": str(context.project_root),
        "TARGET_FILE": str(context.target_file),
        "TARGET_PROFILE": context.target_profile,
        "WORKSPACE_KEY": context.workspace_key,
        "WORKSPACE_DIR": str(context.workspace_dir),
        "SCRATCH_DIR": str(context.scratch_dir),
        "WORKSPACE_NAME": context.workspace_name,
        "ENVIRONMENT_NAME": context.environment_name,
        "ENVIRONMENT_ID": context.environment_id,
        "ENVIRONMENT_WORKSPACE_ID": context.environment_workspace_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["resolve"])
    parser.add_argument("--workspace")
    parser.add_argument("--target")
    parser.add_argument("--project-root", type=pathlib.Path)
    parser.add_argument("--format", choices=["json", "shell"], default="json")
    args = parser.parse_args()

    try:
        context = resolve_context(
            project_root=args.project_root,
            workspace=args.workspace,
            target=args.target,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    values = _as_dict(context)
    if args.format == "shell":
        for key, value in values.items():
            print(f"{key}={shlex.quote(value)}")
    else:
        print(json.dumps(values, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
