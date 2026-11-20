#!/usr/bin/env python3
"""Publish, run and monitor a data product notebook (nb_*) or pipeline (pl_*) in Fabric.

Usage:
  run_notebook_job.py publish|export|runs <data_product_identifier> <item name>
  run_notebook_job.py run|start <data_product_identifier> <item name> [-P|-C|-i fab job args] [--timeout s] [--poll s]
  run_notebook_job.py wait <data_product_identifier> <item name> [--job-id id] [--timeout s] [--poll s]
  run_notebook_job.py status
All commands accept --workspace ws_name, --target profile and --project-root dir.
Exit codes: 0 Completed, 1 failed/cancelled or error, 124 still running when --timeout elapsed.
"""

from __future__ import annotations

import argparse
import difflib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLPACK_ROOT = HERE.parents[2]
sys.path.insert(0, str(TOOLPACK_ROOT / "scripts"))
sys.path.insert(0, str(HERE))

from fab_cli import (  # noqa: E402
    CliError, context_arguments, context_from, exists, fab, fab_data, guarded, item_id, run, wait_for,
    workspace_id, workspace_path,
)
from notebook_environment import ref as environment_ref, resolve as bind_environment  # noqa: E402
from run_manifest import append_event, latest_jobs  # noqa: E402

PIPELINE_PY = TOOLPACK_ROOT / "skills" / "nor-pipeline-author" / "scripts" / "pipeline_definition.py"
TERMINAL = {"Completed", "Failed", "Cancelled", "Deduped"}
TIMEOUT_EXIT = 124


def now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def job_fields(job: dict) -> dict:
    failure = job.get("failureReason") or {}
    failure = failure.get("message") if isinstance(failure, dict) else failure
    return {
        "id": job.get("id") or "", "status": job.get("status") or "",
        "start": job.get("startTimeUtc") or "", "end": job.get("endTimeUtc") or "",
        "failure": " ".join(str(failure or "").split()),
    }


def job_status(item: str, job_id: str) -> dict:
    job = fab_data("job", "run-status", item, "--id", job_id)
    if not isinstance(job, dict) or not job.get("status"):
        raise CliError(f"no status returned for job {job_id}")
    return job_fields(job)


