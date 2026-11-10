# Command-line entry point. From a terminal:
#
#   julia path/to/autobuilder_julia/bin/autobuilder.jl build rubric.json solution.jl
#   julia path/to/autobuilder_julia/bin/autobuilder.jl grade rubric.json solution.jl submission.jl
#
# Works without installing anything: it loads AutoBuilder from this folder.

pushfirst!(LOAD_PATH, dirname(@__DIR__))
using AutoBuilder
exit(AutoBuilder.main(ARGS))
