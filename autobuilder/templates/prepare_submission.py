"""
Copies (or renames) the student's submitted file to student_submission.py
so the generated tests can `from student_submission import ...` regardless
of what the student actually named their file.

Run from /autograder/source after the submission has been copied in by
run_autograder.
"""
import json
import os
import shutil

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SOURCE_DIR, "student_submission.py")

# Files that are part of the autograder itself, not the student's work.
INFRA_FILES = {
    "run_tests.py",
    "prepare_submission.py",
    "solution.py",
    "student_submission.py",
    "setup.sh",
    "run_autograder",
    "requirements.txt",
    "rubric.json",
}


def main():
    with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
        config = json.load(f)
    expected_name = config.get("submission_filename", "submission.py")

    expected_path = os.path.join(SOURCE_DIR, expected_name)
    if os.path.exists(expected_path) and os.path.abspath(expected_path) != TARGET:
        shutil.copy(expected_path, TARGET)
        return

    if os.path.exists(TARGET):
        return  # student's file was already named correctly

    # Fall back: if there's exactly one other .py file, assume it's the
    # submission (handles students uploading with the wrong filename).
    candidates = [
        f for f in os.listdir(SOURCE_DIR)
        if f.endswith(".py") and f not in INFRA_FILES and not f.startswith("test")
    ]
    if len(candidates) == 1:
        shutil.copy(os.path.join(SOURCE_DIR, candidates[0]), TARGET)
    # else: leave student_submission.py absent. Every generated test's
    # `from student_submission import ...` will then fail with a clear
    # ModuleNotFoundError, surfaced per-test with that test's hint.


if __name__ == "__main__":
    main()
