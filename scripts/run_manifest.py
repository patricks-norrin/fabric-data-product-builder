#!/usr/bin/env python3
"""Append one operational event to a JSONL manifest."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def append_event(path: Path, event: str, fields: list[str]) -> None:
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    for field in fields:
        key, separator, value = field.partition("=")
        if not separator or not key:
            raise ValueError(f"field must be key=value: {field!r}")
        record[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as manifest:
        manifest.write(json.dumps(record, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("event")
    parser.add_argument("fields", nargs="*")
    args = parser.parse_args()
    append_event(args.path, args.event, args.fields)


if __name__ == "__main__":
    main()