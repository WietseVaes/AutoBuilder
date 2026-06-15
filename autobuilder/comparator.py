"""
Shared comparison logic, independent of where the values came from.

compare() returns (status, message):
    status == "pass"      values match within tolerance
    status == "shape"     shapes/types don't match (use hint_wrong_size)
    status == "tolerance" same shape, but values are off (use hint_tolerance)

Messages deliberately do NOT include the expected/solution values --
showing those to students would leak the answer.
"""
import numpy as np


def compare(student_val, ref_val, rtol, atol):
    try:
        s = np.asarray(student_val, dtype=float)
        r = np.asarray(ref_val, dtype=float)
    except (TypeError, ValueError):
        return "shape", f"Expected a numeric value or array, but got type {type(student_val).__name__}."

    if s.shape != r.shape:
        return "shape", f"Expected a value of shape {r.shape}, but got shape {s.shape}."

    if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=True):
        return "tolerance", "Your value is not within the required tolerance."

    return "pass", "OK"
