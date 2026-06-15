# autobuilder

A small, self-contained autograder builder for Gradescope, built around
**unittest + gradescope-utils** (the standard PyUnit integration). Given a
`rubric.json` (test specs) and your correct solution script, it generates
a `tests/test_rubric.py` -- one `@weight`-decorated test method per rubric
entry -- and packages it into a Gradescope-ready `autograder.zip`.

## Install

```bash
pip install git+https://github.com/<you>/autobuilder.git
```

This gives you an `autobuilder` command with two subcommands.

## Usage

### 1. Build the autograder zip

```bash
autobuilder build rubric.json solution.py
```

`solution.py` is your correct code. Before generating anything, it's run
once (in an isolated subprocess) to check it actually defines everything
the rubric needs and doesn't crash -- catching rubric/solution mismatches
at build time.

This writes `autograder.zip` (the default `--output`) with the structure:

```
autograder.zip
|-- requirements.txt
|-- run_autograder
|-- run_tests.py
|-- setup.sh
|-- prepare_submission.py
|-- solution.py            (your solution, shipped as-is)
|-- rubric.json
|-- autobuilder/             (small vendored helper: comparator + input conversion)
`-- tests/
    |-- __init__.py
    `-- test_rubric.py       (generated -- one @weight test per rubric entry)
```

Upload `autograder.zip` to Gradescope as the autograder for a programming
assignment (Configure Autograder -> upload `autograder.zip`).

**Students can submit any `.py` file, under any name** --
`prepare_submission.py` copies whatever they uploaded to
`student_submission.py` before tests run. If they submit multiple `.py`
files, all of them are concatenated into `student_submission.py` (so any
function/variable from any of them is importable), and the original files
are also left in place so cross-file imports between them still work.

### 2. Local self-check (for instructors or students)

```bash
autobuilder grade rubric.json solution.py my_submission.py
```

Generates the same `tests/test_rubric.py` and runs it with the exact same
`JSONTestRunner` Gradescope uses, against `solution.py` and
`my_submission.py`. Prints a pass/fail summary with scores and hints.
Useful for testing the rubric and solution before building, or for
students to sanity-check their own solution before submitting.

## rubric.json format

Each entry in `test_suite` is a **variable test** (compare a name from the
student's module) or a **function test** (call a function with given
inputs and compare its return value). The expected value comes from
`solution.py` by default, or can be hardcoded with `"expected"`.

### Variable test, compared against solution.py

```json
{
  "test_name": "A0",
  "type": "variable",
  "variable_name": "A0",
  "description": "Forward Euler approximation dt = 1e-7",
  "hint_wrong_size": "Do you include the initial condition",
  "hint_tolerance": "Is your function dV/dt defined correctly, with correct parameters",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 1
}
```

Generates roughly:

```python
@weight(1)
def test_A0(self):
    "Forward Euler approximation dt = 1e-7"
    try:
        from student_submission import A0
    except Exception as e:
        self.fail(f"Variable 'A0' could not be loaded ({type(e).__name__}: {e}).\n" + "Do you include the initial condition")
        return
    result = A0
    expected = solution.A0
    status, message = compare(result, expected, 1e-06, 1e-06)
    if status == "shape":
        self.fail(message + "\n" + "Do you include the initial condition")
    elif status == "tolerance":
        self.fail(message + "\n" + "Is your function dV/dt defined correctly, with correct parameters")
```

### Variable test, with a hardcoded expected value (no solution.py needed for this entry)

```json
{
  "test_name": "FT1",
  "type": "variable",
  "variable_name": "final_scores",
  "description": "final_scores has the correct shape and values",
  "expected": [7.93, 3.37, 4.33, 3.02],
  "rtol": 0,
  "atol": 0.01,
  "score": 4,
  "hint_wrong_size": "final_scores should be a NumPy array of shape (4,).",
  "hint_tolerance": "Check your scoring formula."
}
```

### Function test

```json
{
  "test_name": "B1",
  "type": "function",
  "function_name": "rk4_step",
  "inputs": [[-1, 4], 0.1],
  "output_index": null,
  "description": "rk4_step([-1, 4], 0.1)",
  "hint_wrong_size": "rk4_step should return a length-2 array/list [R_next, J_next].",
  "hint_tolerance": "Check your RK4 weighted average of the four slopes.",
  "rtol": 1e-6,
  "atol": 1e-6,
  "score": 3
}
```

- `inputs`: positional arguments. JSON lists of numbers (including nested
  lists) are converted to numpy arrays before the call; everything else
  passes through as-is.
- `output_index` (optional): index into the return value before comparing
  (for functions returning multiple values).
- The same `function_name` can appear in multiple test entries with
  different `inputs` -- each is scored independently. Recommended for
  covering edge cases (e.g. an equilibrium point) a single case wouldn't
  catch.

### Top-level config

- `timeout` (seconds, default `10`) -- used only when validating
  `solution.py` at build time
- `requirements`: extra pip packages for `requirements.txt`
  (`gradescope-utils` is always included automatically)

## How grading works

Each generated test method:
1. Tries `from student_submission import <name>` (variable) or the
   function, catching any exception (syntax errors, missing names, etc.)
   and failing with that exception's message plus the rubric's
   `hint_wrong_size`.
2. For function tests, calls the function with `inputs`, catching any
   runtime error the same way.
3. Compares the result to `solution.<name>` / `solution.<func>(*inputs)`
   (or a hardcoded `"expected"`) via `compare()`: shape mismatch ->
   `hint_wrong_size`, tolerance mismatch -> `hint_tolerance`
   (`numpy.allclose(rtol, atol)`).

Output shown to students is just a short message ("Expected a value of
shape (2,), but got shape ()." / "Your value is not within the required
tolerance.") plus your hint -- the actual expected/solution values are
never shown (that would leak the answer), and `JSONTestRunner` runs with
`buffer=False` so stray `print()`/warning output from solution or student
code doesn't end up mixed into a test's reported output.

Note: grading uses direct `import`, matching the standard
gradescope-utils/unittest pattern -- there's no per-test subprocess
timeout. An infinite loop in a student's top-level code would hang the
whole `run_tests.py` until Gradescope's overall submission timeout kicks
in.

## Attempt limits

There's no per-question attempt tracking. Gradescope's autograder
container only gets `/autograder/submission_metadata.yml`, which contains
just `id`, `submitters`, `created_at`, `status` -- no history of previous
submissions or scores. Implementing "lock in your best score after N
attempts" *per question* would require external persistent storage (e.g.
a small database/API keyed by student email + test name) that the
autograder calls over the network -- real infrastructure, not just code.

For a cap on the whole assignment (closer to what gspack provides),
use Gradescope's native per-assignment **Submission Limit** setting
(Assignment Settings), which Gradescope enforces itself before your
autograder ever runs.

## Examples

- `autobuilder/examples/hw6/`: variable-style rubric (global script
  variables `A0`-`A9`), compared against `solution.py`.
- `autobuilder/examples/rk4/`: function-style rubric (`rk4_step(y0, dt)`
  called with several different inputs), compared against `solution.py`.
- `autobuilder/examples/food_truck/`: variable-style rubric with hardcoded
  `"expected"` values (no dependence on `solution.py` for that entry).

Each has a `solution.py` and a few example submissions (correct, wrong
value, wrong/missing name). Run with `autobuilder grade rubric.json
solution.py <submission>.py` from inside the example directory.
