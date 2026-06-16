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


def _check_locked_out(config, metadata):
    """Return a message if all attempt-limited questions are exhausted
    (either full credit earned or all attempts used), otherwise None."""
    test_suite = config.get("test_suite", [])
    limited = [t for t in test_suite if t.get("attempts")]
    if not limited:
        return None

    prev = (metadata.get("previous_submissions") or [])
    if not prev:
        return None

    # previous_submissions[0] is the most recent submission.
    last_results = (prev[0] or {}).get("results") or {}
    by_number = {}
    for t in last_results.get("tests") or []:
        num = t.get("number")
        if num:
            by_number[num] = t

    exhausted = []
    not_exhausted = []
    for t in limited:
        name = t["test_name"]
        limit = int(t["attempts"])
        max_score = float(t.get("score", 0))
        allow_tries = bool(t.get("allow_tries", False))

        result = by_number.get(name) or {}
        extra = result.get("extra_data") or {}
        attempts_used = int(extra.get("attempts_used", 0))
        best_score = float(extra.get("best_score", 0.0))

        if allow_tries:
            # Unlimited -- only lock out if full credit already earned.
            if best_score >= max_score:
                exhausted.append(name)
            else:
                not_exhausted.append(name)
        else:
            if attempts_used >= limit or best_score >= max_score:
                exhausted.append(name)
            else:
                not_exhausted.append(name)

    if not_exhausted:
        return None  # at least one question still has attempts left

    # All attempt-limited questions are done.
    earned = sum(
        float(((by_number.get(t["test_name"]) or {}).get("extra_data") or {}).get("best_score", 0.0))
        for t in limited
    )
    total_possible = sum(float(t.get("score", 0)) for t in limited)

    if earned >= total_possible:
        return (
            "All questions have been answered correctly -- "
            "no further submissions are needed. Your score has been locked in."
        )
    else:
        return (
            "All attempts have been used. "
            f"Your locked score is {earned:g}/{total_possible:g}. "
            "No further submissions will be graded."
        )


def _write_locked_out(message, config, metadata):
    """Write a results.json that carries forward the previous locked scores
    and shows the lockout message, without re-running any tests."""
    prev = (metadata.get("previous_submissions") or [])
    last_results = ((prev[0] or {}).get("results") or {}) if prev else {}

    # Carry forward the previous test results unchanged.
    tests = list(last_results.get("tests") or [])
    total = sum(float(t.get("score", 0.0) or 0.0) for t in tests)

    results = {
        "score": total,
        "output": message,
        "tests": tests,
    }
    os.makedirs("/autograder/results", exist_ok=True)
    with open("/autograder/results/results.json", "w") as f:
        json.dump(results, f)


if __name__ == '__main__':
    config = _load_json(os.path.join(SOURCE_DIR, "rubric.json"))
    metadata = _load_json(METADATA_PATH)

    debug_info = _metadata_debug_summary(metadata) if DEBUG_ENV == "1" else ""

    lockout_message = _check_locked_out(config, metadata)
    if lockout_message:
        _write_locked_out(lockout_message, config, metadata)
        if debug_info:
            with open("/autograder/results/results.json") as f:
                results = json.load(f)
            results["output"] = debug_info + "\n\n" + results.get("output", "")
            with open("/autograder/results/results.json", "w") as f:
                json.dump(results, f)
    else:
        attempt_recorder.clear()
        suite = unittest.defaultTestLoader.discover('tests')
        post_processor = make_post_processor(config, metadata)

        with open('/autograder/results/results.json', 'w') as f:
            JSONTestRunner(visibility='visible', stream=f, buffer=False,
                           post_processor=post_processor).run(suite)

        if debug_info:
            with open('/autograder/results/results.json') as f:
                results = json.load(f)
            results["output"] = debug_info + "\n\n" + (results.get("output") or "")
            with open('/autograder/results/results.json', 'w') as f:
                json.dump(results, f)
