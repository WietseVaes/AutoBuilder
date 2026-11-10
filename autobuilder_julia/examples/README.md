# Julia examples: Gradescope test plan

Back to the [Julia README](../README.md) or the [overview](../../README.md).

Each folder is a complete assignment: `rubric.json`, `solution.jl`, sometimes `test_inputs.jl` and data files, and several submissions. The first line of each submission says the score it should get and why. Every example has been graded locally with these exact results. The test suite (`test/runtests.jl`) checks them on every run.

## Building the zips

`autograder.zip` has already been built in every folder. To rebuild one:

```bash
cd autobuilder_julia/examples/total_test
julia ../../bin/autobuilder.jl build rubric.json solution.jl --inputs test_inputs.jl
```

(Only `total_test` and `callable_test` need `--inputs test_inputs.jl`. Any example can also be built from a notebook solution; `total_test/solution_notebook.ipynb` is one.)

On Gradescope: create a **Programming Assignment** → Configure Autograder → **Zip file upload** → upload `autograder.zip` (the default Ubuntu 22.04 base image is fine) → wait until the image build says it succeeded. Building the image installs Julia and the packages. It takes a few minutes, longest for `plot_test` (Plots, about 3 minutes), `total_test` (Optim) and `dataframe_test` (DataFrames).

## Start here: `total_test` (tests the most)

25 points, 12 tests. It covers:
- strings, integer and float vectors, a range, a dot product
- a matrix-valued function (`rk4_solve`, which must return 2×11)
- functions called with inputs from `test_inputs.jl`
- a package (**Optim**), the standard library (`LinearAlgebra`), and a data file (`data.csv`)
- all five hint types, `_julia` hint overrides, and a **hint image** on T7
- **attempt limits** (T1-T8, T10, T11)
- a Jupyter notebook, a script that crashes part-way, an infinite loop (180 s timeout), and a two-file submission

| Submission | Score | What to look for |
|---|---|---|
| `submission_01_everything_wrong.jl` | 0 | Every test fails, each with a different message (wrong string, NaN, "Expected a 2×11 matrix, but got a 11×2 matrix", ...). T7 shows the hint image. |
| `submission_02_strings_list_fixed.jl` | 10 | `grid` has 6 points: "Expected a vector of length 5, but got a vector of length 6" plus the `_julia` hint. |
| `submission_03_variables_fixed.jl` | 14 | RK4 missing `/6`; `rk4_solve` returns 2×10. |
| `submission_04_correct.jl` | 25 | |
| `submission_05_correct_notebook.ipynb` | 25 | A notebook with a `Pkg.add("Optim")` cell, which the grader skips. |
| `submission_06_crashes_halfway.jl` | 16 | At the top: "Your code stopped with an error: UndefVarError: \`wieghts\` not defined (at ...:25)". T1-T8 are still graded, because this rubric sets `"grade_until_crash": true`. Without it (the default), every test would fail with that error. |
| `submission_07_infinite_loop.jl` | 16 | Takes the full **180 s**. T1-T8 keep their points; T9-T12 say the code did not finish in time. |
| `submission_08_two_files/` (upload **both** files) | 25 | `homework.jl` includes `rk4.jl`, and `homework.jl` is graded. |

**Attempt limits and best scores.** As in the Python version, each student's score per attempt-limited test is their best so far. Once a student has full marks on all of those tests, further submissions are not graded ("All questions have been answered correctly..."). So:

- **To check each row of the table**, upload each submission for a *different* student (Manage Submissions → Upload Submission → pick a student).
- **To check the attempt logic itself**, upload for one student in this order: `01` (0, "attempt: 1/10") → `02` (10) → `03` (14) → `04` (25) → `05`, which should be refused with "All questions have been answered correctly".

## Plots and Unicode names: `plot_test`

20 points, 6 tests. Plots.jl plot tests (a line plot with legend and a hint image, two lines with fixed y-limits, a bar chart stored in a variable), and Unicode names: a variable `λ`, a function `σ²`, an argument `λ₀`.

| Submission | Score | What to look for |
|---|---|---|
| `submission_01_correct.jl` | 20 | |
| `submission_02_wrong_labels.jl` | 10 | P1 lists three problems at once ('xlabel', 'title', legend labels) and shows the hint image; P2's legend is turned off. |
| `submission_03_wrong_data.jl` | 3 | Wrong data in the line plot, one line instead of two ("Expected 2 for 'n_lines', but got 1."), wrong bar heights. |
| `submission_04_not_a_plot.jl` | 0 | Uses `lam` instead of `λ` ("Variable 'λ' is not defined."); the plot function displays the plot but returns nothing ("Expected a Plots.jl plot ... but got type Nothing."); `bars_plot` holds the data instead of a plot. |
| `submission_05_saves_and_displays.jl` | 20 | Correct, and calls `display` and `savefig`, which must work on Gradescope's server without a screen. |

## Assignments that check incorrect work is caught

| Folder | Points | Submissions (score) | Checks |
|---|---|---|---|
| `function_unit_test` | 8 | `01_missing_function` (0), `02_wrong_shape` (0), `03_Euler` (2), `04_correct` (8), `05_type_error` (0) | misnamed function, scalar instead of vector, wrong numerics, a MethodError from too strict a type signature |
| `expected_test` | 4 | `01_missing_var` (0), `02_incorrect` (0), `03_matrix_not_vector` (0), `04_correct` (4) | fixed `"expected"` values in the rubric, a 4×1 matrix vs a vector, attempts (2) |
| `callable_test` | 5 | `01_correct` (5), `02_wrong` (0) | functions passed as inputs from `test_inputs.jl` |
| `extra_files_test` | 2 | `01_correct` (2), `02_header_counted` (0) | data files, including one in a subfolder; a script that crashes on bad input |
| `dataframe_test` | 10 | `01_correct` (10), `02_wrong_columns` (3), `03_wrong_threshold` (0) | DataFrames package; column names, Bool columns, group averages |

## Other examples

| Folder | Points | Submissions |
|---|---|---|
| `basics` | 4 | correct (4), wrong values (1), missing function (3), wrong type (3) |
| `arrays_and_functions` | 13 | correct (13), tolerance (0), wrong type/size (2), missing (4), NaNs (10) |
| `packages_and_inputs` | 7 | correct (7), errors part-way (0), notebook (7); needs `--inputs test_inputs.jl` |

## Testing a submission locally first

```bash
cd autobuilder_julia/examples/total_test
julia ../../bin/autobuilder.jl grade rubric.json solution.jl submission_06_crashes_halfway.jl --inputs test_inputs.jl
```

This runs exactly the code Gradescope runs, so the output should match what you see there. The exceptions are attempt counts and best scores, which depend on a student's earlier Gradescope submissions.
