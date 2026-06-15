"""
Generates reference values by running an instructor's solution script
through the same adapter used to grade students, and pulling out the
values (variables and/or function call results) the rubric cares about.

This is what lets `autobuilder build` take a solution script directly
instead of a pre-pickled reference_values file.
"""
from .grader import _build_test_specs
from .python_adapter import run_python_script


def generate_reference_values(solution_path, test_suite, timeout=10):
    specs = _build_test_specs(test_suite)

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
