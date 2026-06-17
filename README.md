# autobuilder

Builds Gradescope-ready autograder zips from a rubric + solution script, using PyUnit and [gradescope-utils](https://github.com/gradescope/gradescope-utils).

## Installation

The repo must be **public** on GitHub. Then:

```bash
pip install git+https://github.com/WietseVaes/AutoBuilder.git
```

To upgrade:

```bash
pip install --upgrade git+https://github.com/WietseVaes/AutoBuilder.git
```

### Adding `autobuilder` to PATH

After install, if `autobuilder` is not recognised as a command, Python's scripts directory isn't on your PATH.

**Windows**

Temporary (current terminal session only):

```powershell
$env:PATH += ";C:\Users\<you>\AppData\Local\Python\pythoncore-3.14-64\Scripts"
```

Permanent (all future terminal sessions):

```powershell
[System.Environment]::SetEnvironmentVariable(
    "PATH",
    $env:PATH + ";C:\Users\<you>\AppData\Local\Python\pythoncore-3.14-64\Scripts",
    [System.EnvironmentVariableTarget]::User
)
```

Then reopen your terminal.

**macOS**

Temporary:

```bash
export PATH="$PATH:$(python3 -m site --user-base)/bin"
```

Permanent -- add the same line to your shell config and reload:

```bash
echo 'export PATH="$PATH:$(python3 -m site --user-base)/bin"' >> ~/.zshrc
source ~/.zshrc
```

If you use bash instead of zsh, replace `~/.zshrc` with `~/.bash_profile`.

**Linux**

Temporary:

```bash
export PATH="$PATH:$HOME/.local/bin"
```

Permanent:

```bash
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
source ~/.bashrc
```

---

## Building an autograder zip

### Without an inputs file

```bash
autobuilder build rubric.json solution.py
```

### With an inputs file

```bash
autobuilder build rubric.json solution.py --inputs test_inputs.py
```

`test_inputs.py` is a plain Python script defining variables referenced in the rubric with a `$` prefix (see below). Use this when test inputs are computed in Python rather than hardcoded as JSON.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--inputs` | — | Path to a `.py` file defining input variables |
| `--output` | `autograder.zip` | Output zip path |
| `--timeout` | `10` | Seconds allowed when validating `solution.py` at build time |

---

## Local self-check

```bash
autobuilder grade rubric.json solution.py submission.py
autobuilder grade rubric.json solution.py submission.py --inputs test_inputs.py
```

---

## rubric.json format

```json
{
  "language": "python",
  "requirements": ["numpy", "scipy"],
  "extra_files": ["train_data.csv", "test_data.csv"],
  "timeout": 10,
  "debug": false,
  "test_suite": [ ... ]
}
```

| Field | Description |
|-------|-------------|
| `language` | `"python"` (default) or `"julia"`. The whole assignment grades in one language -- see [Student submission](#student-submission) |
| `requirements` | pip packages installed by `setup.sh` on Gradescope |
| `extra_files` | Data files (`.csv` etc.) placed next to `rubric.json`, copied into the autograder zip and available at grading time |
| `timeout` | Seconds allowed when validating `solution.py` at build time |
| `debug` | `true` adds metadata diagnostics to the Gradescope results page (useful for troubleshooting attempt counters) |

### Test entry fields

| Field | Required | Description |
|-------|----------|-------------|
| `test_name` | ✓ | Unique identifier used internally and for attempt tracking |
| `type` | | `"variable"` (default) or `"function"` |
| `description` | ✓ | Test title shown to students |
| `score` | ✓ | Points for this test |
| `rtol`, `atol` | ✓ | Tolerances for `numpy.allclose`. Use `0` for exact/string comparison |
| `attempts` | | Max number of attempted submissions for this question (see below) |
| `allow_tries` | | `true` = no attempt cap, just track running best (default `false`) |

### Hint fields

All hint fields are optional. When a test fails, the message shown to students is always a short, generic description of what went wrong (e.g. `Variable 'A2' is not defined.` or `Your value is not within the required tolerance.`) -- it never reveals the expected/solution value. If a matching hint is set, it's appended on its own line, always prefixed with `Hint:`. Any hint key can be suffixed with `_python` to apply only to Python submissions (e.g. `hint_wrong_size_python`), which overrides the plain version.

| Field | When it appears |
|-------|-----------------|
| `hint_not_defined` | Variable/function could not be imported (falls back to `hint_wrong_size`) |
| `hint_wrong_type` | Value is the wrong Python type (falls back to `hint_wrong_size`) |
| `hint_wrong_size` | Array/DataFrame/plot has the wrong shape |
| `hint_nans` | Value contains NaN (falls back to `hint_tolerance`) |
| `hint_tolerance` | Value is the right type and shape but numerically incorrect |
| `hint_image` | Filename of an image (next to `rubric.json`) shown alongside any hint above |

### Variable test

Compares a named variable from the student's script against `solution.py` (default) or a hardcoded `expected` value.

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
  "hint_wrong_type": "result should be a numpy array.",
  "hint_wrong_size": "result should have shape (3,).",
  "hint_nans": "result must not contain NaN.",
  "hint_tolerance": "Check your formula."
}
```

To use a hardcoded expected value instead of comparing to `solution.py`:

```json
"expected": 42.0
```

Strings, booleans, and lists also work -- set `rtol: 0, atol: 0`:

```json
"expected": "hello world"
```

### Function test

Calls a named function with given inputs and compares the return value against `solution.py`.

```json
{
  "test_name": "B1",
  "type": "function",
  "function_name": "rk4_step",
  "inputs": [[-1, 4], 0.1],
  "description": "rk4_step([-1, 4], 0.1)",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 3,
  "hint_not_defined": "Define a function called rk4_step.",
  "hint_wrong_size": "rk4_step should return a length-2 array.",
  "hint_tolerance": "Check your RK4 weighted average: (k1 + 2*k2 + 2*k3 + k4) / 6."
}
```

JSON lists of numbers are automatically converted to numpy arrays before the call. The same function can appear in multiple test entries with different inputs.

### DataFrame test

Works exactly like a variable or function test -- just have the result be a `pandas.DataFrame`. Column names, shape, dtypes, and values are all checked.

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
  "hint_wrong_type": "build_df should return a pandas DataFrame.",
  "hint_wrong_size": "Check your column names and the number of rows.",
  "hint_nans": "Your DataFrame contains NaN values.",
  "hint_tolerance": "Check the values in each column."
}
```

Column order and names must match exactly. Non-numeric columns are compared for exact equality; numeric columns use `rtol`/`atol` like everything else.

### Plot test

Verifies a matplotlib plot by inspecting the `Axes` object's properties (labels, axis limits, line/bar data) -- never by comparing rendered pixels, which is unreliable across machines (fonts, DPI, anti-aliasing all differ). Use `"type": "plot"` with a function that returns (or a variable that holds) a matplotlib `Axes` or `Figure`.

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
  "hint_wrong_type": "make_plot should return a matplotlib Axes (or Figure).",
  "hint_wrong_size": "Check that you plot exactly one line with the right number of points.",
  "hint_tolerance": "Check the axis labels and the plotted x/y values."
}
```

