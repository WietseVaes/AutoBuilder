# Finding the student's file in /autograder/submission.
#
# Gradescope keeps the submission's folder structure, so the whole folder is
# searched. Accepted files:
#   .jl     used as-is (Pluto notebooks are .jl files too)
#   .ipynb  a Jupyter notebook with a Julia kernel: its code cells are joined
#           into a .jl file written next to the notebook (so `include("x.jl")`
#           of a sibling file still works); lines in Pkg mode (`]add ...`),
#           shell mode (`;ls`) or help mode (`?sin`) are dropped
#
# The student's file is run from where it is -- nothing is copied into the
# autograder's own folder, so a student file can never replace one of the
# autograder's files, and `include` of helper files the student submitted
# next to it works.
#
# Several candidates: the one defining the most of the names the rubric asks
# for is graded (ties: first alphabetically), and the student is told which.

const _JUNK_DIRS = Set(["__MACOSX", ".ipynb_checkpoints"])
const ACCEPTED_TEXT = ".jl or .ipynb (Julia notebook)"

function list_submission_files(dir)
    files = String[]
    isdir(dir) || return files
    for (root, dirs, fs) in walkdir(dir)
        rel_root = relpath(root, dir)
        parts = rel_root == "." ? String[] : splitpath(rel_root)
        any(p -> startswith(p, ".") || p in _JUNK_DIRS, parts) && continue
        for f in fs
            startswith(f, ".") && continue
            rel = rel_root == "." ? f : joinpath(rel_root, f)
            push!(files, replace(rel, '\\' => '/'))
        end
    end
    return sort!(files)
end

function required_names(rubric)
    names = Set{String}()
    for t in get(rubric, "test_suite", Any[])
        n = get(t, "type", "variable") != "variable" && haskey(t, "function_name") ? t["function_name"] : get(t, "variable_name", nothing)
        n === nothing || push!(names, n)
    end
    return names
end

"""
    notebook_to_julia(path) -> String or nothing

The code of a Julia Jupyter notebook, or `nothing` if the file is not a
notebook or is a notebook for another language (e.g. Python).
"""
function notebook_to_julia(path)
    nb = try
        json_parsefile(path)
    catch
        return nothing
    end
    nb isa AbstractDict || return nothing
    meta = get(nb, "metadata", Dict{String,Any}())
    lang = nothing
    if meta isa AbstractDict
        ks = get(meta, "kernelspec", nothing)
        ks isa AbstractDict && (lang = get(ks, "language", nothing))
        li = get(meta, "language_info", nothing)
        lang === nothing && li isa AbstractDict && (lang = get(li, "name", nothing))
    end
    lang !== nothing && lowercase(string(lang)) != "julia" && return nothing
    cells = String[]
    for cell in get(nb, "cells", Any[])
        cell isa AbstractDict && get(cell, "cell_type", "") == "code" || continue
        src = get(cell, "source", "")
        src = src isa AbstractVector ? join(src) : string(src)
        kept = [l for l in split(src, '\n') if !(startswith(lstrip(l), "]") || startswith(lstrip(l), ";") || startswith(lstrip(l), "?"))]
        push!(cells, join(kept, '\n'))
    end
    return join(cells, "\n\n") * "\n"
end

# Top-level definitions, found with regular expressions -- only used to pick
# between several submitted files, so it does not need to be a full parser.
# Julia names can be Unicode (λ, σ², x₀, ∇f, θ′ -- typed as \lambda<tab> etc.).
# (∇ and ∂ are maths symbols in Unicode, like + and =, so they are listed by hand.)
const _JL_NAME = raw"[\p{L}\p{Nl}\p{So}_∇∂][\p{L}\p{N}\p{M}\p{So}\p{Sk}_!′″‴∇∂]*"
const _JL_DEFINITIONS = [
    Regex("^\\s*function\\s+($_JL_NAME)\\s*[({]", "m"),
    Regex("^\\s*($_JL_NAME)\\s*\\([^=\\n]*\\)\\s*=(?!=)", "m"),
    Regex("^\\s*(?:const\\s+|global\\s+)?($_JL_NAME)\\s*(?:::[^=\\n]+)?=(?!=)", "m"),
]

function defined_names(code::AbstractString)
    found = Set{String}()
    for re in _JL_DEFINITIONS, m in eachmatch(re, code)
        push!(found, m.captures[1])
    end
    return found
end

const _JL_INCLUDE = r"\binclude\(\s*\"([^\"]+)\"\s*\)"

# The submitted files (relative paths) that `rel` includes, directly or
# through other included files. `code_of` maps submitted .jl files to code.
function included_files(rel, code, code_of, seen=Set{String}())
    base = dirname(rel)
    for m in eachmatch(_JL_INCLUDE, code)
        target = normpath(isempty(base) ? m.captures[1] : joinpath(base, m.captures[1]))
        target = replace(target, '\\' => '/')
        if haskey(code_of, target) && !(target in seen) && target != rel
            push!(seen, target)
            included_files(target, code_of[target], code_of, seen)
        end
    end
    return seen
end

"""
    find_submission(dir, required) -> (path, graded_file, note)

`path` is the file to run (nothing if none was usable), `graded_file` the
submitted file it came from, and `note` a message for the student (or nothing).
"""
function find_submission(dir, required)
    all_files = list_submission_files(dir)
    candidates = Tuple{String,String,String}[]   # (path to run, submitted file, code)
    for rel in all_files
        abs = joinpath(dir, rel)
        ext = lowercase(splitext(rel)[2])
        if ext == ".jl"
            code = try read(abs, String) catch; "" end
            push!(candidates, (abs, rel, code))
        elseif ext == ".ipynb"
            code = notebook_to_julia(abs)
            code === nothing && continue
            converted = joinpath(dirname(abs), "." * basename(abs) * ".jl")
            write(converted, code)
            push!(candidates, (converted, rel, code))
        end
    end

    if isempty(candidates)
        note = isempty(all_files) ?
            "No files were received in your submission. This assignment accepts $ACCEPTED_TEXT files." :
            "No usable submission file was found. Files received: $(join(all_files, ", ")). " *
            "This assignment accepts $ACCEPTED_TEXT files."
        return (nothing, nothing, note)
    end

    # A file that another submitted file include()s is a helper, not the
    # main file; its definitions count towards the file that includes it.
    code_of = Dict(c[2] => c[3] for c in candidates)
    included = Dict(c[2] => included_files(c[2], c[3], code_of) for c in candidates)
    helpers = union(Set{String}(), values(included)...)
    entries = [c for c in candidates if !(c[2] in helpers)]
    isempty(entries) && (entries = candidates)   # files that include each other

    count(c) = length(intersect(union(defined_names(c[3]), (defined_names(code_of[h]) for h in included[c[2]])...), required))
    best = entries[1]
    best_count = count(best)
    for c in entries[2:end]
        n = count(c)
        if n > best_count
            best, best_count = c, n
        end
    end
    note = nothing
    if length(entries) > 1
        others = sort([c[2] for c in entries if c[2] != best[2]])
        note = "Multiple files were found in your submission ($(join([best[2]; others], ", "))). Graded '$(best[2])'."
    end
    return (best[1], best[2], note)
end
