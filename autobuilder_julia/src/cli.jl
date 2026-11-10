# Command line, mirroring the Python autobuilder:
#
#   autobuilder build RUBRIC SOLUTION [--inputs F] [--output F] [--timeout S]
#   autobuilder grade RUBRIC SOLUTION SUBMISSION [--inputs F] [--timeout S] [--json-out F]

const USAGE = """
Usage:
  autobuilder build RUBRIC SOLUTION [--inputs test_inputs.jl] [--output autograder.zip] [--timeout SECONDS]
  autobuilder grade RUBRIC SOLUTION SUBMISSION [--inputs test_inputs.jl] [--timeout SECONDS] [--json-out results.json]

  build   Build a Gradescope autograder zip (your solution is checked against the rubric first).
  grade   Grade one submission (a .jl/.ipynb file or a folder) locally, exactly as Gradescope would.
"""

function _parse_args(args, allowed)
    positional, options = String[], Dict{String,String}()
    i = 1
    while i <= length(args)
        a = args[i]
        if startswith(a, "--")
            key = a[3:end]
            key in allowed || error("Unknown option $a.\n\n$USAGE")
            i < length(args) || error("Option $a needs a value.")
            options[key] = args[i+1]
            i += 2
        else
            push!(positional, a)
            i += 1
        end
    end
    return positional, options
end

_timeout(opts) = haskey(opts, "timeout") ? parse(Float64, opts["timeout"]) : nothing

"""
    AutoBuilder.main(args) -> exit code

Entry point for `bin/autobuilder.jl`.
"""
function main(args=ARGS)
    if isempty(args) || args[1] in ("-h", "--help", "help")
        print(USAGE)
        return isempty(args) ? 1 : 0
    end
    command, rest = args[1], args[2:end]
    try
        if command == "build"
            pos, opts = _parse_args(rest, ("inputs", "output", "timeout"))
            length(pos) == 2 || error("build needs RUBRIC and SOLUTION.\n\n$USAGE")
            build(pos[1], pos[2]; inputs=get(opts, "inputs", nothing),
                  output=get(opts, "output", "autograder.zip"), timeout=_timeout(opts))
        elseif command == "grade"
            pos, opts = _parse_args(rest, ("inputs", "timeout", "json-out", "metadata"))
            length(pos) == 3 || error("grade needs RUBRIC, SOLUTION and SUBMISSION.\n\n$USAGE")
            grade(pos[1], pos[2], pos[3]; inputs=get(opts, "inputs", nothing), timeout=_timeout(opts),
                  json_out=get(opts, "json-out", nothing), metadata=get(opts, "metadata", nothing))
        else
            error("Unknown command \"$command\".\n\n$USAGE")
        end
    catch e
        e isa ErrorException || rethrow()
        println(stderr, "Error: ", e.msg)
        return 1
    end
    return 0
end