`plot_checks` is a list naming which properties to verify (default: `["xlabel", "ylabel", "title", "n_lines", "line_data"]`):

| Check | What it verifies |
|-------|-------------------|
| `xlabel`, `ylabel`, `title` | Exact string match |
| `xlim`, `ylim` | Axis limits, tolerance-based |
| `n_lines` | Number of plotted lines |
| `line_data` | Each line's x/y data, tolerance-based |
| `n_bars` | Number of bars (bar charts) |
| `bar_heights` | Bar heights, tolerance-based |
| `legend_labels` | Exact list of legend label strings |

`rtol`/`atol` for plot tests default to `1e-2` (looser than the `1e-6` default for numeric tests) since plotted data is usually less precision-sensitive.

When a plot test fails, every mismatched property is listed (not just the first one found), e.g.:

```
The following issues were found:
  - 'xlabel' does not match.
  - 'title' does not match.
  - Legend labels do not match.
```

### Showing an image as a hint

Add `"hint_image"` naming an image file placed next to `rubric.json`:

```json
"hint_tolerance": "Your plot should look like this.",
"hint_image": "expected_plot.png"
```

At build time the image is read and embedded as a base64 data URI baked directly into the generated test code -- no filesystem access is needed at grading time, and nothing depends on a file path being reachable from the student's browser (which it never is, by design). Supported formats: `.png`, `.jpg`/`.jpeg`, `.gif`, `.svg`. The image is shown alongside the hint on any failure for that test.

### Using an inputs file (`$`-references)

In `test_inputs.py`:

```python
import numpy as np
y0 = np.array([-1.0, 4.0])
dt = 0.1
```

