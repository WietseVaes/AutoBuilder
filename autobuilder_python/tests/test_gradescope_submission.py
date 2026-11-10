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
        assert "is not defined. (NameError: name 'undefined_name' is not defined)" in t["output"]
    assert "Your code stopped with an error" not in (results.get("output") or "")
