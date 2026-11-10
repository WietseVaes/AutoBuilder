# The grading worker: runs in its own Julia process, started by run.jl as
#
#     julia [--project=env] worker.jl job.json
#
# It loads the instructor's solution and the student's submission into two
# separate modules, computes the reference value and the student's value for
# every test, compares them, and appends one JSON line per test to the output
# file as it goes. Because each result is written (and flushed) immediately,
# a submission that hangs or crashes on test 7 still keeps tests 1-6.
#
# Output lines:
#   {"event": "script_error", "who": "student"|"solution", "message": ...}
#   {"event": "test", "test_name": ..., "kind": ..., ...}   one per test
#       kind = "compared"         status + message from compare_values
#              "missing"          name not defined (detail: why, if known)
#              "call_error"       reading/calling it raised an error
#              "autograder_error" the solution / rubric failed on this test
#   {"event": "done"}

include(joinpath(@__DIR__, "json.jl"))
include(joinpath(@__DIR__, "values.jl"))
include(joinpath(@__DIR__, "compare.jl"))
include(joinpath(@__DIR__, "plots.jl"))

# There is no screen on Gradescope: make the GR backend of Plots.jl draw
# nowhere, so a submission that calls display(...) or savefig(...) still works.
ENV["GKSwstype"] = "100"

# Top-level Pkg calls in a submission (Pkg.add, Pkg.activate, Pkg.instantiate,
# ...) are skipped: grading never installs anything, and the packages the
# assignment allows are already there. Without this, a notebook starting with
# Pkg.add("Plots") would stop at that line and score nothing. A package that
# isn't available still fails clearly, at `using`.
_is_pkg_call(ex) = ex isa Expr && ex.head === :call && ex.args[1] isa Expr &&
                   ex.args[1].head === :. && ex.args[1].args[1] === :Pkg
function skip_pkg_calls(ex)
    ex isa Expr && ex.head === :toplevel && return Expr(:toplevel, map(skip_pkg_calls, ex.args)...)
    return _is_pkg_call(ex) ? nothing : ex
end

# A fresh module to run a script in, with `include` and `eval` defined the
# way they are inside a normal `module ... end` block, so scripts can
# include their own helper files. `mapexpr` is applied to every top-level
# expression of the script and of the files it includes.
function new_script_module(name::Symbol; mapexpr=identity)
    m = Module(name)
    Core.eval(m, :(include(path::AbstractString) = Base.include($mapexpr, $m, path)))
    Core.eval(m, :(include(f::Function, path::AbstractString) = Base.include(x -> f($mapexpr(x)), $m, path)))
    Core.eval(m, :(eval(x) = Core.eval($m, x)))
    return m
end

# A short, student-friendly description of an error: the error message
# (without the stack trace) plus the line in the student's own file where
# it happened, when that can be found.
function describe_error(e, bt, script_path)
    location = ""
    while e isa LoadError
        location = " (at $(basename(string(e.file))):$(e.line))"
        e = e.error
    end
    msg = strip(sprint(showerror, e))
    # The modules the scripts run in are an implementation detail.
    msg = replace(msg, r" in `Main\.(Submission|Solution|TestInputs)`" => "",
                       r"Main\.(Submission|Solution|TestInputs)\." => "")
    if isempty(location) && script_path !== nothing && bt !== nothing
        for frame in stacktrace(bt)
            f = string(frame.file)
            if !isempty(f) && basename(f) == basename(script_path)
                location = " (at $(basename(script_path)):$(frame.line))"
                break
            end
        end
    end
    # The location goes on the first line; newer Julia versions add
    # suggestion lines after it, which are kept (up to 4 lines in total).
    lines = String.(split(msg, '\n'))
    lines[1] = lines[1] * location
    msg = join(lines[1:min(end, 4)], '\n') * (length(lines) > 4 ? "\n..." : "")
    length(msg) > 600 && (msg = first(msg, 600) * "...")
    return msg
end

function load_script(m::Module, path::String; mapexpr=identity)
    try
        Base.include(mapexpr, m, path)
        return nothing
    catch e
        return describe_error(e, catch_backtrace(), path)
    end
end

# Only names the script itself defined count -- not names it can merely see
# through `using Base` (otherwise a rubric asking for a function `step` would
# "find" Base.step in a submission that never defined it).
function defines(m::Module, name::AbstractString)
    sym = name_symbol(name)
    return sym in names(m; all=true) && isdefined(m, sym)
