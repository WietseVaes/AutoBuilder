"""
Shared comparison logic, independent of where the values came from.

compare() returns (status, message):
    status == "pass"      values match
    status == "shape"     types/shapes don't match (use hint_wrong_size)
    status == "tolerance" same type/shape, but values are off (use hint_tolerance)

Supports:
  - Strings: exact equality (case-sensitive).
  - Booleans: exact equality.
  - Integers: exact equality.
  - Floats and numpy arrays: numpy.allclose(rtol, atol).
  - Lists/tuples of the above: compared element-wise after converting to
    numpy arrays (if all numeric) or recursively (if mixed/string).

Messages never include the expected/solution value -- showing it to
students would leak the answer.
"""
import numpy as np


def _is_numeric(val):
    try:
        np.asarray(val, dtype=float)
        return True
    except (TypeError, ValueError):
        return False


def compare(student_val, ref_val, rtol=1e-6, atol=1e-6):
    # String comparison
    if isinstance(ref_val, str):
        if not isinstance(student_val, str):
            return "shape", f"Expected a string, but got type {type(student_val).__name__}."
        if student_val != ref_val:
            return "tolerance", "Your string value is incorrect."
        return "pass", "OK"

    # Boolean comparison (must come before int since bool is a subclass of int)
    if isinstance(ref_val, bool):
        if not isinstance(student_val, bool):
            return "shape", f"Expected a boolean, but got type {type(student_val).__name__}."
        if student_val != ref_val:
            return "tolerance", "Your boolean value is incorrect."
        return "pass", "OK"

    # Numeric / array comparison
    if _is_numeric(ref_val):
        if not _is_numeric(student_val):
            return "shape", f"Expected a numeric value or array, but got type {type(student_val).__name__}."
        s = np.asarray(student_val, dtype=float)
        r = np.asarray(ref_val, dtype=float)
        if s.shape != r.shape:
            return "shape", f"Expected a value of shape {r.shape}, but got shape {s.shape}."
        if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=True):
            return "tolerance", "Your value is not within the required tolerance."
        return "pass", "OK"

    # Fallback: direct equality for anything else
    if student_val != ref_val:
        return "tolerance", f"Your value is incorrect (got type {type(student_val).__name__})."
    return "pass", "OK"
