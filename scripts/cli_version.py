#!/usr/bin/env python3
"""Parse CLI --version output and compare against a minimum. Stdlib only."""
from __future__ import annotations

import argparse
import re
import sys

VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
PREFERRED_MARKERS = {
    "fab": ("fab", "ms-fabric-cli", "fabric-cli"),
    "az": ("azure-cli",),
}


def parse_version(value: str) -> tuple[int, ...]:
    match = VERSION_RE.search(value)
    if not match:
        raise ValueError(f"no version in {value!r}")
    major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
    return int(major), int(minor), int(patch)


def at_least(have: str, minimum: str) -> bool:
    return parse_version(have) >= parse_version(minimum)


def extract_version(text: str, tool: str) -> str | None:
    markers = PREFERRED_MARKERS.get(tool, (tool,))
    lines = [line for line in text.splitlines() if line.strip()]
    preferred = [
        line
        for line in lines
        if any(marker in line.lower() for marker in markers)
    ]
    for line in preferred or lines[:8]:
        match = VERSION_RE.search(line)
        if match:
            major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
            return f"{major}.{minor}.{patch}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("tool", choices=sorted(PREFERRED_MARKERS))
    compare = sub.add_parser("at_least")
    compare.add_argument("minimum")
    compare.add_argument("have")
    args = parser.parse_args()

    if args.command == "extract":
        version = extract_version(sys.stdin.read(), args.tool)
        if not version:
            return 1
        print(version)
        return 0

    try:
        ok = at_least(args.have, args.minimum)
    except ValueError:
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
