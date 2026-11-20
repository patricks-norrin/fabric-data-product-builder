#!/usr/bin/env python3
"""Read-only preflight of the local CLIs and the target Fabric workspace.

Usage: check_environment.py [data_product_identifier] [--workspace ws_name] [--target profile] [--project-root dir]
Prints one summary line when everything passes, otherwise one consolidated report. Exit 1 only on blockers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "scripts"))

from cli_version import at_least, extract_version  # noqa: E402
from fab_cli import CliError, api, context_arguments, context_from, exists, guarded, item_id, run, workspace_id, workspace_path  # noqa: E402

MIN_CLI = {"fab": "1.9.0", "az": "2.50.0"}
SHARED = "lh_workspace_shared_resources"
LIVY_API = "livyapi/versions/2023-12-01/sessions"


class Report:
    def __init__(self) -> None:
        self.sections: dict[str, list[str]] = {
            "BLOCKERS": [], "ACKNOWLEDGMENTS": [], "RECOMMENDATIONS": [], "SKIPPED": [], "PASSED": [],
        }

    def add(self, section: str, message: str) -> None:
        self.sections[section].append(message)

    def finish(self) -> int:
        blockers = self.sections["BLOCKERS"]
        actions = blockers + self.sections["ACKNOWLEDGMENTS"] + self.sections["RECOMMENDATIONS"]
        if not actions:
            print(f"PASS  preflight complete ({len(self.sections['PASSED'])} checks)")
            return 0
        print("== preflight requires review")
        for heading, messages in self.sections.items():
            if messages:
                print(f"\n{heading}")
                print("\n".join(f"- {message}" for message in messages))
        print(
            f"\n== result: {len(blockers)} blocker(s), {len(self.sections['ACKNOWLEDGMENTS'])} acknowledgment(s), "
            f"{len(self.sections['RECOMMENDATIONS'])} recommendation(s)"
        )
        return 1 if blockers else 0


def check_cli(report: Report, tool: str) -> bool:
    minimum = MIN_CLI[tool]
    try:
        output = run(tool, "--version")
    except CliError:
        report.add("BLOCKERS", f"{tool}: not on PATH (need >= {minimum})")
        return False
    version = extract_version(output.stdout + output.stderr, tool)
    if not version:
        report.add("BLOCKERS", f"{tool}: could not parse '{tool} --version' (need >= {minimum})")
        return False
    if not at_least(version, minimum):
        report.add("BLOCKERS", f"{tool}: {version} < {minimum} (upgrade the CLI; do not copy or patch toolpack scripts)")
        return False
    report.add("PASSED", f"{tool}: {version} (>= {minimum})")
    return True


def check_capacity(report: Report, workspace: str) -> str:
    capacity_id = api(f"workspaces/{workspace}").get("capacityId", "")
    capacities = api("capacities").get("value", [])
    capacity = next((item for item in capacities if item.get("id") == capacity_id), {})
    name, sku, state = capacity.get("displayName", ""), capacity.get("sku", ""), capacity.get("state", "")
    if state == "Active":
        report.add("PASSED", f"capacity: {name} {sku} Active")
    else:
        report.add("BLOCKERS", f"capacity: {name} {sku} state='{state}' (resume it; the agent never starts capacities)")
    settings = api(f"workspaces/{workspace}/spark/settings")
    pool = (settings.get("pool") or {}).get("defaultPool", {}).get("name", "")
    runtime = (settings.get("environment") or {}).get("runtimeVersion", "")
    if sku in ("F2", "F4"):
        if pool == "Starter Pool":
            report.add("RECOMMENDATIONS", f"pool: '{pool}' on {sku} exceeds capacity (set a Small custom pool as default or scale to F8)")
        else:
            report.add("PASSED", f"pool: {pool} on {sku}")
        report.add("ACKNOWLEDGMENTS", f"capacity {sku} is below the F8 this workflow is verified on: acknowledge continuing with possible Spark queueing/failure, or scale to F8")
    else:
        report.add("PASSED", f"pool: {pool} (runtime {runtime}) on {sku}")
    check_workspace_settings(report, settings)
    return capacity_id


def check_workspace_settings(report: Report, settings: dict) -> None:
    rules = json.loads((HERE.parent / "recommended_workspace_settings.json").read_text(encoding="utf-8"))
    show = lambda value: {True: "On", False: "Off"}.get(value, "unknown" if value is None else value)  # noqa: E731
    for rule in rules:
        value = settings
        for key in rule["setting"].split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value == rule["recommended"]:
            report.add("PASSED", f"workspace setting: {rule['label']}: {show(value)}")
        else:
            report.add("RECOMMENDATIONS", (
                f"workspace setting: {rule['label']} is {show(value)}, recommended {show(rule['recommended'])}"
                f"\n    How: {rule['click']}\n    Why: {rule['why']}"
            ))


def check_fabric(report: Report, context, product: str) -> None:
    workspace = workspace_id(context.workspace_name)
    report.add("PASSED", f"auth and workspace: {context.workspace_name} ({workspace})")
    capacity_id = check_capacity(report, workspace)
    root = workspace_path(context)

    shared_id = item_id(workspace, SHARED, "Lakehouse")
    if shared_id:
        report.add("PASSED", f"{SHARED} ({shared_id})")
    else:
        report.add("RECOMMENDATIONS", f"{SHARED} is missing; nor-data-product-config creates it at the workspace root when it pushes the first configuration")

    if context.environment_id:
        environment_capacity = api(f"workspaces/{context.environment_workspace_id}").get("capacityId", "")
        if environment_capacity == capacity_id:
            report.add("PASSED", "environment workspace on same capacity")
        else:
            report.add("BLOCKERS", f"environment workspace capacity {environment_capacity} != {capacity_id}")
        if context.environment_workspace_id == workspace:
            report.add("PASSED", "environment lives in the target workspace")
        else:
            report.add("BLOCKERS", "environment is in another workspace: Spark session acquisition fails for notebooks and Livy (copy it with fab cp)")
    else:
        report.add("PASSED", f"no Environment configured for {context.workspace_key} (optional)")

    product_id = item_id(workspace, f"lh_{product}", "Lakehouse") if product else None
    livy_lakehouse = shared_id or product_id
    if livy_lakehouse:
        try:
            api(f"workspaces/{workspace}/lakehouses/{livy_lakehouse}/{LIVY_API}")
            report.add("PASSED", "livy: sessions endpoint reachable")
        except CliError as exc:
            report.add("BLOCKERS", f"livy: endpoint not reachable (tenant setting or capacity): {exc}")
    else:
        report.add("SKIPPED", "Livy API: no lakehouse in the workspace yet")

    if product:
        if product_id:
            report.add("PASSED", f"lh_{product} ({product_id})")
            if exists(f"{root}/lh_{product}.Lakehouse/Tables/dbo"):
                report.add("PASSED", f"lh_{product} is schema-enabled")
            else:
                report.add("BLOCKERS", f"lh_{product} is not schema-enabled (Tables/dbo missing)")
        else:
            report.add("BLOCKERS", f"lh_{product} missing (provision with nor-data-product-config)")
        config = f"{root}/{SHARED}.Lakehouse/Files/configuration/data_product/{product}/{product}.json"
        if shared_id and exists(config):
            report.add("PASSED", f"config {product}.json present in shared resources")
        else:
            report.add("BLOCKERS", f"config {product}.json missing in shared resources (push with nor-data-product-config)")
        folders = api(f"workspaces/{workspace}/folders").get("value", [])
        folder_id = next((folder["id"] for folder in folders if folder.get("displayName") == product), None)
        if folder_id:
            report.add("PASSED", f"folder {product} ({folder_id})")
        else:
            report.add("RECOMMENDATIONS", f"folder {product} missing (provision with nor-data-product-config)")


def main() -> int:
    parser = context_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("data_product_identifier", nargs="?", default="")
    args = parser.parse_args()
    report = Report()
    fab_ready = check_cli(report, "fab")
    az_ready = check_cli(report, "az")

    context = None
    try:
        context = context_from(args)
    except ValueError as exc:
        report.add("BLOCKERS", f"project target configuration: {exc}")

    if fab_ready and context:
        try:
            check_fabric(report, context, args.data_product_identifier)
        except CliError as exc:
            report.add("BLOCKERS", f"Fabric: {exc} (if not signed in: fab auth login --tenant <id>)")
    else:
        report.add("SKIPPED", "Fabric checks: fab CLI or project target unavailable")

    if az_ready:
        token = run("az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com",
                    "--query", "expiresOn", "-o", "tsv")
        if token.returncode == 0:
            report.add("PASSED", "az token for api.fabric.microsoft.com available")
        else:
            report.add("RECOMMENDATIONS", "no az token: Livy dev loop unavailable until 'az login --tenant <id> --allow-no-subscriptions --use-device-code'")
    else:
        report.add("SKIPPED", "Azure CLI token: az CLI unavailable")
    return report.finish()


if __name__ == "__main__":
    guarded(main)
