# Building the autograder zip, and running it locally.
#
# Zip layout (unzipped to /autograder/source on Gradescope):
#
#   run_autograder      runs grader/run.jl
#   setup.sh            installs Julia (the version used to build) + env/
#   rubric.json         your rubric, unchanged
#   build_info.json     timeout, embedded hint images, versions
#   solution.jl         your solution (run next to each submission)
#   test_inputs.jl      optional: values for "$name" references
#   env/                optional: Project.toml + Manifest.toml
#   grader/             the grader (standard library only)
#   <extra_files>       data files, at the same relative paths

const GRADER_DIR = joinpath(@__DIR__, "grader")
const GRADER_FILES = ["json.jl", "values.jl", "compare.jl", "worker.jl",
                      "submission.jl", "attempts.jl", "run.jl", "plots.jl"]
const DEFAULT_TIMEOUT = 600
const RESERVED = Set(["run_autograder", "setup.sh", "rubric.json", "build_info.json",
                      "solution.jl", "test_inputs.jl"])
const _IMAGE_MIME = Dict(".png" => "image/png", ".jpg" => "image/jpeg", ".jpeg" => "image/jpeg",
                         ".gif" => "image/gif", ".svg" => "image/svg+xml")

const RUN_AUTOGRADER = """
#!/usr/bin/env bash
export JULIA_DEPOT_PATH=/opt/julia_depot
cd /autograder/source
julia --startup-file=no --history-file=no grader/run.jl
"""

const SETUP_SH = raw"""
#!/usr/bin/env bash
set -ex
JULIA_VERSION="@@JULIA_VERSION@@"
export JULIA_DEPOT_PATH=/opt/julia_depot

apt-get update
apt-get install -y curl ca-certificates

if ! julia --version 2>/dev/null | grep -q "version ${JULIA_VERSION}$"; then
    curl -fsSL "https://julialang-s3.julialang.org/bin/linux/x64/${JULIA_VERSION%.*}/julia-${JULIA_VERSION}-linux-x86_64.tar.gz" -o /tmp/julia.tar.gz
    tar -xzf /tmp/julia.tar.gz -C /opt
    ln -sf "/opt/julia-${JULIA_VERSION}/bin/julia" /usr/local/bin/julia
    rm /tmp/julia.tar.gz
fi
julia --version

cd /autograder/source
if [ -f env/Project.toml ]; then
    julia --project=env -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
fi

echo "Setup complete"
"""

function load_rubric(rubric_path)
    rubric = json_parsefile(rubric_path)
    rubric isa AbstractDict || error("rubric.json must contain a JSON object.")
    lang = get(rubric, "language", "julia")
    lang == "julia" || error(
        "rubric.json declares \"language\": \"$lang\", but this is the Julia autobuilder. " *
        "Use the Python autobuilder (autobuilder_python/) for Python assignments.")
    tests = get(rubric, "test_suite", nothing)
    (tests isa AbstractVector && !isempty(tests)) || error("rubric.json needs a non-empty \"test_suite\" list.")
    seen = Set{String}()
    for (i, t) in enumerate(tests)
        name = get(t, "test_name", nothing)
        name isa AbstractString || error("Test #$i in rubric.json has no \"test_name\".")
        name in seen && error("Duplicate test_name \"$name\" in rubric.json.")
        push!(seen, name)
        kind = get(t, "type", "variable")
        if kind == "plot"
            (haskey(t, "function_name") || haskey(t, "variable_name")) ||
                error("Test \"$name\" (type plot) needs a \"function_name\" or a \"variable_name\".")
            haskey(t, "expected") && error("Test \"$name\": plot tests compare with the solution's plot; remove \"expected\".")
            for c in get(t, "plot_checks", Any[])
                c in PLOT_CHECKS || error("Test \"$name\": unknown plot check \"$c\" " *
                                          "(use $(join(sort(collect(PLOT_CHECKS)), ", "))).")
            end
        elseif kind == "variable"
            haskey(t, "variable_name") || error("Test \"$name\" (type variable) needs a \"variable_name\".")
        elseif kind == "function"
            haskey(t, "function_name") || error("Test \"$name\" (type function) needs a \"function_name\".")
        else
            error("Test \"$name\": unknown type \"$kind\" (use \"variable\", \"function\" or \"plot\").")
        end
    end
    # Plot tests need Plots.jl in the assignment's environment.
    if any(t -> get(t, "type", "variable") == "plot", tests) && !isfile(joinpath(dirname(rubric_path), "Project.toml"))
        any(r -> string(r) == "Plots", get(rubric, "requirements", Any[])) || error(
            "rubric.json has plot tests, so \"requirements\" must include \"Plots\".")
    end
    return rubric
end

function _uses_input_refs(rubric)
    for t in rubric["test_suite"]
        vals = Any[get(t, "inputs", Any[])...]
        haskey(t, "expected") && push!(vals, t["expected"])
        any(v -> v isa AbstractString && startswith(v, "\$"), vals) && return true
    end
    return false
end

