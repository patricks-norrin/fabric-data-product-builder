"""Shared helpers for toolpack scripts: project context and the fab/az CLIs. Standard library only.

Every fab call uses the global `--json` flag (fab >= 1.9.0) and reads its result envelope, so scripts never parse
human-readable output and every failure carries the message fab reported.
"""

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
from typing import Any, Callable
from uuid import UUID

from norrin_context import ProjectContext, resolve_context


class CliError(RuntimeError):
    pass


def run(command: str, *args: str) -> subprocess.CompletedProcess:
    executable = shutil.which(command)
    if executable is None:
        raise CliError(f"{command} is not on PATH")
    return subprocess.run(
        [executable, *args], capture_output=True, encoding="utf-8", errors="replace", check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def _tail(text: str, lines: int = 8) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _envelope(text: str) -> dict[str, Any] | None:
    """Return the last fab JSON envelope in stdout; library logging may precede it."""
    starts = ([0] if text.startswith("{") else []) + [match.start() + 1 for match in re.finditer(r"\n\{", text)]
    for start in reversed(starts):
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            continue
        if isinstance(value, dict) and "status" in value:
            return value
    return None


def fab(*args: str) -> dict[str, Any]:
    """Run fab with --json and return its `result` object; raise CliError with fab's own message on failure."""
    result = run("fab", *args, "--json")
    envelope = _envelope(result.stdout)
    label = f"fab {' '.join(args[:2])}"
    if envelope is None:
        if result.returncode == 0:
            return {}
        raise CliError(f"{label} failed (exit {result.returncode}): {_tail(result.stderr or result.stdout)}")
    body = envelope.get("result") or {}
    if envelope.get("status") != "Success" or result.returncode != 0:
        reason = body.get("message") or _tail(result.stderr or result.stdout) or envelope.get("status")
        code = f" [{body['error_code']}]" if body.get("error_code") else ""
        raise CliError(f"{label} failed{code}: {reason}")
    return body


def fab_data(*args: str) -> Any:
    data = fab(*args).get("data") or []
    return data[0] if data else None


def api(endpoint: str, *args: str) -> Any:
    """Call `fab api` and return the response body; HTTP errors raise even though fab exits 0 for them."""
    payload = fab_data("api", endpoint, *args)
    if not isinstance(payload, dict) or "status_code" not in payload:
        raise CliError(f"fab api {endpoint}: unexpected response {payload!r}")
    text = payload.get("text")
    if int(payload["status_code"]) >= 400:
        reason = text.get("message") or text.get("errorCode") if isinstance(text, dict) else text
        raise CliError(f"fab api {endpoint}: HTTP {payload['status_code']}: {reason}")
    return text


def exists(path: str) -> bool:
    # A missing parent makes fab report failure; the caller's next mkdir/cp surfaces any real error.
    try:
        return fab("exists", path).get("message") == "true"
    except CliError:
        return False


def workspace_id(name: str) -> str:
    value = fab_data("get", f"/{name}.Workspace", "-q", "id")
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise CliError(f"workspace '{name}' returned no id: {value!r}") from None


def item_id(workspace: str, name: str, item_type: str) -> str | None:
    items = api(f"workspaces/{workspace}/items", "-P", f"type={item_type}")
    values = items.get("value", []) if isinstance(items, dict) else []
    return next((item["id"] for item in values if item.get("displayName") == name), None)


def wait_for(probe: Callable[[], Any], what: str, attempts: int = 12, delay: float = 5) -> Any:
    """Poll until a newly created item becomes visible to list/exists calls."""
    for attempt in range(attempts):
        value = probe()
        if value:
            return value
        if attempt < attempts - 1:
            time.sleep(delay)
    raise CliError(f"{what} was not visible after {int(attempts * delay)}s")


def onelake_mkdir_p(item_path: str, relative: str) -> None:
    """Create each missing directory level of Files/<a>/<b> inside a lakehouse."""
    current = ""
    for part in relative.strip("/").split("/"):
        current = f"{current}/{part}" if current else part
        if current != "Files" and not exists(f"{item_path}/{current}"):
            fab("mkdir", f"{item_path}/{current}")
            print(f"• created {item_path}/{current}")


def context_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--workspace", "-w", help="logical ws_<name> (default: configuration/fabric_targets.json)")
    parser.add_argument("--target", "-t", help="target profile (default: active_target)")
    parser.add_argument("--project-root", help="directory containing configuration/fabric_targets.json")
    return parser


def context_from(args: argparse.Namespace) -> ProjectContext:
    return resolve_context(
        project_root=Path(args.project_root) if args.project_root else None,
        workspace=args.workspace,
        target=args.target,
    )


def workspace_path(context: ProjectContext) -> str:
    return f"/{context.workspace_name}.Workspace"


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def guarded(main: Callable[[], int]) -> None:
    """Run a script entrypoint, turning expected errors into one ERROR line and exit 1."""
    try:
        sys.exit(main())
    except (CliError, ValueError, OSError) as exc:
        die(str(exc))
    except KeyboardInterrupt:
        die("interrupted; a started Fabric job keeps running", 130)
