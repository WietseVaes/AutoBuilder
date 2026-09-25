"""
Entry point executed by Gradescope.

Finds the student's submission, grades it against rubric.json +
reference_values.pkl using the vendored autobuilder package, and writes
/autograder/results/results.json in Gradescope's results format.

SUBMISSION_DIR / RESULTS_DIR can be overridden via environment variables
for local testing (see autobuilder/sim.py).
"""
import json
import os
import sys

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SOURCE_DIR)

from autobuilder.grader import grade_python_submission, load_reference  # noqa: E402

SUBMISSION_DIR = os.environ.get("AUTOGRADER_SUBMISSION_DIR", "/autograder/submission")
RESULTS_DIR = os.environ.get("AUTOGRADER_RESULTS_DIR", "/autograder/results")


def find_submission(filename):
    """Returns (path, note). note is a string to surface to the student if
    we had to fall back to a different filename than expected."""
    candidate = os.path.join(SUBMISSION_DIR, filename)
    if os.path.exists(candidate):
        return candidate, None

    py_files = [f for f in os.listdir(SUBMISSION_DIR) if f.endswith(".py")]
    if len(py_files) == 1:
        note = (
            f"Note: expected a file named '{filename}' but found "
            f"'{py_files[0]}' instead -- graded that file. Please rename "
            f"your submission to '{filename}' to avoid this warning."
        )
        return os.path.join(SUBMISSION_DIR, py_files[0]), note

    return None, None


def main():
    with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
        config = json.load(f)
    reference = load_reference(os.path.join(SOURCE_DIR, "reference_values.pkl"))

    submission_filename = config.get("submission_filename", "submission.py")
    timeout = config.get("timeout", 10)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_path = os.path.join(RESULTS_DIR, "results.json")

    submission_path, note = find_submission(submission_filename)

    if submission_path is None:
        gradescope_results = {
            "score": 0,
            "output": (
                f"Could not find your submission file. Expected a file "
                f"named '{submission_filename}'. Please make sure you "
                f"upload your script with that exact name."
            ),
        }
        with open(results_path, "w") as f:
            json.dump(gradescope_results, f, indent=2)
        return

    result = grade_python_submission(submission_path, config["test_suite"], reference, timeout=timeout)

    tests = []
    for t in result["tests"]:
        output = t["description"]
        if t["status"] != "pass":
            output += "\n" + t["message"]
            if t["hint"]:
                output += "\nHint: " + t["hint"]
        tests.append({
            "name": t["name"],
            "score": t["score"],
            "max_score": t["max_score"],
            "output": output,
        })

    gradescope_results = {
        "score": result["score"],
        "output": note or "",
        "tests": tests,
    }
    with open(results_path, "w") as f:
        json.dump(gradescope_results, f, indent=2)


if __name__ == "__main__":
    main()
