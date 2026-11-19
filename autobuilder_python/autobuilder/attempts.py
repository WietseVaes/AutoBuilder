"""
Per-question attempt limits with "lock in the max score across attempts"
semantics, using Gradescope's submission_metadata.json.

A test_suite entry can set:
  "attempts": N         -- max number of "attempted" submissions counted
                            for this question. If absent/0, no limit is
                            applied (normal grading, unchanged).
  "allow_tries": true   -- no cap: every attempted submission can still
                            raise the running max (default false, which
                            stops updating the max -- and stops
                            incrementing the displayed count past N --
                            once N attempted submissions have occurred).

"Attempted" means the variable/function was successfully defined in this
submission, regardless of whether its value was correct. This is recorded
by each generated test via autobuilder.attempt_recorder and read back here.

The bookkeeping itself (accumulators carried forward in extra_data, late
penalties, precheck runs, combined questions) lives in scoring.py.
"""

from . import attempt_recorder
from . import scoring


def _precheck_run():
    try:
        from . import student_dispatch
        return student_dispatch.read_state().get("precheck") is True
    except Exception:
        return False


def make_post_processor(config, metadata):
    """Returns a JSONTestRunner post_processor that applies precheck, attempt
    limits, late penalties and combine_questions to the results in place."""

    def post_processor(json_data):
        scoring.finalize(json_data, config, metadata, attempt_recorder.load(),
                         precheck=_precheck_run())

    return post_processor


def locked_out_message(config, metadata):
    """A message if every tracked question is finished, otherwise None.

    Tracked: questions with an "attempts" limit, and with "late_penalties"
    every scored question. Finished: all attempts used, or the most credit it
    can still earn is earned (full credit, or with the late penalty that
    applies to this submission included)."""
    late = bool(config.get("late_penalties"))
    tracked = [t for t in config.get("test_suite", [])
               if t.get("attempts") or (late and float(t.get("score", 0) or 0) > 0)]
    if not tracked or not scoring.previous_results(metadata):
        return None
    accs = scoring.previous_accumulators(metadata)
    penalty, _ = scoring.late_penalty(config, scoring.submission_time(metadata))

    earned = possible = 0.0
    attempts_ran_out = False
    for t in tracked:
        used, best = accs.get(t["test_name"], (0, 0.0))
        max_score = float(t.get("score", 0) or 0)
        maxed = best >= scoring.most_credit(max_score, penalty)
        out_of_attempts = bool(t.get("attempts")) and t.get("allow_tries") is not True \
            and used >= int(t["attempts"])
        if not (maxed or out_of_attempts):
            return None
        attempts_ran_out |= not maxed
        earned += best
        possible += max_score

    if earned >= possible - 1e-9:
        return ("✅ **All questions have been answered correctly.** "
                "No further submissions are needed. Your score has been locked in.")
    if penalty > 0 and not attempts_ran_out:
        return scoring.late_maximum_message(scoring._fmt(round(penalty * 100, 6)), earned, possible)
    return (f"**All attempts have been used.** Your locked score is "
            f"{scoring._fmt(round(earned, 6))}/{scoring._fmt(possible)}. "
            "No further submissions will be graded.")


def locked_out_results(metadata, message):
    """The previous submission's results, carried forward unchanged.
    `message` is Markdown."""
    tests = list(scoring.previous_results(metadata).get("tests") or [])
    return {
        "score": round(sum(float(t.get("score", 0.0) or 0.0) for t in tests), 6),
        "output": message,
        "output_format": "md",
        "tests": tests,
    }
