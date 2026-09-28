"""
Normalizes the student's submission to a single entry-point file based on
the language declared in rubric.json's top-level "language" field
("python" or "julia", default "python"), and writes a small marker file
(student_language.json) recording the language and the normalized file's
path -- read by autobuilder.student_dispatch at grading time to pick the
right adapter.

Run from /autograder/source, with the student's raw upload still sitting
untouched in /autograder/submission (AUTOBUILDER_SUBMISSION_DIR overrides
the path, for local testing). Nothing from the submission is ever copied
into /autograder/source except the single file chosen as the student's
entry point (as student_submission.py / .jl) and, if present, sibling
files that sit next to it (as student_helpers/*) -- see "Helper modules"
below. This keeps a student file that happens to share a name with one of
the autograder's own files (solution.py, rubric.json, run_tests.py, ...)
from ever overwriting or being mistaken for that file.

Gradescope keeps the submission's folder structure, so candidates are
found by walking /autograder/submission recursively, not just its top
level.

Detection and normalization, by extension:
  .py     -> used directly (language: "python")
  .ipynb  -> Jupyter notebook with a Python kernel: code cells
             concatenated, magics/shell-escapes stripped, converted to
             Python source in a temporary folder (language: "python")
  .jl     -> used directly (language: "julia")
  (.ipynb with a Julia kernel is not yet supported)

Only files matching the declared language are considered candidates. A
submission in the other language is reported as a clear note in the
marker (surfaced to the student as "wrong language" rather than silently
ignored or guessed about), rather than supporting mixed Python+Julia
submissions.

If multiple files of the declared language are submitted, the one that
defines the most names the rubric is looking for is selected (via AST
inspection for Python; a lightweight regex-based scan for Julia, since
Julia has no stdlib AST module readily available without invoking the
julia executable itself), and a note in the marker tells the student
which file was graded.

If no usable file is found at all, the marker note lists every file that
was received (so students can tell if they uploaded the wrong thing
entirely) and which extensions this assignment accepts.

Helper modules: if the chosen file has sibling files in the same
submission subfolder (e.g. a student splits their work into main.py +
helpers.py), those siblings are copied into /autograder/source/
student_helpers/ (flattened -- just the winning file's own folder, not
the whole submission tree). student_dispatch.py points the student's
subprocess at that folder via sys.path so `import helpers`-style imports
in the student's main file resolve. This is wired up for Python only;
Julia submissions with helper files are not yet supported.
"""
import ast
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from autobuilder.notebook_convert import notebook_to_python as _notebook_to_python

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
SUBMISSION_DIR = os.environ.get("AUTOBUILDER_SUBMISSION_DIR", "/autograder/submission")
PY_TARGET = os.path.join(SOURCE_DIR, "student_submission.py")
JL_TARGET = os.path.join(SOURCE_DIR, "student_submission.jl")
HELPERS_DIR = os.path.join(SOURCE_DIR, "student_helpers")
MARKER_PATH = os.path.join(SOURCE_DIR, "student_language.json")

# Folders Gradescope/zip tooling or editors sometimes leave behind that are
# never a student's actual submission content.
_JUNK_DIRS = {"__MACOSX", ".ipynb_checkpoints"}


def _list_all_files():
    """Every file under SUBMISSION_DIR, as paths relative to it, walked
    recursively since Gradescope preserves the submission's folder
    structure. Hidden files/dirs and known junk dirs are skipped."""
    paths = []
    if not os.path.isdir(SUBMISSION_DIR):
        return paths
    for root, dirs, files in os.walk(SUBMISSION_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in _JUNK_DIRS]
        for fname in files:
            if fname.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(root, fname), SUBMISSION_DIR)
            paths.append(rel.replace(os.sep, "/"))
    return sorted(paths)


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
    """candidates: list of (abs_path, rel_path) tuples. Returns the tuple
    that defines the most of the rubric's required names (ties broken by
    sort order, i.e. the first alphabetically)."""
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda c: len(defined_names_fn(c[0]) & required))


