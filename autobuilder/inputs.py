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
