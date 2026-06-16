"""
Copies the student's submitted file to student_submission.py so the
generated tests can `from student_submission import ...` regardless of
what the student named their file.

Run from /autograder/source after the submission has been copied in by
run_autograder. After cp -r, /autograder/source contains both the
autograder's own files and whatever the student submitted, mixed together
-- this picks out the student's file(s) by excluding the known autograder
files.

Notebook support: any submitted .ipynb file is converted to a .py file
first (code cells concatenated in order, magics like %matplotlib and
shell escapes like !pip install stripped, since they aren't valid plain
Python). After that conversion, .ipynb-derived and native .py submissions
are treated identically by the rest of this script.

- Exactly one .py file (after notebook conversion) -> copied directly to
  student_submission.py
- Multiple .py files -> the one that defines the most names the rubric is
  looking for (variable_name/function_name from test_suite) is picked and
  copied. (Blindly concatenating multiple files is fragile -- if two files
  define the same name, whichever comes last would silently win.) The
  other submitted files are left in place too, so cross-file imports from
  the chosen file still resolve.
- No .py/.ipynb files submitted -> student_submission.py is left absent;
  every generated test's `from student_submission import ...` then fails
  with a clear ModuleNotFoundError, surfaced per-test with that test's hint.
"""
import ast
import json
import os
import re
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

# Lines that are valid in a Jupyter cell but not in plain Python.
_MAGIC_OR_SHELL = re.compile(r"^\s*[%!]")


def _notebook_to_python(ipynb_path):
    """Extract and concatenate code cells from a .ipynb file into a single
    Python source string. Magic commands (%...) and shell escapes (!...)
    are stripped since they aren't valid outside Jupyter. Returns None if
    the file can't be parsed as a notebook."""
    try:
        with open(ipynb_path, encoding="utf-8") as f:
            notebook = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None

    chunks = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        if isinstance(source, str):
            source = source.splitlines(keepends=True)
        cleaned_lines = [line for line in source if not _MAGIC_OR_SHELL.match(line)]
        if cleaned_lines:
            chunks.append("".join(cleaned_lines))

    return "\n\n".join(chunks) + "\n"


def _convert_notebooks():
    """Convert every .ipynb in SOURCE_DIR to a sibling .py file. Returns
    the set of generated .py filenames so callers can include them as
    submission candidates."""
    generated = set()
    for fname in os.listdir(SOURCE_DIR):
        if not fname.endswith(".ipynb"):
            continue
        code = _notebook_to_python(os.path.join(SOURCE_DIR, fname))
        if code is None:
            continue
        py_name = fname[:-len(".ipynb")] + ".py"
        # Don't clobber a same-named .py file that's part of the autograder
        # or that the student also submitted directly.
        if py_name in INFRA_FILES:
            py_name = fname[:-len(".ipynb")] + "_notebook.py"
        with open(os.path.join(SOURCE_DIR, py_name), "w", encoding="utf-8") as f:
            f.write(code)
        generated.add(py_name)
    return generated


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
    notebook_derived = _convert_notebooks()

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
