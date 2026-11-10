using Test
using AutoBuilder

const ROOT = dirname(@__DIR__)
const EXAMPLES = joinpath(ROOT, "examples")
const GRADER = joinpath(ROOT, "src", "grader")

# The grader's building blocks, loaded the same way worker.jl/run.jl load them.
module G
    include(joinpath(Main.GRADER, "json.jl"))
    include(joinpath(Main.GRADER, "values.jl"))
    include(joinpath(Main.GRADER, "compare.jl"))
    include(joinpath(Main.GRADER, "submission.jl"))
    include(joinpath(Main.GRADER, "attempts.jl"))
end

status(s, r; rtol=1e-6, atol=1e-6) = G.compare_values(s, r, rtol, atol)[1]

# Grade quietly; returns (results, printed output).
function quiet_grade(args...; kw...)
    buf = IOBuffer()
    res = grade(args...; io=buf, kw...)
    return res, String(take!(buf))
end

score(res) = Float64(res["score"])
outputs(res) = join([t["output"] for t in res["tests"]], "\n") * "\n" * res["output"]

# A throwaway assignment folder.
function assignment(dir; rubric, solution, files=Dict{String,String}())
    mkpath(dir)
    write(joinpath(dir, "rubric.json"), G.json_string(rubric; indent=2))
    write(joinpath(dir, "solution.jl"), solution)
    for (name, content) in files
        mkpath(dirname(joinpath(dir, name)))
        write(joinpath(dir, name), content)
    end
    return joinpath(dir, "rubric.json"), joinpath(dir, "solution.jl")
end

const SIMPLE_RUBRIC = Dict(
    "language" => "julia",
    "test_suite" => [
        Dict("test_name" => "T1", "type" => "variable", "variable_name" => "x",
             "description" => "x is 42", "score" => 1, "hint_not_defined" => "Define x."),
        Dict("test_name" => "T2", "type" => "function", "function_name" => "double",
             "inputs" => [2.0], "description" => "double(2.0)", "score" => 1),
    ],
)
const SIMPLE_SOLUTION = "x = 42\ndouble(v) = 2v\n"

@testset "AutoBuilder" begin

@testset "json" begin
    s = """{"a": [1, 2.5, -3e-2, true, null, "h\\u00e9\\n\\ud83d\\ude00"], "b": {"c": "≈ ℯ"}}"""
    v = G.json_parse(s)
    @test v["a"][1] === 1
    @test v["a"][2] === 2.5
    @test v["a"][3] ≈ -0.03
    @test v["a"][4] === true
    @test v["a"][5] === nothing
    @test v["a"][6] == "hé\n😀"
    @test v["b"]["c"] == "≈ ℯ"
    @test G.json_parse(G.json_string(v)) == v
    @test G.json_parse(G.json_string(v; indent=2)) == v
    @test G.json_parse("[NaN, Infinity, -Infinity]")[2] == Inf
    @test G.json_string([NaN, 1.0]) == "[null,1.0]"
    @test_throws ErrorException G.json_parse("{\"a\": }")
end

@testset "rubric values" begin
    @test G.to_julia([1, 2, 3]) isa Vector{Int}
    @test G.to_julia([1.0, 2, 3]) isa Vector{Float64}
    @test G.to_julia([[1, 2], [3, 4]]) == [1 2; 3 4]
    @test G.to_julia([[1.0, 2], [3, 4]]) isa Matrix{Float64}
    @test G.to_julia(["a", "b"]) isa Vector{String}
    @test G.to_julia([true, false]) isa Vector{Bool}
    @test G.to_julia(Any[1, "a"]) == Any[1, "a"]
    @test G.to_julia(Any[]) == Any[]
    m = Module(); Core.eval(m, :(f(x) = x + 1))
    @test G.resolve_value("\$f", m)(1) == 2
    @test_throws ErrorException G.resolve_value("\$g", m)
    @test_throws ErrorException G.resolve_value("\$f", nothing)
end

