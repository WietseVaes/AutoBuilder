"""
Python language adapter.

Runs a script in an isolated subprocess (so a crash, infinite loop, or
os.exit() can't take down the grader), with a timeout, and returns the
requested values -- a mix of captured global variables and function
call results, per the "tests" spec list (see _runner.py).

Returns a dict:
    {
        "_error": str | None,            # traceback if the script itself crashed
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


def run_python_script(script_path, tests, timeout=10):
    fd, output_path = tempfile.mkstemp(suffix=".pkl")
    os.close(fd)
    try:
        proc = subprocess.run(
            [sys.executable, RUNNER_PATH, script_path, output_path, json.dumps(tests)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, "rb") as f:
                result = pickle.load(f)
        else:
            # Runner itself crashed (shouldn't normally happen)
            result = {
                "_error": proc.stderr or "Grader failed to run the script (no output produced).",
                "values": {},
                "_missing": [t["name"] for t in tests],
                "_call_errors": {},
            }
    except subprocess.TimeoutExpired:
        result = {
            "_error": f"This did not finish within {timeout} seconds.",
            "values": {},
            "_missing": [t["name"] for t in tests],
            "_call_errors": {},
        }
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    return result
