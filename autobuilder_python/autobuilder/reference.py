"""
Validates an instructor's solution.py at build time by running it through
the same adapter used to grade students, and pulling out the values
(variables and/or function call results) the rubric cares about.
"""
from .python_adapter import run_python_script


def generate_reference_values(solution_path, test_suite, timeout=10):
    """Run the solution and return a {test_name: value} dict.

    Raises RuntimeError if the solution crashes, is missing required
    names, or raises errors when called with the rubric inputs.
    """
    specs = _build_solution_specs(test_suite)
    run_result = run_python_script(solution_path, specs, timeout=timeout)

    error = run_result["_error"] or run_result.get("_script_error")
    if error:
        raise RuntimeError(
            "Your solution script raised an error and could not be used to "
            "generate reference values:\n" + error
        )
    if run_result.get("_timed_out"):
        raise RuntimeError(
            f"Your solution did not finish within {timeout} seconds. "
            "Increase \"timeout\" in rubric.json (or pass --timeout)."
        )
    if run_result["_missing"]:
        missing = ", ".join(run_result["_missing"])
        raise RuntimeError(
            "Your solution script did not define everything the rubric "
            f"requires (missing for test(s): {missing})."
        )
    if run_result["_call_errors"]:
        details = "\n\n".join(
            f"{name}:\n{tb}" for name, tb in run_result["_call_errors"].items()
        )
        raise RuntimeError(
            "One or more functions in your solution raised an error when "
            f"called with the rubric's test inputs:\n\n{details}"
        )

    return run_result["values"]


def _build_solution_specs(test_suite):
    """Build adapter specs for validating the solution.

    Plot tests are skipped -- plot comparison calls solution functions
    directly in the generated test code at grading time, so there is
    nothing to pre-validate here.
    """
    specs = []
    for t in test_suite:
        ttype = t.get("type", "variable")
        if ttype == "plot":
            continue

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