function _julia_version(rubric)
    v = get(rubric, "julia_version", nothing)
    if v === nothing
        isempty(VERSION.prerelease) || error(
            "You are building with a pre-release Julia ($VERSION). Set \"julia_version\" in rubric.json " *
            "to the released version the autograder should use, e.g. \"1.11.7\".")
        return "$(VERSION.major).$(VERSION.minor).$(VERSION.patch)"
    end
    v = string(v)
    occursin(r"^\d+\.\d+\.\d+$", v) || error("\"julia_version\" must look like \"1.11.7\", got \"$v\".")
    vn = VersionNumber(v)
    (vn.major, vn.minor) == (VERSION.major, VERSION.minor) || @warn(
        "rubric.json asks for Julia $v on Gradescope, but you are building with Julia $VERSION. " *
        "Packages are resolved and the solution is checked with Julia $VERSION; " *
        "build with Julia $(vn.major).$(vn.minor) to be sure it behaves the same.")
    return v
end

function image_markdown(path, alt)
    mime = get(_IMAGE_MIME, lowercase(splitext(path)[2]), nothing)
    mime === nothing && error("hint_image: unsupported image type \"$(splitext(path)[2])\" for $path " *
                              "(supported: $(join(sort(collect(keys(_IMAGE_MIME))), ", "))).")
    return "![$alt](data:$mime;base64,$(base64encode(read(path))))"
end

_lf(s) = replace(s, "\r\n" => "\n")

"""
    stage(staging, rubric_path, solution_path; inputs, timeout, fresh_env)

Lay out everything that goes into the autograder zip in the folder `staging`.
Returns the parsed rubric.
"""
function stage(staging, rubric_path, solution_path; inputs=nothing, timeout=nothing, fresh_env=true)
    isfile(rubric_path) || error("Rubric not found: $rubric_path")
    rubric_path = abspath(rubric_path)
    rubric_dir = dirname(rubric_path)
    rubric = load_rubric(rubric_path)
    isfile(solution_path) || error("Solution not found: $solution_path")
    sol_ext = lowercase(splitext(solution_path)[2])
    sol_ext in (".jl", ".ipynb") || error(
        "The solution must be a Julia file (.jl) or a Julia Jupyter notebook (.ipynb), got \"$(basename(solution_path))\".")
    # A notebook solution is converted exactly like a student notebook (code
    # cells joined, ]add / ;shell / ?help lines dropped) and shipped as solution.jl.
    solution_code = sol_ext == ".jl" ? read(solution_path, String) : notebook_to_julia(solution_path)
    solution_code === nothing && error(
        "\"$(basename(solution_path))\" is not a Julia notebook (its kernel is another language).")
    if inputs === nothing
        _uses_input_refs(rubric) && error(
            "rubric.json uses \"\$name\" references, so an inputs file is needed (--inputs test_inputs.jl).")
    else
        isfile(inputs) || error("Inputs file not found: $inputs")
    end

    mkpath(staging)
    cp(rubric_path, joinpath(staging, "rubric.json"))
    write(joinpath(staging, "solution.jl"), solution_code)
    inputs === nothing || cp(inputs, joinpath(staging, "test_inputs.jl"))

    for f in get(rubric, "extra_files", Any[])
        f = replace(string(f), '\\' => '/')
        first_part = first(split(f, '/'))
        (f in RESERVED || first_part in ("grader", "env")) &&
            error("extra_files: \"$f\" clashes with a file the autograder uses itself; please rename it.")
        src = joinpath(rubric_dir, f)
        ispath(src) || error("extra_files: \"$f\" not found next to rubric.json (looked at $src)")
        dest = joinpath(staging, f)
        mkpath(dirname(dest))
        cp(src, dest; force=true)
    end

    hint_images = Dict{String,Any}()
    for t in rubric["test_suite"]
        haskey(t, "hint_image") || continue
        img = joinpath(rubric_dir, t["hint_image"])
        isfile(img) || error("Test \"$(t["test_name"])\": hint_image \"$(t["hint_image"])\" not found next to rubric.json.")
        hint_images[t["test_name"]] = image_markdown(img, t["test_name"])
    end

    mkpath(joinpath(staging, "grader"))
    for f in GRADER_FILES
        cp(joinpath(GRADER_DIR, f), joinpath(staging, "grader", f))
    end

    setup_environment(joinpath(staging, "env"), rubric, rubric_dir; fresh=fresh_env)

    julia_version = _julia_version(rubric)
    build_info = Dict{String,Any}(
        "timeout" => timeout === nothing ? get(rubric, "timeout", DEFAULT_TIMEOUT) : timeout,
        "hint_images" => hint_images,
        "julia_version" => julia_version,
        "built_with_julia" => string(VERSION),
    )
    write(joinpath(staging, "build_info.json"), json_string(build_info; indent=2))
    write(joinpath(staging, "run_autograder"), _lf(RUN_AUTOGRADER))
    write(joinpath(staging, "setup.sh"), _lf(replace(SETUP_SH, "@@JULIA_VERSION@@" => julia_version)))
    return rubric
end

