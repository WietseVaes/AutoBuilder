"""
Core grading orchestration. Loads a rubric and a reference-values dump,
runs a student submission through the appropriate language adapter, and
scores each rubric entry via the comparator.

Currently handles type="variable", language="python" entries (the existing
gspack-style rubric, unchanged). Other (type, language) combinations are
skipped here -- they'll be picked up by adapters added later.
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


def _is_python_variable_test(t):
    return t.get("type", "variable") == "variable" and t.get("language", "python") == "python"


def grade_python_submission(script_path, rubric, reference, timeout=10):
    relevant = [t for t in rubric if _is_python_variable_test(t)]
    var_names = [t["variable_name"] for t in relevant]

    run_result = run_python_script(script_path, var_names, timeout=timeout)

    tests = []
    total_score = 0.0
    max_score = 0.0

    for t in relevant:
        name = t["test_name"]
        var = t["variable_name"]
        score = t["score"]
        max_score += score

        if var in run_result["_missing"]:
            if run_result["_error"]:
                status = "error"
                # last line of the traceback is usually the useful bit
                message = run_result["_error"].strip().splitlines()[-1]
            else:
                status = "missing"
                message = f"Variable '{var}' was never defined."
            hint = t.get("hint_wrong_size", "")
            earned = 0.0
        else:
            ref_val = reference.get(var)
            status, message = compare(run_result["values"][var], ref_val, t["rtol"], t["atol"])
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
