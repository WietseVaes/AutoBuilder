"""
Converts a Jupyter notebook (.ipynb) with a Python kernel into a single
Python source string: code cells concatenated in order, markdown cells
skipped, magic commands (%...) and shell escapes (!...) stripped since
they aren't valid outside Jupyter.

Used by both prepare_submission.py (vendored into the autograder zip, for
real Gradescope submissions) and cli.py's `autobuilder grade` (for local
self-checks) -- kept as a single shared implementation so the two stay in
sync.
"""
import json
import re

_MAGIC_OR_SHELL = re.compile(r"^\s*[%!]")


def notebook_to_python(ipynb_path):
    """Returns the converted Python source, or None if the file can't be
    parsed as a notebook, or has a non-Python kernel."""
    try:
        with open(ipynb_path, encoding="utf-8") as f:
            notebook = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None

    kernel_lang = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "python")
    if kernel_lang != "python":
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
