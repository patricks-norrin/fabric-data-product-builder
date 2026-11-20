"""Write fake `fab`/`az` executables for driving toolpack scripts end to end.

A handler is Python source run with `cmd` (arguments without --json, joined by spaces), `args`, `STATE` (the
directory in $FAKE) and helpers `ok(data, message)`, `fail(message)`, `api(text, status_code)` and `text(value)`.
Every call is appended to STATE/<name>-calls. Unmatched calls fail loudly.
"""

import os
import pathlib
import sys

PRELUDE = '''
import json, os, pathlib, sys
args = [a for a in sys.argv[1:] if a != "--json"]
cmd = " ".join(args)
STATE = pathlib.Path(os.environ["FAKE"])
with (STATE / (pathlib.Path(sys.argv[0]).name + "-calls")).open("a", encoding="utf-8") as _calls:
    _calls.write(cmd + "\\n")

def ok(data=None, message=None):
    result = {}
    if data is not None:
        result["data"] = data if isinstance(data, list) else [data]
    if message is not None:
        result["message"] = message
    print(json.dumps({"status": "Success", "command": args[0] if args else "", "result": result}))
    sys.exit(0)

def fail(message):
    print(json.dumps({"status": "Failure", "result": {"message": message, "error_code": "Fake"}}))
    sys.exit(1)

def api(body, status_code=200):
    ok({"status_code": status_code, "text": body})

def text(value):
    print(value)
    sys.exit(0)

'''


def install(bin_dir: pathlib.Path, name: str, handler: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / name
    path.write_text(
        f"#!{sys.executable}\n{PRELUDE}{handler}\nfail('unexpected call: ' + cmd)\n", encoding="utf-8",
    )
    path.chmod(0o755)


def environment(bin_dir: pathlib.Path, state: pathlib.Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE"] = str(state)
    return env
