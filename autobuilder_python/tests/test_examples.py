"""
Integration tests: run `autobuilder grade` on bundled examples and verify:
  - total score
  - number of passing / failing individual tests
  - specific hint messages that students would see

The plot examples (plot_test/, python/) are covered at the end.
"""
import dataclasses
import os
import subprocess
import sys
from typing import List

import pytest

EXAMPLES = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "examples")
)
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


@dataclasses.dataclass
class GradeResult:
    score: float
    n_passed: int
    n_failed: int
    raw: str  # full stdout


def _grade(example: str, solution: str, submission: str, inputs: str = None) -> GradeResult:
    d = os.path.join(EXAMPLES, example)
    cmd = [
        sys.executable, "-m", "autobuilder.cli",
        "grade",
        os.path.join(d, "rubric.json"),
        os.path.join(d, solution),
        os.path.join(d, submission),
    ]
    if inputs:
        cmd += ["--inputs", os.path.join(d, inputs)]
    proc = subprocess.run(
        cmd,
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


# ---------------------------------------------------------------------------
# Callable inputs (--inputs flag with a function value)
# ---------------------------------------------------------------------------

def test_grade_callable_correct():
    g = _grade("callable_test", "solution.py", "submission_01_correct.py",
               inputs="test_inputs.py")
    assert g.score == 3, f"Score: expected 3, got {g.score}\n{g.raw}"
    assert g.n_passed == 1, f"Pass count: expected 1, got {g.n_passed}\n{g.raw}"
    assert g.n_failed == 0, f"Fail count: expected 0, got {g.n_failed}\n{g.raw}"


def test_grade_callable_wrong():
    g = _grade("callable_test", "solution.py", "submission_02_wrong.py",
               inputs="test_inputs.py")
    assert g.score == 0, f"Score: expected 0, got {g.score}\n{g.raw}"
    assert g.n_passed == 0, f"Pass count: expected 0, got {g.n_passed}\n{g.raw}"
    assert g.n_failed == 1, f"Fail count: expected 1, got {g.n_failed}\n{g.raw}"
    assert "apply_twice should apply f to x, then apply f to the result" in g.raw, (
        f"Expected hint not found\n{g.raw}"
    )


# ---------------------------------------------------------------------------
# extra_files (regression: relative-path data files must resolve from the
# rubric's folder, not from whatever directory the CLI happens to be run
# from -- Gradescope always runs from /autograder/source).
# ---------------------------------------------------------------------------

def test_extra_files_build_and_grade_from_different_cwd(tmp_path):
    d = os.path.join(EXAMPLES, "extra_files_test")
    rubric = os.path.join(d, "rubric.json")
    solution = os.path.join(d, "solution.py")
    submission = os.path.join(d, "submission_01_correct.py")
    output_zip = os.path.join(str(tmp_path), "autograder.zip")

    # Force `-m autobuilder.cli` to resolve to *this* checkout rather than
    # whatever "autobuilder" happens to be installed/editable-linked
    # elsewhere on this machine -- cwd is deliberately not the repo, so it
    # can no longer rely on cwd shadowing to find the right package.
    env = dict(os.environ, PYTHONPATH=REPO_ROOT + os.pathsep + os.environ.get("PYTHONPATH", ""))

    build_proc = subprocess.run(
        [sys.executable, "-m", "autobuilder.cli", "build", rubric, solution, "--output", output_zip],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert build_proc.returncode == 0, (
        f"autobuilder build failed when run from a different working directory "
        f"(regression: solution.py's pd.read_csv('data.csv') needs cwd=rubric's folder).\n"
        f"--- stdout ---\n{build_proc.stdout}\n--- stderr ---\n{build_proc.stderr}"
    )
    assert os.path.exists(output_zip)

    grade_proc = subprocess.run(
        [sys.executable, "-m", "autobuilder.cli", "grade", rubric, solution, submission],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert grade_proc.returncode == 0, (
        f"autobuilder grade failed when run from a different working directory.\n"
        f"--- stdout ---\n{grade_proc.stdout}\n--- stderr ---\n{grade_proc.stderr}"
    )
    score = None
    for line in grade_proc.stdout.splitlines():
        if line.startswith("Total:"):
            score = float(line.split(":", 1)[1].strip())
    assert score == 1, f"Score: expected 1, got {score}\n{grade_proc.stdout}"
    assert grade_proc.stdout.count("[PASS]") == 1, grade_proc.stdout
    assert grade_proc.stdout.count("[FAIL]") == 0, grade_proc.stdout


# ---------------------------------------------------------------------------
# total_test, including a script that crashes part-way and one that hangs:
# like the Julia autobuilder, everything graded before the crash / timeout
# keeps its result.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("submission, score, hints", [
    ("submission_01_everything_wrong.py", 0, []),
    ("submission_04_correct.py", 20, []),
    ("submission_06_crashes_halfway.py", 16, [
        "Your code stopped with an error: NameError: name 'wieghts' is not defined",
        "(line ",
        "Everything defined before that point was still graded.",
        "Variable 'max_x1' is not defined. (your code stopped with an error before reaching it)",
    ]),
    ("submission_07_infinite_loop.py", 10, [
        "Your code did not finish within 10 seconds, so this test could not be completed.",
    ]),
])
def test_total_test(submission, score, hints):
    r = _grade("total_test", "solution.py", submission, inputs="test_inputs.py")
    assert r.score == score, r.raw
    for h in hints:
        assert h in r.raw, f"missing {h!r} in:\n{r.raw}"


def test_total_test_notebook_solution():
    r = _grade("total_test", "solution_notebook.ipynb", "submission_04_correct.py", inputs="test_inputs.py")
    assert r.score == 20, r.raw


# ---------------------------------------------------------------------------
# Plot examples. Regression for two bugs found in v0.7.0 development:
#  - plot tests of a function with no inputs failed with
#    "name 'inputs' is not defined" (the reference call is solution.f(*inputs))
#  - on Windows, non-ASCII text in submissions/rubrics (x², ≈) was read with
#    the system code page, so a correct plot label didn't match
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("example, submission, score, hints", [
    ("plot_test", "submission_01_correct.py", 10, []),
    ("plot_test", "submission_04_multiple_wrong.py", 4, ["'xlabel' does not match.", "Legend labels do not match."]),
    ("python", "submission_01_correct.py", 19, []),
    ("python", "submission_05_nans_and_wrong_plot_labels.py", 10, []),
])
def test_plot_examples(example, submission, score, hints):
    r = _grade(example, "solution.py", submission)
    assert r.score == score, r.raw
    for h in hints:
        assert h in r.raw, f"missing {h!r} in:\n{r.raw}"
