#!/usr/bin/env python3
"""Parse CLI --version output and compare against a minimum. Stdlib only."""
from __future__ import annotations

import argparse
import re
import sys

VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LOGGED_IN_TRUE = re.compile(r"Logged\s+In:\s*True", re.IGNORECASE)
LOGGED_IN_FALSE = re.compile(r"Logged\s+In:\s*False", re.IGNORECASE)
LOGGED_IN_TO = re.compile(r"Logged\s+in\s+to\s+\S+", re.IGNORECASE)
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


def fab_logged_in(text: str) -> bool:
    """True when `fab auth status` reports an interactive login. Ignores token lines."""
    plain = ANSI_RE.sub("", text)
    if LOGGED_IN_FALSE.search(plain):
        return False
    return bool(LOGGED_IN_TRUE.search(plain) or LOGGED_IN_TO.search(plain))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("tool", choices=sorted(PREFERRED_MARKERS))
    compare = sub.add_parser("at_least")
    compare.add_argument("minimum")
    compare.add_argument("have")
    sub.add_parser("fab_logged_in")
    args = parser.parse_args()

    if args.command == "extract":
        version = extract_version(sys.stdin.read(), args.tool)
        if not version:
            return 1
        print(version)
        return 0

    if args.command == "fab_logged_in":
        return 0 if fab_logged_in(sys.stdin.read()) else 1

    try:
        ok = at_least(args.have, args.minimum)
    except ValueError:
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
