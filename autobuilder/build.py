"""
Builds a Gradescope-ready autograder zip from a rubric.json + a reference
values dump.

    python -m autobuilder.build RUBRIC REFERENCE --output autograder.zip \\
        [--submission-filename HW6.py] [--timeout 10]

The output zip is self-contained: it vendors the autobuilder grading code
directly (no `git clone` / `pip install` of a third-party autograder
package), so setup.sh only needs to install numerical-computing
dependencies.
"""
import argparse
import json
import os
import pickle
import shutil
import tempfile
import zipfile

PACKAGE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(PACKAGE_DIR, "templates")

# Files from this package that the grader needs at runtime on Gradescope.
VENDOR_FILES = ["__init__.py", "_runner.py", "python_adapter.py", "comparator.py", "grader.py"]

DEFAULT_SUBMISSION_FILENAME = "submission.py"
DEFAULT_TIMEOUT = 10


def build(rubric_path, reference_path, output_path, submission_filename=None, timeout=None):
    with open(rubric_path) as f:
        config = json.load(f)

    if submission_filename:
        config["submission_filename"] = submission_filename
    config.setdefault("submission_filename", DEFAULT_SUBMISSION_FILENAME)

    if timeout is not None:
        config["timeout"] = timeout
    config.setdefault("timeout", DEFAULT_TIMEOUT)

    requirements = config.get("requirements", [])

    with tempfile.TemporaryDirectory() as staging:
        # Vendor the grading package
        pkg_dir = os.path.join(staging, "autobuilder")
        os.makedirs(pkg_dir)
        for fname in VENDOR_FILES:
            shutil.copy(os.path.join(PACKAGE_DIR, fname), os.path.join(pkg_dir, fname))

        # rubric.json (with submission_filename / timeout merged in)
        with open(os.path.join(staging, "rubric.json"), "w") as f:
            json.dump(config, f, indent=2)

        # reference_values.pkl (re-pickled so format is consistent)
        with open(reference_path, "rb") as f:
            ref_data = pickle.load(f)
        with open(os.path.join(staging, "reference_values.pkl"), "wb") as f:
            pickle.dump(ref_data, f)

        # run_grader.py
        shutil.copy(os.path.join(TEMPLATES_DIR, "run_grader.py"), os.path.join(staging, "run_grader.py"))

        # setup.sh (fill in requirements)
        with open(os.path.join(TEMPLATES_DIR, "setup.sh")) as f:
            setup_sh = f.read().format(requirements=" ".join(requirements))
        setup_path = os.path.join(staging, "setup.sh")
        with open(setup_path, "w") as f:
            f.write(setup_sh)
        os.chmod(setup_path, 0o755)

        # run_autograder
        run_autograder_path = os.path.join(staging, "run_autograder")
        shutil.copy(os.path.join(TEMPLATES_DIR, "run_autograder"), run_autograder_path)
        os.chmod(run_autograder_path, 0o755)

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
    parser = argparse.ArgumentParser(description="Build a Gradescope autograder zip.")
    parser.add_argument("rubric", help="Path to rubric.json")
    parser.add_argument("reference", help="Path to reference_values dump (pickle)")
    parser.add_argument("--output", default="autograder.zip", help="Output zip path")
    parser.add_argument("--submission-filename", help="Expected name of the student's submission file")
    parser.add_argument("--timeout", type=float, help="Per-run timeout in seconds")
    args = parser.parse_args(argv)

    out = build(args.rubric, args.reference, args.output, args.submission_filename, args.timeout)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
