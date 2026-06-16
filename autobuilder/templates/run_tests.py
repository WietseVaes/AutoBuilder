import json
import os
import unittest

from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner

from autobuilder import attempt_recorder
from autobuilder.attempts import make_post_processor

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
METADATA_PATH = "/autograder/submission_metadata.json"
DEBUG_ENV = os.environ.get("AUTOBUILDER_DEBUG", "0")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _metadata_debug_summary(metadata):
    """Produce a short human-readable summary of metadata for debugging."""
    if not metadata:
        return "submission_metadata.json: not found or empty"

    lines = ["submission_metadata.json keys: " + ", ".join(str(k) for k in metadata.keys())]

    prev = metadata.get("previous_submissions") or []
    lines.append(f"previous_submissions count: {len(prev)}")

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

    attempt_recorder.clear()

    suite = unittest.defaultTestLoader.discover('tests')
    post_processor = make_post_processor(config, metadata)

    with open('/autograder/results/results.json', 'w') as f:
        JSONTestRunner(visibility='visible', stream=f, buffer=False,
                       post_processor=post_processor).run(suite)

    # Inject debug info into the top-level output field if requested.
    if debug_info:
        try:
            with open('/autograder/results/results.json') as f:
                results = json.load(f)
            results["output"] = debug_info + "\n\n" + (results.get("output") or "")
            with open('/autograder/results/results.json', 'w') as f:
                json.dump(results, f)
        except (OSError, ValueError):
            pass