class Job:
    def __init__(self, context, product: str, name: str) -> None:
        self.context = context
        self.product = product
        self.name = name
        self.type = "DataPipeline" if name.startswith("pl_") else "Notebook"
        self.local = context.workspace_dir / product / f"{name}.{self.type}"
        self.folder = f"{workspace_path(context)}/{product}.Folder"
        self.item = f"{self.folder}/{name}.{self.type}"
        self.workspace_id = workspace_id(context.workspace_name)

    def record(self, event: str, **fields: object) -> None:
        record(self.context, event, item=self.item, notebook=self.name, **fields)

    def publish(self) -> int:
        content = "pipeline-content.json" if self.type == "DataPipeline" else "notebook-content.py"
        if not (self.local / content).is_file():
            hint = " (render it with nor-pipeline-author)" if self.type == "DataPipeline" else ""
            raise CliError(f"missing {self.local / content}{hint}")
        if not exists(self.folder):
            raise CliError(f"folder {self.product} missing (run nor-data-product-config)")
        if self.type == "DataPipeline":
            self.publish_pipeline()
        else:
            self.publish_notebook()
        published = wait_for(lambda: item_id(self.workspace_id, self.name, self.type), f"{self.name}")
        print(f"PASS  published {self.name} ({published}) in folder {self.product}")
        return 0

    def publish_pipeline(self) -> None:
        config = self.context.scratch_dir / "publish" / self.product / f"{self.name}.deploy.yml"
        checked = subprocess.run([
            sys.executable, str(PIPELINE_PY), "deploy-config", str(self.local), str(config),
            "--workspace-dir", str(self.context.workspace_dir), "--workspace-id", self.workspace_id,
        ], capture_output=True, text=True)
        if checked.returncode:
            raise CliError(f"invalid {self.name} definition:\n{(checked.stdout + checked.stderr).strip()}")
        fab("deploy", "--config", str(config), "-f")

    def publish_notebook(self) -> None:
        """A Git-sync Environment binding is rebound to the same-named Environment in the target workspace."""
        source = self.local
        environment = environment_ref(self.local, self.context.workspace_dir)
        if environment:
            environment_id = item_id(self.workspace_id, environment, "Environment")
            if not environment_id:
                raise CliError(f"{self.name} binds Environment {environment}, which is not in "
                               f"{self.context.workspace_name}; create it first")
            source = self.context.scratch_dir / "publish" / self.product / f"{self.name}.Notebook"
            bind_environment(self.local, source, environment_id, self.workspace_id)
            print(f"• bound {self.name} to Environment {environment} ({environment_id})")
        fab("import", self.item, "-i", str(source), "--format", ".py", "-f")

    def start(self, fab_args: list[str]) -> str:
        self.record("job_requested", data_product=self.product)
        print(f"• [{now()}] starting {self.name} in {self.context.workspace_name}", flush=True)
        job = fab_data("job", "start", self.item, *fab_args)
        job_id = job_fields(job)["id"] if isinstance(job, dict) else ""
        if not job_id:
            raise CliError(f"fab job start returned no job instance id for {self.name}: {job!r}")
        self.record("job_started", job_id=job_id, data_product=self.product, workspace=self.context.workspace_name)
        print(f"PASS  started {self.name} (job {job_id})")
        return job_id

    def wait(self, job_id: str, timeout: int, poll: int) -> int:
        started, last, errors = time.monotonic(), "", 0
        print(f"• waiting for {self.name} (job {job_id}): polling every {poll}s, timeout {timeout}s", flush=True)
        while True:
            elapsed = int(time.monotonic() - started)
            try:
                job = job_status(self.item, job_id)
            except CliError as exc:
                errors += 1
                print(f"WARN  [{now()}] {self.name} status unreadable ({errors}/5): {exc}", flush=True)
                if errors >= 5:
                    raise CliError(f"could not read status of job {job_id} five times in a row") from None
            else:
                errors = 0
                print(f"[{now()}] {self.name} {job['status']} {elapsed}s (job {job_id})", flush=True)
                if job["status"] != last:
                    last = job["status"]
                    self.record("job_status", job_id=job_id, status=last)
                if last in TERMINAL:
                    return self.finish(job_id, job)
            if elapsed >= timeout:
                self.record("job_wait_timeout", job_id=job_id, status=last, waited_s=elapsed)
                print(f"WARN  {self.name} still {last or 'unknown'} after {elapsed}s; the Fabric job keeps running. "
                      f"Resume with: wait {self.product} {self.name} --job-id {job_id}")
                return TIMEOUT_EXIT
            time.sleep(poll)

    def finish(self, job_id: str, job: dict) -> int:
        self.record("job_finished", job_id=job_id, data_product=self.product, status=job["status"],
                    start_utc=job["start"], end_utc=job["end"], failure_reason=job["failure"])
        span = f"job {job_id}, {job['start']} -> {job['end']}"
        if job["status"] == "Completed":
            print(f"PASS  {self.name} Completed ({span})")
            return 0
        print(f"FAIL  {self.name} {job['status']} ({span})")
        if job["failure"]:
            print(f"failureReason: {job['failure']}")
        if self.type == "DataPipeline":
            print(f"next: load nor-spark-diagnostics for pipeline {self.item}, workspace {self.workspace_id}, "
                  f"job instance {job_id} before changing or rerunning it")
        else:
            print(f"next: load nor-spark-diagnostics with job instance {job_id} before changing or rerunning {self.name}")
        return 1

    def export(self) -> int:
        if self.type != "Notebook":
            raise CliError("export compares notebooks only")
        out = self.context.scratch_dir / "export" / self.product
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        fab("export", self.item, "-o", str(out), "--format", ".py", "-f")
        read = lambda path: [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]  # noqa: E731
        diff = list(difflib.unified_diff(
            read(self.local / "notebook-content.py"), read(out / f"{self.name}.Notebook" / "notebook-content.py"),
            "local", "remote", lineterm="",
        ))
        if diff:
            print("\n".join(diff))
            print("WARN  remote differs from local (see above)")
        else:
            print("PASS  remote definition identical to local")
        return 0