@testset "compare" begin
    @test status("abc", "abc") == "pass"
    @test status(1, "abc") == "wrong_type"
    @test status("abd", "abc") == "tolerance"
    @test status(true, true) == "pass"
    @test status(1, true) == "wrong_type"
    @test status(2.0, 2) == "pass"
    @test status(2.0 + 1e-9, 2.0) == "pass"
    @test status(2.1, 2.0) == "tolerance"
    @test status(2.1, 2.0; rtol=0.1) == "pass"
    @test status([1, 2], 1.0) == "wrong_size"
    @test status([1, 2, 3], [1, 2]) == "wrong_size"
    @test status([1 2 3], [1, 2, 3]) == "wrong_size"          # row matrix vs vector
    @test status([1.0, NaN], [1.0, 2.0]) == "nans"
    @test status([Inf, 1.0], [Inf, 1.0]) == "pass"
    @test status(1 + 2im, 1 + 2im) == "pass"
    @test status(0:0.5:1, [0.0, 0.5, 1.0]) == "pass"          # ranges count as vectors
    @test status((1.0, 2.0), [1.0, 2.0]) == "pass"
    @test status("x", [1.0]) == "wrong_type"
    @test status(Any[1, 2.0], [1.0, 2.0]) == "pass"
    @test status(rand(2, 2, 2), zeros(2, 2, 2)) == "tolerance"
    @test status((1, "a"), (1, "a")) == "pass"
    @test status((1, "b"), (1, "a")) == "tolerance"
    @test G.compare_values((1, "b"), (1, "a"), 0, 0)[2] == "Element 2: Your string value is incorrect."
    @test status((1, "a", 3), (1, "a")) == "wrong_size"
    @test status((a=1, b=2.0), (a=1, b=2.0)) == "pass"
    @test status((a=1, c=2.0), (a=1, b=2.0)) == "wrong_size"
    @test status((1, 2.0), (a=1, b=2.0)) == "wrong_type"
    @test status(Dict("a" => 1.0), Dict("a" => 1.0)) == "pass"
    @test status(Dict("a" => 1.5), Dict("a" => 1.0)) == "tolerance"
    @test status(Dict("b" => 1.0), Dict("a" => 1.0)) == "wrong_size"
    @test status(["a", "b"], ["a", "b"]) == "pass"
    @test status(:sym, :sym) == "pass"
    @test status("sym", :sym) == "wrong_type"
    @test status(nothing, nothing) == "pass"
    # Same-named structs from different modules (solution vs submission).
    m1, m2 = Module(), Module()
    for m in (m1, m2)
        Core.eval(m, :(struct Point; x::Float64; y::Float64; end))
    end
    @test status(m2.Point(1.0, 2.0), m1.Point(1.0, 2.0)) == "pass"
    @test status(m2.Point(1.0, 2.5), m1.Point(1.0, 2.0)) == "tolerance"
    @test status((1.0, 2.0), m1.Point(1.0, 2.0)) == "wrong_type"
    # Messages never contain the expected value.
    @test !occursin("12345", G.compare_values(1.0, 12345.0, 0, 0)[2])
end

@testset "crc32 and zip" begin
    @test AutoBuilder.crc32(Vector{UInt8}("123456789")) == 0xcbf43926
    dir = mktempdir()
    mkpath(joinpath(dir, "sub"))
    write(joinpath(dir, "run_autograder"), "#!/bin/bash\n")
    write(joinpath(dir, "sub", "a.txt"), "héllo")
    z = joinpath(dir, "out.zip")
    AutoBuilder.write_zip(z, dir, ["run_autograder", "sub/a.txt"])
    bytes = read(z)
    # Walk the central directory: names, modes, and data via the local headers.
    eocd = findlast(Vector{UInt8}([0x50, 0x4b, 0x05, 0x06]), bytes)[1]
    u16(i) = Int(ltoh(reinterpret(UInt16, bytes[i:i+1])[1]))
    u32(i) = Int(ltoh(reinterpret(UInt32, bytes[i:i+3])[1]))
    @test u16(eocd + 10) == 2
    p = u32(eocd + 16) + 1
    entries = Dict{String,Tuple{Int,String}}()
    for _ in 1:2
        namelen = u16(p + 28)
        name = String(bytes[p+46:p+45+namelen])
        mode = u32(p + 38) >> 16
        off = u32(p + 42) + 1
        size = u32(off + 18)
        data = String(bytes[off+30+u16(off+26):off+29+u16(off+26)+size])
        entries[name] = (mode, data)
        p += 46 + namelen
    end
    @test entries["run_autograder"] == (0o100755, "#!/bin/bash\n")
    @test entries["sub/a.txt"] == (0o100644, "héllo")
