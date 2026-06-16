"""
Builds a Gradescope-ready PyUnit autograder zip from a rubric.json + a
correct solution script.

    autobuilder build RUBRIC SOLUTION --output autograder.zip [--timeout 10]

Output layout (matches the gradescope-utils PyUnit convention):

    autograder.zip
    |-- requirements.txt
    |-- run_autograder
    |-- run_tests.py
    |-- setup.sh
    |-- prepare_submission.py
    |-- solution.py            (your solution, shipped as-is)
    |-- rubric.json
    |-- autobuilder/            (small vendored helper package)
    |   |-- __init__.py
    |   |-- comparator.py
    |   `-- inputs.py
    `-- tests/
        |-- __init__.py
        `-- test_rubric.py      (generated from rubric.json's test_suite)

Each test_suite entry becomes one @weight-decorated unittest method that
imports the relevant name from `student_submission` and compares it against
either `solution.<name>` / `solution.<func>(*inputs)` or a hardcoded
"expected" value.

Students can submit any .py file under any name -- prepare_submission.py
copies (or, if multiple .py files are submitted, concatenates) whatever
was uploaded into student_submission.py before tests run.

Before generating anything, the solution is validated (run once, in an
isolated subprocess) to make sure it actually defines everything the rubric
needs and doesn't crash -- this catches rubric/solution mismatches at build
time rather than when a student submits.
"""
import argparse
import json
import os
import shutil
import tempfile
import zipfile

from .codegen import generate_test_file
from .reference import generate_reference_values

PACKAGE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(PACKAGE_DIR, "templates")

# Files from this package vendored into the zip for the generated tests to import.
VENDOR_FILES = ["__init__.py", "comparator.py", "inputs.py", "attempts.py", "attempt_recorder.py"]

DEFAULT_TIMEOUT = 10


def build(rubric_path, solution_path, output_path, timeout=None):
    with open(rubric_path) as f:
        config = json.load(f)

    if timeout is not None:
        config["timeout"] = timeout
    config.setdefault("timeout", DEFAULT_TIMEOUT)

    # Validate the solution against the rubric before generating anything --
    # raises with a clear message if it crashes or is missing variables/functions.
    generate_reference_values(solution_path, config["test_suite"], timeout=config["timeout"])

    requirements = list(dict.fromkeys(["gradescope-utils>=0.3.1"] + config.get("requirements", [])))

    with tempfile.TemporaryDirectory() as staging:
        # vendored helper package (comparator + input conversion)
        pkg_dir = os.path.join(staging, "autobuilder")
        os.makedirs(pkg_dir)
        for fname in VENDOR_FILES:
            shutil.copy(os.path.join(PACKAGE_DIR, fname), os.path.join(pkg_dir, fname))

        # tests/
        tests_dir = os.path.join(staging, "tests")
        os.makedirs(tests_dir)
        with open(os.path.join(tests_dir, "__init__.py"), "w"):
            pass
        with open(os.path.join(tests_dir, "test_rubric.py"), "w") as f:
            f.write(generate_test_file(config["test_suite"]))

        # solution.py
        shutil.copy(solution_path, os.path.join(staging, "solution.py"))

        # rubric.json (with submission_filename / timeout merged in)
        with open(os.path.join(staging, "rubric.json"), "w") as f:
            json.dump(config, f, indent=2)

        # run_tests.py / prepare_submission.py
        shutil.copy(os.path.join(TEMPLATES_DIR, "run_tests.py"), os.path.join(staging, "run_tests.py"))
        shutil.copy(os.path.join(TEMPLATES_DIR, "prepare_submission.py"), os.path.join(staging, "prepare_submission.py"))

        # run_autograder
        run_autograder_path = os.path.join(staging, "run_autograder")
        shutil.copy(os.path.join(TEMPLATES_DIR, "run_autograder"), run_autograder_path)
        os.chmod(run_autograder_path, 0o755)

        # setup.sh
        setup_path = os.path.join(staging, "setup.sh")
        shutil.copy(os.path.join(TEMPLATES_DIR, "setup.sh"), setup_path)
        os.chmod(setup_path, 0o755)

        # requirements.txt
        with open(os.path.join(staging, "requirements.txt"), "w") as f:
            f.write("\n".join(requirements) + "\n")

        # zip it up
        if os.path.exists(output_path):
            os.remove(output_path)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(staging):
                for fname in files:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, staging)
                    zf.write(full, rel)

    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a Gradescope PyUnit autograder zip.")
    parser.add_argument("rubric", help="Path to rubric.json")
    parser.add_argument("solution", help="Path to your correct solution .py script")
    parser.add_argument("--output", default="autograder.zip", help="Output zip path")
    parser.add_argument("--timeout", type=float, help="Per-run timeout (seconds) for validating the solution")
    args = parser.parse_args(argv)

    out = build(args.rubric, args.solution, args.output, args.timeout)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
