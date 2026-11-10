# AutoBuilder

Builds Gradescope autograders from a `rubric.json` and a solution script. There are two separate tools, one per language:

| | For | Solution | Students submit | Documentation |
|---|---|---|---|---|
| **[Python autobuilder](autobuilder_python/README.md)** | Python assignments | `solution.py` or `.ipynb` | `.py`, `.ipynb` | [autobuilder_python/README.md](autobuilder_python/README.md) |
| **[Julia autobuilder](autobuilder_julia/README.md)** | Julia assignments | `solution.jl` or `.ipynb` | `.jl`, Julia `.ipynb`, Pluto | [autobuilder_julia/README.md](autobuilder_julia/README.md) |

They share no code, only the `rubric.json` format and the commands:

| | Python | Julia |
|---|---|---|
| Build the zip to upload to Gradescope | `autobuilder build rubric.json solution.py` | `julia autobuilder_julia/bin/autobuilder.jl build rubric.json solution.jl` |
| Grade one submission locally, as Gradescope will | `autobuilder grade rubric.json solution.py submission.py` | `julia autobuilder_julia/bin/autobuilder.jl grade rubric.json solution.jl submission.jl` |

A rubric declares its language with `"language": "python"` (the default) or `"language": "julia"`. Each tool rejects the other language's rubrics, and you can change one tool without affecting the other.

## What both do

- **Test types:** variables, functions (with inputs, including functions as inputs), DataFrames and plots (matplotlib / Plots.jl). Students get a short message per test plus your hints, never the expected answer.
- **Hints:** five kinds (not defined, wrong type, wrong size, NaN, wrong value), optionally with an image. `hint_*_python` / `hint_*_julia` give language-specific wording in a shared rubric.
- **Attempt limits:** a score per question that locks in the best attempt.
- **Robust grading:** if the student's script crashes part-way, everything defined before the crash is still graded; if it runs out of time, finished tests keep their result.
- **Submissions:** any file name, notebooks, several files, and data files you ship with the assignment.

## Differences

| | Python | Julia |
|---|---|---|
| Packages | `"requirements"`: pip packages, newest version when Gradescope builds the image (pin them yourself, e.g. `numpy==1.26.4`) | `"requirements"`: Julia packages, exact versions pinned automatically at build time |
| Packages in local `grade` | everything installed on your machine | only the assignment's packages, as on Gradescope |
| Default `timeout` | 10 s | 600 s (Julia needs a few seconds to start) |
| Checking at build time | the solution runs and defines every name the rubric asks for | the solution is graded against its own rubric with the real autograder |
| Plots | matplotlib (`Axes` / `Figure`) | Plots.jl |

## Getting started

- **Python:** `pip install "git+https://github.com/WietseVaes/AutoBuilder.git#subdirectory=autobuilder_python"`, then see the [Python README](autobuilder_python/README.md).
- **Julia:** clone this repository (nothing to install), then see the [Julia README](autobuilder_julia/README.md). It starts with [a complete example of building a rubric](autobuilder_julia/README.md#a-complete-example-building-a-rubric).
- **Examples:** [Python examples](autobuilder_python/examples) and [Julia examples](autobuilder_julia/examples). The [Julia examples guide](autobuilder_julia/examples/README.md) is a step-by-step plan for testing on Gradescope, with every submission's expected score.

Built with the help of [Anthropic's Claude](https://claude.com).
