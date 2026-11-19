import json
import os
import unittest

from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner

from autobuilder import attempt_recorder
from autobuilder.attempts import make_post_processor, locked_out_message, locked_out_results
from autobuilder import student_dispatch
from autobuilder.scoring import md_text

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
METADATA_PATH = os.environ.get("AUTOBUILDER_METADATA_PATH", "/autograder/submission_metadata.json")
RESULTS_DIR = os.environ.get("AUTOBUILDER_RESULTS_DIR", "/autograder/results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "results.json")
DEBUG_ENV = os.environ.get("AUTOBUILDER_DEBUG", "0")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _submission_note():
    """A student-facing note prepare_submission.py may have left about how
    it picked (or failed to find) the student's file -- e.g. which file
    was graded when several were submitted, or which files were received
    when none were usable."""
    marker = _load_json(os.path.join(SOURCE_DIR, "student_language.json"))
    return marker.get("note")


def _metadata_debug_summary(metadata):
    if not metadata:
        return "submission_metadata.json: not found or empty"
    lines = ["submission_metadata.json keys: " + ", ".join(str(k) for k in metadata.keys())]
    prev = metadata.get("previous_submissions") or []
    lines.append(f"previous_submissions count: {len(prev)} (newest first, [0] = most recent)")
    for i, sub in enumerate(prev):
        sub_keys = list((sub or {}).keys())
        has_results = "results" in (sub or {})
        results_tests = []
        if has_results:
            for t in ((sub.get("results") or {}).get("tests") or []):
                results_tests.append(f"{t.get('number','?')}:extra={t.get('extra_data')}")
        lines.append(f"  [{i}] keys={sub_keys} has_results={has_results} tests={results_tests}")
    return "\n".join(lines)


if __name__ == '__main__':
    config = _load_json(os.path.join(SOURCE_DIR, "rubric.json"))
    metadata = _load_json(METADATA_PATH)

    debug_info = _metadata_debug_summary(metadata) if DEBUG_ENV == "1" else ""
    submission_note = _submission_note()
    # Outputs are Markdown (output_format "md"): plain notes are escaped.
    prefix = "\n\n".join(md_text(p) for p in (submission_note, debug_info) if p)

    lockout_message = locked_out_message(config, metadata)
    if lockout_message:
        results = locked_out_results(metadata, lockout_message)
        if prefix:
            results["output"] = prefix + "\n\n" + results["output"]
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(RESULTS_PATH, "w") as f:
            json.dump(results, f)
    else:
        attempt_recorder.clear()
        student_dispatch.clear_notes()
        student_dispatch.clear_state()
        suite = unittest.defaultTestLoader.discover('tests')
        post_processor = make_post_processor(config, metadata)

        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(RESULTS_PATH, 'w') as f:
            JSONTestRunner(visibility='visible', stream=f, buffer=False,
                           post_processor=post_processor).run(suite)

        # Shown once at the top: the script crashed part-way / ran out of time.
        grading_notes = "\n\n".join(student_dispatch.read_notes())
        prefix = "\n\n".join(md_text(p) for p in (submission_note, grading_notes, debug_info) if p)

        if prefix:
            with open(RESULTS_PATH) as f:
                results = json.load(f)
            results["output"] = prefix + "\n\n" + (results.get("output") or "")
            with open(RESULTS_PATH, 'w') as f:
                json.dump(results, f)