In `rubric.json`, reference with `$`:

```json
"inputs": ["$y0", "$dt"]
```

Also works for `expected`:

```json
"expected": "$my_expected_value"
```

Numpy arrays are automatically serialised to lists when embedded in the generated test code.

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

## Student submission

Each assignment grades in exactly one language, declared once in `rubric.json`:

```json
{
  "language": "julia"
}
```

Defaults to `"python"` if omitted, so existing rubrics work unchanged. Students submit:
- **Python**: a `.py` file, or a `.ipynb` Jupyter notebook with a Python kernel, under any name.
- **Julia**: a `.jl` file, under any name.

If multiple files of the right language are submitted, the one that defines the most names the rubric is looking for is selected automatically. A submission in the *wrong* language for the assignment (e.g. a `.py` file submitted to a `language: "julia"` rubric) is rejected with a clear message rather than silently ignored or guessed about.

`.ipynb` (Jupyter notebook) submissions are converted to plain Python before grading: code cells are concatenated in order, markdown cells are skipped, and lines starting with `%` (magic commands like `%matplotlib inline`) or `!` (shell escapes like `!pip install ...`) are stripped, since they aren't valid outside Jupyter. Julia-kernel notebooks aren't supported yet.

### Julia support status (since v0.5.0)

Variable, scalar, string, and array tests work for Julia submissions the same way they do for Python: a generated test gets the value via a small Julia driver script (`_runner.jl`, run via the `julia` executable, vendored into the zip), serializes it to JSON, and compares it with the exact same `compare()` logic used for Python -- so a single rubric entry's hints/tolerances/scoring work identically regardless of language, with no duplicated comparison code.

The solution (`solution.py`) is always Python, regardless of the assignment's declared language -- it's the instructor-controlled ground truth and doesn't need to match what students submit.

**Not yet supported for Julia submissions:**
- DataFrame tests (would need a `DataFrames.jl` -> JSON serialization path)
- Plot tests (matplotlib's `Axes` introspection has no Julia equivalent; Julia's plotting ecosystem -- Plots.jl, Makie.jl -- would need separate, backend-specific extraction code)
- Julia-kernel Jupyter/Pluto notebooks

**Important: the Julia path has not been tested against a real `julia` interpreter** -- this development environment has no Julia install and no network access to install one. The Python-side orchestration (language validation, building the subprocess call, JSON round-tripping, error handling when `julia` isn't found) has been verified, but `_runner.jl` itself (the actual Julia code that includes a script and serializes values) has only been reviewed, not executed. If you try the `autobuilder/examples/julia_test/` example and a variable reports as "not defined" even though it clearly is, `_runner.jl` will report (in `_error`) every name Julia actually sees defined after running the script -- check that message first, it's designed to make this specific failure mode diagnosable without needing back-and-forth.

`setup.sh` only installs Julia (currently pinned to 1.10.4) and the `JSON` package when `rubric.json` declares `"language": "julia"` -- Python-only assignments (the default) build and grade without any Julia-related setup overhead.

---

## Worked examples

- `autobuilder/examples/total_test/`: strings, lists, numpy arrays, a function (RK4 step), and a maximisation problem, with five example submissions (four `.py`, one `.ipynb`) showing a progression from 0/20 to 20/20. Every test entry's `rubric.json` has all five hint types filled in, as a reference.
- `autobuilder/examples/dataframe_test/`: a `pandas.DataFrame` built from scratch, a derived column, and a groupby summary -- three submissions showing a column-name mismatch and a value mismatch cascading into a dependent test.
- `autobuilder/examples/plot_test/`: a numpy array plus a matplotlib plot of it, with separate `hint_wrong_size`/`hint_tolerance` hints on both the array test and the plot test. The plot test's `hint_image` (a rendered reference plot, `expected_damped_wave.png`) is attached only to its tolerance-failure path -- five submissions demonstrate the image appearing only when the *values* are wrong (not the size), and every plot mismatch being listed individually rather than stopping at the first.
- `autobuilder/examples/julia_test/`: `rubric.json` with `"language": "julia"`, the same string/scalar/array/function checks as the other examples, with three `.jl` submissions (correct, wrong values, misnamed function). **Untested against a real Julia install**, see the Julia support section above.

```bash
cd autobuilder/examples/total_test
autobuilder grade rubric.json solution.py submission_04_correct.py --inputs test_inputs.py
autobuilder build rubric.json solution.py --inputs test_inputs.py
```
