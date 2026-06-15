"""
Per-question attempt limits with "lock in the max score across attempts"
semantics, using Gradescope's submission_metadata.json for cross-submission
history.

A test_suite entry can set:
  "attempts": N         -- max number of "attempted" submissions counted
                            for this question. If absent/0, no limit is
                            applied (normal grading, unchanged).
  "allow_tries": true   -- no cap: every attempted submission counts toward
                            the running max (default false, which caps at
                            the first N attempted submissions).

"Attempted" means the variable/function was successfully defined in that
submission, regardless of whether its value was correct.

This module is defensive: if submission_metadata.json is missing, empty,
or doesn't have the expected shape, it's treated as "no previous
submissions" -- this never raises.
"""


def _previous_attempts(metadata, test_name):
    """[(score, attempted), ...] for this test across previous submissions,
    oldest first. Submissions from before this feature existed (no
    extra_data) are treated as "not attempted" (benefit of the doubt, so
    students aren't retroactively charged attempts)."""
    history = []
    try:
        previous_submissions = metadata.get("previous_submissions") or []
        for sub in previous_submissions:
            results = (sub or {}).get("results") or {}
            for t in results.get("tests") or []:
                if t.get("number") == test_name:
                    score = t.get("score", 0.0) or 0.0
                    extra = t.get("extra_data") or {}
                    attempted = bool(extra.get("attempted", False))
                    history.append((float(score), attempted))
                    break
    except (AttributeError, TypeError):
        return []
    return history


def make_post_processor(config, metadata, attempt_status):
    """Returns a JSONTestRunner post_processor that applies attempt limits
    and rewrites each affected test's score/name in place."""

    def post_processor(json_data):
        tests = json_data.get("tests", [])
        by_number = {t.get("number"): t for t in tests}

        for t in config.get("test_suite", []):
            attempts_limit = t.get("attempts")
            if not attempts_limit:
                continue

            test_name = t["test_name"]
            result = by_number.get(test_name)
            if result is None:
                continue

            allow_tries = bool(t.get("allow_tries", False))

            history = _previous_attempts(metadata, test_name)
            current_attempted = bool(attempt_status.get(test_name, False))
            current_score = float(result.get("score", 0.0) or 0.0)
            history.append((current_score, current_attempted))

            attempted_scores = [score for score, attempted in history if attempted]

            kept = attempted_scores if allow_tries else attempted_scores[:int(attempts_limit)]
            locked_score = max(kept) if kept else 0.0
            result["score"] = locked_score

            used = len(attempted_scores)
            shown = used if allow_tries else min(used, int(attempts_limit))
            result["name"] = f"{result['name']} (attempt: {shown}/{int(attempts_limit)})"

            # So future submissions' submission_metadata.json can read this back.
            result["extra_data"] = {"attempted": current_attempted}

        # Recompute the overall score so it reflects any locked values above.
        if tests:
            json_data["score"] = sum(t.get("score", 0.0) or 0.0 for t in tests)

    return post_processor