end

@testset "submission picking" begin
    dir = mktempdir()
    write(joinpath(dir, "a.jl"), "x = 1\n")
    write(joinpath(dir, "b.jl"), "x = 1\nfunction double(v)\n 2v\nend\n")
    write(joinpath(dir, "notes.txt"), "hi")
    mkpath(joinpath(dir, "__MACOSX")); write(joinpath(dir, "__MACOSX", "c.jl"), "")
    path, graded, note = G.find_submission(dir, Set(["x", "double"]))
    @test graded == "b.jl"
    @test occursin("Graded 'b.jl'", note)

    # main.jl includes lib/helpers.jl: main.jl is graded even though both
    # define one required name and "helpers" doesn't come first alphabetically.
    inc = mktempdir()
    mkpath(joinpath(inc, "lib"))
    write(joinpath(inc, "main.jl"), "include(\"lib/helpers.jl\")\nx = 1\n")
    write(joinpath(inc, "lib", "helpers.jl"), "double(v) = 2v\n")
    write(joinpath(inc, "a_scratch.jl"), "x = 2\n")
    path, graded, note = G.find_submission(inc, Set(["x", "double"]))
    @test graded == "main.jl"
    @test occursin("Graded 'main.jl'", note) && !occursin("helpers", note)

    empty = mktempdir()
    write(joinpath(empty, "hw.py"), "x = 1\n")
    path, graded, note = G.find_submission(empty, Set(["x"]))
    @test path === nothing
    @test occursin("hw.py", note) && occursin(".jl", note)

    @test G.notebook_to_julia(joinpath(EXAMPLES, "packages_and_inputs", "submission_03_notebook.ipynb")) !== nothing
    pynb = joinpath(mktempdir(), "py.ipynb")
    write(pynb, """{"cells": [], "metadata": {"kernelspec": {"language": "python"}}}""")
    @test G.notebook_to_julia(pynb) === nothing
    @test G.defined_names("const a = 1\nf(x) = 2\nfunction g!(y)\nend\nb::Int = 3\nc == 4\n") ==
          Set(["a", "f", "g!", "b"])
    # Unicode names (\lambda<tab>, \sigma<tab>\^2<tab>, \nabla<tab>, x\_0<tab>, θ\prime<tab>)
    @test G.defined_names("λ = 0.2\nσ²(v) = 1\nfunction ∇f(x)\nend\nx₀ = 3\nθ′ = 1\n") ==
          Set(["λ", "σ²", "∇f", "x₀", "θ′"])
    # Julia treats the micro sign µ (U+00B5) as Greek μ (\mu<tab>) in names.
    @test G.name_symbol("µ") === Symbol("μ")
    @test G.name_symbol("σ²") === :σ²
    # Several submitted files: the one defining the Unicode names is picked.
    uni = mktempdir()
    write(joinpath(uni, "a_notes.jl"), "x = 1\n")
    write(joinpath(uni, "b_homework.jl"), "λ = 0.2\nσ²(v) = 1\n")
    @test G.find_submission(uni, Set(["λ", "σ²"]))[2] == "b_homework.jl"
end

@testset "attempt limits" begin
    rubric = Dict("test_suite" => [Dict("test_name" => "T", "score" => 2, "attempts" => 2)])
    prev(used, best) = Dict("previous_submissions" => [Dict("results" => Dict("tests" => [
        Dict("number" => "T", "score" => best, "extra_data" => Dict("attempts_used" => used, "best_score" => best))]))])
    mk(score) = Dict{String,Any}("tests" => [Dict{String,Any}("number" => "T", "name" => "t", "score" => score,
                                                              "max_score" => 2, "output" => "")])
    r = G.apply_attempt_limits!(mk(0), rubric, Dict(), Dict("T" => true))
    @test r["tests"][1]["extra_data"]["attempts_used"] == 1
    r = G.apply_attempt_limits!(mk(2), rubric, prev(1, 0.0), Dict("T" => true))
    @test r["score"] == 2.0 && startswith(r["tests"][1]["name"], "(attempt: 2/2)")
    r = G.apply_attempt_limits!(mk(2), rubric, prev(2, 0.0), Dict("T" => true))   # over budget
    @test r["score"] == 0.0
    r = G.apply_attempt_limits!(mk(0), rubric, prev(1, 2.0), Dict("T" => true))   # best is kept
    @test r["score"] == 2.0
    @test G.locked_out_message(rubric, prev(1, 0.0)) === nothing
    @test occursin("All attempts have been used", G.locked_out_message(rubric, prev(2, 0.5)))
    @test occursin("answered correctly", G.locked_out_message(rubric, prev(1, 2.0)))
    @test G.locked_out_message(rubric, Dict("previous_submissions" => "garbage")) === nothing
