"""
Shared comparison logic, independent of where the values came from
(Python adapter, Octave adapter, etc).

compare() returns (status, message):
    status == "pass"      values match within tolerance
    status == "shape"     shapes/types don't match (use hint_wrong_size)
    status == "tolerance" same shape, but values are off (use hint_tolerance)
"""
import numpy as np


def compare(student_val, ref_val, rtol, atol):
    try:
        s = np.asarray(student_val, dtype=float)
        r = np.asarray(ref_val, dtype=float)
    except (TypeError, ValueError):
        return "shape", "Could not interpret your value as a numeric array."

    if s.shape != r.shape:
        return "shape", f"Expected an array of shape {r.shape}, got {s.shape}."

    if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=True):
        max_err = float(np.max(np.abs(s - r)))
        return "tolerance", f"Values are out of tolerance (max absolute error {max_err:.3e})."

    return "pass", "OK"
