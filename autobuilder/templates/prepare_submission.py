"""
Copies the student's submitted file to student_submission.py so the
generated tests can `from student_submission import ...` regardless of
what the student named their file.

Run from /autograder/source after the submission has been copied in by
run_autograder. After cp -r, /autograder/source contains both the
autograder's own files and whatever the student submitted, mixed together
-- this picks out the student's .py file(s) by excluding the known
autograder files.

- Exactly one .py file submitted -> copied directly to student_submission.py
- Multiple .py files submitted -> the one that defines the most names the
  rubric is looking for (variable_name/function_name from test_suite) is
  picked and copied. (Blindly concatenating multiple files is fragile --
  if two files define the same name, whichever comes last would silently
  win.) The other submitted files are left in place too, so cross-file
  imports from the chosen file still resolve.
- No .py files submitted -> student_submission.py is left absent; every
  generated test's `from student_submission import ...` then fails with a
  clear ModuleNotFoundError, surfaced per-test with that test's hint.
"""
import ast
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


def _required_names(config):
    names = set()
    for t in config.get("test_suite", []):
        ttype = t.get("type", "variable")
        name = t.get("variable_name") if ttype == "variable" else t.get("function_name")
        if name:
            names.add(name)
    return names


def _defined_names(path):
    try:
        with open(path) as f:
            tree = ast.parse(f.read(), filename=path)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return set()

    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


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

    try:
        with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
            config = json.load(f)
    except (OSError, ValueError):
        config = {}

    required = _required_names(config)
    best = max(candidates, key=lambda f: len(_defined_names(os.path.join(SOURCE_DIR, f)) & required))
    shutil.copy(os.path.join(SOURCE_DIR, best), TARGET)


if __name__ == "__main__":
    main()
