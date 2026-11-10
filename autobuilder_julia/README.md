# autobuilder (Julia)

Builds Gradescope-ready autograder zips for **Julia** assignments from a rubric + solution script. Everything runs in Julia: your solution and the student's code are loaded side by side and their values are compared directly, with no conversion step between languages.

For Python assignments, use the separate Python autobuilder: see the [Python README](../autobuilder_python/README.md). Both read the same `rubric.json` format and have the same `build` / `grade` commands. Back to the [overview](../README.md).

Built with the help of [Anthropic's Claude](https://claude.com).

## Contents

- [Installation](#installation)
- [Building an autograder zip](#building-an-autograder-zip)
- [Local self-check](#local-self-check)
- [A complete example: building a rubric](#a-complete-example-building-a-rubric)
- [rubric.json format](#rubricjson-format)
- [Packages](#packages)
- [Student submission](#student-submission)
- [Worked examples](#worked-examples)
- [How it works](#how-it-works)

## Installation

Needs **Julia 1.10 or newer**. The autobuilder only uses Julia's standard library, so there is nothing else to install. Clone the repository and run the script in `autobuilder_julia/bin`:

```bash
git clone https://github.com/WietseVaes/AutoBuilder.git
julia AutoBuilder/autobuilder_julia/bin/autobuilder.jl build rubric.json solution.jl
```

Or install it as a package and use it from the Julia REPL:

```julia
using Pkg
Pkg.add(url="https://github.com/WietseVaes/AutoBuilder.git", subdir="autobuilder_julia")

using AutoBuilder
build("rubric.json", "solution.jl")
grade("rubric.json", "solution.jl", "submission.jl")
```

To upgrade the package: `Pkg.update("AutoBuilder")`. For a clone: `git pull`.

### A short `autobuilder-jl` command

To type `autobuilder-jl build ...` instead of `julia path/to/autobuilder.jl build ...`, add a shortcut. Replace `<path>` with where you cloned the repository. The name `autobuilder-jl` keeps it apart from the Python `autobuilder` command.

**Windows** (PowerShell): add this line to your profile (`notepad $PROFILE`), then reopen the terminal:

```powershell
function autobuilder-jl { julia "<path>\AutoBuilder\autobuilder_julia\bin\autobuilder.jl" @args }
```

**macOS** (zsh):

```bash
echo 'alias autobuilder-jl="julia <path>/AutoBuilder/autobuilder_julia/bin/autobuilder.jl"' >> ~/.zshrc
source ~/.zshrc
```

**Linux** (bash):

```bash
echo 'alias autobuilder-jl="julia <path>/AutoBuilder/autobuilder_julia/bin/autobuilder.jl"' >> ~/.bashrc
source ~/.bashrc
```

The rest of this README writes `julia autobuilder.jl` for the full command.

---

## Building an autograder zip

### Without an inputs file

```bash
julia autobuilder.jl build rubric.json solution.jl
```

`build` first grades your solution against its own rubric, with exactly the code that will run on Gradescope. A mistake in the rubric or solution therefore shows up now rather than after students submit. Then it writes `autograder.zip`.

The solution can also be a Jupyter notebook with a Julia kernel (`julia autobuilder.jl build rubric.json solution.ipynb`). It's converted to `solution.jl` at build time, the same way student notebooks are: code cells are joined, and `]add`, `;shell` and `?help` lines are dropped. `grade` accepts a notebook solution too.

### With an inputs file

```bash
julia autobuilder.jl build rubric.json solution.jl --inputs test_inputs.jl
```

`test_inputs.jl` is a plain Julia script defining values referenced in the rubric with a `$` prefix (see [below](#using-an-inputs-file--references)). It can hold any Julia value, including functions.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--inputs` | — | Path to a `.jl` file defining input values |
| `--output` | `autograder.zip` | Output zip path |
| `--timeout` | `600` | Seconds a submission may run in total on Gradescope (overrides the rubric's `timeout`) |

From the REPL: `build("rubric.json", "solution.jl"; inputs="test_inputs.jl", output="autograder.zip", timeout=600)`.

### Uploading to Gradescope

Create a **Programming Assignment** → *Configure Autograder* → **Zip file upload** → upload `autograder.zip`. The default base image (Ubuntu 22.04) works. Gradescope then builds the image, installing Julia (the version you built with) and your packages. That takes a few minutes, but happens only once per upload; after that each submission takes a few seconds.

---

## Local self-check

```bash
julia autobuilder.jl grade rubric.json solution.jl submission.jl
julia autobuilder.jl grade rubric.json solution.jl submission.jl --inputs test_inputs.jl
```

This grades one submission with exactly the code Gradescope runs, so the output matches what students will see. The exceptions are attempt counts and best scores, which depend on a student's earlier submissions. `SUBMISSION` can be a single file or a folder of files. `--json-out results.json` also saves the results.

---

## A complete example: building a rubric

Say the assignment asks students to compute a decay rate, write a function, and make a plot.

**1. Write the solution**, `solution.jl`:

```julia
using Plots

λ = log(2) / 5.7            # \lambda<tab>: decay rate of carbon-14 (per 1000 years)

remaining(m0, t) = m0 * exp(-λ * t)

function decay_plot()
    t = range(0, 20; length=50)
    return plot(t, remaining.(100, t); xlabel="time (1000 years)", ylabel="mass (g)",
                title="Radioactive decay", label="C-14")
end
```

**2. Write the rubric**, `rubric.json`, with one entry per thing to check:

```json
{
  "language": "julia",
  "requirements": ["Plots"],
  "test_suite": [
    {
      "test_name": "Q1",
      "type": "variable",
      "variable_name": "λ",
      "description": "λ is the decay rate log(2)/5.7",
      "rtol": 1e-6,
      "atol": 1e-9,
      "score": 2,
      "hint_not_defined": "Name the decay rate λ (type \\lambda then Tab).",
      "hint_tolerance": "λ = log(2) / half-life."
    },
    {
      "test_name": "Q2a",
      "type": "function",
      "function_name": "remaining",
      "inputs": [100.0, 5.7],
      "description": "remaining(100, 5.7) is half of 100",
      "score": 2,
      "hint_not_defined": "Define a function remaining(m0, t).",
      "hint_tolerance": "After one half-life, half of the mass remains."
    },
    {
      "test_name": "Q2b",
      "type": "function",
      "function_name": "remaining",
      "inputs": [[100.0, 50.0], 1.0],
      "description": "remaining works for a vector of masses",
      "score": 1,
      "hint_wrong_size": "Return one value per starting mass.",
      "hint_tolerance": "Use the same formula for every starting mass."
    },
    {
      "test_name": "Q3",
      "type": "plot",
      "function_name": "decay_plot",
      "inputs": [],
      "description": "decay_plot() draws the labelled decay curve",
      "plot_checks": ["xlabel", "ylabel", "title", "n_lines", "line_data"],
      "score": 3,
      "hint_wrong_type": "decay_plot() should return the plot, not display it.",
      "hint_tolerance": "Check the labels and plot remaining.(100, t) for 50 points of t in [0, 20]."
    }
  ]
}
```

**3. Try it on a test submission**, ideally one with a mistake, to see the messages students will get:

```bash
julia autobuilder.jl grade rubric.json solution.jl my_wrong_attempt.jl
```

For an attempt that wrote `m0 * exp(-t / λ)` instead of `m0 * exp(-λ * t)`:

```
[PASS] λ is the decay rate log(2)/5.7
[FAIL] remaining(100, 5.7) is half of 100
       Your value is not within the required tolerance.
       Hint: After one half-life, half of the mass remains.
[FAIL] remaining works for a vector of masses
       Your value is not within the required tolerance.
       Hint: Use the same formula for every starting mass.
[FAIL] decay_plot() draws the labelled decay curve
       The following issues were found:
         - Line 1's data does not match within tolerance.
       Hint: Check the labels and plot remaining.(100, t) for 50 points of t in [0, 20].

Total: 2
```

**4. Build and upload:**

```bash
julia autobuilder.jl build rubric.json solution.jl
```

```
Checking the solution against the rubric...
Solution check: 4/4 tests pass.
Wrote autograder.zip
```

---

## rubric.json format

```json
{
  "language": "julia",
  "requirements": ["DataFrames", "Plots"],
  "extra_files": ["train_data.csv", "data/test_data.csv"],
  "timeout": 600,
  "julia_version": "1.11.7",
  "grade_until_crash": false,
  "debug": false,
  "test_suite": [ ... ]
}
```

| Field | Description |
|-------|-------------|
| `language` | `"julia"`, or leave it out. A `"python"` rubric is rejected -- use the [Python autobuilder](../autobuilder_python/README.md) for those |
| `requirements` | **Julia** packages the assignment uses (see [Packages](#packages)). Standard-library packages (`LinearAlgebra`, `Statistics`, `Printf`, ...) never need listing |
| `extra_files` | Data files placed next to `rubric.json` (subfolders work), copied into the zip at the same relative path. Code runs from that folder, so `readlines("data.csv")` works |
| `timeout` | Seconds a submission may run in total, including loading packages (default 600) |
| `julia_version` | Julia version installed on Gradescope (default: the version you build with) |
| `grade_until_crash` | What happens when the student's script crashes part-way or runs out of time. `false` (default): nothing is graded; every test fails with the error, e.g. `Variable 'x' is not defined. (UndefVarError: ...)` or `Variable 'x' is not defined. (This did not finish within 600 seconds.)`. `true`: everything graded before the crash or timeout keeps its result, and the error is shown once at the top |
| `debug` | `true` adds everything the code printed while grading to the results page |

### Test entry fields

| Field | Required | Description |
|-------|----------|-------------|
| `test_name` | ✓ | Unique identifier used internally and for attempt tracking |
| `type` | | `"variable"` (default), `"function"` or `"plot"` |
| `variable_name` / `function_name` | ✓ | What to check. Unicode names like `"λ"`, `"σ²"` or `"x₀"` work |
| `description` | ✓ | Test title shown to students |
| `score` | ✓ | Points for this test |
| `rtol`, `atol` | | Tolerances: values pass when `abs(s - r) <= atol + rtol*abs(r)` elementwise, as in `numpy.allclose`. Default `1e-6` (`1e-2` for plot tests). Use `0` for exact comparison |
| `inputs` | | Function arguments (function and plot tests) |
| `output_index` | | Check one value of a returned tuple. Counts from **0** (as in the Python autobuilder): `0` is the first value |
| `expected` | | A fixed expected value instead of the solution's (not for plot tests) |
| `attempts` | | Max number of attempted submissions for this question (see below) |
| `allow_tries` | | `true` = no attempt cap, just track running best (default `false`) |

### Hint fields

All hint fields are optional. When a test fails, the message shown to students is always a short, generic description of what went wrong (e.g. `Variable 'A2' is not defined.` or `Expected a 2×2 matrix, but got a vector of length 4.`) -- it never reveals the expected/solution value. If a matching hint is set, it's appended on its own line, always prefixed with `Hint:`. Any hint key can be suffixed with `_julia` (e.g. `hint_wrong_size_julia`), which overrides the plain version. This lets one rubric carry both `_python` and `_julia` wording; the Python autobuilder reads the `_python` ones.

| Field | When it appears |
|-------|-----------------|
| `hint_not_defined` | Variable/function is not defined (falls back to `hint_wrong_size`) |
| `hint_wrong_type` | Value is the wrong kind of type, e.g. a string instead of a number (falls back to `hint_wrong_size`) |
| `hint_wrong_size` | Array/DataFrame/plot has the wrong size, e.g. a 1×3 matrix instead of a vector |
| `hint_nans` | Value contains NaN (falls back to `hint_tolerance`) |
| `hint_tolerance` | Value is the right type and size but incorrect |
| `hint_image` | Filename of an image (next to `rubric.json`) shown alongside the `hint_nans` / `hint_tolerance` hints |

### Variable test

Compares a named variable from the student's script against `solution.jl` (default) or a hardcoded `expected` value.

```json
{
  "test_name": "A1",
  "type": "variable",
  "variable_name": "result",
  "description": "result is correct",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 2,
  "hint_not_defined": "Define a variable called result.",
  "hint_wrong_type": "result should be a Vector of numbers.",
  "hint_wrong_size": "result should have 3 elements.",
  "hint_nans": "result must not contain NaN.",
  "hint_tolerance": "Check your formula."
}
```

To use a hardcoded expected value instead of comparing to `solution.jl`:

```json
"expected": 42.0
```

Strings, booleans, vectors and matrices also work -- set `rtol: 0, atol: 0` for exact comparison:

```json
"expected": "hello world"
```

### Function test

Calls a named function with given inputs and compares the return value against `solution.jl`.

```json
{
  "test_name": "B1",
  "type": "function",
  "function_name": "rk4_step",
  "inputs": [[-1.0, 4.0], 0.1],
  "description": "rk4_step([-1, 4], 0.1)",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 3,
  "hint_not_defined": "Define a function called rk4_step.",
  "hint_wrong_size": "rk4_step should return a length-2 vector.",
  "hint_tolerance": "Check your RK4 weighted average: (k1 + 2k2 + 2k3 + k4) / 6."
}
```

The same function can appear in multiple test entries with different inputs. Each call gets its own copy of the inputs, so a function that modifies its arguments can't affect other tests. JSON values become the Julia value you would most likely have written:

| In rubric.json | In Julia |
|---|---|
| `5` / `5.0` / `1e-3` | `5` (Int) / `5.0` / `0.001` (Float64) |
| `[1, 2, 3]` / `[1.0, 2, 3]` | `Vector{Int}` / `Vector{Float64}` |
| `[[1, 2, 3], [4, 5, 6]]` | 2×3 `Matrix` (each inner list is a **row**) |
| `["a", "b"]`, `[true, false]` | `Vector{String}`, `Vector{Bool}` |
| `"$name"` | the value of `name` from the [inputs file](#using-an-inputs-file--references) |

Write `1.0` rather than `1` when the student's function only accepts floats (e.g. `f(x::Vector{Float64})`).

### DataFrame test

Works exactly like a variable or function test -- just have the result be a `DataFrame` (add `"DataFrames"` to `requirements`). Column names, size, and values are all checked.

```json
{
  "test_name": "D1",
  "type": "function",
  "function_name": "build_df",
  "inputs": [5],
  "description": "build_df(5) returns the correct DataFrame",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 4,
  "hint_not_defined": "Define a function called build_df(n).",
  "hint_wrong_type": "build_df should return a DataFrame.",
  "hint_wrong_size": "Check your column names and the number of rows.",
  "hint_nans": "Your DataFrame contains NaN values.",
  "hint_tolerance": "Check the values in each column."
}
```

Column order and names must match exactly. Text columns must be equal; numeric columns use `rtol`/`atol` like everything else. A failure names the column, e.g. `Column 'score': Your value is not within the required tolerance.`

### Plot test

Verifies a **Plots.jl** plot by inspecting its properties (labels, axis limits, line/bar data) -- never by comparing rendered pixels, which is unreliable across machines. Use `"type": "plot"` with a function that returns (or a variable that holds) a plot, i.e. the result of `plot(...)`, `scatter(...)`, `bar(...)`, `histogram(...)` or `plot!(p, ...)`. Add `"Plots"` to `requirements`.

```json
{
  "test_name": "P1",
  "type": "plot",
  "function_name": "make_plot",
  "inputs": [1.0],
  "description": "make_plot(1.0) produces the correct sine curve",
  "plot_checks": ["xlabel", "ylabel", "n_lines", "line_data"],
  "rtol": 1e-2,
  "atol": 1e-2,
  "score": 5,
  "hint_not_defined": "Define a function called make_plot(scale).",
  "hint_wrong_type": "make_plot should return the plot (end it with plot(...), not display(...)).",
  "hint_wrong_size": "Check that you plot exactly one line with the right number of points.",
  "hint_tolerance": "Check the axis labels and the plotted x/y values."
}
```

`plot_checks` is a list naming which properties to verify (default: `["xlabel", "ylabel", "title", "n_lines", "line_data"]`):

| Check | What it verifies |
|-------|-------------------|
| `xlabel`, `ylabel`, `title` | Exact string match |
| `xlim`, `ylim` | Axis limits as drawn (also when Plots chose them automatically), tolerance-based |
| `n_lines` | Number of plotted lines and scatter series |
| `line_data` | Each line's x/y data, tolerance-based |
| `n_bars` | Number of bars (bar charts and histograms) |
| `bar_heights` | Bar heights, tolerance-based |
| `legend_labels` | Exact list of legend labels (empty if the legend is turned off) |

`rtol`/`atol` for plot tests default to `1e-2` (looser than the `1e-6` default for numeric tests) since plotted data is usually less precision-sensitive. Only the first subplot is checked.

When a plot test fails, every mismatched property is listed (not just the first one found), e.g.:

```
The following issues were found:
  - 'xlabel' does not match.
  - 'title' does not match.
  - Legend labels do not match.
```

Students can call `display(...)` or `savefig(...)` in their code; that works on Gradescope too, where there is no screen.

The plot test reads some Plots.jl internals. That's safe because the Plots version is pinned in the zip, but **after upgrading Plots, rebuild and check**: `build` grades your solution against itself first, so a Plots change that breaks the checks shows up there.

### Other Julia values

Any value can be checked. Collections are compared element by element, and a failure says where:

| Reference value | Check |
|---|---|
| Number, numeric array (any dimension), numeric tuple | same size, no NaN, within tolerance; Ints, floats and complex numbers mix freely, and a range counts as a vector |
| String / `true`, `false` | exact |
| Tuple, named tuple, dictionary, array of anything | same length / names / keys, then each element, e.g. `Element 2: ...` |
| Struct, e.g. `Point(1.0, 2.0)` | same type name, then field by field, e.g. `Field y: ...` (the student's own `Point` type counts) |
| Anything else (`Symbol`, `nothing`, ...) | equal |

### Showing an image as a hint

Add `"hint_image"` naming an image file placed next to `rubric.json`:

```json
"hint_tolerance": "Your plot should look like this.",
"hint_image": "expected_plot.png"
```

At build time the image is read and embedded in the zip as a base64 data URI -- no filesystem access is needed at grading time, and nothing depends on a file path being reachable from the student's browser. Supported formats: `.png`, `.jpg`/`.jpeg`, `.gif`, `.svg`. The image is shown with the `hint_nans` / `hint_tolerance` hint for that test. Tip: make it from your solution with `savefig(decay_plot(), "expected_plot.png")`.

### Using an inputs file (`$`-references)

In `test_inputs.jl`:

```julia
y0 = [-1.0, 4.0]
dt = 0.1
f(x) = x^2          # functions work too
A = [1 2; 3 4]
```

In `rubric.json`, reference with `$`:

```json
"inputs": ["$y0", "$dt"]
```

Also works for `expected`:

```json
"expected": "$my_expected_value"
```

Pass the file with `--inputs test_inputs.jl`. It is shipped in the zip and run on Gradescope, so the values don't have to be expressible in JSON.

### Attempt limits

```json
"attempts": 5,
"allow_tries": false
```

`attempts` sets the maximum number of "attempted" submissions counted for this question. A submission counts as attempted if the variable or function was defined, regardless of correctness. The student's score is locked at the **best score across their attempts**.

`allow_tries: true` removes the cap -- every submission updates the running best with no limit.

Once all attempt-limited questions in a rubric are exhausted (or full credit is earned on all of them), further submissions are blocked with a message and the previous results are carried forward unchanged.

Attempt tracking requires Gradescope's "Allow resubmission" setting to be enabled on the assignment.

---

## Packages

List the packages in `"requirements"`:

```json
"requirements": ["SpecialFunctions", "DataFrames", "Plots"]
```

At build time these are resolved into a fresh environment, whose `Manifest.toml` goes into the zip. That pins the exact version of every package. On Gradescope, `setup.sh` installs and precompiles exactly those versions once, when the autograder image is built; grading never downloads anything.

If you already have a course environment, put its `Project.toml` (and optionally `Manifest.toml`) next to `rubric.json` instead. It is then used as-is, and `"requirements"` is ignored.

Students get only the packages in that environment plus the standard library, both locally and on Gradescope. A student who uses something else gets a clear `Package X not found` error. `Pkg.add(...)`, `Pkg.activate(...)` and similar calls in student code are skipped, and so are `]add` lines in notebooks.

**Updating** a package or the Julia version means rebuilding: run `build` again (with the newer Julia, if you want that version) and upload the new zip. Nothing changes on Gradescope until you do.

---

## Student submission

Students submit a `.jl` file, a Jupyter notebook (`.ipynb` with a Julia kernel), or a Pluto notebook (also a `.jl` file), under any name. They can also submit several files: a file that another submitted file `include`s is treated as a helper. Of the remaining files, the one that defines the most names the rubric is looking for is graded, and the student is told which one.

The student's code runs from where it was submitted, so `include("helpers.jl")` works, and nothing is copied over the autograder's own files: a student file named `solution.jl` or `rubric.json` changes nothing.

`.ipynb` submissions are converted to plain Julia before grading: code cells are joined in order, markdown cells are skipped, and lines in Pkg mode (`]add ...`), shell mode (`;ls`) or help mode (`?sin`) are dropped.

Unicode names (`λ`, `σ²`, `x₀`, `∇f`, typed as `\lambda<tab>` etc.) work everywhere: as variables, function names, function arguments, and in the rubric. A rubric written with the micro sign `µ` also finds a student's Greek `μ` (`\mu<tab>`), since Julia treats them as the same name.

What students see when their code goes wrong:

- **The script crashes part-way** (e.g. an `UndefVarError` on line 30): by default every test fails with the crash message, e.g. ``Variable 'x' is not defined. (UndefVarError: `y` not defined (at hw3.jl:30))``. With `"grade_until_crash": true` in the rubric, everything defined *before* that line is still graded instead: the error and its line number are shown once at the top of the results, and tests for names defined after it say "not defined. Your code stopped with an error before reaching it."
- **The code runs out of time** (e.g. an infinite loop inside a function): by default every test fails with `... is not defined. (This did not finish within N seconds.)`. With `"grade_until_crash": true`, tests that already finished keep their result, and the rest say "Your code did not finish within N seconds, so this test could not be completed."
- **A function raises an error:** that test shows the error message and the line in the student's file, e.g. `` UndefVarError: `x` not defined (at hw3.jl:12) ``.

`grade` shows the same messages, and uses the same time limit as the zip.

---

## Worked examples

All in [`examples/`](examples). [`examples/README.md`](examples/README.md) is a step-by-step plan for trying them on Gradescope, with every submission's expected score.

- `examples/total_test/` (**tests the most**): strings, vectors, a range, a dot product, RK4 functions (vector and 2×11 matrix results) with inputs from `test_inputs.jl`, a package (Optim), a data file, a hint image, attempt limits, and eight submissions from 0/25 to 25/25 -- including a notebook, a script that crashes part-way and an infinite loop (both graded up to that point: this rubric sets `"grade_until_crash": true`), and a two-file submission.
- `examples/plot_test/`: Plots.jl plot tests (a line plot with legend, two lines with fixed y-limits, a bar chart stored in a variable) and Unicode names (`λ`, `σ²`, `λ₀`), with submissions that get the labels wrong, the data wrong, or return no plot at all.
- `examples/function_unit_test/`, `expected_test/`, `callable_test/`, `extra_files_test/`, `dataframe_test/`: Julia versions of the Python examples, each with submissions that are wrong in a specific way.
- `examples/basics/`, `arrays_and_functions/`, `packages_and_inputs/`: smaller examples (matrices, tuples, structs, named tuples, a package).

```bash
cd autobuilder_julia/examples/total_test
julia ../../bin/autobuilder.jl grade rubric.json solution.jl submission_04_correct.jl --inputs test_inputs.jl
julia ../../bin/autobuilder.jl build rubric.json solution.jl --inputs test_inputs.jl
```

---

## How it works

```
run_autograder ─► grader/run.jl         finds the student's file, writes results.json
                    └─► grader/worker.jl   a separate Julia process (killed at the timeout):
                          solution.jl  → module Solution    ┐ each test: reference value vs
                          student file → module Submission  ┘ student value, compared
```

The worker writes each test's result as soon as it is known, which is what lets `"grade_until_crash": true` keep the earlier results after a hang or crash. The grader (`src/grader/`) uses only the standard library and is copied into every zip.

The zip contains `run_autograder`, `setup.sh`, your `rubric.json` (unchanged), `build_info.json`, `solution.jl`, the optional `test_inputs.jl` and `env/` (your packages), the `grader/` folder, and your `extra_files`.

As with the Python autobuilder, the solution file sits in the autograder's folder on Gradescope, so a student who deliberately reads files from disk could find it.

Run the autobuilder's own tests with:

```bash
julia --project=autobuilder_julia -e 'using Pkg; Pkg.test()'
```
