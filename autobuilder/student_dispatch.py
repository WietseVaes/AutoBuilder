"""
Single entry point the generated tests call to get a value out of the
student's submission, regardless of which language they submitted in.

prepare_submission.py writes a small marker file, student_language.json,
recording which language was detected ("python" or "julia") and the path
to the normalized submission file. This module reads that marker once
(cached) and dispatches to the matching adapter.

Each test_rubric.py test calls get_student_result(spec) with a single-test
spec dict (the same shape _runner.py / _runner.jl expect), and gets back
(value, error) where exactly one of the two is set:
    value is not None and error is None  -> success, value is the result
    error is not None                    -> the spec's "name" key will be
                                              in error["missing"] (not
                                              defined) or error["call_error"]
                                              (raised when called), and
                                              error["detail"] has the message

This mirrors the _missing / _call_errors distinction the language adapters
already produce, just narrowed to a single test so generated code doesn't
need to know about adapter internals.
"""
import json
import os

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

_cache = {}


def _load_marker():
    if "marker" not in _cache:
        try:
            with open(MARKER_PATH) as f:
                _cache["marker"] = json.load(f)
        except (OSError, ValueError):
            _cache["marker"] = {"language": "python", "submission_path": os.path.join(SOURCE_DIR, "student_submission.py")}
    return _cache["marker"]


def _summarize_error(detail, language):
    """Reduce a possibly multi-line error/traceback to the single most
    useful line, accounting for the fact that Python tracebacks put the
    actual exception message LAST, while Julia's showerror output (as
    captured by _runner.jl) puts it FIRST."""
    if not detail:
        return detail
    lines = [l for l in detail.strip().splitlines() if l.strip()]
    if not lines:
        return detail.strip()
    return lines[0] if language == "julia" else lines[-1]


def get_student_result(spec, timeout=None):
    """Run a single test spec against the student's submission. Returns
    a dict with keys: "value" (if successful), "missing" (bool), or
    "call_error" (string), exactly one of which is meaningful."""
    if timeout is None:
        try:
            with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
                timeout = json.load(f).get("timeout", 60)
        except (OSError, ValueError):
            timeout = 60
    marker = _load_marker()
    language = marker.get("language")
    submission_path = marker.get("submission_path")

    if language is None or submission_path is None or not os.path.exists(submission_path):
        return {"missing": True, "error_detail": "No submission file was found."}

    cache_key = (language, submission_path)
    if cache_key not in _cache:
        if language == "julia":
            from .julia_adapter import run_julia_script
            _cache[cache_key] = run_julia_script(submission_path, _all_specs(), timeout=timeout)
        else:
            from .python_adapter import run_python_script
            _cache[cache_key] = run_python_script(submission_path, _all_specs(), timeout=timeout)

    run_result = _cache[cache_key]
    name = spec["name"]

    if run_result.get("_error"):
        return {"missing": True, "error_detail": _summarize_error(run_result["_error"], language)}
    if name in run_result.get("_missing", []):
        return {"missing": True, "error_detail": None}
    if name in run_result.get("_call_errors", {}):
        return {"call_error": _summarize_error(run_result["_call_errors"][name], language)}
    return {"value": run_result["values"][name]}


def _all_specs():
    """The full list of test specs for this rubric, loaded once so a
    single subprocess call to the adapter covers every test instead of
    one subprocess per test."""
    if "all_specs" not in _cache:
        with open(os.path.join(SOURCE_DIR, "all_test_specs.json")) as f:
            _cache["all_specs"] = json.load(f)
    return _cache["all_specs"]
