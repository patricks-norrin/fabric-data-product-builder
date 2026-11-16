#!/usr/bin/env python3
"""Append operational events to a JSONL manifest and list the latest recorded job per notebook."""

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


def latest_jobs(path: Path) -> dict[str, dict]:
    """Return the most recent job_started record per notebook item path, in start order."""
    jobs: dict[str, dict] = {}
    if not path.exists():
        return jobs
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event") == "job_started" and record.get("item") and record.get("job_id"):
            jobs.pop(record["item"], None)
            jobs[record["item"]] = record
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("event", nargs="?")
    parser.add_argument("fields", nargs="*")
    parser.add_argument("--latest-jobs", action="store_true", help="print item<TAB>job_id per notebook")
    args = parser.parse_args()

    if args.latest_jobs:
        for item, record in latest_jobs(args.path).items():
            print(f"{item}\t{record['job_id']}")
        return
    if not args.event:
        parser.error("event is required unless --latest-jobs is used")
    append_event(args.path, args.event, args.fields)


if __name__ == "__main__":
    main()
