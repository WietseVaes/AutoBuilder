# Plot tests for Plots.jl: compare the properties of the student's plot with
# those of the solution's plot -- never rendered pixels. Same checks, defaults
# and messages as the Python autobuilder's matplotlib plot tests:
#
#   "xlabel", "ylabel", "title"   exact string match
#   "xlim", "ylim"                axis limits (as drawn, also when automatic), tolerance
#   "n_lines"                     number of line/scatter series
#   "line_data"                   x and y data of each line/scatter series, tolerance
#   "n_bars"                      number of bars (bar charts and histograms)
#   "bar_heights"                 bar heights, tolerance
#   "legend_labels"               exact list of legend labels ([] if the legend is off)
#
# Only the first subplot is looked at. The grader itself does not load
# Plots: the plot object is inspected through its own fields, and the few
# Plots functions needed are taken from the module the plot came from.
#
# This reads some Plots.jl internals (series_list, subplot attributes), which
# are stable but not an official API. The assignment's Manifest pins the
# Plots version, so a Plots update can only break this when you rebuild with
# a newer Plots -- and then `build` reports it, because the solution is graded
# against itself first.

const DEFAULT_PLOT_CHECKS = ["xlabel", "ylabel", "title", "n_lines", "line_data"]
const PLOT_CHECKS = Set(["xlabel", "ylabel", "title", "xlim", "ylim", "n_lines", "line_data",
                         "n_bars", "bar_heights", "legend_labels"])
const _LINE_TYPES = Set([:path, :line, :steppre, :steppost, :stepmid, :scatter, :sticks, :straightline])

is_plots_plot(x) = nameof(typeof(x)) === :Plot && hasfield(typeof(x), :series_list) && hasfield(typeof(x), :subplots)

_floats(v) = v === nothing ? Float64[] : Float64[Float64(e) for e in v]

function _split_on_nan(v)
    parts, cur = Vector{Vector{Float64}}(), Float64[]
    for e in v
        if isnan(e)
            isempty(cur) || push!(parts, cur)
            cur = Float64[]
        else
            push!(cur, e)
        end
    end
    isempty(cur) || push!(parts, cur)
    return parts
end

"""
    extract_plot_info(p, checks) -> Dict

The requested properties of a Plots.jl plot, as plain values.
"""
function extract_plot_info(p, checks)
    Plots_ = parentmodule(typeof(p))
    sp = p.subplots[1]
    series = [s for s in p.series_list if s[:subplot] === sp && s[:primary] !== false]
    lines = [s for s in series if s[:seriestype] in _LINE_TYPES]
    shapes = [s for s in series if s[:seriestype] === :shape]   # what bar() and histogram() produce
    bars = Vector{Float64}[]
    for s in shapes, poly in _split_on_nan(_floats(s[:y]))
        push!(bars, poly)
    end
    info = Dict{String,Any}()
    for c in checks
        if c == "xlabel"
            info[c] = string(sp[:xaxis][:guide])
        elseif c == "ylabel"
            info[c] = string(sp[:yaxis][:guide])
        elseif c == "title"
            info[c] = string(sp[:title])
        elseif c == "xlim"
            info[c] = collect(Float64, Plots_.xlims(sp))
        elseif c == "ylim"
            info[c] = collect(Float64, Plots_.ylims(sp))
        elseif c == "n_lines"
            info[c] = length(lines)
        elseif c == "line_data"
            info[c] = [(_floats(s[:x]), _floats(s[:y])) for s in lines]
        elseif c == "n_bars"
            info[c] = length(bars)
        elseif c == "bar_heights"
            # Each bar is a rectangle [h, base, base, h, h]: the first point is its top.
            info[c] = Float64[poly[1] for poly in bars]
        elseif c == "legend_labels"
            legend_off = sp[:legend_position] in (:none, false)
            info[c] = legend_off ? String[] :
                      String[string(s[:label]) for s in series if !isempty(string(s[:label]))]
        end
    end
    return info
end

function _numbers_problem(name, s, r, rtol, atol)
    length(s) == length(r) || return ("wrong_size", "$name has the wrong number of values.")
    any(isnan, s) && return ("nans", "$name contains NaN.")
    _all_close(s, r, rtol, atol) || return ("tolerance", "$name is not within the required tolerance.")
    return nothing
end

"""
    compare_plot_info(student, reference, rtol, atol) -> (status, message)

Checks every requested property and lists *all* mismatches, not just the
first. The status is the most severe one found (wrong_type > wrong_size >
nans > tolerance), which picks the hint.
"""
function compare_plot_info(s, r, rtol, atol)
    problems = Tuple{String,String}[]
    for key in sort!(collect(keys(r)); by=k -> findfirst(==(k), ["xlabel", "ylabel", "title", "legend_labels",
                                                               "xlim", "ylim", "n_lines", "line_data",
                                                               "n_bars", "bar_heights"]))
        sv, rv = s[key], r[key]
        if key in ("xlabel", "ylabel", "title")
            sv == rv || push!(problems, ("tolerance", "'$key' does not match."))
        elseif key == "legend_labels"
            sv == rv || push!(problems, ("tolerance", "Legend labels do not match."))
        elseif key in ("n_lines", "n_bars")
            sv == rv || push!(problems, ("wrong_size", "Expected $rv for '$key', but got $sv."))
        elseif key in ("xlim", "ylim", "bar_heights")
            p = _numbers_problem("'$key'", sv, rv, rtol, atol)
            p === nothing || push!(problems, p)
        elseif key == "line_data"
            if length(sv) != length(rv)
                push!(problems, ("wrong_size", "Number of plotted lines does not match."))
                continue
            end
            for (i, ((sx, sy), (rx, ry))) in enumerate(zip(sv, rv))
                if length(sx) != length(rx) || length(sy) != length(ry)
                    push!(problems, ("wrong_size", "Line $i has the wrong number of data points."))
                elseif any(isnan, sx) || any(isnan, sy)
                    push!(problems, ("nans", "Line $i contains NaN values."))
                elseif !(_all_close(sx, rx, rtol, atol) && _all_close(sy, ry, rtol, atol))
                    push!(problems, ("tolerance", "Line $i's data does not match within tolerance."))
                end
            end
        end
    end
    isempty(problems) && return PASS
    severity = Dict("wrong_type" => 3, "wrong_size" => 2, "nans" => 1, "tolerance" => 0)
    worst = problems[argmax([severity[p[1]] for p in problems])][1]
    return (worst, "The following issues were found:\n" * join(["  - " * p[2] for p in problems], "\n"))
end

"""(status, message) for a plot test: student value vs reference plot."""
function compare_plots(student, reference, checks, rtol, atol)
    is_plots_plot(reference) || error("the solution did not produce a Plots.jl plot for this test " *
                                      "(got type $(_type_name(reference))).")
    is_plots_plot(student) || return ("wrong_type",
        "Expected a Plots.jl plot (the result of plot(...), scatter(...), bar(...), ...), " *
        "but got type $(_type_name(student)).")
    return compare_plot_info(extract_plot_info(student, checks), extract_plot_info(reference, checks), rtol, atol)
end
