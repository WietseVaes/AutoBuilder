"""
Shared conversion helpers used by generated test code.

Rubric "inputs" and "expected" values come from JSON, so they're numbers,
strings, bools, and (possibly nested) lists. Lists of numbers are converted
to numpy arrays before being passed to a function or compared -- this is
usually what's wanted for numerical-methods assignments. Everything else
passes through unchanged.
"""
import numpy as np


def _is_numeric_list(x):
    if not isinstance(x, list) or len(x) == 0:
        return False
    for item in x:
        if isinstance(item, list):
            if not _is_numeric_list(item):
                return False
        elif not isinstance(item, (int, float)):
            return False
    return True


def convert_value(x):
    if _is_numeric_list(x):
        return np.array(x, dtype=float)
    return x


def convert_inputs(inputs):
    return [convert_value(x) for x in inputs]


def resolve_callable_inputs(inputs, module):
    """Replace {"__callable__": "varname"} markers with actual callables.

    Markers are produced by build._resolve_inputs when a $-prefixed input
    variable is callable. Pass the imported test_inputs module as `module`.
    Returns the inputs list unchanged when no markers are present.
    """
    if not any(isinstance(x, dict) and "__callable__" in x for x in inputs):
        return inputs
    if module is None:
        raise ImportError(
            "Callable inputs require a test_inputs.py file. "
            "Pass --inputs to `autobuilder grade` or `autobuilder build`."
        )
    return [
        getattr(module, x["__callable__"]) if isinstance(x, dict) and "__callable__" in x else x
        for x in inputs
    ]
