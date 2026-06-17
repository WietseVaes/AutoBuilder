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

# ---------------------------------------------------------------------------
# Plot extraction (Plots.jl)
# ---------------------------------------------------------------------------
# Works via duck-typing: accesses .subplots / .series_list without importing
# Plots, so _runner.jl itself doesn't need `using Plots` -- the student's
# script already loaded it into their module.

function _safe_collect(v)
    v === nothing && return Float64[]
    try; return collect(Float64, v); catch; end
    try; return collect(v); catch; end
    return []
end

function _extract_plot_info(p, checks)
    info = Dict{String, Any}()
    sp = p.subplots[1]

    _line_types = Set([:path, :line, :steppre, :steppost, :stepmid])
    line_series = filter(s -> get(s.plotattributes, :seriestype, :path) in _line_types, p.series_list)
    bar_series  = filter(s -> get(s.plotattributes, :seriestype, :path) == :bar,        p.series_list)

    for check in checks
        if check == "xlabel"
            info["xlabel"] = string(sp[:xaxis][:guide])
        elseif check == "ylabel"
            info["ylabel"] = string(sp[:yaxis][:guide])
        elseif check == "title"
            info["title"] = string(sp[:title])
        elseif check == "xlim"
            lims = sp[:xaxis][:lims]
            info["xlim"] = lims == :auto ? nothing : [Float64(lims[1]), Float64(lims[2])]
        elseif check == "ylim"
            lims = sp[:yaxis][:lims]
            info["ylim"] = lims == :auto ? nothing : [Float64(lims[1]), Float64(lims[2])]
        elseif check == "n_lines"
            info["n_lines"] = length(line_series)
        elseif check == "line_data"
            info["line_data"] = [
                let x = s[:x], y = s[:y]
                    x_vals = x === nothing ? collect(eachindex(y)) : _safe_collect(x)
                    [x_vals, _safe_collect(y)]
                end
                for s in line_series
            ]
        elseif check == "n_bars"
            info["n_bars"] = isempty(bar_series) ? 0 : sum(length(s[:y]) for s in bar_series)
        elseif check == "bar_heights"
            info["bar_heights"] = isempty(bar_series) ? Float64[] :
                vcat([_safe_collect(s[:y]) for s in bar_series]...)
        elseif check == "legend_labels"
            info["legend_labels"] = [
                string(s[:label]) for s in p.series_list
                if s[:label] !== false && string(s[:label]) != ""
            ]
        end
    end
    return info
end

# ---------------------------------------------------------------------------

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
        Base.include(mod, script_path)
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
                    val = getfield(mod, varname)
                    plot_checks = get(t, "plot_checks", nothing)
                    result["values"][name] = plot_checks !== nothing ?
                        Base.invokelatest(_extract_plot_info, val, plot_checks) : to_jsonsafe(val)
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
                plot_checks = get(t, "plot_checks", nothing)
                if plot_checks !== nothing
                    # Plot test: extract a plain dict from the Plots.jl object.
                    # invokelatest is required: Plots methods are defined in a newer
                    # world than _runner.jl's main() (loaded via `using Plots` in the
                    # student script), so a direct call would be a world-age error.
                    result["values"][name] = Base.invokelatest(_extract_plot_info, output, plot_checks)
                else
                    if get(t, "output_index", nothing) !== nothing
                        # JSON test specs use 0-based indices (Python convention);
                        # Julia is 1-based.
                        output = output[t["output_index"] + 1]
                    end
                    result["values"][name] = to_jsonsafe(output)
                end
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
