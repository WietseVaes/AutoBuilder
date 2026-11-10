"""
Python language adapter.

Runs a script in an isolated subprocess (so a crash, infinite loop, or
os.exit() can't take down the grader), with a timeout, and returns the
requested values -- a mix of captured global variables and function
call results, per the "tests" spec list (see _runner.py).

Returns a dict:
    {
        "_error": str | None,            # the runner itself failed (no results at all)
        "_script_error": str | None,     # traceback if the script crashed part-way;
                                         # everything defined before it is still in values
        "_timed_out": bool,              # killed at the timeout
        "_unfinished": [test_name, ...], # tests that never got a result (timeout/exit)
        "values": {test_name: value},    # successfully captured values
        "_missing": [test_name, ...],    # variable/function never defined
        "_call_errors": {test_name: tb}, # function raised when called
    }
"""
import json
import os
import pickle
import subprocess
import sys
import tempfile

RUNNER_PATH = os.path.join(os.path.dirname(__file__), "_runner.py")


def _read_records(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "rb") as f:
        while True:
            try:
                records.append(pickle.load(f))
            except EOFError:
                break
            except Exception:
                break   # a record cut short by the kill at the timeout
    return records


def run_python_script(script_path, tests, timeout=10):
    fd, output_path = tempfile.mkstemp(suffix=".pkl")
    os.close(fd)
    result = {"_error": None, "_script_error": None, "_timed_out": False, "_unfinished": [],
              "values": {}, "_missing": [], "_call_errors": {}}
    stderr = ""
    try:
        try:
            proc = subprocess.run(
                [sys.executable, RUNNER_PATH, script_path, output_path, json.dumps(tests)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stderr = proc.stderr
        except subprocess.TimeoutExpired:
            result["_timed_out"] = True

        records = _read_records(output_path)
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    seen = set()
    for r in records:
        kind = r.get("kind")
        if kind == "script_error":
            result["_script_error"] = r["detail"]
        elif kind == "value":
            result["values"][r["name"]] = r["value"]
        elif kind == "missing":
            result["_missing"].append(r["name"])
        elif kind == "call_error":
            result["_call_errors"][r["name"]] = r["detail"]
        if "name" in r:
            seen.add(r["name"])

    result["_unfinished"] = [t["name"] for t in tests if t["name"] not in seen]
    if not records and not result["_timed_out"]:
        # The runner itself crashed before producing anything.
        result["_error"] = stderr or "Grader failed to run the script (no output produced)."
    return result
