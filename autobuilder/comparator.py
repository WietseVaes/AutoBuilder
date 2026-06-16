"""
Shared comparison logic.

compare() returns (status, message) where status is one of:
    "pass"        values match
    "not_defined" variable/function was not importable (handled in codegen,
                  not here -- included for completeness)
    "wrong_type"  student value has wrong Python type
    "wrong_size"  student value has wrong shape (numeric arrays only)
    "nans"        student value contains NaN
    "tolerance"   correct type/shape but values are out of tolerance

Messages never include the expected/solution value.
"""
import numpy as np


def _is_numeric(val):
    try:
        np.asarray(val, dtype=float)
        return True
    except (TypeError, ValueError):
        return False


def compare(student_val, ref_val, rtol=1e-6, atol=1e-6):
    # ── String ────────────────────────────────────────────────────────────────
    if isinstance(ref_val, str):
        if not isinstance(student_val, str):
            return "wrong_type", f"Expected a string, but got type {type(student_val).__name__}."
        if student_val != ref_val:
            return "tolerance", "Your string value is incorrect."
        return "pass", "OK"

    # ── Boolean (before int -- bool is a subclass of int) ─────────────────────
    if isinstance(ref_val, bool):
        if not isinstance(student_val, bool):
            return "wrong_type", f"Expected a boolean, but got type {type(student_val).__name__}."
        if student_val != ref_val:
            return "tolerance", "Your boolean value is incorrect."
        return "pass", "OK"

    # ── Numeric / array ───────────────────────────────────────────────────────
    if _is_numeric(ref_val):
        if not _is_numeric(student_val):
            return "wrong_type", f"Expected a numeric value or array, but got type {type(student_val).__name__}."
        s = np.asarray(student_val, dtype=float)
        r = np.asarray(ref_val, dtype=float)
        if s.shape != r.shape:
            return "wrong_size", f"Expected shape {r.shape}, but got shape {s.shape}."
        if np.any(np.isnan(s)):
            return "nans", "Your value contains NaN."
        if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=False):
            return "tolerance", "Your value is not within the required tolerance."
        return "pass", "OK"

    # ── Fallback: direct equality ─────────────────────────────────────────────
    if type(student_val) is not type(ref_val):
        return "wrong_type", f"Expected type {type(ref_val).__name__}, but got {type(student_val).__name__}."
    if student_val != ref_val:
        return "tolerance", f"Your value is incorrect."
    return "pass", "OK"
