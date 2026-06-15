"""
Copies the student's submitted file(s) to student_submission.py so the
generated tests can `from student_submission import ...` regardless of
what the student named their file.

Run from /autograder/source after the submission has been copied in by
run_autograder. After cp -r, /autograder/source contains both the
autograder's own files and whatever the student submitted, mixed together
-- this picks out the student's .py file(s) by excluding the known
autograder files.

- Exactly one .py file submitted -> copied directly to student_submission.py
- Multiple .py files submitted -> concatenated together (in name order)
  into student_submission.py, so functions/variables from any of them are
  importable. (If two files define the same name, the later one wins --
  students should generally submit a single file.)
- No .py files submitted -> student_submission.py is left absent; every
  generated test's `from student_submission import ...` then fails with a
  clear ModuleNotFoundError, surfaced per-test with that test's hint.
"""
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
    candidates = sorted(
        f for f in os.listdir(SOURCE_DIR)
        if f.endswith(".py") and f not in INFRA_FILES and not f.startswith("test")
    )

    if not candidates:
        return

    if len(candidates) == 1:
        shutil.copy(os.path.join(SOURCE_DIR, candidates[0]), TARGET)
        return

    with open(TARGET, "w") as out:
        for fname in candidates:
            out.write(f"\n# ---- {fname} ----\n")
            with open(os.path.join(SOURCE_DIR, fname)) as f:
                out.write(f.read())
            out.write("\n")


if __name__ == "__main__":
    main()