end

@testset "example: basics" begin
    d = joinpath(EXAMPLES, "basics")
    g(s) = quiet_grade(joinpath(d, "rubric.json"), joinpath(d, "solution.jl"), joinpath(d, s))
    res, out = g("submission_01_correct.jl")
    @test score(res) == 4
    res, out = g("submission_02_wrong_values.jl")
    @test score(res) == 1
    @test occursin("Check the exact spelling: 'hello from autobuilder'.", out)
    @test occursin("add_one should return x + 1.", out)
    res, out = g("submission_03_missing_function.jl")
    @test score(res) == 3
    @test occursin("Function 'add_one' is not defined.", out)
    @test occursin("Hint: Define a function called add_one(x).", out)
    res, out = g("submission_04_wrong_type.jl")
    @test score(res) == 3
    @test occursin("Expected a string, but got type Int64.", out)
end

@testset "example: arrays_and_functions" begin
    d = joinpath(EXAMPLES, "arrays_and_functions")
    g(s) = quiet_grade(joinpath(d, "rubric.json"), joinpath(d, "solution.jl"), joinpath(d, s))
    expected = Dict("submission_01_correct.jl" => 13, "submission_02_tolerance.jl" => 0,
                    "submission_03_wrong_type_and_size.jl" => 2, "submission_04_missing.jl" => 4,
                    "submission_05_nans.jl" => 10)
    for (s, total) in expected
        res, out = g(s)
        @test score(res) == total
        s == "submission_03_wrong_type_and_size.jl" && @test occursin("Expected a 2×2 matrix, but got a vector of length 4.", out)
        s == "submission_05_nans.jl" && @test occursin("Hint: fibonacci should not contain NaN.", out)
    end
end

@testset "example: packages_and_inputs" begin
    d = joinpath(EXAMPLES, "packages_and_inputs")
    g(s) = quiet_grade(joinpath(d, "rubric.json"), joinpath(d, "solution.jl"), joinpath(d, s);
                       inputs=joinpath(d, "test_inputs.jl"))
    res, out = g("submission_01_correct.jl")
    @test score(res) == 7
    res, out = g("submission_03_notebook.ipynb")
    @test score(res) == 7
    res, out = g("submission_02_errors.jl")
    @test score(res) == 0
    @test occursin("Your code stopped with an error: UndefVarError: `gamma` not defined (at submission_02_errors.jl:20)", out)
    @test occursin("Function 'gamma_ratio' is not defined. Your code stopped with an error before reaching it.", out)
    @test occursin("Field y: Your value is not within the required tolerance.", out)
    @test occursin("`undefined_helper` not defined", out)
    @test occursin("Expected a named tuple, but got type Tuple{Float64, Float64}.", out)
    @test !occursin("Main.Submission", out)
end

