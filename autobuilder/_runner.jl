#!/usr/bin/env julia
# Vendored into the autograder zip. Run as:
#   julia _runner.jl <script_path> <output_path> <tests_json>
#
# Mirrors autobuilder/_runner.py: includes a script once, then for each
# requested test either reads a global variable or calls a function with
# given inputs, and writes a single JSON result file.
#
# Output JSON shape (matches what python_adapter.py expects from
# run_python_script, so grader.py / codegen-generated comparisons don't
# need to know which language produced the result):
#   {
#     "_error": <string or null>,
#     "values": {test_name: <json-safe value>, ...},
#     "_missing": [test_name, ...],
#     "_call_errors": {test_name: <string>, ...}
#   }
#
# Value serialization:
#   Number, String, Bool      -> as-is
#   Vector, Matrix, Tuple     -> nested JSON arrays (row-major for matrices)
#   missing/NaN entries       -> kept as NaN (JSON.jl encodes as "NaN" string
#                                 by default; we post-process to a literal
#                                 `NaN` token the Python side specifically
#                                 understands -- see _to_jsonsafe below)

import JSON

function to_jsonsafe(x)
    if x isa AbstractArray
        return [to_jsonsafe(v) for v in eachrow_or_self(x)]
    elseif x isa Tuple
        return [to_jsonsafe(v) for v in x]
    elseif x isa Number
        if x isa AbstractFloat && isnan(x)
            return "__NaN__"
        end
        return x
    else
        return x
    end
end

# Matrices serialize row-major as a list of row-lists; vectors serialize as
# a flat list. (Julia stores matrices column-major internally, but the
# *logical* row/col structure -- what numpy.asarray would produce from the
# same nested list on the Python side -- is row-major, so we iterate rows.)
function eachrow_or_self(x::AbstractMatrix)
    return (collect(x[i, :]) for i in 1:size(x, 1))
end
function eachrow_or_self(x::AbstractVector)
    return x
end
function eachrow_or_self(x::AbstractArray)
    return x  # higher-dimensional arrays: best effort, flatten via collect
end

function defined_names(mod)
    return sort([string(n) for n in names(mod, all=true)
                 if !startswith(string(n), "#") && n != :eval && n != :include])
end

function main()
    script_path, output_path, tests_json = ARGS[1], ARGS[2], ARGS[3]
    tests = JSON.parse(tests_json)

    result = Dict(
        "_error" => nothing,
        "values" => Dict{String, Any}(),
        "_missing" => String[],
        "_call_errors" => Dict{String, Any}(),
        "_debug_defined_names" => String[],
    )

    mod = Module(:StudentSolution)

    try
        Base.eval(mod, :(include($script_path)))
    catch e
        msg_io = IOBuffer()
        showerror(msg_io, e)
        backtrace_io = IOBuffer()
        Base.show_backtrace(backtrace_io, catch_backtrace())
        # First line is the actual error (e.g. "UndefVarError: `x` not
        # defined" or "LoadError: ..."), which is what matters to a
        # student -- the backtrace after it is mostly internal Julia call
        # stack frames, kept for instructors who want the full detail.
        result["_error"] = String(take!(msg_io)) * "\n" * String(take!(backtrace_io))
        open(output_path, "w") do f
            JSON.print(f, result)
        end
        return
    end

    result["_debug_defined_names"] = defined_names(mod)

    for t in tests
        name = t["name"]

        if t["type"] == "variable"
            varname = Symbol(t["variable_name"])
            if isdefined(mod, varname)
                try
                    result["values"][name] = to_jsonsafe(getfield(mod, varname))
                catch e
                    io = IOBuffer()
                    showerror(io, e)
                    result["_call_errors"][name] = String(take!(io))
                end
            else
                push!(result["_missing"], name)
            end

        elseif t["type"] == "function"
            fname = Symbol(t["function_name"])
            if !isdefined(mod, fname) || !(getfield(mod, fname) isa Function)
                push!(result["_missing"], name)
                continue
            end
            f = getfield(mod, fname)
            inputs = get(t, "inputs", [])
            try
                output = Base.invokelatest(f, inputs...)
                if get(t, "output_index", nothing) !== nothing
                    # JSON test specs use 0-based indices (Python convention);
                    # Julia is 1-based.
                    output = output[t["output_index"] + 1]
                end
                result["values"][name] = to_jsonsafe(output)
            catch e
                io = IOBuffer()
                showerror(io, e)
                result["_call_errors"][name] = String(take!(io))
            end
        end
    end

    open(output_path, "w") do f
        JSON.print(f, result)
    end

    # Diagnostic for the "everything reports missing but the script ran fine"
    # failure mode: if every requested variable/function came back missing,
    # something structural is wrong with how names are being looked up
    # (rather than a typo in one rubric entry) -- surface what was actually
    # defined so this is debuggable from the test output directly.
    if length(result["_missing"]) == length(tests) && length(tests) > 0
        result["_error"] = (
            "Diagnostic: every requested name was reported as not defined, " *
            "but the script ran without error. Names actually defined: " *
            join(result["_debug_defined_names"], ", ")
        )
        open(output_path, "w") do f
            JSON.print(f, result)
        end
    end
end

main()
