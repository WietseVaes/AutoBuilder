"""
Shared comparison logic.

compare() returns (status, message) where status is one of:
    "pass"        values match
    "wrong_type"  student value has wrong Python type
    "wrong_size"  student value has wrong shape (numeric arrays/DataFrames)
    "nans"        student value contains NaN
    "tolerance"   correct type/shape but values are out of tolerance

Messages never include the expected/solution value.
"""
import numpy as np

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


def _is_numeric(val):
    try:
        np.asarray(val, dtype=float)
        return True
    except (TypeError, ValueError):
        return False


def _compare_dataframe(student_val, ref_val, rtol, atol):
    if not isinstance(student_val, pd.DataFrame):
        return "wrong_type", f"Expected a pandas DataFrame, but got type {type(student_val).__name__}."

    ref_cols = list(ref_val.columns)
    student_cols = list(student_val.columns)
    if student_cols != ref_cols:
        return "wrong_size", (
            f"Expected columns {ref_cols}, but got columns {student_cols}."
        )

    if student_val.shape != ref_val.shape:
        return "wrong_size", f"Expected shape {ref_val.shape}, but got shape {student_val.shape}."

    numeric_cols = ref_val.select_dtypes(include=[np.number]).columns
    non_numeric_cols = [c for c in ref_cols if c not in numeric_cols]

    # Non-numeric columns: exact match required.
    for col in non_numeric_cols:
        if not student_val[col].equals(ref_val[col]):
            return "tolerance", f"Column '{col}' does not match the expected values."

    if len(numeric_cols) > 0:
        s = student_val[numeric_cols].to_numpy(dtype=float)
        r = ref_val[numeric_cols].to_numpy(dtype=float)
        if np.any(np.isnan(s)):
            return "nans", "Your DataFrame contains NaN values in a numeric column."
        if not np.allclose(s, r, rtol=rtol, atol=atol, equal_nan=False):
            return "tolerance", "One or more numeric columns are not within the required tolerance."

    return "pass", "OK"


def compare(student_val, ref_val, rtol=1e-6, atol=1e-6):
    # ── pandas DataFrame ──────────────────────────────────────────────────────
    if _HAS_PANDAS and isinstance(ref_val, pd.DataFrame):
        return _compare_dataframe(student_val, ref_val, rtol, atol)

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
        return "tolerance", "Your value is incorrect."
    return "pass", "OK"
