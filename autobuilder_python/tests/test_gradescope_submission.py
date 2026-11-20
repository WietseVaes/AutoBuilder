"""
Regression tests for the real Gradescope submission flow: prepare_submission.py
scanning /autograder/submission and run_tests.py grading against
/autograder/source, run as separate subprocesses exactly as run_autograder
invokes them (minus the bash wrapper itself, which just cd's and calls these
two scripts).

These simulate the Gradescope container layout with temporary directories,
using env var overrides (AUTOBUILDER_SUBMISSION_DIR / AUTOBUILDER_RESULTS_DIR
/ AUTOBUILDER_METADATA_PATH / AUTOBUILDER_STATUS_PATH) instead of the real
/autograder/* absolute paths.

Regression coverage (v0.6.11): previously run_autograder did
`cp -r /autograder/submission/* /autograder/source/`, so a submitted file
sharing a name with an autograder file (solution.py, rubric.json, ...)
silently overwrote it. These tests build a real autograder zip, extract it
as the "source" side, and submit adversarial filenames to confirm they can
no longer clobber anything under source.
"""
import json
import os
import subprocess
import sys
import zipfile

from autobuilder.build import build as build_zip

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _rubric_config(**overrides):
    config = {
        "language": "python",
        "test_suite": [
            {
                "test_name": "check_x",
                "type": "variable",
                "variable_name": "x",
                "score": 10,
                "description": "x should be 42",
            }
        ],
    }
    config.update(overrides)
    return config


def _build_source_dir(tmp_path, rubric_config, solution_code):
    """Builds a real autograder zip via autobuilder.build.build() and
    extracts it -- the same layout Gradescope unpacks into
    /autograder/source."""
    rubric_src = tmp_path / "rubric_src"
    rubric_src.mkdir()
    rubric_path = rubric_src / "rubric.json"
    rubric_path.write_text(json.dumps(rubric_config))
    solution_path = rubric_src / "solution.py"
    solution_path.write_text(solution_code)

    zip_path = tmp_path / "autograder.zip"
    build_zip(str(rubric_path), str(solution_path), str(zip_path))

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(source_dir)
    return source_dir


def _write_submission(tmp_path, files):
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    for rel, content in files.items():
        p = submission_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return submission_dir


def _run_gradescope_flow(source_dir, submission_dir, tmp_path):
    """Runs prepare_submission.py then run_tests.py, cwd=source_dir, exactly
    as templates/run_autograder does (aside from the bash wrapper). Returns
    (results_dict, marker_dict)."""
    results_dir = tmp_path / "results"
    env = dict(os.environ)
    env["AUTOBUILDER_SUBMISSION_DIR"] = str(submission_dir)
    env["AUTOBUILDER_RESULTS_DIR"] = str(results_dir)
    env["AUTOBUILDER_METADATA_PATH"] = str(tmp_path / "no_such_metadata.json")
    env["AUTOBUILDER_STATUS_PATH"] = str(tmp_path / "attempt_status.json")

    prep = subprocess.run(
        [sys.executable, "prepare_submission.py"],
        cwd=str(source_dir), env=env, capture_output=True, text=True,
    )
    assert prep.returncode == 0, (
        f"prepare_submission.py failed.\n--- stdout ---\n{prep.stdout}\n--- stderr ---\n{prep.stderr}"
    )

    run = subprocess.run(
        [sys.executable, "run_tests.py"],
        cwd=str(source_dir), env=env, capture_output=True, text=True,
    )
    assert run.returncode == 0, (
        f"run_tests.py failed.\n--- stdout ---\n{run.stdout}\n--- stderr ---\n{run.stderr}"
    )

    with open(results_dir / "results.json") as f:
        results = json.load(f)

    marker_path = source_dir / "student_language.json"
    marker = json.loads(marker_path.read_text()) if marker_path.exists() else {}
    return results, marker


def test_decoy_solution_with_homework_graded_against_instructor_solution(tmp_path):
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    original_solution = (source_dir / "solution.py").read_text()

    submission_dir = _write_submission(tmp_path, {
        # Decoy: shares a name with the instructor's reference solution, but
        # does not itself solve the assignment (doesn't even define x).
        "solution.py": "y = 999\n",
        "hw1.py": "x = 42\n",
    })

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    # The instructor's solution.py under /autograder/source must be
    # untouched -- this is the core regression: it used to get overwritten
    # by cp -r, so `import solution` in the generated tests would import
    # the student's file instead.
    assert (source_dir / "solution.py").read_text() == original_solution

    assert marker.get("graded_file") == "hw1.py"
    assert results["score"] == 10
    assert results["tests"][0]["status"] == "passed"


