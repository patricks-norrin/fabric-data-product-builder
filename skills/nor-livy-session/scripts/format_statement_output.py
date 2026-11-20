#!/usr/bin/env python3
"""Print a Livy statement result (stdin JSON) as text; exit 1 on error output."""
import json
import sys
from typing import Any


def format_output(statement: dict[str, Any]) -> int:
    output = statement.get("output") or {}
    if output.get("status") not in ("ok", "error"):
        raise ValueError("statement has no completed output")
    text = (output.get("data") or {}).get("text/plain", "")
    if text:
        print(text)
    if output["status"] == "error":
        print(f"ERROR {output.get('ename')}: {output.get('evalue')}")
        print("".join(output.get("traceback") or [])[-3000:])
        return 1
    print(f"[statement ok, execution_count={output.get('execution_count')}]")
    return 0


if __name__ == "__main__":
    sys.exit(format_output(json.load(sys.stdin)))
