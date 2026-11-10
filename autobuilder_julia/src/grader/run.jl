# Gradescope entry point, called by run_autograder as
#
#     cd /autograder/source && julia grader/run.jl
#
# 1. If every attempt-limited question is used up, re-post the locked scores.
# 2. Find the student's file in /autograder/submission (submission.jl).
# 3. Run worker.jl in a separate Julia process (with the course environment
#    in env/, if any), killing it after the timeout.
# 4. Turn each test's outcome into a Gradescope test result with the right
#    hint, apply attempt limits, and write /autograder/results/results.json.
#
# The /autograder paths can be overridden with environment variables, which
# is how `AutoBuilder.grade` and `AutoBuilder.build` run this same file
# locally: AUTOBUILDER_SUBMISSION_DIR, AUTOBUILDER_RESULTS_DIR,
# AUTOBUILDER_METADATA_PATH.

include(joinpath(@__DIR__, "json.jl"))
include(joinpath(@__DIR__, "submission.jl"))
include(joinpath(@__DIR__, "attempts.jl"))

const SOURCE_DIR = dirname(@__DIR__)
const SUBMISSION_DIR = get(ENV, "AUTOBUILDER_SUBMISSION_DIR", "/autograder/submission")
const RESULTS_DIR = get(ENV, "AUTOBUILDER_RESULTS_DIR", "/autograder/results")
const METADATA_PATH = get(ENV, "AUTOBUILDER_METADATA_PATH", "/autograder/submission_metadata.json")

read_json_or_empty(path) = try json_parsefile(path) catch; Dict{String,Any}() end

# ── Running the worker ────────────────────────────────────────────────────

function worker_command(job_path)
    env_dir = joinpath(SOURCE_DIR, "env")
    has_env = isfile(joinpath(env_dir, "Project.toml"))
    # Without a course environment, point the active project at an empty
    # throwaway folder: a submission calling Pkg.add must never modify the
    # default environment (on your own machine, when grading locally).
    project = has_env ? env_dir : mkpath(joinpath(dirname(job_path), "empty_project"))
    flags = ["--startup-file=no", "--history-file=no", "--project=$project"]
    cmd = `$(Base.julia_cmd()) $flags $(joinpath(@__DIR__, "worker.jl")) $job_path`

    env = Dict{String,String}(k => v for (k, v) in ENV if k != "JULIA_PROJECT")
    # Only the course environment and the standard library are visible, so a
    # package that works on the instructor's machine but is not part of the
    # assignment's environment fails locally too, not just on Gradescope.
    sep = Sys.iswindows() ? ";" : ":"
    env["JULIA_LOAD_PATH"] = has_env ? "@$(sep)@stdlib" : "@stdlib"
    # Grading never installs packages (Pkg.add in a submission fails fast).
    env["JULIA_PKG_OFFLINE"] = "true"
    return setenv(cmd, env)
end

"""
Run the worker; returns (events, timed_out, log) where events are the
parsed JSON lines it wrote and log is everything the scripts printed.
"""
function run_worker(student_path, tests, timeout)
    work = mktempdir()
    out_path = joinpath(work, "results.jsonl")
    log_path = joinpath(work, "output.log")
    job_path = joinpath(work, "job.json")
    inputs = joinpath(SOURCE_DIR, "test_inputs.jl")
    job = Dict(
        "solution" => joinpath(SOURCE_DIR, "solution.jl"),
        "student" => student_path,
        "inputs_file" => isfile(inputs) ? inputs : nothing,
        "tests" => tests,
        "out" => out_path,
        "cwd" => SOURCE_DIR,
    )
    write(job_path, json_string(job))

    timed_out = false
    open(log_path, "w") do log
        p = run(pipeline(worker_command(job_path); stdin=devnull, stdout=log, stderr=log); wait=false)
        if timedwait(() -> process_exited(p), Float64(timeout); pollint=0.2) === :timed_out
            timed_out = true
            kill(p)
            timedwait(() -> process_exited(p), 5.0) === :timed_out && kill(p, Base.SIGKILL)
        end
    end

    events = Any[]
    if isfile(out_path)
        for line in eachline(out_path)
            isempty(strip(line)) && continue
            try
                push!(events, json_parse(line))
            catch
            end
        end
    end
    log = try read(log_path, String) catch; "" end
    rm(work; recursive=true, force=true)
    return events, timed_out, log
end

# ── Turning outcomes into Gradescope test results ─────────────────────────

# Most specific hint: hint_<key>_julia, then hint_<key>, then the fallback key.
function hint(t, key, fallback=nothing)
    for k in (key * "_julia", key)
        v = get(t, k, "")
        v isa AbstractString && !isempty(v) && return v
    end
    return fallback === nothing ? "" : hint(t, fallback)
end

hint_suffix(h, image_md=nothing) =
    (isempty(h) ? "" : "\nHint: " * h) * (image_md === nothing ? "" : "\n\n" * image_md)

"""(calls, name, "Variable 'x'" / "Function 'f'") for a test."""
function test_target(t)
    calls = haskey(t, "function_name") && get(t, "type", "variable") != "variable"   # function test, or plot test of a function
    name = calls ? t["function_name"] : t["variable_name"]
    return calls, name, calls ? "Function '$name'" : "Variable '$name'"
end

