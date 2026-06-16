"""
Julia language adapter.

Mirrors python_adapter.py exactly: runs a .jl script via subprocess (with a
timeout), passing it the test specs as JSON, and reads back a result dict
in the same shape python_adapter.run_python_script returns -- so grader.py
and codegen-generated comparisons never need to know which language
produced a value.

Requires the `julia` executable to be on PATH (installed by setup.sh) and
the JSON.jl package to be installed in that Julia environment (also done
by setup.sh, via `julia -e 'using Pkg; Pkg.add("JSON")'`).
"""
import json
import os
import subprocess
import tempfile

RUNNER_PATH = os.path.join(os.path.dirname(__file__), "_runner.jl")


def _restore_nans(obj):
    """JSON has no NaN literal; _runner.jl encodes NaN floats as the
    sentinel string "__NaN__". Walk the parsed result and convert back."""
    if obj == "__NaN__":
        return float("nan")
    if isinstance(obj, list):
        return [_restore_nans(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _restore_nans(v) for k, v in obj.items()}
    return obj


def run_julia_script(script_path, tests, timeout=10, julia_executable="julia"):
    fd, output_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(output_path)  # _runner.jl creates this; absence afterward signals a hard crash

    try:
        proc = subprocess.run(
            [julia_executable, RUNNER_PATH, script_path, output_path, json.dumps(tests)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path) as f:
                result = _restore_nans(json.load(f))
        else:
            result = {
                "_error": proc.stderr or "Grader failed to run the Julia script (no output produced).",
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
    except FileNotFoundError:
        result = {
            "_error": (
                f"Could not find the '{julia_executable}' executable. "
                "Julia must be installed and on PATH to grade Julia submissions."
            ),
            "values": {},
            "_missing": [t["name"] for t in tests],
            "_call_errors": {},
        }
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    return result
