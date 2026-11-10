"""
    AutoBuilder

Builds Gradescope autograders for Julia assignments from a `rubric.json`
and a solution script.

    using AutoBuilder
    grade("rubric.json", "solution.jl", "submission.jl")   # try it locally
    build("rubric.json", "solution.jl")                    # -> autograder.zip

The rubric format is shared with the Python autobuilder (autobuilder_python).
"""
module AutoBuilder

using Base64: base64encode

export build, grade

# The grader's own files (also shipped inside every autograder zip). Only the
# JSON helpers and the notebook converter (for notebook solutions) are needed
# here; the rest runs as separate scripts.
include("grader/json.jl")
include("grader/submission.jl")
const PLOT_CHECKS = Set(["xlabel", "ylabel", "title", "xlim", "ylim", "n_lines", "line_data",
                         "n_bars", "bar_heights", "legend_labels"])   # as in grader/plots.jl

include("zip.jl")
include("environment.jl")
include("build.jl")
include("cli.jl")

end
