"""
Records per-test "attempted" status (was the variable/function
successfully defined this run?) to a small JSON file alongside the
autograder source, so attempts.py's post_processor can read it back after
the test suite finishes.

A file is used (rather than a shared class attribute on TestRubric)
because unittest's test discovery can import the test module under a
different name than a plain `import` would, leaving a class object that's
distinct from the one actually used by the running test suite -- a file is
immune to that.
"""
import json
import os

STATUS_PATH = os.environ.get(
    "AUTOBUILDER_STATUS_PATH",
    "/autograder/results/_attempt_status.json"
)


def clear():
    try:
        os.remove(STATUS_PATH)
    except OSError:
        pass


def record(test_name, attempted):
    status = load()
    status[test_name] = bool(attempted)
    try:
        with open(STATUS_PATH, "w") as f:
            json.dump(status, f)
    except OSError:
        pass


def load():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
