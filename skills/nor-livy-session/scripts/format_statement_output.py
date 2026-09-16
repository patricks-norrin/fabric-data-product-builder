#!/usr/bin/env python3
"""Print a Livy statement result (stdin JSON) as text; exit 1 on error output."""
import json, sys
o = (json.load(sys.stdin).get("output") or {})
txt = (o.get("data") or {}).get("text/plain", "")
if txt:
    print(txt)
if o.get("status") == "error":
    print(f"ERROR {o.get('ename')}: {o.get('evalue')}")
    print("".join(o.get("traceback") or [])[-3000:])
    sys.exit(1)
print(f"[statement ok, execution_count={o.get('execution_count')}]")
