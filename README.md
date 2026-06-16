# autobuilder

Builds Gradescope-ready autograder zips from a rubric + solution script, using PyUnit and [gradescope-utils](https://github.com/gradescope/gradescope-utils). No manual pickling, no third-party autograder package needed on Gradescope's end.

## Installation

Make sure the repo is **public** on GitHub, then:

```bash
pip install git+https://github.com/WietseVaes/AutoBuilder.git
```

To upgrade:

```bash
pip install --upgrade git+https://github.com/WietseVaes/AutoBuilder.git
```

If `autobuilder` is not recognised as a command after install, add Python's Scripts folder to your PATH. On Windows:

```powershell
[System.Environment]::SetEnvironmentVariable(
    "PATH",
    $env:PATH + ";C:\Users\<you>\AppData\Local\Python\pythoncore-3.14-64\Scripts",
    [System.EnvironmentVariableTarget]::User
)
```

Then reopen your terminal.

---

## Building an autograder zip

### Without an inputs file

```bash
autobuilder build rubric.json solution.py
```

Generates `autograder.zip` in the current folder. Upload this to Gradescope under Configure Autograder.

### With an inputs file

```bash
autobuilder build rubric.json solution.py --inputs test_inputs.py
```

`test_inputs.py` is a plain Python script that defines variables referenced in the rubric with a `$` prefix (see below). Useful when test inputs are computed or loaded from data rather than hardcoded as JSON.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--inputs` | — | Path to a `.py` file defining input variables |
| `--output` | `autograder.zip` | Output zip path |
| `--timeout` | `10` | Seconds allowed when validating `solution.py` at build time |

---

## Local self-check

Run the exact same grading logic locally before uploading:

```bash
autobuilder grade rubric.json solution.py submission.py
autobuilder grade rubric.json solution.py submission.py --inputs test_inputs.py
```

---

## rubric.json format

```json
{
  "requirements": ["numpy", "scipy"],
  "timeout": 10,
  "debug": false,
  "test_suite": [ ... ]
}
```

`requirements` are installed by `setup.sh` on Gradescope. `debug: true` adds metadata diagnostics to the Gradescope results page (useful for troubleshooting attempt counters). `timeout` only applies when validating `solution.py` at build time.

### Test entry fields

Every test entry requires:

| Field | Description |
|-------|-------------|
| `test_name` | Unique identifier, used internally and for attempt tracking |
| `type` | `"variable"` (default) or `"function"` |
| `description` | Shown to students as the test title |
| `score` | Points for this test |
| `hint_wrong_size` | Shown when the type or shape is wrong |
| `hint_tolerance` | Shown when the value is wrong |
| `rtol`, `atol` | Tolerances for `numpy.allclose` (use `0` for exact/string comparison) |

### Variable test

Compares a named variable from the student's script against `solution.py` or a hardcoded `expected` value.

```json
{
  "test_name": "A1",
  "type": "variable",
  "variable_name": "result",
  "description": "result is correct",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 2,
  "hint_wrong_size": "result should be a numpy array of shape (3,).",
  "hint_tolerance": "Check your formula."
}
```

To use a hardcoded expected value instead of `solution.py`:

```json
"expected": 42.0
```

Strings and booleans work too -- set `rtol: 0, atol: 0` and put the value in `expected`:

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

### Attempt limits

```json
"attempts": 5,
"allow_tries": false
```

`attempts` sets the maximum number of "attempted" submissions counted for this question (a submission counts as attempted if the variable or function was defined, regardless of correctness). The student's score is locked at the **best score across their attempts**.

`allow_tries: true` removes the cap -- every submission updates the running best with no limit.

Once all attempt-limited questions in a rubric are exhausted (or full credit is earned), further submissions are blocked with a message and the previous results are carried forward unchanged.

Attempt tracking requires Gradescope's "Allow resubmission" setting to be enabled on the assignment.

---

## Student submission

Students can submit **any `.py` file under any name**. If multiple `.py` files are submitted, the one that defines the most names the rubric is looking for is selected automatically.

---

## Worked example

See `autobuilder/examples/total_test/` for a complete example covering strings, lists, numpy arrays, a function (RK4), and a maximisation problem -- with `solution.py`, `rubric.json`, `test_inputs.py`, and four example student submissions showing a progression from 0/20 to 20/20.

```bash
cd autobuilder/examples/total_test
autobuilder grade rubric.json solution.py submission_04_correct.py --inputs test_inputs.py
autobuilder build rubric.json solution.py --inputs test_inputs.py
```
