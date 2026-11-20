#!/usr/bin/env python3
"""Validate and push a data product configuration, then provision its folder and lakehouse.

Usage: push_data_product_config.py <data_product_identifier> [--no-provision] [--workspace ws_name] [--target profile]
Creates lh_workspace_shared_resources at the workspace root when it is missing. Idempotent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
sys.path.insert(0, str(HERE))

from fab_cli import (  # noqa: E402
    CliError, context_arguments, context_from, exists, fab, guarded, item_id, onelake_mkdir_p, wait_for,
    workspace_id, workspace_path,
)
from validate_data_product_config import main as validate  # noqa: E402

CONFIG_DIR = "configuration/data_product"


def push(local: Path, lakehouse: str, relative_dir: str) -> str:
    onelake_mkdir_p(lakehouse, relative_dir)
    fab("cp", str(local), f"{lakehouse}/{relative_dir}/", "-f")
    remote = f"{lakehouse}/{relative_dir}/{local.name}"
    if not exists(remote):
        raise CliError(f"{remote} not found after cp")
    print(f"PASS  pushed {remote}")
    return remote


def main() -> int:
    parser = context_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("data_product_identifier")
    parser.add_argument("--no-provision", action="store_true")
    args = parser.parse_args()
    product = args.data_product_identifier
    context = context_from(args)
    config = context.project_root / CONFIG_DIR / product / f"{product}.json"
    project_config = context.project_root / CONFIG_DIR / "project_configuration" / "project_configuration.json"
    if not config.is_file():
        raise CliError(f"missing {config}")
    if validate(str(config), str(context.project_root)):
        raise CliError("config invalid")

    workspace = workspace_id(context.workspace_name)
    root = workspace_path(context)
    shared = f"{root}/lh_workspace_shared_resources.Lakehouse"
    if not exists(shared):
        print("• creating lh_workspace_shared_resources at workspace root")
        fab("mkdir", shared, "-P", "enableSchemas=true")
        wait_for(lambda: exists(shared), "lh_workspace_shared_resources")

    push(config, shared, f"Files/{CONFIG_DIR}/{product}")
    if project_config.is_file():
        push(project_config, shared, f"Files/{CONFIG_DIR}/project_configuration")

    if args.no_provision:
        return 0
    folder = f"{root}/{product}.Folder"
    if exists(folder):
        print(f"PASS  folder {product} exists")
    else:
        fab("mkdir", folder)
        print(f"PASS  folder {product} created")
    lakehouse = f"lh_{product}"
    lakehouse_id = item_id(workspace, lakehouse, "Lakehouse")
    if lakehouse_id:
        print(f"PASS  lakehouse {lakehouse} exists ({lakehouse_id})")
    else:
        fab("mkdir", f"{folder}/{lakehouse}.Lakehouse", "-P", "enableSchemas=true")
        lakehouse_id = wait_for(lambda: item_id(workspace, lakehouse, "Lakehouse"), lakehouse)
        print(f"PASS  lakehouse {lakehouse} created in folder {product} ({lakehouse_id})")
    if exists(f"{root}/{lakehouse}.Lakehouse/Tables/dbo"):
        print(f"PASS  {lakehouse} schema-enabled")
    else:
        print(f"WARN  {lakehouse}: Tables/dbo not visible yet (schema enablement pending?)")
    print(f"LAKEHOUSE_ID={lakehouse_id}")
    print(f"WORKSPACE_ID={workspace}")
    return 0


if __name__ == "__main__":
    guarded(main)
