"""
Per-question attempt limits with "lock in the max score across attempts"
semantics, using Gradescope's submission_metadata.json.

Gradescope only gives the autograder the *immediately preceding*
submission's full results (previous_submissions[-1]["results"]) -- not the
full history. So instead of replaying history, each submission carries
forward a small accumulator in extra_data:

    {"attempts_used": int, "best_score": float}

Each run reads that accumulator from the previous submission's matching
test (matched by the @number(test_name) field), updates it based on
whether *this* submission attempted the question and what it scored, and
writes the updated accumulator back into extra_data for the next run to
pick up.

A test_suite entry can set:
  "attempts": N         -- max number of "attempted" submissions counted
                            for this question. If absent/0, no limit is
                            applied (normal grading, unchanged).
  "allow_tries": true   -- no cap: every attempted submission updates the
                            running max (default false, which stops
                            updating the max -- and stops incrementing the
                            displayed count past N -- once N attempted
                            submissions have occurred).

"Attempted" means the variable/function was successfully defined in this
submission, regardless of whether its value was correct.

This module is defensive: if submission_metadata.json is missing, empty,
or doesn't have the expected shape, it's treated as "first submission,
empty accumulator" -- this never raises.
"""


def _previous_accumulator(metadata, test_name):
    try:
        previous_submissions = metadata.get("previous_submissions") or []
        if not previous_submissions:
            return {"attempts_used": 0, "best_score": 0.0}

        last = previous_submissions[-1] or {}
        results = last.get("results") or {}
        for t in results.get("tests") or []:
            if t.get("number") == test_name:
                extra = t.get("extra_data") or {}
                return {
                    "attempts_used": int(extra.get("attempts_used", 0)),
                    "best_score": float(extra.get("best_score", 0.0)),
                }
    except (AttributeError, TypeError, ValueError):
        pass
    return {"attempts_used": 0, "best_score": 0.0}


def make_post_processor(config, metadata, attempt_status):
    """Returns a JSONTestRunner post_processor that applies attempt limits
    and rewrites each affected test's score/name/extra_data in place."""

    def post_processor(json_data):
        tests = json_data.get("tests", [])
        by_number = {t.get("number"): t for t in tests}

        for t in config.get("test_suite", []):
            attempts_limit = t.get("attempts")
            if not attempts_limit:
                continue
            attempts_limit = int(attempts_limit)

            test_name = t["test_name"]
            result = by_number.get(test_name)
            if result is None:
                continue

            allow_tries = bool(t.get("allow_tries", False))
            max_score = float(result.get("max_score", 0.0) or 0.0)
            current_score = float(result.get("score", 0.0) or 0.0)
            current_attempted = bool(attempt_status.get(test_name, False))

            prev = _previous_accumulator(metadata, test_name)
            attempts_used = prev["attempts_used"]
            best_score = prev["best_score"]

            if current_attempted:
                within_budget = allow_tries or attempts_used < attempts_limit
                attempts_used += 1
                if within_budget:
                    best_score = max(best_score, current_score)

            best_score = min(best_score, max_score)

            result["score"] = best_score
            shown = attempts_used if allow_tries else min(attempts_used, attempts_limit)
            result["name"] = f"{result['name']} (attempt: {shown}/{attempts_limit})"
            result["extra_data"] = {"attempts_used": attempts_used, "best_score": best_score}

        if tests:
            json_data["score"] = sum(t.get("score", 0.0) or 0.0 for t in tests)

    return post_processor