def _gather_candidates(language, all_files, convert_dir):
    """Returns (candidates, other_language_files). candidates is a list of
    (abs_path, rel_path) usable as the student's main submission -- for
    notebooks, abs_path points at a converted .py file written under
    convert_dir, while rel_path is still the original submitted path (used
    in messages to the student)."""
    candidates = []
    other = []
    for rel in all_files:
        ext = os.path.splitext(rel)[1].lower()
        abs_path = os.path.join(SUBMISSION_DIR, rel)
        if language == "julia":
            if ext == ".jl":
                candidates.append((abs_path, rel))
            elif ext in (".py", ".ipynb"):
                other.append(rel)
        else:
            if ext == ".py":
                candidates.append((abs_path, rel))
            elif ext == ".ipynb":
                code = _notebook_to_python(abs_path)
                if code is None:
                    continue
                converted_name = rel.replace("/", "__") + ".py"
                converted_path = os.path.join(convert_dir, converted_name)
                with open(converted_path, "w", encoding="utf-8") as f:
                    f.write(code)
                candidates.append((converted_path, rel))
            elif ext == ".jl":
                other.append(rel)
    return candidates, other


def _copy_helpers(winner_rel, all_files):
    """Copy sibling files that sit in the same submission subfolder as the
    winning file into student_helpers/, so the student's entry-point file
    can import a module they submitted alongside it. Returns the helpers
    dir path, or None if there were no siblings."""
    winner_dir = os.path.dirname(winner_rel)
    siblings = [
        rel for rel in all_files
        if rel != winner_rel and os.path.dirname(rel) == winner_dir
    ]
    if not siblings:
        return None
    os.makedirs(HELPERS_DIR, exist_ok=True)
    for rel in siblings:
        shutil.copy(os.path.join(SUBMISSION_DIR, rel), os.path.join(HELPERS_DIR, os.path.basename(rel)))
    return HELPERS_DIR


def _accepted_extensions_text(language):
    return ".jl" if language == "julia" else ".py or .ipynb"


def main():
    try:
        with open(os.path.join(SOURCE_DIR, "rubric.json")) as f:
            config = json.load(f)
    except (OSError, ValueError):
        config = {}
    required = _required_names(config)
    language = config.get("language", "python")

    marker = {"language": language, "submission_path": None}

    all_files = _list_all_files()

    with tempfile.TemporaryDirectory() as convert_dir:
        candidates, other_language_files = _gather_candidates(language, all_files, convert_dir)

        if candidates:
            defined_names_fn = _defined_names_julia if language == "julia" else _defined_names_python
            winner_abs, winner_rel = _pick_best(candidates, required, defined_names_fn)
            target = JL_TARGET if language == "julia" else PY_TARGET
            shutil.copy(winner_abs, target)
            marker["submission_path"] = target
            marker["graded_file"] = winner_rel

            if len(candidates) > 1:
                other_names = sorted(rel for _abs, rel in candidates if rel != winner_rel)
                marker["note"] = (
                    f"Multiple files were found in your submission "
                    f"({', '.join([winner_rel] + other_names)}). "
                    f"Graded '{winner_rel}'."
                )

            if language != "julia":
                helpers_dir = _copy_helpers(winner_rel, all_files)
                marker["helpers_dir"] = helpers_dir

        elif other_language_files:
            expects = "Python (.py/.ipynb)" if language != "julia" else "Julia (.jl)"
            got = "Julia (.jl)" if language != "julia" else "Python (.py/.ipynb)"
            marker["note"] = (
                f"This assignment expects a {expects} submission, but a "
                f"{got} file was uploaded instead. Please submit a "
                f"{_accepted_extensions_text(language)} file."
            )

        else:
            if all_files:
                received = ", ".join(all_files)
                marker["note"] = (
                    f"No usable submission file was found. Files received: "
                    f"{received}. This assignment accepts "
                    f"{_accepted_extensions_text(language)} files."
                )
            else:
                marker["note"] = (
                    f"No files were received in your submission. This "
                    f"assignment accepts {_accepted_extensions_text(language)} files."
                )

    with open(MARKER_PATH, "w") as f:
        json.dump(marker, f)


if __name__ == "__main__":
    main()
