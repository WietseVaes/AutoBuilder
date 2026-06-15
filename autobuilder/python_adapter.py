"""
Python language adapter.

Runs a student's script in an isolated subprocess (so a crash, infinite
loop, or os.exit() can't take down the grader), with a timeout, and returns
the requested variables from its global namespace.

Returns a dict:
    {
        "_error": str | None,   # traceback text if the script itself crashed
        "values": {name: value, ...},  # successfully captured variables
        "_missing": [name, ...],        # requested vars that were never defined
    }
"""
import json
import os
import pickle
import subprocess
import sys
import tempfile

RUNNER_PATH = os.path.join(os.path.dirname(__file__), "_runner.py")


def run_python_script(script_path, var_names, timeout=10):
    fd, output_path = tempfile.mkstemp(suffix=".pkl")
    os.close(fd)
    try:
        proc = subprocess.run(
            [sys.executable, RUNNER_PATH, script_path, output_path, json.dumps(var_names)],
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
                "_error": proc.stderr or "Grader failed to run the submission (no output produced).",
                "values": {},
                "_missing": list(var_names),
            }
    except subprocess.TimeoutExpired:
        result = {
            "_error": f"Your script did not finish within {timeout} seconds.",
            "values": {},
            "_missing": list(var_names),
        }
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    return result
