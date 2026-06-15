"""
Shared comparison logic, independent of where the values came from.

compare() returns (status, message):
    status == "pass"      values match within tolerance
    status == "shape"     shapes/types don't match (use hint_wrong_size)
    status == "tolerance" same shape, but values are off (use hint_tolerance)

Messages are written to be shown directly to students: short, and
"expected X, received Y" where the values are small enough to display.
"""
import numpy as np

MAX_DISPLAY_ELEMENTS = 10


def _format_value(x):
    arr = np.asarray(x)
    if arr.size == 0:
        return "[]"
    if arr.size == 1:
        return f"{arr.item():.6g}"
    if arr.size <= MAX_DISPLAY_ELEMENTS:
        return np.array2string(arr, precision=4, separator=", ", suppress_small=True)
    return f"array of shape {arr.shape} (too large to display)"


def compare(student_val, ref_val, rtol, atol):
    try:
        s = np.asarray(student_val, dtype=float)
        r = np.asarray(ref_val, dtype=float)
    except (TypeError, ValueError):
        return "shape", f"Expected a numeric value or array, but got type {type(student_val).__name__}."

    if s.shape != r.shape:
        return "shape", (
            f"Expected a value of shape {r.shape}, but got shape {s.shape}.\n"
            f"  Expected: {_format_value(r)}\n"
            f"  Received: {_format_value(s)}"
        )

    if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=True):
        max_err = float(np.max(np.abs(s - r)))
        message = f"Values are out of tolerance (max absolute error {max_err:.3e})."
        if s.size <= MAX_DISPLAY_ELEMENTS:
            message += f"\n  Expected: {_format_value(r)}\n  Received: {_format_value(s)}"
        return "tolerance", message

    return "pass", "OK"
