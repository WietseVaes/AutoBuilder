# autobuilder

A small, self-contained autograder builder for Gradescope. Given a
`rubric.json` (test specs + tolerances) and a pickle of reference values
(the correct outputs your solution script produces), it builds a
Gradescope-ready `autograder.zip` -- no third-party autograder package
needs to be installed on Gradescope's end (the grading code is vendored
directly into the zip).

## Install

```bash
pip install git+https://github.com/<you>/autobuilder.git
```

This gives you an `autobuilder` command with two subcommands.

## Usage

### 1. Build the autograder zip

```bash
autobuilder build rubric.json reference_values.pkl \
    --output autograder.zip \
    --submission-filename HW6.py
```

Upload `autograder.zip` to Gradescope as the autograder for a programming
assignment (Configure Autograder -> upload `autograder.zip`).

`--submission-filename` is the file name students are expected to upload
(e.g. `HW6.py`). If a student's submission has a different name but is the
only `.py` file they uploaded, the grader still grades it and leaves a note
telling them to rename it.

`--timeout` (seconds, default 10) bounds how long each submission is allowed
to run before being marked as timed out.

### 2. Local self-check (for instructors or students)

```bash
autobuilder grade rubric.json reference_values.pkl my_submission.py
```

Runs the exact same grading logic locally and prints a pass/fail summary
with per-test hints -- useful for testing the rubric itself, or for
students to sanity-check their solution before submitting.

## rubric.json format

```json
{
  "submission_filename": "HW6.py",
  "timeout": 10,
  "requirements": ["numpy", "scipy"],
  "test_suite": [
    {
      "test_name": "A0",
      "variable_name": "A0",
      "description": "Forward Euler approximation dt = 1e-7",
      "hint_wrong_size": "Do you include the initial condition",
      "hint_tolerance": "Is your function dV/dt defined correctly, with correct parameters",
      "rtol": 1e-6,
      "atol": 1e-6,
      "score": 1
    }
  ]
}
```

Each test entry compares a named variable from the student's global
namespace to the corresponding value in `reference_values.pkl`, using
`numpy.allclose(rtol, atol)`. `submission_filename`, `timeout`, and
`requirements` are optional (with defaults of `submission.py`, `10`, and
`[]`).

## Generating reference_values.pkl

For now, `reference_values.pkl` is a pickled dict `{variable_name: value}`
produced by running your solution script and pickling the variables named
in `test_suite`. (A `build-reference` command that does this automatically
from a solution script is on the roadmap.)

## How grading works

Each submission is run once, in an isolated subprocess with a timeout. The
grader then pulls out whatever variables from `test_suite` ended up defined
in the student's global namespace -- variables defined before a crash are
still graded, variables after are reported as missing with the actual error
message attached. Each comparison checks shape first (`hint_wrong_size` on
mismatch), then numeric tolerance (`hint_tolerance` on mismatch).

## Example

See `autobuilder/examples/hw6/` for a worked example: a rubric, a reference
values dump, and a few example submissions (correct, broken, partially
wrong) you can run through `autobuilder grade`.
