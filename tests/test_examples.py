"""
Integration tests: run `autobuilder grade` on bundled examples and verify:
  - total score
  - number of passing / failing individual tests
  - specific hint messages that students would see

Plot-heavy examples (python/, julia/) are excluded here; add a separate CI
job for those once precompilation time is acceptable.
"""
import dataclasses
import os
import subprocess
import sys
from typing import List

import pytest

EXAMPLES = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "autobuilder", "examples")
)


@dataclasses.dataclass
class GradeResult:
    score: float
    n_passed: int
    n_failed: int
    raw: str  # full stdout


def _grade(example: str, solution: str, submission: str) -> GradeResult:
    d = os.path.join(EXAMPLES, example)
    proc = subprocess.run(
        [
            sys.executable, "-m", "autobuilder.cli",
            "grade",
            os.path.join(d, "rubric.json"),
            os.path.join(d, solution),
            os.path.join(d, submission),
        ],
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout
    score = None
    for line in stdout.splitlines():
        if line.startswith("Total:"):
            score = float(line.split(":", 1)[1].strip())
    if score is None:
        raise AssertionError(
            f"No 'Total:' line in grader output.\n"
            f"--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
    return GradeResult(
        score=score,
        n_passed=stdout.count("[PASS]"),
        n_failed=stdout.count("[FAIL]"),
        raw=stdout,
    )


# ---------------------------------------------------------------------------
# Test matrix
# ---------------------------------------------------------------------------
# Each entry: (example, solution, submission, score, n_pass, n_fail, hints)
#
# hints is a list of strings that must appear verbatim in the grader output.
# They are drawn from:
#   - the comparator message  (comparator.py → compare())
#   - the rubric hint fields  (hint_tolerance, hint_not_defined, …)
# ---------------------------------------------------------------------------
CASES = [
    # ── julia_test ─────────────────────────────────────────────────────────
    # Regression for v0.5.10: when the autograder is built with solution.jl,
    # the instructor's file must NOT be selected as the student submission.
    (
        "julia_test", "solution.jl", "submission_01_correct.jl",
        4, 4, 0, [],
    ),
    (
        "julia_test", "solution.jl", "submission_02_wrong_values.jl",
        # JL1 greeting wrong, JL2 scale_factor wrong, JL3 squares OK, JL4 add_one wrong
        1, 1, 3,
        [
            # JL1 → comparator: "Your string value is incorrect."
            #        hint_tolerance from rubric:
            "Check the exact spelling: 'hello from autobuilder'.",
            # JL2 → comparator: "Your value is not within the required tolerance."
            #        hint_tolerance:
            "scale_factor should be 2.5.",
            # JL4 → same comparator message, different hint_tolerance:
            "add_one should return x + 1.",
        ],
    ),

    # ── function_unit_test ─────────────────────────────────────────────────
    (
        "function_unit_test", "solution.py", "submission_04_correct.py",
        8, 3, 0, [],
    ),
    (
        "function_unit_test", "solution.py", "submission_01_missing_function.py",
        # Student defined `rk4` instead of `rk4_step` → all 3 tests fail.
        # Rubric has no hint_not_defined, so the fallback is hint_wrong_size.
        0, 0, 3,
        [
            # codegen "Function 'rk4_step' is not defined." message:
            "Function 'rk4_step' is not defined.",
            # fallback hint (hint_wrong_size used as hint_not_defined):
            "rk4_step should return a length-2 array/list [R_next, J_next].",
        ],
    ),

    # ── dataframe_test ─────────────────────────────────────────────────────
    (
        "dataframe_test", "solution.py", "submission_01_correct.py",
        10, 3, 0, [],
    ),
    (
        "dataframe_test", "solution.py", "submission_01_wrong_columns.py",
        # grades_df uses "Name" instead of "name".
        # DF1 + DF2 fail (column mismatch on the full DataFrame); DF3 (summary_df) passes
        # because its groupby only touches "passed" and "score" columns, which are correct.
        3, 1, 2,
        [
            # comparator._compare_dataframe column check message:
            "Expected columns ['name', 'score', 'passed'], but got columns ['Name', 'score', 'passed'].",
            # DF1 hint_wrong_size:
            "grades_df should have columns ['name', 'score', 'passed'] and 5 rows",
        ],
    ),
    (
        "dataframe_test", "solution.py", "submission_02_wrong_threshold.py",
        # Student uses score >= 80 instead of score >= 70.
        # grades_df has correct columns but wrong "passed" values (bool, non-numeric).
        # DF1 and DF2 both compare the full grades_df → "Column 'passed' does not match".
        # DF3 compares summary_df → wrong average_score values → tolerance fail.
        0, 0, 3,
        [
            # comparator._compare_dataframe non-numeric column mismatch (DF1 + DF2):
            "Column 'passed' does not match the expected values.",
            # DF2 hint_tolerance:
            "passed should be True where score >= 70, and False otherwise.",
            # DF3 hint_tolerance:
            "Use grades_df.groupby('passed')['score'].mean() to compute group averages.",
        ],
    ),

    # ── expected_test ──────────────────────────────────────────────────────
    # Rubric uses hard-coded "expected" values; solution is not executed.
    (
        "expected_test", "solution.py", "submission_03_correct.py",
        4, 1, 0, [],
    ),
    (
        "expected_test", "solution.py", "submission_01_misisng_var.py",
        # Student named the variable `scores` instead of `final_scores`.
        # No hint_not_defined in rubric → fallback to hint_wrong_size.
        0, 0, 1,
        [
            # codegen "Variable 'final_scores' is not defined." message:
            "Variable 'final_scores' is not defined.",
            # fallback hint (hint_wrong_size):
            "final_scores should be a NumPy array of shape (4,)",
        ],
    ),

    # ── julia_test: missing function ───────────────────────────────────────
    (
        "julia_test", "solution.jl", "submission_03_missing_function.jl",
        # greeting, scale_factor, squares all correct; add_one not defined.
        3, 3, 1,
        [
            # codegen "Function 'add_one' is not defined." message:
            "Function 'add_one' is not defined.",
            # hint_not_defined from rubric:
            "Define a function called add_one(x).",
        ],
    ),

    # ── julia_test: wrong type ─────────────────────────────────────────────
    (
        "julia_test", "solution.jl", "submission_04_wrong_type.jl",
        # greeting = 42 (Int64 → Python int) instead of a string; rest correct.
        3, 3, 1,
        [
            # comparator wrong_type message for string-expected:
            "Expected a string, but got type int.",
            # hint_wrong_type from rubric:
            "greeting should be a string.",
        ],
    ),

    # ── function_unit_test: wrong size (scalar instead of array) ──────────
    (
        "function_unit_test", "solution.py", "submission_02_wrong_shape.py",
        # rk4_step returns float(np.sum(result)) → shape () instead of (2,).
        0, 0, 3,
        [
            # comparator wrong_size message:
            "Expected shape (2,), but got shape ().",
            # hint_wrong_size from rubric:
            "rk4_step should return a length-2 array/list [R_next, J_next].",
        ],
    ),

    # ── function_unit_test: notebook submission ────────────────────────────
    (
        "function_unit_test", "solution.py", "submission_05_correct.ipynb",
        # Same correct RK4 implementation, submitted as a Jupyter notebook.
        8, 3, 0, [],
    ),
]


@pytest.mark.parametrize(
    "example,solution,submission,expected_score,expected_pass,expected_fail,hints",
    CASES,
    ids=[f"{ex}/{sub}" for ex, _sol, sub, *_ in CASES],
)
def test_grade(example, solution, submission,
               expected_score, expected_pass, expected_fail, hints):
    g = _grade(example, solution, submission)

    assert g.score == expected_score, (
        f"Score: expected {expected_score}, got {g.score}\n{g.raw}"
    )
    assert g.n_passed == expected_pass, (
        f"Pass count: expected {expected_pass}, got {g.n_passed}\n{g.raw}"
    )
    assert g.n_failed == expected_fail, (
        f"Fail count: expected {expected_fail}, got {g.n_failed}\n{g.raw}"
    )
    for snippet in hints:
        assert snippet in g.raw, (
            f"Expected hint not found in grader output:\n"
            f"  {snippet!r}\n\nFull output:\n{g.raw}"
        )
