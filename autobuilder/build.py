"""
Builds a Gradescope-ready PyUnit autograder zip from a rubric.json + a
correct solution script, and optionally a test inputs file.

    autobuilder build RUBRIC SOLUTION [--inputs inputs.py] --output autograder.zip

The optional --inputs file is a plain .py script that defines variables
used as test inputs in the rubric. In rubric.json, reference them with a
"$" prefix:

    "inputs": ["$x1", 0.1]

At build time the inputs file is executed and "$x1" is replaced with the
actual value of x1 from that namespace. This lets you compute or load test
inputs in Python rather than hardcoding them as JSON literals in the rubric.

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
    |   |-- inputs.py
    |   |-- attempts.py
    |   `-- attempt_recorder.py
    `-- tests/
        |-- __init__.py
        `-- test_rubric.py      (generated from rubric.json's test_suite)
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
VENDOR_FILES = ["__init__.py", "comparator.py", "inputs.py", "attempts.py", "attempt_recorder.py", "plot_check.py"]

DEFAULT_TIMEOUT = 10


def _load_inputs_namespace(inputs_file_path):
    """Execute the inputs file and return its global namespace."""
    ns = {}
    with open(inputs_file_path) as f:
        code = f.read()
    exec(compile(code, inputs_file_path, "exec"), ns)
    return ns


def _resolve_inputs(test_suite, inputs_ns):
    """Replace "$varname" strings in test_suite inputs/expected with the
    actual values from the inputs namespace, converted to JSON-safe form
    (numpy arrays become nested lists). Modifies test_suite in place."""
    import copy
    import numpy as np

    def to_json_safe(val):
        if isinstance(val, np.ndarray):
            return val.tolist()
        if isinstance(val, np.generic):
            return val.item()
        if isinstance(val, (list, tuple)):
            return [to_json_safe(v) for v in val]
        return val

    def resolve(item):
        if isinstance(item, str) and item.startswith("$"):
            varname = item[1:]
            if varname not in inputs_ns:
                raise RuntimeError(
                    f"Input '${varname}' not found in inputs file. "
                    f"Available names: {sorted(k for k in inputs_ns if not k.startswith('_'))}"
                )
            return to_json_safe(inputs_ns[varname])
        return item

    test_suite = copy.deepcopy(test_suite)
    for t in test_suite:
        if "inputs" in t:
            t["inputs"] = [resolve(item) for item in t["inputs"]]
        if "expected" in t:
            t["expected"] = resolve(t["expected"])
    return test_suite


def _resolve_hint_images(test_suite, rubric_dir):
    """For any test with a 'hint_image' field (an image filename next to
    rubric.json), bake the image into a 'hint_image_md' markdown string
    with the image embedded as base64. Leaves test_suite entries without
    hint_image untouched."""
    import copy
    from .hint_image import image_to_markdown

    test_suite = copy.deepcopy(test_suite)
    for t in test_suite:
        if "hint_image" in t:
            image_path = os.path.join(rubric_dir, t["hint_image"])
            if not os.path.exists(image_path):
                raise RuntimeError(
                    f"Test '{t.get('test_name')}': hint_image '{t['hint_image']}' "
                    f"not found next to rubric.json (looked at {image_path})"
                )
            t["hint_image_md"] = image_to_markdown(image_path, alt_text=t.get("test_name", "hint"))
    return test_suite


def build(rubric_path, solution_path, output_path, inputs_file=None, timeout=None):
    with open(rubric_path) as f:
        config = json.load(f)

    if timeout is not None:
        config["timeout"] = timeout
    config.setdefault("timeout", DEFAULT_TIMEOUT)

    # Resolve $-prefixed inputs from the inputs file, if provided.
    if inputs_file:
        inputs_ns = _load_inputs_namespace(inputs_file)
        config["test_suite"] = _resolve_inputs(config["test_suite"], inputs_ns)

    # Resolve hint_image references (image filenames) into baked-in base64
    # markdown, so grading time never needs filesystem access to the image.
    rubric_dir = os.path.dirname(os.path.abspath(rubric_path))
    config["test_suite"] = _resolve_hint_images(config["test_suite"], rubric_dir)

    # Validate the solution against the (resolved) rubric before generating anything.
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

        # extra_files (e.g. data files like .csv needed at grading time)
        for fname in config.get("extra_files", []):
            src = os.path.join(rubric_dir, fname)
            if not os.path.exists(src):
                raise RuntimeError(
                    f"extra_files: '{fname}' not found next to rubric.json (looked at {src})"
                )
            shutil.copy(src, os.path.join(staging, fname))

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
    parser.add_argument("--inputs", help="Path to a .py file defining test input variables (referenced as $varname in rubric.json)")
    parser.add_argument("--output", default="autograder.zip", help="Output zip path")
    parser.add_argument("--timeout", type=float, help="Per-run timeout (seconds) for validating the solution")
    args = parser.parse_args(argv)

    out = build(args.rubric, args.solution, args.output, args.inputs, args.timeout)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