"""
    run_staged(staging, submission; metadata_path=nothing) -> results Dict

Run the staged autograder exactly as Gradescope would (same run.jl, same
worker), against `submission` -- a file, or a folder of files.
"""
function run_staged(staging, submission; metadata_path=nothing)
    work = mktempdir()
    subdir = joinpath(work, "submission")
    resdir = joinpath(work, "results")
    mkpath(subdir)
    if isdir(submission)
        for f in readdir(submission)
            cp(joinpath(submission, f), joinpath(subdir, f))
        end
    else
        isfile(submission) || error("Submission not found: $submission")
        cp(submission, joinpath(subdir, basename(submission)))
    end
    env = Dict{String,String}(k => v for (k, v) in ENV if !(k in ("JULIA_PROJECT", "JULIA_LOAD_PATH")))
    env["AUTOBUILDER_SUBMISSION_DIR"] = subdir
    env["AUTOBUILDER_RESULTS_DIR"] = resdir
    env["AUTOBUILDER_METADATA_PATH"] = metadata_path === nothing ? joinpath(work, "no_metadata.json") : abspath(metadata_path)
    cmd = `$(Base.julia_cmd()) --startup-file=no --history-file=no $(joinpath(staging, "grader", "run.jl"))`
    run(Cmd(setenv(cmd, env); dir=staging))
    results = json_parsefile(joinpath(resdir, "results.json"))
    rm(work; recursive=true, force=true)
    return results
end

function _check_solution(rubric, results, io)
    cfg = Dict(t["test_name"] => t for t in rubric["test_suite"])
    errors, warnings = String[], String[]
    for t in results["tests"]
        t["status"] == "passed" && continue
        line = "  $(t["number"]): $(replace(strip(t["output"]), "\n" => "\n      "))"
        haskey(cfg[t["number"]], "expected") ? push!(warnings, line) : push!(errors, line)
    end
    top = strip(get(results, "output", ""))
    if !isempty(errors)
        error("Your solution does not pass its own rubric:\n" * join(errors, "\n") *
              (isempty(top) ? "" : "\n\n" * top))
    end
    if !isempty(warnings)
        println(io, "Warning: your solution does not match the fixed \"expected\" values of these tests:")
        foreach(w -> println(io, w), warnings)
    end
    n = length(results["tests"])
    println(io, "Solution check: $(n - length(warnings))/$n tests pass.")
end

"""
    build(rubric, solution; inputs=nothing, output="autograder.zip", timeout=nothing)

Build a Gradescope autograder zip from `rubric.json` and your `solution.jl`.
The solution is first graded against itself with the real autograder, so a
broken rubric or solution is caught here rather than on Gradescope.

- `inputs`: a .jl file defining values for "\$name" references in the rubric
- `timeout`: seconds a submission may run in total (default: rubric's
  "timeout", else 600)
"""
function build(rubric, solution; inputs=nothing, output="autograder.zip", timeout=nothing, io::IO=stdout)
    staging = mktempdir()
    try
        rub = stage(staging, rubric, solution; inputs=inputs, timeout=timeout, fresh_env=true)
        files = list_files(staging)   # before the check, which may create files
        println(io, "Checking the solution against the rubric...")
        _check_solution(rub, run_staged(staging, solution), io)
        isfile(output) && rm(output)
        write_zip(output, staging, files)
        println(io, "Wrote $output")
    finally
        rm(staging; recursive=true, force=true)
    end
    return output
end

"""
    grade(rubric, solution, submission; inputs=nothing, timeout=nothing, json_out=nothing)

Grade one submission locally with the same autograder `build` produces and
print the result. `submission` can be a file or a folder. Returns the
Gradescope results as a Dict.
"""
function grade(rubric, solution, submission; inputs=nothing, timeout=nothing, json_out=nothing,
               metadata=nothing, io::IO=stdout)
    staging = mktempdir()
    try
        stage(staging, rubric, solution; inputs=inputs, timeout=timeout, fresh_env=false)
        results = run_staged(staging, submission; metadata_path=metadata)
        print_results(io, results)
        if json_out !== nothing
            write(json_out, json_string(Dict("tests" => results["tests"], "total" => results["score"]); indent=2))
        end
        return results
    finally
        rm(staging; recursive=true, force=true)
    end
end

_fmt_score(x) = isinteger(x) ? string(Int(x)) : string(x)

function print_results(io, results)
    top = strip(get(results, "output", ""))
    if !isempty(top)
        println(io, top)
        println(io)
    end
    for t in results["tests"]
        # Results re-posted from an earlier submission may have no "status".
        passed = get(t, "status", nothing) == "passed" ||
                 (!haskey(t, "status") && Float64(get(t, "score", 0)) >= Float64(get(t, "max_score", 0)) > 0)
        println(io, "[", passed ? "PASS" : "FAIL", "] ", get(t, "name", get(t, "number", "?")))
        out = rstrip(get(t, "output", ""))
        isempty(out) && continue
        for line in split(out, '\n')
            # Embedded hint images are long base64 strings; don't print them.
            startswith(line, "![") && occursin("base64,", line) && (line = "[hint image]")
            println(io, "       ", line)
        end
    end
    println(io, "\nTotal: ", _fmt_score(Float64(results["score"])))
end
