# Per-question attempt limits that lock in the best score, using Gradescope's
# /autograder/submission_metadata.json. Same behaviour and rubric fields as
# the Python autobuilder:
#
#   "attempts": N         count at most N attempted submissions for this test
#   "allow_tries": true   no cap: every attempt can still raise the best score
#
# Gradescope only shows the autograder the previous submission's results, so
# each submission carries a small accumulator forward in the test's
# extra_data: {"attempts_used": n, "best_score": s}. "Attempted" means the
# variable/function was defined in this submission, right or wrong.
#
# Missing or malformed metadata counts as "first submission"; never throws.

_fmt(x) = isinteger(x) ? string(Int(x)) : string(round(x; sigdigits=6))

function _previous_submission_tests(metadata)
    try
        prev = get(metadata, "previous_submissions", nothing)
        (prev isa AbstractVector && !isempty(prev)) || return Dict{String,Any}()
        # Newest first: [1] is the submission right before this one.
        results = get(prev[1], "results", nothing)
        results isa AbstractDict || return Dict{String,Any}()
        by_number = Dict{String,Any}()
        for t in something(get(results, "tests", nothing), Any[])
            n = get(t, "number", nothing)
            n === nothing || (by_number[string(n)] = t)
        end
        return by_number
    catch
        return Dict{String,Any}()
    end
end

function _accumulator(prev_tests, name)
    try
        t = get(prev_tests, name, nothing)
        extra = t === nothing ? nothing : get(t, "extra_data", nothing)
        if extra isa AbstractDict && haskey(extra, "attempts_used")
            return (Int(extra["attempts_used"]), Float64(something(get(extra, "best_score", 0.0), 0.0)))
        end
    catch
    end
    return (0, 0.0)
end

"""
    apply_attempt_limits!(results, rubric, metadata, attempted)

Rewrite score / name / output / extra_data of each attempt-limited test in
`results` (the Gradescope results Dict) and recompute the total score.
`attempted[test_name]` says whether the student defined the name this time.
"""
function apply_attempt_limits!(results, rubric, metadata, attempted)
    prev_tests = _previous_submission_tests(metadata)
    by_number = Dict(t["number"] => t for t in results["tests"])
    for cfg in get(rubric, "test_suite", Any[])
        limit = get(cfg, "attempts", nothing)
        (limit === nothing || limit == 0) && continue
        limit = Int(limit)
        name = cfg["test_name"]
        res = get(by_number, name, nothing)
        res === nothing && continue

        allow_tries = get(cfg, "allow_tries", false) === true
        max_score = Float64(res["max_score"])
        used, best = _accumulator(prev_tests, name)
        if get(attempted, name, false)
            within_budget = allow_tries || used < limit
            used += 1
            within_budget && (best = max(best, Float64(res["score"])))
        end
        best = min(best, max_score)

        res["score"] = best
        shown = allow_tries ? used : min(used, limit)
        res["name"] = "(attempt: $shown/$limit) $(res["name"])"
        res["extra_data"] = Dict("attempts_used" => used, "best_score" => best)
        existing = strip(get(res, "output", ""))
        res["output"] = "Locked score: $(_fmt(best))/$(_fmt(max_score))" * (isempty(existing) ? "" : "\n" * existing)
    end
    results["score"] = sum(Float64(t["score"]) for t in results["tests"]; init=0.0)
    return results
end

"""
    locked_out_message(rubric, metadata) -> String or nothing

When every attempt-limited test is used up (or already at full score), the
submission is not graded again; this returns the message to show instead.
"""
function locked_out_message(rubric, metadata)
    limited = [t for t in get(rubric, "test_suite", Any[]) if !(get(t, "attempts", 0) in (nothing, 0))]
    isempty(limited) && return nothing
    prev_tests = _previous_submission_tests(metadata)
    isempty(prev_tests) && return nothing

    earned = 0.0
    possible = 0.0
    for t in limited
        used, best = _accumulator(prev_tests, t["test_name"])
        max_score = Float64(get(t, "score", 0))
        done = best >= max_score || (get(t, "allow_tries", false) !== true && used >= Int(t["attempts"]))
        done || return nothing
        earned += best
        possible += max_score
    end
    earned >= possible && return "All questions have been answered correctly -- no further submissions " *
                                 "are needed. Your score has been locked in."
    return "All attempts have been used. Your locked score is $(_fmt(earned))/$(_fmt(possible)). " *
           "No further submissions will be graded."
end

"""The previous submission's results, carried forward unchanged."""
function locked_out_results(metadata, message)
    tests = Any[]
    try
        prev = metadata["previous_submissions"][1]["results"]
        tests = collect(something(get(prev, "tests", nothing), Any[]))
    catch
    end
    score = sum(Float64(get(t, "score", 0.0)) for t in tests; init=0.0)
    return Dict{String,Any}("score" => score, "output" => message, "tests" => tests)
end
