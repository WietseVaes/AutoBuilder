"""
Core grading orchestration. Loads a rubric and reference values, runs a
script through the appropriate language adapter, and scores each rubric
entry via the comparator.

Each test_suite entry has:
  - "language": "python" (default; only python is currently supported)
  - "type": "variable" (default) or "function"
  - for "variable": "variable_name"
  - for "function": "function_name", "inputs" (list, JSON-serializable),
    optional "output_index" (for functions returning multiple values)
  - "rtol", "atol", "score", "description",
    "hint_wrong_size", "hint_tolerance"

Reference values and run results are both keyed by "test_name" (not
variable/function name), since the same function can be exercised by
multiple test entries with different inputs.
"""
import json
import pickle

from .comparator import compare
from .python_adapter import run_python_script


def load_rubric(path):
    with open(path) as f:
        return json.load(f)["test_suite"]


def load_reference(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _is_python_test(t):
    return t.get("language", "python") == "python"


def _build_test_specs(test_suite):
    """Build the minimal per-test spec list passed to the adapter."""
    specs = []
    for t in test_suite:
        if not _is_python_test(t):
            continue
        ttype = t.get("type", "variable")
        spec = {"name": t["test_name"], "type": ttype}
        if ttype == "variable":
            spec["variable_name"] = t["variable_name"]
        elif ttype == "function":
            spec["function_name"] = t["function_name"]
            spec["inputs"] = t.get("inputs", [])
            if "output_index" in t:
                spec["output_index"] = t["output_index"]
        specs.append(spec)
    return specs


def grade_python_submission(script_path, test_suite, reference, timeout=10):
    relevant = [t for t in test_suite if _is_python_test(t)]
    specs = _build_test_specs(relevant)

    run_result = run_python_script(script_path, specs, timeout=timeout)

    tests = []
    total_score = 0.0
    max_score = 0.0

    for t in relevant:
        name = t["test_name"]
        score = t["score"]
        max_score += score
        ttype = t.get("type", "variable")

        if name in run_result["_missing"]:
            if run_result["_error"]:
                status = "error"
                message = run_result["_error"].strip().splitlines()[-1]
            else:
                status = "missing"
                if ttype == "function":
                    message = f"Function '{t['function_name']}' was not defined."
                else:
                    message = f"Variable '{t['variable_name']}' was never defined."
            hint = t.get("hint_wrong_size", "")
            earned = 0.0

        elif name in run_result["_call_errors"]:
            status = "error"
            message = run_result["_call_errors"][name].strip().splitlines()[-1]
            hint = t.get("hint_wrong_size", "")
            earned = 0.0

        else:
            ref_val = reference.get(name)
            status, message = compare(run_result["values"][name], ref_val, t["rtol"], t["atol"])
            if status == "pass":
                hint = ""
                earned = float(score)
            elif status == "shape":
                hint = t.get("hint_wrong_size", "")
                earned = 0.0
            else:  # tolerance
                hint = t.get("hint_tolerance", "")
                earned = 0.0

        total_score += earned
        tests.append({
            "name": name,
            "description": t.get("description", ""),
            "score": earned,
            "max_score": score,
            "status": status,
            "message": message,
            "hint": hint,
        })

    return {"score": total_score, "max_score": max_score, "tests": tests}