def test_single_file_named_solution_py_graded_normally(tmp_path):
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    submission_dir = _write_submission(tmp_path, {"solution.py": "x = 42\n"})

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    assert marker.get("graded_file") == "solution.py"
    assert results["score"] == 10
    assert results["tests"][0]["status"] == "passed"


def test_single_file_named_test_hw_graded_normally(tmp_path):
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    submission_dir = _write_submission(tmp_path, {"test_hw.py": "x = 42\n"})

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    assert marker.get("graded_file") == "test_hw.py"
    assert results["score"] == 10
    assert results["tests"][0]["status"] == "passed"


def test_submitted_rubric_json_does_not_change_scores(tmp_path):
    rubric_config = _rubric_config()
    source_dir = _build_source_dir(tmp_path, rubric_config, "x = 42\n")
    original_rubric = json.loads((source_dir / "rubric.json").read_text())

    # A decoy rubric.json with no test_suite at all -- if this were ever
    # read instead of the instructor's copy, scoring would be wildly wrong
    # (or crash outright).
    submission_dir = _write_submission(tmp_path, {
        "hw1.py": "x = 42\n",
        "rubric.json": json.dumps({"language": "python", "test_suite": []}),
    })

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    on_disk_rubric = json.loads((source_dir / "rubric.json").read_text())
    assert on_disk_rubric["test_suite"] == original_rubric["test_suite"]

    assert marker.get("graded_file") == "hw1.py"
    assert results["score"] == 10
    assert len(results["tests"]) == 1


def test_no_usable_file_lists_received_files_and_accepted_extensions(tmp_path):
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    submission_dir = _write_submission(tmp_path, {
        "notes.txt": "I forgot to attach my code\n",
        "readme.md": "oops\n",
    })

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    assert marker.get("submission_path") is None
    note = marker.get("note", "")
    assert "notes.txt" in note
    assert "readme.md" in note
    assert ".py" in note and ".ipynb" in note


def test_multiple_candidates_note_names_graded_file(tmp_path):
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    submission_dir = _write_submission(tmp_path, {
        "attempt1.py": "# scratch, doesn't define anything the rubric wants\n",
        "hw1.py": "x = 42\n",
    })

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    assert marker.get("graded_file") == "hw1.py"
    note = marker.get("note", "")
    assert "hw1.py" in note
    assert "Graded 'hw1.py'" in note
    assert results["score"] == 10


def test_student_helper_module_is_importable(tmp_path):
    """A student's main file may `import` a sibling module they submitted
    alongside it; prepare_submission.py copies such siblings into
    student_helpers/ and the runner subprocess adds that folder to
    sys.path so the import resolves."""
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    submission_dir = _write_submission(tmp_path, {
        "hw1.py": "from helper import answer\nx = answer()\n",
        "helper.py": "def answer():\n    return 42\n",
    })

    results, marker = _run_gradescope_flow(source_dir, submission_dir, tmp_path)

    assert marker.get("graded_file") == "hw1.py"
    assert marker.get("helpers_dir")
    assert results["score"] == 10
    assert results["tests"][0]["status"] == "passed"


def test_julia_rubric_is_rejected_by_python_builder(tmp_path):
    """The Python builder only builds Python autograders; a Julia rubric
    must point the instructor at autobuilder_julia instead of half-working."""
    import pytest
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps(_rubric_config(language="julia")))
    solution = tmp_path / "solution.py"
    solution.write_text("x = 42\n")
    with pytest.raises(RuntimeError, match="autobuilder_julia"):
        build_zip(str(rubric), str(solution), str(tmp_path / "autograder.zip"))


def test_shell_scripts_are_lf_and_executable_in_zip(tmp_path):
    """run_autograder/setup.sh run under bash on Gradescope: a CRLF line
    ending (from a Windows checkout) or a missing exec bit breaks them."""
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps(_rubric_config()))
    solution = tmp_path / "solution.py"
    solution.write_text("x = 42\n")
    zip_path = tmp_path / "autograder.zip"
    build_zip(str(rubric), str(solution), str(zip_path))
    with zipfile.ZipFile(zip_path) as zf:
        for name in ("run_autograder", "setup.sh"):
            assert b"\r" not in zf.read(name)
            assert (zf.getinfo(name).external_attr >> 16) & 0o111


def test_notebook_solution_builds_and_grades(tmp_path):
    """A Jupyter notebook can be the solution: it is converted to solution.py
    in the zip, and grading against it gives the same result."""
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps(_rubric_config()))
    nb = {"cells": [{"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None,
                     "source": ["%matplotlib inline\n", "x = 42\n"]}],
          "metadata": {"kernelspec": {"language": "python", "name": "python3"}},
          "nbformat": 4, "nbformat_minor": 5}
    solution = tmp_path / "solution.ipynb"
    solution.write_text(json.dumps(nb))
    zip_path = tmp_path / "autograder.zip"
    build_zip(str(rubric), str(solution), str(zip_path))
    with zipfile.ZipFile(zip_path) as zf:
        code = zf.read("solution.py").decode()
    assert "x = 42" in code and "%matplotlib" not in code


