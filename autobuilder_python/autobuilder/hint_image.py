"""
Embeds an image directly into hint/output text as a base64 data URI, so it
renders via Gradescope's markdown output format without depending on any
file being reachable from the student's browser (relative/absolute
filesystem paths into the grading container do not work for this --
Gradescope's results viewer has no access to autograder container files).

Usage in a rubric:
    "hint_tolerance": "Your plot should look like this.",
    "hint_image": "expected_plot.png"

"hint_image" names a file placed next to rubric.json (also listed in
extra_files so it ships in the zip, or simply any image autobuilder can
find at build time). At build time it's read, base64-encoded, and baked
into the generated test file as a literal string -- no filesystem lookup
happens during grading itself.
"""
import base64
import os

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


def image_to_markdown(image_path, alt_text="hint image"):
    """Read an image file and return a markdown image tag with the image
    embedded as a base64 data URI."""
    ext = os.path.splitext(image_path)[1].lower()
    mime = _MIME_BY_EXT.get(ext)
    if mime is None:
        raise RuntimeError(
            f"hint_image: unsupported image extension '{ext}' for '{image_path}'. "
            f"Supported: {', '.join(_MIME_BY_EXT)}"
        )
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"![{alt_text}](data:{mime};base64,{data})"
