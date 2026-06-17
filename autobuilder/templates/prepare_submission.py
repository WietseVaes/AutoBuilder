"""
Normalizes the student's submission to a single entry-point file based on
the language declared in rubric.json's top-level "language" field
("python" or "julia", default "python"), and writes a small marker file
(student_language.json) recording the language and the normalized file's
path -- read by autobuilder.student_dispatch at grading time to pick the
right adapter.

Run from /autograder/source after the submission has been copied in by
run_autograder. After cp -r, /autograder/source contains both the
autograder's own files and whatever the student submitted, mixed together
-- this picks out the student's file(s) by excluding the known autograder
files.

Only files matching the declared language are considered. A submission in
the other language is reported as a clear note in the marker (surfaced to
the student as "wrong language" rather than silently ignored or guessed
about), rather than supporting mixed Python+Julia submissions.

Detection and normalization, by extension:
  .py     -> used directly (language: "python")
  .ipynb  -> Jupyter notebook with a Python kernel: code cells
             concatenated, magics/shell-escapes stripped, written to a
             sibling .py file (language: "python")
  .jl     -> used directly (language: "julia")
  (.ipynb with a Julia kernel is not yet supported)

If multiple files of the declared language are submitted, the one that
defines the most names the rubric is looking for is selected (via AST
inspection for Python; a lightweight regex-based scan for Julia, since
Julia has no stdlib AST module readily available without invoking the
julia executable itself).
"""
import ast
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from autobuilder.notebook_convert import notebook_to_python as _notebook_to_python

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
PY_TARGET = os.path.join(SOURCE_DIR, "student_submission.py")
JL_TARGET = os.path.join(SOURCE_DIR, "student_submission.jl")
MARKER_PATH = os.path.join(SOURCE_DIR, "student_language.json")

INFRA_FILES = {
    "run_tests.py",
    "prepare_submission.py",
    "solution.py",
    "student_submission.py",
    "student_submission.jl",
    "student_language.json",
    "all_test_specs.json",
    "setup.sh",
    "run_autograder",
    "requirements.txt",
    "rubric.json",
    "_runner.jl",
}


def _convert_notebooks():
    generated = set()
    for fname in os.listdir(SOURCE_DIR):
        if not fname.endswith(".ipynb"):
            continue
        code = _notebook_to_python(os.path.join(SOURCE_DIR, fname))
        if code is None:
            continue
        py_name = fname[:-len(".ipynb")] + ".py"
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


def _defined_names_python(path):
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


# Matches top-level `function foo(...)` / `foo(...) = ...` / `foo = ...`
# definitions. Not a full Julia parser -- good enough to pick between
# multiple submitted .jl files by counting which one defines more of the
# names the rubric cares about.
_JL_FUNC_DEF = re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_!]*)\s*\(", re.MULTILINE)
_JL_INLINE_FUNC_DEF = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_!]*)\s*\([^=]*\)\s*=", re.MULTILINE)
_JL_ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_!]*)\s*=(?!=)", re.MULTILINE)


def _defined_names_julia(path):
    try:
        with open(path, encoding="utf-8") as f:
            code = f.read()
    except (OSError, UnicodeDecodeError):
        return set()
    names = set()
    for pattern in (_JL_FUNC_DEF, _JL_INLINE_FUNC_DEF, _JL_ASSIGN):
        names.update(pattern.findall(code))
    return names


def _pick_best(candidates, required, defined_names_fn):
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda f: len(defined_names_fn(os.path.join(SOURCE_DIR, f)) & required))


def main():
    _convert_notebooks()

    try:
        with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
            config = json.load(f)
    except (OSError, ValueError):
        config = {}
    required = _required_names(config)
    language = config.get("language", "python")

    marker = {"language": language, "submission_path": None}

    if language == "julia":
        candidates = sorted(
            f for f in os.listdir(SOURCE_DIR)
            if f.endswith(".jl") and f not in INFRA_FILES and not f.startswith("test")
        )
        if candidates:
            best = _pick_best(candidates, required, _defined_names_julia)
            shutil.copy(os.path.join(SOURCE_DIR, best), JL_TARGET)
            marker["submission_path"] = JL_TARGET

        # If a .py file was submitted to a Julia-only assignment, flag it
        # clearly rather than silently ignoring it.
        py_candidates = [
            f for f in os.listdir(SOURCE_DIR)
            if f.endswith(".py") and f not in INFRA_FILES and not f.startswith("test")
        ]
        if not candidates and py_candidates:
            marker["note"] = (
                "This assignment expects a Julia (.jl) submission, but a "
                "Python file was uploaded instead. Please submit a .jl file."
            )

    else:  # python
        candidates = sorted(
            f for f in os.listdir(SOURCE_DIR)
            if f.endswith(".py") and f not in INFRA_FILES and not f.startswith("test")
        )
        if candidates:
            best = _pick_best(candidates, required, _defined_names_python)
            shutil.copy(os.path.join(SOURCE_DIR, best), PY_TARGET)
            marker["submission_path"] = PY_TARGET

        jl_candidates = [
            f for f in os.listdir(SOURCE_DIR)
            if f.endswith(".jl") and f not in INFRA_FILES and not f.startswith("test")
        ]
        if not candidates and jl_candidates:
            marker["note"] = (
                "This assignment expects a Python (.py/.ipynb) submission, but "
                "a Julia file was uploaded instead. Please submit a .py file."
            )

    with open(MARKER_PATH, "w") as f:
        json.dump(marker, f)


if __name__ == "__main__":
    main()
