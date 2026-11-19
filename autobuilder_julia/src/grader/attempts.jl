# Per-question attempt limits that lock in the best score, using Gradescope's
# /autograder/submission_metadata.json. Same behaviour and rubric fields as
# the Python autobuilder:
#
#   "attempts": N         count at most N attempted submissions for this test
#   "allow_tries": true   no cap: every attempt can still raise the best score
#
# "Attempted" means the variable/function was defined in this submission,
# right or wrong. The bookkeeping (accumulators carried forward in
# extra_data, late penalties, precheck runs, combined questions) is in
# scoring.jl.
#
# Missing or malformed metadata counts as "first submission"; never throws.

include(joinpath(@__DIR__, "scoring.jl"))

"""
    apply_attempt_limits!(results, rubric, metadata, attempted; precheck=false)

Apply attempt limits, late penalties, precheck and combine_questions to
`results` (the Gradescope results Dict) and recompute the total score.
"""
apply_attempt_limits!(results, rubric, metadata, attempted; precheck=false) =
    finalize_results!(results, rubric, metadata, attempted; precheck=precheck)

"""
    locked_out_message(rubric, metadata) -> String or nothing

When every attempt-limited test is used up (or already at full score), the
submission is not graded again; this returns the message to show instead.
"""
function locked_out_message(rubric, metadata)
    metadata isa AbstractDict || return nothing
    # Tracked: questions with an "attempts" limit, and with "late_penalties"
    # every scored question. Finished: all attempts used, or the most credit
    # it can still earn is earned (full credit, or with the late penalty that
    # applies to this submission included).
    has_limit(t) = !(get(t, "attempts", 0) in (nothing, 0))
    late = get(rubric, "late_penalties", nothing) isa AbstractVector && !isempty(rubric["late_penalties"])
    tracked = [t for t in get(rubric, "test_suite", Any[]) if has_limit(t) || (late && _score_of(t) > 0)]
    isempty(tracked) && return nothing
    isempty(previous_results(metadata)) && return nothing
    accs = previous_accumulators(metadata)
    penalty, _ = late_penalty(rubric, submission_time(metadata))

    earned = 0.0
    possible = 0.0
    attempts_ran_out = false
    for t in tracked
        used, best = get(accs, t["test_name"], (0, 0.0))
        max_score = _score_of(t)
        maxed = best >= most_credit(max_score, penalty)
        out_of_attempts = has_limit(t) && get(t, "allow_tries", false) !== true && used >= Int(t["attempts"])
        (maxed || out_of_attempts) || return nothing
        attempts_ran_out |= !maxed
        earned += best
        possible += max_score
    end
    earned >= possible - 1e-9 && return "✅ **All questions have been answered correctly.** No further submissions " *
                                        "are needed. Your score has been locked in."
    penalty > 0 && !attempts_ran_out &&
        return late_maximum_message(_fmt(round(penalty * 100; digits=6)), earned, possible)
    return "**All attempts have been used.** Your locked score is $(_fmt(round(earned; digits=6)))/$(_fmt(possible)). " *
           "No further submissions will be graded."
end

"""The previous submission's results, carried forward unchanged. `message` is Markdown."""
function locked_out_results(metadata, message)
    tests = get(previous_results(metadata), "tests", nothing)
    tests = tests isa AbstractVector ? collect(tests) : Any[]
    score = round(sum(Float64(something(get(t, "score", 0.0), 0.0)) for t in tests; init=0.0); digits=6)
    return Dict{String,Any}("score" => score, "output" => message, "output_format" => "md", "tests" => tests)
end