def record(context, event: str, **fields: object) -> None:
    append_event(context.scratch_dir / "operational_manifest.jsonl", event,
                 [f"{key}={value}" for key, value in fields.items()])


def status(context) -> int:
    jobs = latest_jobs(context.scratch_dir / "operational_manifest.jsonl")
    if not jobs:
        print(f"• no jobs recorded in {context.scratch_dir / 'operational_manifest.jsonl'}")
        return 0
    row = "{:<32} {:<11} {:<28} {:<28} {}"
    print(row.format("notebook", "status", "start_utc", "end_utc", "job_id"))
    for item, entry in jobs.items():
        name = item.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        try:
            job = job_status(item, entry["job_id"])
        except CliError:
            print(row.format(name, "unreadable", "-", "-", entry["job_id"]))
            continue
        print(row.format(name, job["status"], job["start"] or "-", job["end"] or "-", entry["job_id"]))
        if job["failure"]:
            print(f"  failureReason: {job['failure']}")
    return 0


PASSTHROUGH = ("-P", "--params", "-C", "--config", "-i", "--input")


def split_fab_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """Separate `fab job start` options (forwarded unchanged) from this script's own arguments."""
    own, forwarded, index = [], [], 0
    while index < len(argv):
        if argv[index] in PASSTHROUGH and index + 1 < len(argv):
            forwarded += argv[index:index + 2]
            index += 2
        else:
            own.append(argv[index])
            index += 1
    return own, forwarded


def main() -> int:
    parser = context_arguments(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("command", choices=("publish", "run", "start", "wait", "status", "export", "runs"))
    parser.add_argument("data_product_identifier", nargs="?")
    parser.add_argument("item", nargs="?", help="nb_* notebook or pl_* pipeline name")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--poll", "--polling_interval", type=int, default=30)
    parser.add_argument("--job-id")
    own, fab_args = split_fab_args(sys.argv[1:])
    args = parser.parse_args(own)
    if args.timeout < 0 or args.poll <= 0:
        parser.error("--timeout and --poll must be positive integers")
    context = context_from(args)
    if args.command == "status":
        return status(context)
    if not args.data_product_identifier or not args.item:
        parser.error(f"{args.command} requires <data_product_identifier> <item name>")
    if fab_args and args.command not in ("run", "start"):
        parser.error(f"{' '.join(fab_args)} applies only to run/start")
    job = Job(context, args.data_product_identifier, args.item)
    if args.command == "publish":
        return job.publish()
    if args.command == "export":
        return job.export()
    if args.command == "runs":
        listed = run("fab", "job", "run-list", job.item)
        print((listed.stdout + listed.stderr).strip())
        return listed.returncode
    if args.command == "start":
        job_id = job.start(fab_args)
        print(f"next: wait {job.product} {job.name} --job-id {job_id}   |   status")
        return 0
    if args.command == "run":
        return job.wait(job.start(fab_args), args.timeout, args.poll)
    job_id = args.job_id or latest_jobs(context.scratch_dir / "operational_manifest.jsonl").get(job.item, {}).get("job_id")
    if not job_id:
        raise CliError(f"no job recorded for {job.name}; pass --job-id (see: runs {job.product} {job.name})")
    return job.wait(job_id, args.timeout, args.poll)


if __name__ == "__main__":
    guarded(main)