# The Julia versions of the Python examples: every submission's score, plus
# a message that shows it failed for the intended reason.
EXAMPLE_CASES = [
    # (example, submission, score, text that must appear)
    ("total_test", "submission_01_everything_wrong.jl", 0, "Expected a 2×11 matrix, but got a 11×2 matrix."),
    ("total_test", "submission_02_strings_list_fixed.jl", 10, "Hint: In Julia: grid = range(0, 1; length=5) gives exactly 5 points."),
    ("total_test", "submission_03_variables_fixed.jl", 14, "Expected a 2×11 matrix, but got a 2×10 matrix."),
    ("total_test", "submission_04_correct.jl", 25, "Total: 25"),
    ("total_test", "submission_05_correct_notebook.ipynb", 25, "Total: 25"),
    ("total_test", "submission_06_crashes_halfway.jl", 16, "`wieghts` not defined (at submission_06_crashes_halfway.jl:"),
    ("total_test", "submission_08_two_files", 25, "Total: 25"),
    ("function_unit_test", "submission_01_missing_function.jl", 0, "Function 'rk4_step' is not defined."),
    ("function_unit_test", "submission_02_wrong_shape.jl", 0, "Expected a vector of length 2, but got a single number."),
    ("function_unit_test", "submission_03_Euler.jl", 2, "Your value is not within the required tolerance."),
    ("function_unit_test", "submission_04_correct.jl", 8, "Total: 8"),
    ("function_unit_test", "submission_05_type_error.jl", 0, "MethodError: no method matching rk4_step"),
    ("callable_test", "submission_01_correct.jl", 5, "Total: 5"),
    ("callable_test", "submission_02_wrong.jl", 0, "f(f(x))"),
    ("expected_test", "submission_01_missing_var.jl", 0, "Variable 'final_scores' is not defined."),
    ("expected_test", "submission_02_incorrect.jl", 0, "Your value is not within the required tolerance."),
    ("expected_test", "submission_03_matrix_not_vector.jl", 0, "Expected a vector of length 4, but got a 4×1 matrix."),
    ("expected_test", "submission_04_correct.jl", 4, "Total: 4"),
    ("extra_files_test", "submission_01_correct.jl", 2, "Total: 2"),
    ("extra_files_test", "submission_02_header_counted.jl", 0, "cannot parse \"y\" as Float64"),
    ("dataframe_test", "submission_01_correct.jl", 10, "Total: 10"),
    ("dataframe_test", "submission_02_wrong_columns.jl", 3, "but got columns [\"Name\", \"score\", \"passed\"]"),
    ("dataframe_test", "submission_03_wrong_threshold.jl", 0, "Column 'average_score': Your value is not within the required tolerance."),
    ("plot_test", "submission_01_correct.jl", 20, "Total: 20"),
    ("plot_test", "submission_02_wrong_labels.jl", 10, "  - 'xlabel' does not match.\n         - 'title' does not match.\n         - Legend labels do not match."),
    ("plot_test", "submission_03_wrong_data.jl", 3, "Expected 2 for 'n_lines', but got 1."),
    ("plot_test", "submission_04_not_a_plot.jl", 0, "Expected a Plots.jl plot (the result of plot(...), scatter(...), bar(...), ...), but got type Nothing."),
    ("plot_test", "submission_05_saves_and_displays.jl", 20, "Total: 20"),
]

@testset "notebook as the solution" begin
    d = joinpath(EXAMPLES, "total_test")
    g(s) = quiet_grade(joinpath(d, "rubric.json"), joinpath(d, "solution_notebook.ipynb"), joinpath(d, s);
                       inputs=joinpath(d, "test_inputs.jl"))
    @test score(g("submission_03_variables_fixed.jl")[1]) == 14
    @test score(g("submission_04_correct.jl")[1]) == 25
    # Pkg calls in the solution are skipped too (Example is not installed).
    tmp = mktempdir()
    rb, sol = assignment(tmp; rubric=SIMPLE_RUBRIC, solution="import Pkg; Pkg.add(\"Example\")\n" * SIMPLE_SOLUTION)
    f = joinpath(tmp, "s.jl"); write(f, SIMPLE_SOLUTION)
    @test score(quiet_grade(rb, sol, f)[1]) == 2
    # A Python notebook is not a Julia solution.
    pynb = joinpath(mktempdir(), "solution.ipynb")
    write(pynb, """{"cells": [], "metadata": {"kernelspec": {"language": "python"}}}""")
    err = try
        build(joinpath(d, "rubric.json"), pynb; inputs=joinpath(d, "test_inputs.jl"),
              output=joinpath(mktempdir(), "x.zip"), io=devnull)
        nothing
    catch e
        e
    end
    @test err isa ErrorException && occursin("not a Julia notebook", err.msg)
end

