# The Julia packages an assignment uses.
#
# Two ways to declare them (the first one found wins):
#
#   1. A Project.toml (and optionally Manifest.toml) next to rubric.json --
#      e.g. your course environment. Shipped as-is, so students are graded
#      with exactly those package versions.
#   2. "requirements": ["DataFrames", "SpecialFunctions"] in rubric.json.
#      At build time these are resolved into a fresh environment; the
#      resulting Manifest.toml pins every version and ships in the zip.
#
# Standard-library packages (LinearAlgebra, Statistics, Printf, ...) are
# always available and never need to be listed.
#
# On Gradescope, setup.sh installs and precompiles the environment once when
# the autograder image is built, so grading itself never downloads anything.

function _run_pkg(env_dir, code)
    env = Dict{String,String}(k => v for (k, v) in ENV if !(k in ("JULIA_PROJECT", "JULIA_LOAD_PATH")))
    cmd = setenv(`$(Base.julia_cmd()) --startup-file=no --history-file=no --project=$env_dir -e "using Pkg; $code"`, env)
    try
        run(cmd)
    catch e
        e isa ProcessFailedException || rethrow()
        error("Setting up the Julia packages failed (`$code`); see the Pkg output above. " *
              "\"requirements\" in rubric.json must be Julia package names.")
    end
end

_env_cache_dir(reqs) = joinpath(first(DEPOT_PATH), "autobuilder", "envs",
                                string(hash((sort(reqs), string(VERSION))); base=16))

"""
    setup_environment(env_dir, rubric, rubric_dir; fresh=true) -> Symbol

Fill `env_dir` with the assignment's Project.toml/Manifest.toml and make
sure the packages are installed locally. Returns `:project`, `:requirements`
or `:none`. With `fresh=false` (used by `grade`), a previously resolved
environment for the same requirements is reused to save time.
"""
function setup_environment(env_dir, rubric, rubric_dir; fresh=true)
    reqs = String[string(r) for r in get(rubric, "requirements", Any[])]
    project = joinpath(rubric_dir, "Project.toml")

    if isfile(project)
        mkpath(env_dir)
        cp(project, joinpath(env_dir, "Project.toml"); force=true)
        manifest = joinpath(rubric_dir, "Manifest.toml")
        isfile(manifest) && cp(manifest, joinpath(env_dir, "Manifest.toml"); force=true)
        isempty(reqs) || @warn "Using the Project.toml next to rubric.json; the rubric's \"requirements\" are ignored."
        _run_pkg(env_dir, "Pkg.instantiate()")
        return :project
    elseif !isempty(reqs)
        cache = _env_cache_dir(reqs)
        if fresh || !isfile(joinpath(cache, "Manifest.toml"))
            tmp = mktempdir()
            _run_pkg(tmp, "Pkg.add($(repr(reqs)))")
            mkpath(cache)
            for f in ("Project.toml", "Manifest.toml")
                cp(joinpath(tmp, f), joinpath(cache, f); force=true)
            end
        end
        mkpath(env_dir)
        for f in ("Project.toml", "Manifest.toml")
            cp(joinpath(cache, f), joinpath(env_dir, f); force=true)
        end
        fresh || _run_pkg(env_dir, "Pkg.instantiate()")
        return :requirements
    end
    return :none
end