def test_script_crash_grades_what_was_defined_before_it(tmp_path):
    """With "grade_until_crash": true, a crash part-way keeps everything
    defined before it, and the error is shown once at the top of results.json."""
    config = _rubric_config(grade_until_crash=True)
    config["test_suite"].append({"test_name": "check_y", "type": "variable", "variable_name": "y",
                                 "score": 5, "description": "y should be 1"})
    source_dir = _build_source_dir(tmp_path, config, "x = 42\ny = 1\n")
    submission_dir = _write_submission(tmp_path, {"hw.py": "x = 42\nprint(undefined_name)\ny = 1\n"})
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    by_number = {t["number"]: t for t in results["tests"]}
    assert by_number["check_x"]["score"] == 10
    assert by_number["check_y"]["score"] == 0
    assert "Your code stopped with an error: NameError" in results["output"]
    assert "(line 2)" in results["output"]


def test_script_crash_fails_every_test_by_default(tmp_path):
    """Without "grade_until_crash" (default false), a crash fails every test
    with the crash message, as before v0.7.0."""
    config = _rubric_config()
    config["test_suite"].append({"test_name": "check_y", "type": "variable", "variable_name": "y",
                                 "score": 5, "description": "y should be 1"})
    source_dir = _build_source_dir(tmp_path, config, "x = 42\ny = 1\n")
    submission_dir = _write_submission(tmp_path, {"hw.py": "x = 42\nprint(undefined_name)\ny = 1\n"})
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    assert results["score"] == 0
    for t in results["tests"]:
        assert t["score"] == 0
        # Markdown output: "_" is escaped (shown as a plain underscore).
        assert "is not defined. (NameError: name 'undefined\\_name' is not defined)" in t["output"]
    assert "Your code stopped with an error" not in (results.get("output") or "")


def _loop_config(**overrides):
    """x (a variable) is graded first, then double (a function) hangs."""
    config = _rubric_config(timeout=5, **overrides)
    config["test_suite"].append({"test_name": "check_double", "type": "function", "function_name": "double",
                                 "inputs": [2.0], "score": 5, "description": "double(2.0)"})
    return config


_LOOP_SUBMISSION = {"hw.py": "x = 42\ndef double(v):\n    while True:\n        pass\n"}


def test_timeout_fails_every_test_by_default(tmp_path):
    """Without "grade_until_crash" (default false), running out of time
    fails every test with the timeout, even ones that finished."""
    source_dir = _build_source_dir(tmp_path, _loop_config(), "x = 42\ndef double(v):\n    return 2 * v\n")
    submission_dir = _write_submission(tmp_path, _LOOP_SUBMISSION)
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    assert results["score"] == 0
    for t in results["tests"]:
        assert "is not defined. (This did not finish within 5 seconds.)" in t["output"]


def test_timeout_keeps_finished_tests_with_grade_until_crash(tmp_path):
    source_dir = _build_source_dir(tmp_path, _loop_config(grade_until_crash=True),
                                   "x = 42\ndef double(v):\n    return 2 * v\n")
    submission_dir = _write_submission(tmp_path, _LOOP_SUBMISSION)
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    by_number = {t["number"]: t for t in results["tests"]}
    assert by_number["check_x"]["score"] == 10
    assert "did not finish within 5 seconds, so this test could not be completed" in by_number["check_double"]["output"]


# ── precheck, combine_questions, late_penalties ──────────────────────────────