"""Outcome when the script crashed and "grade_until_crash" is off: every test fails with the crash message."""
function crash_outcome(t, crash)
    _, _, what = test_target(t)
    return (false, false, "$what is not defined. ($crash)" * hint_suffix(hint(t, "hint_not_defined", "hint_wrong_size")))
end

"""(passed, attempted, output) for one test."""
function test_outcome(t, ev, timeout, timed_out, image_md)
    calls, name, what = test_target(t)
    h_not_defined = hint(t, "hint_not_defined", "hint_wrong_size")

    if ev === nothing
        msg = timed_out ?
            "Your code did not finish within $timeout seconds, so this test could not be completed." :
            "Grading stopped unexpectedly before this test could run (does your code call exit()?)."
        return (false, false, msg)
    end

    kind = ev["kind"]
    if kind == "autograder_error"
        return (false, false, "Autograder error on this test: $(ev["detail"]) Please let your instructor know.")
    elseif kind == "missing"
        # (The error itself is shown once, at the top of the results.)
        extra = get(ev, "detail", nothing) === nothing ? "" : " Your code stopped with an error before reaching it."
        return (false, false, "$what is not defined.$extra" * hint_suffix(h_not_defined))
    elseif kind == "call_error"
        verb = calls ? "calling" : "reading"
        return (false, true, "Your code raised an error when $verb '$name': $(ev["detail"])" * hint_suffix(h_not_defined))
    end

    status = ev["status"]
    status == "pass" && return (true, true, "")
    h = status == "wrong_type" ? hint(t, "hint_wrong_type", "hint_wrong_size") :
        status == "wrong_size" ? hint(t, "hint_wrong_size") :
        status == "nans"       ? hint(t, "hint_nans", "hint_tolerance") :
                                 hint(t, "hint_tolerance")
    img = status in ("nans", "tolerance") ? image_md : nothing
    return (false, true, ev["message"] * hint_suffix(h, img))
end

function grade(rubric, build_info, metadata)
    tests_cfg = get(rubric, "test_suite", Any[])
    timeout = get(build_info, "timeout", 600)
    timeout isa AbstractFloat && isinteger(timeout) && (timeout = Int(timeout))   # "40 seconds", not "40.0"
    hint_images = get(build_info, "hint_images", Dict{String,Any}())
    notes = String[]

    student_path, _, note = find_submission(SUBMISSION_DIR, required_names(rubric))
    note === nothing || push!(notes, note)

    # rubric.json "grade_until_crash" (default false): when the student's
    # script crashes part-way, grade everything it defined before the crash
    # (true), or fail every test with the crash message (false).
    grade_until_crash = get(rubric, "grade_until_crash", false) === true
    crash = nothing   # the crash message, when every test fails because of it

    by_test = Dict{String,Any}()
    timed_out = false
    log = ""
    if student_path !== nothing
        events, timed_out, log = run_worker(student_path, tests_cfg, timeout)
        for ev in events
            if ev["event"] == "test"
                by_test[ev["test_name"]] = ev
            elseif ev["event"] == "script_error"
                who = ev["who"]
                if who == "student" && grade_until_crash
                    push!(notes, "Your code stopped with an error: $(ev["message"])\n" *
                                 "Everything defined before that point was still graded.")
                elseif who == "student"
                    crash = first(split(ev["message"], '\n'))
                else
                    push!(notes, "Autograder error: the $(who == "solution" ? "reference solution" : "test inputs file") " *
                                 "failed to run ($(ev["message"])). Please let your instructor know.")
                end
            end
        end
        timed_out && push!(notes, "Your code did not finish within $timeout seconds.")
    end

    results_tests = Any[]
    attempted = Dict{String,Bool}()
    for t in tests_cfg
        name = t["test_name"]
        image_md = get(hint_images, name, nothing)
        passed, tried, output = if student_path === nothing
            (false, false, "No submission file was found.")
        elseif crash !== nothing
            crash_outcome(t, crash)
        else
            test_outcome(t, get(by_test, name, nothing), timeout, timed_out, image_md)
        end
        attempted[name] = tried
        max_score = get(t, "score", 0)
        r = Dict{String,Any}(
            "name" => get(t, "description", name),
            "number" => name,
            "score" => passed ? max_score : 0,
            "max_score" => max_score,
            "status" => passed ? "passed" : "failed",
            "output" => output,
            "visibility" => "visible",
        )
        image_md === nothing || (r["output_format"] = "md")
        push!(results_tests, r)
    end

    if get(rubric, "debug", false) === true && !isempty(strip(log))
        tail = length(log) > 3000 ? "..." * last(log, 3000) : log
        push!(notes, "Debug -- everything printed while grading:\n" * tail)
    end

    results = Dict{String,Any}("tests" => results_tests, "output" => join(notes, "\n\n"))
    apply_attempt_limits!(results, rubric, metadata, attempted)
    return results
end

function main()
    rubric = json_parsefile(joinpath(SOURCE_DIR, "rubric.json"))
    build_info = read_json_or_empty(joinpath(SOURCE_DIR, "build_info.json"))
    metadata = read_json_or_empty(METADATA_PATH)

    lock_message = locked_out_message(rubric, metadata)
    results = lock_message === nothing ? grade(rubric, build_info, metadata) :
                                         locked_out_results(metadata, lock_message)
    mkpath(RESULTS_DIR)
    write(joinpath(RESULTS_DIR, "results.json"), json_string(results; indent=2))
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main()