end

struct NotDefined end

function fetch_value(m::Module, t, inputs)
    kind = get(t, "type", "variable")
    # A plot test reads a variable holding a plot, or calls a function returning one.
    if kind == "variable" || (kind == "plot" && !haskey(t, "function_name"))
        name = t["variable_name"]
        defines(m, name) || return NotDefined()
        return getglobal(m, name_symbol(name))
    end
    name = t["function_name"]
    defines(m, name) || return NotDefined()
    f = getglobal(m, name_symbol(name))
    out = f(deepcopy(inputs)...)
    idx = get(t, "output_index", nothing)
    # output_index is 0-based in rubric.json (shared with the Python autobuilder).
    idx === nothing || (out = out[idx+1])
    return out
end

function grade_test(t, sol, stu, inputs_mod, student_script_error, solution_path, student_path)
    name = t["test_name"]
    result = Dict{String,Any}("event" => "test", "test_name" => name)

    # Reference value: the rubric's "expected", or the solution's own answer.
    local inputs, expected
    try
        inputs = Any[resolve_value(x, inputs_mod) for x in get(t, "inputs", Any[])]
        if haskey(t, "expected")
            expected = resolve_value(t["expected"], inputs_mod)
        else
            sol === nothing && error("the solution could not be loaded.")
            expected = fetch_value(sol, t, inputs)
            expected isa NotDefined && error("the solution does not define what this test asks for.")
        end
        if get(t, "type", "variable") == "plot" && !is_plots_plot(expected)
            error("the solution did not produce a Plots.jl plot for this test (got type $(_type_name(expected))).")
        end
    catch e
        result["kind"] = "autograder_error"
        result["detail"] = describe_error(e, catch_backtrace(), solution_path)
        return result
    end

    # Student value.
    local actual
    try
        actual = fetch_value(stu, t, inputs)
    catch e
        result["kind"] = "call_error"
        result["detail"] = describe_error(e, catch_backtrace(), student_path)
        return result
    end
    if actual isa NotDefined
        result["kind"] = "missing"
        result["detail"] = student_script_error
        return result
    end

    is_plot = get(t, "type", "variable") == "plot"
    # Plot data is usually less precision-sensitive: looser default tolerances, as in Python.
    rtol = Float64(get(t, "rtol", is_plot ? 1e-2 : 1e-6))
    atol = Float64(get(t, "atol", is_plot ? 1e-2 : 1e-6))
    status, message = try
        is_plot ? compare_plots(actual, expected, get(t, "plot_checks", DEFAULT_PLOT_CHECKS), rtol, atol) :
                  compare_values(actual, expected, rtol, atol)
    catch e
        ("wrong_type", "Your value could not be compared with the expected answer: " *
                       describe_error(e, nothing, nothing))
    end
    result["kind"] = "compared"
    result["status"] = status
    result["message"] = message
    return result
end

function emit(io, d)
    println(io, json_string(d))
    flush(io)
end

function main(job_path)
    job = json_parsefile(job_path)
    out = open(job["out"], "w")
    cd(job["cwd"])

    inputs_mod = nothing
    if job["inputs_file"] !== nothing
        inputs_mod = new_script_module(:TestInputs)
        err = load_script(inputs_mod, job["inputs_file"])
        err === nothing || emit(out, Dict("event" => "script_error", "who" => "inputs", "message" => err))
    end

    solution_path = job["solution"]
    sol = nothing
    if solution_path !== nothing
        sol = new_script_module(:Solution; mapexpr=skip_pkg_calls)
        err = load_script(sol, solution_path; mapexpr=skip_pkg_calls)
        err === nothing || emit(out, Dict("event" => "script_error", "who" => "solution", "message" => err))
    end

    student_path = job["student"]
    stu = new_script_module(:Submission; mapexpr=skip_pkg_calls)
    student_err = load_script(stu, student_path; mapexpr=skip_pkg_calls)
    student_err === nothing ||
        emit(out, Dict("event" => "script_error", "who" => "student", "message" => student_err))

    # Everything the scripts defined lives in a newer "world" than this
    # function was compiled in; invokelatest makes all of it visible.
    for t in job["tests"]
        res = Base.invokelatest(grade_test, t, sol, stu, inputs_mod, student_err, solution_path, student_path)
        emit(out, res)
    end
    emit(out, Dict("event" => "done"))
    close(out)
end

main(ARGS[1])
