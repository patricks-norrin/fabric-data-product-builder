#!/usr/bin/env python3
"""Manage Fabric Livy sessions and execute notebook cells using the standard library."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "scripts"))

import fab_cli
from norrin_context import ProjectContext, resolve_context
from run_manifest import append_event
from notebook_cells import parse as parse_cells
from format_statement_output import format_output


API = "https://api.fabric.microsoft.com/v1"
PREFLIGHT = "Run nor-environment-check with the same project, workspace and target before retrying."


class LivyError(RuntimeError):
    pass


def cli_output(command: str, arguments: list[str]) -> str:
    executable = shutil.which(command)
    if executable is None:
        raise LivyError(f"{command} is not on PATH")
    result = subprocess.run(
        [executable, *arguments], capture_output=True, encoding="utf-8", check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if result.returncode:
        if command == "az":
            raise LivyError(
                "no Azure CLI token: run 'az login --tenant <tenant-id> "
                "--allow-no-subscriptions --use-device-code'"
            )
        reason = result.stderr.strip() or result.stdout.strip()
        raise LivyError(f"{command} failed (exit {result.returncode}): {reason}")
    return result.stdout.strip()


def error_message(response: dict[str, Any], default: str) -> str:
    error = response.get("error")
    nested_message = error.get("message") if isinstance(error, dict) else None
    return str(response.get("message") or nested_message or response.get("errorCode") or default)


class LivySession:
    def __init__(self, context: ProjectContext) -> None:
        self.context = context
        self.directory = context.scratch_dir / "livy"
        self.state_path = self.directory / "livy_session.json"
        self.manifest = context.scratch_dir / "operational_manifest.jsonl"
        self.base = ""
        self.session_id = ""

    def record(self, event: str, **fields: object) -> None:
        append_event(self.manifest, event, [f"{key}={value}" for key, value in fields.items()])

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content = self.request_bytes(method, path, body)
        if not content and method == "DELETE":
            return {}
        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise LivyError(f"Livy {method} returned invalid JSON: {exc}") from None
        if not isinstance(payload, dict):
            raise LivyError(f"Livy {method} returned a non-object response")
        return payload

    def request_bytes(
        self, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> bytes:
        token = cli_output("az", [
            "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com",
            "--query", "accessToken", "-o", "tsv",
        ])
        if not token:
            raise LivyError("Azure CLI returned no access token; run az login for the customer tenant")
        request = Request(
            f"{API}/{path}", method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                content = response.read()
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read())
            except ValueError:
                reason = str(exc.reason)
            else:
                reason = error_message(payload, str(exc.reason)) if isinstance(payload, dict) else str(exc.reason)
            raise LivyError(f"Livy {method} failed (HTTP {exc.code}): {reason}") from None
        except URLError as exc:
            raise LivyError(f"Livy {method} failed: {exc.reason}") from None
        except TimeoutError:
            raise LivyError(f"Livy {method} request timed out") from None
        return content

    def load(self) -> None:
        if not self.state_path.is_file():
            raise LivyError("no session (run: livy_session.py create <lakehouse_name>)")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not all(
            isinstance(state.get(key), str) and state[key] for key in ("base", "session_id")
        ):
            raise LivyError(f"invalid session state: {self.state_path}")
        self.base = state["base"]
        self.session_id = state["session_id"]

    def session_json(self) -> dict[str, Any]:
        return self.request("GET", f"{self.base}/{self.session_id}")

    def wait_idle(self) -> None:
        start = time.monotonic()
        while True:
            response = self.session_json()
            state = response.get("state")
            if not isinstance(state, str):
                reason = error_message(response, "no session state returned")
                self.record("livy_failed", session_id=self.session_id, reason=reason)
                raise LivyError(f"could not read session state: {reason}. {PREFLIGHT}")
            details = response.get("fabricSessionStateInfo") or {}
            inner = details.get("state")
            reason = details.get("errorMessage", "")
            elapsed = int(time.monotonic() - start)
            if inner in ("error", "dead") or state in (
                "dead", "error", "killed", "shutting_down", "success",
            ):
                self.record("livy_failed", session_id=self.session_id, state=inner or state, reason=reason)
                raise LivyError(f"session failed while starting: {reason or state}. {PREFLIGHT}")
            if state == "idle":
                self.record("livy_ready", session_id=self.session_id, duration_seconds=elapsed)
                print(f"session idle after {elapsed}s")
                return
            if elapsed > 900:
                self.record("livy_failed", session_id=self.session_id, state="timeout")
                raise LivyError("timeout waiting for idle")
            print(f"  {elapsed}s {state} {inner or ''}", flush=True)
            time.sleep(10)

    def create(self, lakehouse: str, no_environment: bool = False) -> int:
        workspace_id = fab_cli.workspace_id(self.context.workspace_name)
        lakehouse_id = fab_cli.item_id(workspace_id, lakehouse, "Lakehouse")
        if not lakehouse_id:
            raise LivyError(f"lakehouse {lakehouse} not found in {self.context.workspace_name}")
        self.base = (
            f"workspaces/{workspace_id}/lakehouses/{lakehouse_id}"
            "/livyapi/versions/2023-12-01/sessions"
        )
        environment_id = "" if no_environment else self.context.environment_id
        body: dict[str, Any] = {"name": f"nor-{lakehouse}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"}
        if environment_id:
            body["conf"] = {"spark.fabric.environmentDetails": json.dumps({"id": environment_id})}
        self.record(
            "livy_create_requested", workspace_id=workspace_id, lakehouse_id=lakehouse_id, lakehouse=lakehouse,
        )
        try:
            response = self.request("POST", self.base, body)
            session_id = response.get("id")
            if not isinstance(session_id, str):
                raise LivyError(error_message(response, "no session id returned"))
            try:
                UUID(session_id)
            except ValueError:
                raise LivyError(error_message(response, "invalid session id returned")) from None
        except LivyError as exc:
            self.record(
                "livy_create_failed", workspace_id=workspace_id, lakehouse_id=lakehouse_id, reason=str(exc),
            )
            raise LivyError(f"session create failed: {exc}. {PREFLIGHT}") from None
        self.session_id = session_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({
            "base": self.base, "session_id": self.session_id, "lakehouse": lakehouse,
            "workspace_name": self.context.workspace_name, "environment": environment_id,
        }), encoding="utf-8")
        self.record(
            "livy_created", session_id=self.session_id, workspace_id=workspace_id,
            lakehouse_id=lakehouse_id, environment_id=environment_id,
        )
        environment_name = self.context.environment_name if environment_id else "none"
        print(f"session {self.session_id} on {lakehouse} (environment {environment_name})", flush=True)
        self.wait_idle()
        preamble = (HERE.parent / "preamble/livy_preamble.py").read_text(encoding="utf-8")
        preamble = preamble.replace('"__WORKSPACE_NAME__"', json.dumps(self.context.workspace_name))
        return self.submit("pyspark", preamble)

    def submit(self, kind: str, code: str) -> int:
        path = f"{self.base}/{self.session_id}/statements"
        response = self.request("POST", path, {"kind": kind, "code": code})
        statement_id = response.get("id")
        if isinstance(statement_id, bool) or not isinstance(statement_id, int) or statement_id < 0:
            raise LivyError(f"statement submit failed: {error_message(response, 'no statement id returned')}")
        while True:
            response = self.request("GET", f"{path}/{statement_id}")
            state = response.get("state")
            if state == "available":
                return format_output(response)
            if state in ("error", "cancelled"):
                if (response.get("output") or {}).get("status") == "error":
                    return format_output(response)
                print(f"ERROR statement {statement_id} {state}", file=sys.stderr)
                return 1
            if state not in ("waiting", "running", "cancelling"):
                raise LivyError(f"statement {statement_id} returned unexpected state: {state!r}")
            time.sleep(3)

    def run_cells(self, notebook: Path, selection: str, keep_going: bool) -> int:
        cells = parse_cells(notebook)
        by_index = {cell["index"]: cell for cell in cells}
        indices = (
            [cell["index"] for cell in cells if cell["type"] != "markdown"]
            if selection == "all" else [int(value) for value in selection.split(",")]
        )
        if any(index not in by_index or by_index[index]["type"] == "markdown" for index in indices):
            raise LivyError("selection must contain existing code or parameter cell numbers")
        result = 0
        for index in indices:
            cell = by_index[index]
            print(f"\n=== cell {index} [{cell['type']}/{cell['kind']}] {cell['title']}", flush=True)
            if self.submit(cell["kind"], cell.get("livy_source", cell["source"])):
                result = 1
                if not keep_going:
                    print(f"stopped at cell {index}")
                    break
        self.record(
            "cells_finished", session_id=self.session_id, notebook=notebook,
            selection=selection, status="failed" if result else "completed",
        )
        return result

    def download_log(
        self, notebook_id: str, livy_id: str, app_id: str, file_name: str, size: int, workspace_id: str | None,
    ) -> int:
        """Save the tail of a driver log under .scratch and print only the lines that look like failures."""
        workspace_id = workspace_id or fab_cli.workspace_id(self.context.workspace_name)
        app_path = (f"workspaces/{workspace_id}/notebooks/{notebook_id}/livySessions/{livy_id}"
                    f"/applications/{app_id}/logs")
        meta = self.request("GET", f"{app_path}?{urlencode({'type': 'driver', 'meta': 'true', 'fileName': file_name})}")
        length = (meta.get("containerLogMeta") or {}).get("length")
        if not isinstance(length, int):
            raise LivyError(f"no {file_name} log length returned (monitoring data may have expired): {meta}")
        offset = max(length - size, 0)
        content = self.request_bytes("GET", f"{app_path}?" + urlencode({
            "type": "driver", "fileName": file_name, "isDownload": "true", "isPartial": "true",
            "offset": offset, "size": size,
        }))
        target = self.context.scratch_dir / "diagnostics" / f"{livy_id}_{file_name}.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print(f"{file_name}: {length} bytes; saved bytes {offset}-{length} to {target}")
        lines = content.decode("utf-8", errors="replace").splitlines()
        matches = [f"{number}: {line}" for number, line in enumerate(lines, 1)
                   if re.search(r"Traceback|Exception|Error", line)]
        print("\n".join(matches[:20]) or "no Traceback/Exception/Error lines in the saved range")
        return 0

    def delete(self) -> None:
        self.record("livy_delete_requested", session_id=self.session_id)
        self.request("DELETE", f"{self.base}/{self.session_id}")
        self.record("livy_deleted", session_id=self.session_id)
        self.state_path.unlink()
        print(f"session {self.session_id} deleted")


def main(argv: list[str] | None = None) -> int:
    context_parser = argparse.ArgumentParser(add_help=False)
    context_parser.add_argument("--workspace", "-w")
    context_parser.add_argument("--target", "-t")
    context_parser.add_argument("--project-root", type=Path)
    context_args, remaining = context_parser.parse_known_args(argv)
    parser = argparse.ArgumentParser(description=__doc__, parents=[context_parser])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("lakehouse")
    create.add_argument("--no-environment", action="store_true")
    commands.add_parser("status")
    statement = commands.add_parser("statement")
    source = statement.add_mutually_exclusive_group(required=True)
    source.add_argument("-f", "--file", type=Path)
    source.add_argument("code", nargs="?")
    cells = commands.add_parser("run-cells")
    cells.add_argument("notebook", type=Path)
    cells.add_argument("selection", nargs="?", default="all")
    cells.add_argument("--keep-going", action="store_true")
    commands.add_parser("delete")
    log = commands.add_parser("download-log", help="save a bounded driver log tail for nor-spark-diagnostics")
    log.add_argument("notebook_id")
    log.add_argument("livy_id")
    log.add_argument("app_id")
    log.add_argument("--file", choices=("stdout", "stderr"), default="stdout")
    log.add_argument("--bytes", type=int, default=16384)
    log.add_argument("--workspace-id", help="workspace of the notebook when it differs from the project target")
    args = parser.parse_args(remaining)
    try:
        context = resolve_context(
            project_root=context_args.project_root, workspace=context_args.workspace, target=context_args.target,
        )
        session = LivySession(context)
        if args.command == "create":
            return session.create(args.lakehouse, args.no_environment)
        if args.command == "download-log":
            return session.download_log(
                args.notebook_id, args.livy_id, args.app_id, args.file, args.bytes, args.workspace_id,
            )
        session.load()
        if args.command == "status":
            response = session.session_json()
            print({"state": response.get("state"), "inner": (response.get("fabricSessionStateInfo") or {}).get("state")})
        elif args.command == "statement":
            code = args.file.read_text(encoding="utf-8") if args.file else args.code
            return session.submit("pyspark", code)
        elif args.command == "run-cells":
            return session.run_cells(args.notebook, args.selection, args.keep_going)
        else:
            session.delete()
        return 0
    except (LivyError, fab_cli.CliError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; the remote session may still be running (use status or delete)", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
