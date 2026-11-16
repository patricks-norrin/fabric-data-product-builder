#!/usr/bin/env python3
"""Parse a Fabric notebook definition (notebook-content.py) into cells.
Usage: notebook_cells.py <file> --list | --cell N | --json"""
import sys, json, re, shlex
from pathlib import Path

MARKERS = {"# CELL ********************": "code", "# PARAMETERS CELL ********************": "parameters",
           "# MARKDOWN ********************": "markdown", "# METADATA ********************": "metadata"}

def parse(path):
    cells, cur, kind = [], [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.rstrip() in MARKERS:
            if kind and kind != "metadata":
                cells.append({"type": kind, "source": "\n".join(cur).strip("\n")})
            kind, cur = MARKERS[line.rstrip()], []
        elif kind:
            cur.append(line)
    if kind and kind != "metadata":
        cells.append({"type": kind, "source": "\n".join(cur).strip("\n")})
    for i, c in enumerate(cells, 1):
        c["index"] = i
        first = next((l for l in c["source"].splitlines() if l.strip()), "")
        c["title"] = first[:80]
        c["kind"] = "sql" if c["source"].lstrip().startswith("%%sql") else "pyspark"
        if c["kind"] == "sql":
            c["source"] = re.sub(r"^\s*%%sql[^\n]*\n", "", c["source"], count=1)
        if c["source"].lstrip().startswith("%pip "):
            command = c["source"].strip()
            if "\n" in command:
                raise ValueError(f"cell {i}: keep %pip in a dedicated single-line cell")
            args = shlex.split(command)[1:]
            c["livy_source"] = (
                'import subprocess, sys\n'
                'print("Livy: running %pip via driver-only pip; executor libraries are not updated.")\n'
                f'subprocess.run([sys.executable, "-m", "pip"] + {args!r}, check=True)\n'
            )
    return cells

if __name__ == "__main__":
    cells = parse(sys.argv[1]); mode = sys.argv[2] if len(sys.argv) > 2 else "--list"
    if mode == "--list":
        for c in cells: print(f"{c['index']:>3}  {c['type']:<10} {c['kind']:<7} {c['title']}")
    elif mode == "--cell": print(next(c for c in cells if c["index"] == int(sys.argv[3]))["source"])
    else: print(json.dumps(cells))