@testset "examples mirrored from Python" begin
    for (ex, sub, total, text) in EXAMPLE_CASES
        d = joinpath(EXAMPLES, ex)
        inputs = isfile(joinpath(d, "test_inputs.jl")) ? joinpath(d, "test_inputs.jl") : nothing
        res, out = quiet_grade(joinpath(d, "rubric.json"), joinpath(d, "solution.jl"), joinpath(d, sub); inputs=inputs)
        @test score(res) == total
        @test occursin(text, out)
        (score(res) == total && occursin(text, out)) || println("Unexpected result for $ex/$sub:\n$out")
    end
end

@testset "gradescope situations" begin
    tmp = mktempdir()
    rubric, solution = assignment(joinpath(tmp, "a"); rubric=SIMPLE_RUBRIC, solution=SIMPLE_SOLUTION)

    # Student files named like the autograder's own files change nothing.
    sub = joinpath(tmp, "decoys"); mkpath(sub)
    write(joinpath(sub, "solution.jl"), "x = 1\ndouble(v) = 3v\n")   # a wrong "solution"
    write(joinpath(sub, "rubric.json"), """{"test_suite": []}""")
    res, out = quiet_grade(rubric, solution, sub)
    @test score(res) == 0
    @test length(res["tests"]) == 2

    # A main file that includes a helper file submitted next to it.
    sub = joinpath(tmp, "helpers"); mkpath(sub)
    write(joinpath(sub, "main.jl"), "include(\"helpers.jl\")\nx = 42\n")
    write(joinpath(sub, "helpers.jl"), "double(v) = v + v\n")
    res, out = quiet_grade(rubric, solution, sub)
    @test score(res) == 2
    @test !occursin("Multiple files", out)   # an included file is a helper, not a candidate

    # Names only visible through `using Base` don't count as defined.
    r2 = deepcopy(SIMPLE_RUBRIC)
    push!(r2["test_suite"], Dict("test_name" => "T3", "type" => "function", "function_name" => "step",
                                 "inputs" => [1.0], "score" => 1))
    rubric2, solution2 = assignment(joinpath(tmp, "b"); rubric=r2, solution=SIMPLE_SOLUTION * "step(v) = v + 1\n")
    f = joinpath(tmp, "nostep.jl"); write(f, SIMPLE_SOLUTION)
    res, out = quiet_grade(rubric2, solution2, f)
    @test score(res) == 2
    @test occursin("Function 'step' is not defined.", out)

    # Packages outside the assignment's environment are not available.
    f = joinpath(tmp, "usespkg.jl"); write(f, "using SpecialFunctions\n" * SIMPLE_SOLUTION)
    res, out = quiet_grade(rubric, solution, f)
    @test score(res) == 0
    @test occursin("SpecialFunctions", out)

    # A function that never returns: earlier tests keep their result.
    f = joinpath(tmp, "loop.jl"); write(f, "x = 42\nfunction double(v)\n while true; end\nend\n")
    res, out = quiet_grade(rubric, solution, f; timeout=30)
    @test score(res) == 1
    @test occursin("did not finish within 30", out)

    # Pkg calls in a submission are skipped instead of stopping the script.
    f = joinpath(tmp, "pkgcalls.jl")
    write(f, "using Pkg; Pkg.add(\"Example\")\nimport Pkg\nPkg.activate(\".\")\nPkg.instantiate()\n" * SIMPLE_SOLUTION)
    res, out = quiet_grade(rubric, solution, f)
    @test score(res) == 2

    # exit() in the submission.
    f = joinpath(tmp, "exit.jl"); write(f, "x = 42\ndouble(v) = exit(0)\n")
    res, out = quiet_grade(rubric, solution, f)
    @test score(res) == 1
    @test occursin("call exit()", out)

    # No usable file.
    f = joinpath(tmp, "hw.py"); write(f, "x = 42\n")
    res, out = quiet_grade(rubric, solution, f)
    @test score(res) == 0
    @test occursin("No usable submission file was found. Files received: hw.py.", out)

    # Locked out after the attempts are used up: previous results are re-posted.
    r3 = deepcopy(SIMPLE_RUBRIC)
    r3["test_suite"][1]["attempts"] = 1
    rubric3, solution3 = assignment(joinpath(tmp, "c"); rubric=r3, solution=SIMPLE_SOLUTION)
    meta = joinpath(tmp, "metadata.json")
    write(meta, G.json_string(Dict("previous_submissions" => [Dict("results" => Dict("tests" => [
        Dict("number" => "T1", "score" => 0, "max_score" => 1, "extra_data" => Dict("attempts_used" => 1, "best_score" => 0))]))])))
    res, out = quiet_grade(rubric3, solution3, joinpath(tmp, "nostep.jl"); metadata=meta)
    @test occursin("All attempts have been used", res["output"])
    @test length(res["tests"]) == 1

    # Fixed "expected" values and hint_*_julia overrides.
    r4 = Dict("language" => "julia", "test_suite" => [
        Dict("test_name" => "E", "type" => "variable", "variable_name" => "v", "expected" => [[1, 2], [3, 4]],
             "score" => 1, "hint_tolerance" => "generic", "hint_tolerance_julia" => "julia-specific",
             "hint_tolerance_python" => "python-specific")])
    rubric4, solution4 = assignment(joinpath(tmp, "d"); rubric=r4, solution="v = [1 2; 3 4]\n")
    f = joinpath(tmp, "v.jl"); write(f, "v = [1 2; 3 5]\n")
    res, out = quiet_grade(rubric4, solution4, f)
    @test score(res) == 0
    @test occursin("Hint: julia-specific", out) && !occursin("generic", out)
