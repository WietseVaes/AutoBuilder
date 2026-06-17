"""
Generates reference values by running an instructor's solution script
through the same adapter used to grade students, and pulling out the
values (variables and/or function call results) the rubric cares about.

Supports both .py (Python adapter) and .jl (Julia adapter) solutions.
"""
from .python_adapter import run_python_script


def generate_reference_values(solution_path, test_suite, timeout=10):
    """Run the solution and return a {test_name: value} dict.

    Dispatches to the Python or Julia adapter based on the solution file
    extension. Raises RuntimeError if the solution crashes, is missing
    required names, or raises errors when called with the rubric inputs.
    """
    specs = _build_solution_specs(test_suite)

    if solution_path.endswith(".jl"):
        from .julia_adapter import run_julia_script
        run_result = run_julia_script(solution_path, specs, timeout=timeout)
    else:
        run_result = run_python_script(solution_path, specs, timeout=timeout)

    if run_result["_error"]:
        raise RuntimeError(
            "Your solution script raised an error and could not be used to "
            "generate reference values:\n" + run_result["_error"]
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
    """Build adapter specs for all variable/function tests in the rubric.

    Plot tests are excluded: for Python solutions, plot comparison calls
    solution functions directly in the generated test code; for Julia
    solutions, plot tests are not supported at all.
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
