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
  "requirements": ["numpy", "scipy"],
  "extra_files": ["train_data.csv", "test_data.csv"],
  "timeout": 10,
  "debug": false,
  "test_suite": [ ... ]
}
```

| Field | Description |
|-------|-------------|
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

All hint fields are optional. When a test fails, the most specific matching hint is shown with a `Hint:` prefix. Any hint key can be suffixed with `_python` to apply only to Python submissions (e.g. `hint_wrong_size_python`), which overrides the plain version.

| Field | When it appears |
|-------|-----------------|
| `hint_not_defined` | Variable/function could not be imported (falls back to `hint_wrong_size`) |
| `hint_wrong_type` | Value is the wrong Python type (falls back to `hint_wrong_size`) |
| `hint_wrong_size` | Array has the wrong shape |
| `hint_nans` | Value contains NaN (falls back to `hint_tolerance`) |
| `hint_tolerance` | Value is the right type and shape but numerically incorrect |

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

Students can submit **any `.py` or `.ipynb` file under any name**. If multiple files are submitted, the one that defines the most names the rubric is looking for is selected automatically.

`.ipynb` (Jupyter notebook) submissions are converted to plain Python before grading: code cells are concatenated in order, markdown cells are skipped, and lines starting with `%` (magic commands like `%matplotlib inline`) or `!` (shell escapes like `!pip install ...`) are stripped, since they aren't valid outside Jupyter. No extra rubric configuration is needed -- notebook and script submissions are graded identically once converted.

---

## Worked example

See `autobuilder/examples/total_test/` for a complete example covering strings, lists, numpy arrays, a function (RK4 step), and a maximisation problem -- with `solution.py`, `rubric.json`, `test_inputs.py`, and five example student submissions showing a progression from 0/20 to 20/20. `submission_05_correct_notebook.ipynb` is the same correct solution submitted as a Jupyter notebook (with markdown cells and a `%matplotlib`/`!pip install` thrown in), to demonstrate `.ipynb` support. Every test entry in its `rubric.json` has all five hint types (`hint_not_defined`, `hint_wrong_type`, `hint_wrong_size`, `hint_nans`, `hint_tolerance`) filled in, plus two `_python`-suffixed overrides, as a reference for how to write them.

```bash
cd autobuilder/examples/total_test
autobuilder grade rubric.json solution.py submission_04_correct.py --inputs test_inputs.py
autobuilder build rubric.json solution.py --inputs test_inputs.py
```