end

@testset "build" begin
    tmp = mktempdir()
    rubric, solution = assignment(joinpath(tmp, "a"); rubric=SIMPLE_RUBRIC, solution=SIMPLE_SOLUTION,
                                  files=Dict("data/values.csv" => "1,2\n"))
    r = G.json_parsefile(rubric); r["extra_files"] = ["data/values.csv"]
    write(rubric, G.json_string(r))
    z = joinpath(tmp, "autograder.zip")
    build(rubric, solution; output=z, io=devnull)
    bytes = read(z)
    for name in ("run_autograder", "setup.sh", "rubric.json", "build_info.json", "solution.jl",
                 "grader/run.jl", "grader/worker.jl", "data/values.csv")
        @test occursin(name, String(copy(bytes)))
    end
    @test !occursin("bash\r", String(copy(bytes)))   # shell scripts keep LF endings
    @test occursin("JULIA_VERSION=\"$(VERSION.major).$(VERSION.minor).$(VERSION.patch)\"", String(copy(bytes)))

    # Problems are reported at build time, not on Gradescope.
    bad, badsol = assignment(joinpath(tmp, "b"); rubric=SIMPLE_RUBRIC, solution="x = 41\ndouble(v) = 2v\n")
    write(badsol, "double(v) = 2v\n")
    @test_throws ErrorException build(bad, badsol; output=joinpath(tmp, "b.zip"), io=devnull)
    for (change, msg) in [
            (r -> r["language"] = "python", "Python autobuilder"),
            (r -> r["test_suite"][1]["type"] = "plot", "must include \"Plots\""),
            (r -> (r["requirements"] = ["Plots"]; r["test_suite"][1]["type"] = "plot";
                   r["test_suite"][1]["plot_checks"] = ["colour"]), "unknown plot check \"colour\""),
            (r -> r["test_suite"][2]["inputs"] = ["\$v"], "inputs file is needed"),
            (r -> r["extra_files"] = ["missing.csv"], "not found"),
            (r -> r["extra_files"] = ["solution.jl"], "clashes"),
            (r -> r["requirements"] = ["numpy"], "Julia package names"),
        ]
        r = deepcopy(SIMPLE_RUBRIC); change(r)
        rb, sol = assignment(mktempdir(); rubric=r, solution=SIMPLE_SOLUTION)
        err = try
            redirect_stderr(devnull) do
                build(rb, sol; output=joinpath(tmp, "x.zip"), io=devnull)
            end
            nothing
        catch e
            e
        end
        @test err isa ErrorException && occursin(msg, err.msg)
    end
end

@testset "command line" begin
    d = joinpath(EXAMPLES, "basics")
    cli = joinpath(ROOT, "bin", "autobuilder.jl")
    out = read(`$(Base.julia_cmd()) --startup-file=no $cli grade $(joinpath(d, "rubric.json")) $(joinpath(d, "solution.jl")) $(joinpath(d, "submission_03_missing_function.jl"))`, String)
    @test occursin("Total: 3", out)
    @test !success(`$(Base.julia_cmd()) --startup-file=no $cli frobnicate`)
end

end
