"""
Single entry point the generated tests call to get a value out of the
student's submission.

prepare_submission.py writes a small marker file, student_language.json,
recording the path to the normalized submission file (and, optionally, a
folder of helper modules the student submitted next to it). This module
reads that marker once (cached) and runs the submission through the
Python adapter -- once, for all tests.

Each test_rubric.py test calls get_student_result(spec) with a single-test
spec dict (the same shape _runner.py expects), and gets back a dict where
exactly one of these is meaningful:
    "value"       -> success, the student's value / function result
    "missing"     -> the name is not defined ("error_detail" may explain why,
                     e.g. the script crashed before reaching it)
    "call_error"  -> reading/calling the name raised an error
    "timed_out"   -> the code ran out of time before this test ran
                     ("message" says so)

Like the Julia autobuilder, rubric.json "grade_until_crash" decides what
happens when the script crashes part-way or runs out of time:
  - false (the default): nothing is graded; every test fails with the error
  - true: everything graded before the crash/timeout keeps its result, and
    the error (with its line number) is shown once at the top of the results

Messages for the top of the results are written to _grading_notes.json in
the source folder; run_tests.py (and `autobuilder grade`) show them.
"""
import json
import os
import re

# Normally resolved relative to this file's location (two levels up from
# .../source/autobuilder/student_dispatch.py is .../source, where
# run_tests.py, rubric.json, student_language.json, and all_test_specs.json
# all live). AUTOBUILDER_SOURCE_DIR overrides this -- needed because
# `autobuilder grade` runs in-process against a temp directory, and if the
# `autobuilder` package is already imported from site-packages (which it
# normally is, since this whole CLI lives in that package), Python's module
# cache can resolve `autobuilder.student_dispatch` to the installed copy
# instead of the one staged in the temp directory, making __file__-based
# resolution point at the wrong place entirely.
SOURCE_DIR = os.environ.get(
    "AUTOBUILDER_SOURCE_DIR",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
MARKER_PATH = os.path.join(SOURCE_DIR, "student_language.json")
NOTES_PATH = os.path.join(SOURCE_DIR, "_grading_notes.json")

_cache = {}


def _load_marker():
    if "marker" not in _cache:
        try:
            with open(MARKER_PATH) as f:
                _cache["marker"] = json.load(f)
        except (OSError, ValueError):
            _cache["marker"] = {"submission_path": os.path.join(SOURCE_DIR, "student_submission.py")}
    return _cache["marker"]


_FRAME = re.compile(r'File "(.*)", line (\d+)')


def _summarize_error(detail, script_path=None):
    """Reduce a traceback to its last line (where Python puts the actual
    exception message), plus the line in the student's file where it
    happened, if the traceback goes through it."""
    if not detail:
        return detail
    lines = [l for l in detail.strip().splitlines() if l.strip()]
    if not lines:
        return detail.strip()
    message = lines[-1].strip()
    if script_path:
        student_lines = [m.group(2) for m in _FRAME.finditer(detail)
                         if os.path.basename(m.group(1)) == os.path.basename(script_path)]
        # SyntaxErrors report the line as `File "...", line N` too.
        if student_lines:
            message += f" (line {student_lines[-1]})"
    return message


def _rubric():
    if "rubric" not in _cache:
        try:
            with open(os.path.join(SOURCE_DIR, "rubric.json"), encoding="utf-8") as f:
                _cache["rubric"] = json.load(f)
        except (OSError, ValueError):
            _cache["rubric"] = {}
    return _cache["rubric"]


def _timeout():
    return _rubric().get("timeout", 600)


def _grade_until_crash():
    """rubric.json "grade_until_crash" (default false): when the student's
    script crashes part-way or runs out of time, keep what was graded before
    that (true), or fail every test with the error (false)."""
    return _rubric().get("grade_until_crash", False) is True


def _write_notes(notes):
    try:
        with open(NOTES_PATH, "w") as f:
            json.dump(notes, f)
    except OSError:
        pass


def read_notes():
    """Messages for the top of the results (used by run_tests.py and the CLI)."""
    try:
        with open(NOTES_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def clear_notes():
    try:
        os.remove(NOTES_PATH)
    except OSError:
        pass


def _fmt_seconds(t):
    return int(t) if float(t).is_integer() else t


def get_student_result(spec, timeout=None):
    """Run a single test spec against the student's submission. Returns
    a dict with keys: "value" (if successful), "missing" (bool),
    "call_error" (string) or "timed_out" (bool), exactly one of which is
    meaningful."""
    if timeout is None:
        timeout = _timeout()
    marker = _load_marker()
    submission_path = marker.get("submission_path")

    if submission_path is None or not os.path.exists(submission_path):
        return {"missing": True, "error_detail": "No submission file was found."}

    if submission_path not in _cache:
        from .python_adapter import run_python_script
        helpers_dir = marker.get("helpers_dir")
        if helpers_dir:
            os.environ["AUTOBUILDER_STUDENT_HELPERS_DIR"] = helpers_dir
        run_result = run_python_script(submission_path, _all_specs(), timeout=timeout)
        _cache[submission_path] = run_result

        notes = []
        if run_result.get("_script_error") and _grade_until_crash():
            notes.append(
                "Your code stopped with an error: "
                f"{_summarize_error(run_result['_script_error'], submission_path)}\n"
                "Everything defined before that point was still graded."
            )
        if run_result.get("_timed_out") and _grade_until_crash():
            notes.append(f"Your code did not finish within {_fmt_seconds(timeout)} seconds.")
        _write_notes(notes)

    run_result = _cache[submission_path]
    name = spec["name"]

    if run_result.get("_error"):
        return {"missing": True, "error_detail": _summarize_error(run_result["_error"], submission_path)}
    if not _grade_until_crash():
        # The script crashed or ran out of time: nothing is graded, every
        # test fails with the error, e.g.
        # "Variable 'x' is not defined. (NameError: name 'y' is not defined)".
        if run_result.get("_script_error"):
            return {"missing": True, "error_detail": _summarize_error(run_result["_script_error"])}
        if run_result.get("_timed_out"):
            return {"missing": True, "error_detail": f"This did not finish within {_fmt_seconds(timeout)} seconds."}
    if name in run_result.get("_unfinished", []):
        if run_result.get("_timed_out"):
            message = (f"Your code did not finish within {_fmt_seconds(timeout)} seconds, "
                       "so this test could not be completed.")
        else:
            message = "Grading stopped unexpectedly before this test could run (does your code call os._exit()?)."
        return {"timed_out": True, "message": message}
    if name in run_result.get("_missing", []):
        detail = "your code stopped with an error before reaching it" if run_result.get("_script_error") else None
        return {"missing": True, "error_detail": detail}
    if name in run_result.get("_call_errors", {}):
        return {"call_error": _summarize_error(run_result["_call_errors"][name], submission_path)}
    return {"value": run_result["values"][name]}


def _all_specs():
    """The full list of test specs for this rubric, loaded once so a
    single subprocess call to the adapter covers every test instead of
    one subprocess per test."""
    if "all_specs" not in _cache:
        with open(os.path.join(SOURCE_DIR, "all_test_specs.json")) as f:
            _cache["all_specs"] = json.load(f)
    return _cache["all_specs"]