def _run_with_metadata(source_dir, submission_dir, tmp_path, metadata, tag="run"):
    """Like _run_gradescope_flow, with a submission_metadata.json (previous
    submissions, created_at). `tag` keeps the result folders of several runs apart."""
    run_dir = tmp_path / tag
    run_dir.mkdir()
    meta_path = run_dir / "submission_metadata.json"
    meta_path.write_text(json.dumps(metadata))
    results_dir = run_dir / "results"
    env = dict(os.environ)
    env.update({
        "AUTOBUILDER_SUBMISSION_DIR": str(submission_dir),
        "AUTOBUILDER_RESULTS_DIR": str(results_dir),
        "AUTOBUILDER_METADATA_PATH": str(meta_path),
        "AUTOBUILDER_STATUS_PATH": str(run_dir / "attempt_status.json"),
    })
    env.pop("AUTOBUILDER_NOW", None)
    for script in ("prepare_submission.py", "run_tests.py"):
        proc = subprocess.run([sys.executable, script], cwd=str(source_dir), env=env,
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads((results_dir / "results.json").read_text())


def _previous(results, when="2026-11-01T12:00:00+00:00"):
    return {"submission_time": when, "score": results["score"], "results": results}


def _resubmit(tmp_path, files, old_name):
    (tmp_path / "submission").rename(tmp_path / old_name)
    return _write_submission(tmp_path, files)


def _precheck_config(**overrides):
    config = _rubric_config(precheck=True, **overrides)
    config["test_suite"][0]["attempts"] = 3
    config["test_suite"].append({"test_name": "fmt_x", "type": "variable", "variable_name": "x",
                                 "score": 0, "description": "x is defined"})
    config["test_suite"].append({"test_name": "check_double", "type": "function", "function_name": "double",
                                 "inputs": [2.0], "score": 5, "attempts": 3, "description": "double(2.0)"})
    return config


_PRECHECK_SOLUTION = "x = 42\ndef double(v):\n    return 2 * v\n"


def test_precheck_runs_only_zero_point_tests(tmp_path):
    source_dir = _build_source_dir(tmp_path, _precheck_config(timeout=5), _PRECHECK_SOLUTION)
    # double() would hang: in a precheck it is never called.
    submission_dir = _write_submission(tmp_path, {
        "hw.py": "Precheck = True\nx = 42\ndef double(v):\n    while True:\n        pass\n"})
    results = _run_with_metadata(source_dir, submission_dir, tmp_path, {})
    visible = [t for t in results["tests"] if t.get("visibility") != "hidden"]
    assert [t["number"] for t in visible] == ["fmt_x"]
    assert visible[0]["status"] == "passed"
    assert results["score"] == 0
    assert "Precheck run" in results["output"]
    assert "did not finish" not in json.dumps(results)
    assert visible[0]["extra_data"] == {"precheck": True}    # no attempts used


def test_precheck_keeps_previous_scores_hidden_and_uses_no_attempts(tmp_path):
    source_dir = _build_source_dir(tmp_path, _precheck_config(), _PRECHECK_SOLUTION)
    # x wrong, so not every attempt-limited test is done (no lockout).
    full = _write_submission(tmp_path, {"hw.py": "x = 0\ndef double(v):\n    return 2 * v\n"})
    first = _run_with_metadata(source_dir, full, tmp_path, {}, tag="first")
    assert first["score"] == 5

    pre = _resubmit(tmp_path, {"hw.py": "precheck = True\nx = 0\n"}, "sub_1")
    second = _run_with_metadata(source_dir, pre, tmp_path,
                                {"previous_submissions": [_previous(first)]}, tag="second")
    assert second["score"] == 5
    hidden = {t["number"]: t for t in second["tests"] if t.get("visibility") == "hidden"}
    assert hidden["check_double"]["extra_data"] == {"attempts_used": 1, "best_score": 5.0}

    # A graded run after the precheck still sees the history (1 attempt used, not 2).
    graded = _resubmit(tmp_path, {"hw.py": "x = 42\ndef double(v):\n    return 0\n"}, "sub_2")
    third = _run_with_metadata(source_dir, graded, tmp_path,
                               {"previous_submissions": [_previous(first),
                                                         _previous(second, "2026-11-02T12:00:00+00:00")]},
                               tag="third")
    by_number = {t["number"]: t for t in third["tests"]}
    # Full credit since the first run: done, so no attempt is used and it counts as passed.
    assert by_number["check_double"]["extra_data"] == {"attempts_used": 1, "best_score": 5.0}
    assert by_number["check_double"]["status"] == "passed"
    assert "Previously correct" in by_number["check_double"]["output"]


def test_precheck_variable_ignored_unless_rubric_allows_it(tmp_path):
    config = _precheck_config()
    config["precheck"] = False
    source_dir = _build_source_dir(tmp_path, config, _PRECHECK_SOLUTION)
    submission_dir = _write_submission(tmp_path, {"hw.py": "precheck = True\n" + _PRECHECK_SOLUTION})
    results = _run_with_metadata(source_dir, submission_dir, tmp_path, {})
    assert results["score"] == 15
    assert {t["number"] for t in results["tests"]} == {"check_x", "fmt_x", "check_double"}


def _combined_config(**overrides):
    return {
        "language": "python",
        "combine_questions": True,
        **overrides,
        "test_suite": [
            {"test_name": "1a", "type": "variable", "variable_name": "a", "score": 1,
             "description": "a is one", "hint_tolerance": "Count again.", "attempts": 5},
            {"test_name": "1b", "type": "variable", "variable_name": "b", "score": 2,
             "description": "b is two", "hint_not_defined": "Define b.", "attempts": 5},
            {"test_name": "2a", "type": "function", "function_name": "f", "inputs": [3],
             "score": 3, "description": "f(3) is nine"},
        ],
    }


_COMBINED_SOLUTION = "a = 1\nb = 2\ndef f(x):\n    return x * x\n"


def test_combine_questions_groups_parts_and_lists_only_errors(tmp_path):
    source_dir = _build_source_dir(tmp_path, _combined_config(), _COMBINED_SOLUTION)
    submission_dir = _write_submission(tmp_path, {"hw.py": "a = 5\ndef f(x):\n    return x * x\n"})
    results = _run_with_metadata(source_dir, submission_dir, tmp_path, {})
    assert all("number" not in t for t in results["tests"])   # Gradescope shows "Question 1", not "1) Question 1"
    by_name = {t["name"]: t for t in results["tests"]}
    assert set(by_name) == {"Question 1", "Question 2"}
    q1, q2 = by_name["Question 1"], by_name["Question 2"]
    assert q1["name"] == "Question 1" and q1["max_score"] == 3 and q1["score"] == 0
    assert q2["score"] == 3 and q2["output"] == "**✅ All parts correct.**"
    out = q1["output"]
    assert out.startswith("**❌ Incorrect answers:**")
    assert "- **Part a: `a`** — a is one" in out and "  ▸ **Hint:** Count again." in out
    assert "  ▸ **Attempts:** 1/5 (4 left)" in out
    assert "- **Part b: `b`** — b is two" in out and "Define b." in out
    assert out.index("a is one") < out.index("b is two")
    assert "Test Failed" not in out
    assert q1["extra_data"] == {"parts": {"1a": {"attempts_used": 1, "best_score": 0.0},
                                          "1b": {"attempts_used": 0, "best_score": 0.0}}}


def test_combine_questions_keeps_part_history(tmp_path):
    source_dir = _build_source_dir(tmp_path, _combined_config(), _COMBINED_SOLUTION)
    first = _write_submission(tmp_path, {"hw.py": "a = 1\nb = 0\n"})   # b wrong: no lockout
    r1 = _run_with_metadata(source_dir, first, tmp_path, {}, tag="first")
    second = _resubmit(tmp_path, {"hw.py": "a = 7\nb = 2\n"}, "sub_1")
    r2 = _run_with_metadata(source_dir, second, tmp_path, {"previous_submissions": [_previous(r1)]}, tag="second")
    q1 = {t["name"]: t for t in r2["tests"]}["Question 1"]
    assert q1["score"] == 3                      # 1a kept (attempts), 1b correct
    assert q1["status"] == "passed" and "Incorrect" not in q1["output"]
    assert q1["output"] == ("**⚠️ Previously correct, now incorrect (full credit kept):**\n\n"
                            "- **Part a: `a`** — a is one")
    assert q1["extra_data"]["parts"]["1a"]["attempts_used"] == 1     # no attempt used once correct


def _late_config():
    config = _rubric_config(late_penalties=[
        {"after": "2026-11-20T23:59:00-08:00", "penalty": 0.1},
        {"after": "2026-11-22T23:59:00-08:00", "penalty": 0.5},
    ])
    config["test_suite"].append({"test_name": "check_y", "type": "variable", "variable_name": "y",
                                 "score": 4, "description": "y should be 1"})
    return config


def test_late_penalty_only_hits_answers_fixed_after_the_deadline(tmp_path):
    source_dir = _build_source_dir(tmp_path, _late_config(), "x = 42\ny = 1\n")
    on_time = _write_submission(tmp_path, {"hw.py": "x = 42\ny = 0\n"})
    r1 = _run_with_metadata(source_dir, on_time, tmp_path,
                            {"created_at": "2026-11-20T10:00:00-08:00"}, tag="on_time")
    assert r1["score"] == 10 and "late" not in r1["output"]

    late = _resubmit(tmp_path, {"hw.py": "x = 0\ny = 1\n"}, "sub_1")
    r2 = _run_with_metadata(source_dir, late, tmp_path,
                            {"created_at": "2026-11-21T09:00:00.123456-08:00",
                             "previous_submissions": [_previous(r1)]}, tag="late")
    by_number = {t["number"]: t for t in r2["tests"]}
    assert by_number["check_x"]["score"] == 10                 # correct on time: kept
    assert "Previously correct" in by_number["check_x"]["output"]
    assert abs(by_number["check_y"]["score"] - 3.6) < 1e-9     # fixed late: 4 * 0.9
    assert "10% late penalty" in by_number["check_y"]["output"]
    assert "submitted after Nov 20, 2026 at 11:59 PM PST" in r2["output"]
    assert r2["output_format"] == "md" and by_number["check_y"]["output_format"] == "md"

    # Even later: 50%, but the 3.6 already earned is kept.
    later = _resubmit(tmp_path, {"hw.py": "x = 42\ny = 1\n"}, "sub_2")
    r3 = _run_with_metadata(source_dir, later, tmp_path,
                            {"created_at": "2026-11-23T09:00:00-08:00",
                             "previous_submissions": [_previous(r1),
                                                      _previous(r2, "2026-11-21T17:00:00+00:00")]},
                            tag="later")
    assert abs(r3["score"] - 13.6) < 1e-9


def test_malformed_late_penalties_rejected_at_build(tmp_path):
    import pytest
    config = _rubric_config(late_penalties=[{"after": "2026-11-20 23:59", "penalty": 0.1}])
    with pytest.raises(RuntimeError, match="time zone"):
        _build_source_dir(tmp_path, config, "x = 42\n")


def test_numpy_always_in_requirements(tmp_path):
    """comparator.py needs numpy: a rubric without "requirements" used to give
    a zip whose tests could not even be imported on Gradescope."""
    source_dir = _build_source_dir(tmp_path, _rubric_config(), "x = 42\n")
    reqs = (source_dir / "requirements.txt").read_text().split()
    assert reqs[:2] == ["gradescope-utils>=0.3.1", "numpy"]
    (tmp_path / "pinned").mkdir()
    other = _build_source_dir(tmp_path / "pinned", _rubric_config(requirements=["numpy==1.26.4"]), "x = 42\n")
    assert (other / "requirements.txt").read_text().split() == ["gradescope-utils>=0.3.1", "numpy==1.26.4"]


def test_unknown_result_rows_are_kept():
    """A row that matches no rubric test (e.g. the tests failed to import) is
    shown instead of silently dropped."""
    from autobuilder.scoring import finalize
    results = {"tests": [{"name": "test_rubric (unittest.loader._FailedTest)", "score": 0.0,
                          "max_score": 0.0, "status": "failed", "output": "ImportError: no numpy"}]}
    finalize(results, _rubric_config(combine_questions=True), {}, {})
    assert [t["output"] for t in results["tests"]] == ["```\nImportError: no numpy\n```"]


def test_late_maximum_reached_mixes_on_time_and_late_credit(tmp_path):
    """x correct on time (10/10) and y fixed late (4 * 0.9 = 3.6): the most
    credit still possible is 13.6/14, not 14 * 0.9. That is said once, and
    later submissions are not graded."""
    source_dir = _build_source_dir(tmp_path, _late_config(), "x = 42\ny = 1\n")
    on_time = _write_submission(tmp_path, {"hw.py": "x = 42\ny = 0\n"})
    r1 = _run_with_metadata(source_dir, on_time, tmp_path,
                            {"created_at": "2026-11-20T10:00:00-08:00"}, tag="on_time")
    late = _resubmit(tmp_path, {"hw.py": "x = 42\ny = 1\n"}, "sub_1")
    r2 = _run_with_metadata(source_dir, late, tmp_path,
                            {"created_at": "2026-11-21T09:00:00-08:00",
                             "previous_submissions": [_previous(r1)]}, tag="late")
    assert abs(r2["score"] - 13.6) < 1e-9
    assert "this is the most credit you can receive (13.6/14)" in r2["output"]
    later = _resubmit(tmp_path, {"hw.py": "x = 0\ny = 0\n"}, "sub_2")
    r3 = _run_with_metadata(source_dir, later, tmp_path,
                            {"created_at": "2026-11-23T09:00:00-08:00",
                             "previous_submissions": [_previous(r1),
                                                      _previous(r2, "2026-11-21T17:00:00+00:00")]},
                            tag="later")
    assert abs(r3["score"] - 13.6) < 1e-9
    assert r3["output"].startswith("✅ **All questions are correct.** With the 50% late penalty included")


def test_question_1_on_time_questions_2_and_3_late(tmp_path):
    """Question 1 correct before the deadline, Questions 2 and 3 only after
    it: Question 1 keeps full credit, 2 and 3 get the 20% penalty, the most
    credit possible is 3 + 0.8 * (3 + 3) = 7.8 (not 9 * 0.8 = 7.2), and the
    next submission is not graded."""
    config = _combined_config(late_penalties=[{"after": "2026-11-20T23:59:00-08:00", "penalty": 0.2}])
    config["test_suite"].append({"test_name": "3", "type": "variable", "variable_name": "c",
                                 "score": 3, "description": "c is three"})
    source_dir = _build_source_dir(tmp_path, config, _COMBINED_SOLUTION + "c = 3\n")

    on_time = _write_submission(tmp_path, {"hw.py": "a = 1\nb = 2\nc = 0\n"})
    r1 = _run_with_metadata(source_dir, on_time, tmp_path,
                            {"created_at": "2026-11-20T10:00:00-08:00"}, tag="on_time")
    assert r1["score"] == 3 and "Late" not in r1["output"]

    late = _resubmit(tmp_path, {"hw.py": _COMBINED_SOLUTION + "c = 3\n"}, "sub_1")
    r2 = _run_with_metadata(source_dir, late, tmp_path,
                            {"created_at": "2026-11-21T09:00:00-08:00",
                             "previous_submissions": [_previous(r1)]}, tag="late")
    by_name = {t["name"]: t for t in r2["tests"]}
    assert by_name["Question 1"]["score"] == 3
    assert by_name["Question 1"]["output"] == "**✅ All parts correct.**"     # no penalty mentioned
    assert abs(by_name["Question 2"]["score"] - 2.4) < 1e-9
    assert "**✅ Correct, with the 20% late penalty:**" in by_name["Question 2"]["output"]
    assert "- **Part a: `f`** — f(3) is nine (2.4/3)" in by_name["Question 2"]["output"]
    assert abs(by_name["Question 3"]["score"] - 2.4) < 1e-9
    assert abs(r2["score"] - 7.8) < 1e-9
    assert "**Late submission:** submitted after Nov 20, 2026 at 11:59 PM PST" in r2["output"]
    assert "the most credit you can receive (7.8/9)" in r2["output"]

    again = _resubmit(tmp_path, {"hw.py": "a = 0\n"}, "sub_2")
    r3 = _run_with_metadata(source_dir, again, tmp_path,
                            {"created_at": "2026-11-22T09:00:00-08:00",
                             "previous_submissions": [_previous(r1),
                                                      _previous(r2, "2026-11-21T17:00:00+00:00")]},
                            tag="again")
    assert abs(r3["score"] - 7.8) < 1e-9
    assert "the most credit you can receive (7.8/9)" in r3["output"]


def test_deadlines_are_shown_readably():
    from autobuilder.scoring import format_time, parse_time
    assert format_time(parse_time("2026-11-20T23:59:00-08:00")) == "Nov 20, 2026 at 11:59 PM PST"
    assert format_time(parse_time("2026-06-01T09:05:00-07:00")) == "Jun 1, 2026 at 9:05 AM PDT"
    assert format_time(parse_time("2026-06-01T12:00:00Z")) == "Jun 1, 2026 at 12:00 PM UTC"
    assert format_time(parse_time("2026-06-01T00:30:00+05:30")) == "Jun 1, 2026 at 12:30 AM UTC+5:30"


def test_student_text_is_escaped_and_tracebacks_are_code():
    from autobuilder.scoring import finalize
    config = _rubric_config()
    results = {"tests": [{"number": "check_x", "name": "x", "score": 0.0, "max_score": 10.0,
                          "status": "failed",
                          "output": "Test Failed: got <b>*bold*</b> for my_var\nHint: Look again."}]}
    finalize(results, config, {}, {})
    out = results["tests"][0]["output"]
    assert out == "▸ got \\<b\\>\\*bold\\*\\</b\\> for my\\_var  \n▸ **Hint:** Look again."
    results = {"tests": [{"number": "check_x", "name": "x", "score": 0.0, "max_score": 10.0,
                          "status": "failed",
                          "output": "Test Failed: Traceback (most recent call last):\n  File x\nValueError: no"}]}
    finalize(results, config, {}, {})
    assert "▸ Error:\n\n```\nTraceback (most recent call last):\n  File x\nValueError: no\n```" \
        in results["tests"][0]["output"]


_FORBIDDEN_SOLUTION = (
    "import numpy as np\n"
    "def bisect(f, a, b):\n"
    "    for _ in range(80):\n"
    "        m = (a + b) / 2\n"
    "        if f(a) * f(m) <= 0:\n"
    "            b = m\n"
    "        else:\n"
    "            a = m\n"
    "    return m\n"
    "root = bisect(lambda t: t * t - 2, 0, 2)\n"
    "def solve2(A, b):\n"
    "    return np.linalg.inv(A) @ b\n"
    "sol = np.linalg.solve([[2.0, 0.0], [0.0, 4.0]], [2.0, 4.0])\n"
)


def _forbidden_config():
    return _rubric_config(test_suite=[
        {"test_name": "root", "type": "variable", "variable_name": "root", "score": 2,
         "rtol": 1e-8, "atol": 1e-8, "forbidden_functions": ["numpy.roots", "sqrt"]},
        {"test_name": "solve2", "type": "function", "function_name": "solve2",
         "inputs": [[[2.0, 0.0], [0.0, 4.0]], [2.0, 4.0]], "score": 2,
         "forbidden_functions": ["linalg.solve"]},
        {"test_name": "sol", "type": "variable", "variable_name": "sol", "score": 1},
    ])


def test_forbidden_functions_zero_only_the_test_that_uses_them(tmp_path):
    """A forbidden function on the path to the tested name fails that test,
    whatever the value; the same function elsewhere in the file (for a test
    that does not forbid it), in comments or in strings is fine."""
    source_dir = _build_source_dir(tmp_path, _forbidden_config(), _FORBIDDEN_SOLUTION)
    submission = (
        "import numpy as np\n"
        "from math import sqrt as s\n"
        "# root = np.roots([1, 0, -2]) would be easier\n"
        "note = 'np.linalg.solve(A, b)'\n"
        "helper = s\n"
        "def root_of(c):\n"
        "    return helper(c)\n"
        "root = root_of(2)\n"
        "def solve2(A, b):\n"
        "    return np.linalg.inv(A) @ b\n"
        "sol = np.linalg.solve([[2.0, 0.0], [0.0, 4.0]], [2.0, 4.0])\n"
    )
    submission_dir = _write_submission(tmp_path, {"hw.py": submission})
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    by_number = {t["number"]: t for t in results["tests"]}
    assert by_number["root"]["score"] == 0
    assert "Do not use sqrt for this problem (line 5)" in by_number["root"]["output"]
    assert by_number["solve2"]["score"] == 2
    assert by_number["sol"]["score"] == 1


def test_forbidden_function_through_mutation_and_helper_module(tmp_path):
    source_dir = _build_source_dir(tmp_path, _forbidden_config(), _FORBIDDEN_SOLUTION)
    submission_dir = _write_submission(tmp_path, {
        "hw.py": (
            "import numpy as np\n"
            "import mysolver\n"
            "out = []\n"
            "def fill(o):\n"
            "    o.append(float(np.roots([1, 0, -2]).max()))\n"
            "fill(out)\n"
            "root = out[0]\n"
            "def solve2(A, b):\n"
            "    return mysolver.solve_it(A, b)\n"
            "sol = np.array([1.0, 1.0])\n"
        ),
        "mysolver.py": "from numpy.linalg import solve\ndef solve_it(A, b):\n    return solve(A, b)\n",
    })
    results, _ = _run_gradescope_flow(source_dir, submission_dir, tmp_path)
    by_number = {t["number"]: t for t in results["tests"]}
    assert by_number["root"]["score"] == 0
    assert "Do not use numpy.roots" in by_number["root"]["output"]
    assert by_number["solve2"]["score"] == 0
    assert "Do not use linalg.solve for this problem (line 3 of mysolver.py)" \
        in by_number["solve2"]["output"].replace("\\", "")
    assert by_number["sol"]["score"] == 1


def test_forbidden_function_in_solution_rejected_at_build(tmp_path):
    import pytest
    config = _forbidden_config()
    config["test_suite"][2]["forbidden_functions"] = ["solve"]
    with pytest.raises(RuntimeError, match="solution itself uses a forbidden function"):
        _build_source_dir(tmp_path, config, _FORBIDDEN_SOLUTION)
    config["test_suite"][2]["forbidden_functions"] = "solve"
    with pytest.raises(RuntimeError, match="must be a list"):
        (tmp_path / "b").mkdir()
        _build_source_dir(tmp_path / "b", config, _FORBIDDEN_SOLUTION)


def test_forbidden_analysis_unit():
    from autobuilder.forbidden import _Graph, forbidden_uses
    import ast
    src = (
        "import scipy.optimize as so\n"
        "from scipy.optimize import brentq as b\n"
        "x = 2.0\n"
        "r1 = b(lambda t: t - x, 0, 5)\n"
        "def f(x):\n"
        "    return x**2 - 2\n"
        "def brentq(g, a, c):\n"
        "    return (a + c) / 2\n"
        "r2 = brentq(f, 0, 2)\n"
        "alias = so.newton\n"
        "r3 = alias(f, 1.0)\n"
        "acc = 0.0\n"
        "for k in range(3):\n"
        "    acc += so.root_scalar(f, bracket=[0, 2]).root\n"
        "both = r1 + r2\n"
    )
    g = _Graph()
    g.build([(g.add_file(src, "hw.py"), "hw.py")])
    F = ["brentq", "newton", "scipy.optimize.root_scalar"]
    assert forbidden_uses(g, "x", F) == []
    assert forbidden_uses(g, "f", F) == []
    assert [h[0] for h in forbidden_uses(g, "r1", F)] == ["brentq"]
    assert forbidden_uses(g, "r2", F) == []          # the student's own brentq
    assert [h[0] for h in forbidden_uses(g, "r3", F)] == ["newton"]
    assert [h[0] for h in forbidden_uses(g, "acc", F)] == ["scipy.optimize.root_scalar"]
    assert [h[0] for h in forbidden_uses(g, "both", F)] == ["brentq"]
