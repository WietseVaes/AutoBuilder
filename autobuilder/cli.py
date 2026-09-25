"""
Command-line entrypoint, installed as `autobuilder`.

    autobuilder build RUBRIC SOLUTION --output autograder.zip [--timeout 10]
    autobuilder grade RUBRIC SOLUTION SUBMISSION [--timeout 10]

`build` produces a Gradescope-ready PyUnit autograder zip (see build.py for
the layout). The solution is validated against the rubric before anything
is generated.

`grade` runs the exact same generated tests locally via JSONTestRunner
(the same runner Gradescope uses), against SOLUTION and SUBMISSION -- for
local self-checks before building/uploading, or for testing the rubric and
solution themselves.
"""
import argparse
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

from .build import build as build_zip, _bake_expected_values
from .codegen import generate_test_file

PACKAGE_DIR = os.path.dirname(__file__)
VENDOR_FILES = [
    "__init__.py", "comparator.py", "inputs.py", "attempts.py",
    "attempt_recorder.py", "plot_check.py", "python_adapter.py",
    "_runner.py", "julia_adapter.py", "_runner.jl", "student_dispatch.py", "notebook_convert.py",
]


def cmd_build(args):
    out = build_zip(args.rubric, args.solution, args.output, args.inputs, args.timeout)
    print(f"Wrote {out}")
    return 0


def cmd_grade(args):
    from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner
    from .build import _load_inputs_namespace, _resolve_inputs, _resolve_hint_images, _build_all_specs

    with open(args.rubric) as f:
        config = json.load(f)

    if args.inputs:
        inputs_ns = _load_inputs_namespace(args.inputs)
        config["test_suite"] = _resolve_inputs(config["test_suite"], inputs_ns)

    rubric_dir = os.path.dirname(os.path.abspath(args.rubric))
    config["test_suite"] = _resolve_hint_images(config["test_suite"], rubric_dir)

    rubric_language = config.get("language", "python")
    submission_ext = os.path.splitext(args.submission)[1].lower()
    is_julia_solution = args.solution.endswith(".jl")

    if is_julia_solution:
        from .reference import generate_reference_values
        ref_values = generate_reference_values(args.solution, config["test_suite"], timeout=args.timeout)
        _bake_expected_values(config["test_suite"], ref_values)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AUTOBUILDER_STATUS_PATH"] = os.path.join(tmp, "_attempt_status.json")
        os.environ["AUTOBUILDER_SOURCE_DIR"] = tmp
        pkg_dir = os.path.join(tmp, "autobuilder")
        os.makedirs(pkg_dir)
        for fname in VENDOR_FILES:
            shutil.copy(os.path.join(PACKAGE_DIR, fname), os.path.join(pkg_dir, fname))
        from .build import _has_callable_inputs
        if args.inputs and _has_callable_inputs(config["test_suite"]):
            shutil.copy(args.inputs, os.path.join(pkg_dir, "test_inputs.py"))
            os.environ["AUTOBUILDER_TEST_INPUTS_PATH"] = os.path.abspath(args.inputs)

        if not is_julia_solution:
            shutil.copy(args.solution, os.path.join(tmp, "solution.py"))

        # This rubric is single-language (rubric.json's top-level
        # "language" field) -- the submission's extension must match.
        if rubric_language == "julia":
            if submission_ext != ".jl":
                print(
                    f"This rubric expects a Julia (.jl) submission, but "
                    f"'{args.submission}' is not a .jl file."
                )
                return 1
            submission_target = os.path.join(tmp, "student_submission.jl")
            shutil.copy(args.submission, submission_target)
        else:
            if submission_ext == ".ipynb":
                from .notebook_convert import notebook_to_python
                code = notebook_to_python(args.submission)
                if code is None:
                    print(f"Could not convert {args.submission} as a Python notebook.")
                    return 1
                submission_target = os.path.join(tmp, "student_submission.py")
                with open(submission_target, "w", encoding="utf-8") as f:
                    f.write(code)
            elif submission_ext == ".py":
                submission_target = os.path.join(tmp, "student_submission.py")
                shutil.copy(args.submission, submission_target)
            else:
                print(
                    f"This rubric expects a Python (.py/.ipynb) submission, but "
                    f"'{args.submission}' is not one."
                )
                return 1

        with open(os.path.join(tmp, "student_language.json"), "w") as f:
            json.dump({"language": rubric_language, "submission_path": submission_target}, f)
        with open(os.path.join(tmp, "all_test_specs.json"), "w") as f:
            json.dump(_build_all_specs(config["test_suite"]), f)


        with open(os.path.join(tmp, "test_rubric.py"), "w") as f:
            f.write(generate_test_file(config["test_suite"], has_python_solution=not is_julia_solution))

        sys.path.insert(0, tmp)
        try:
            from autobuilder import attempt_recorder
            from autobuilder.attempts import make_post_processor

            attempt_recorder.clear()

            module = importlib.import_module("test_rubric")
            suite = unittest.TestLoader().loadTestsFromModule(module)

            post_processor = make_post_processor(config, {})

            stream = io.StringIO()
            JSONTestRunner(visibility="visible", stream=stream, buffer=False,
                            post_processor=post_processor).run(suite)
            results = json.loads(stream.getvalue())
        finally:
            sys.path.remove(tmp)
            os.environ.pop("AUTOBUILDER_SOURCE_DIR", None)
            os.environ.pop("AUTOBUILDER_TEST_INPUTS_PATH", None)
            for mod in ["test_rubric", "solution", "student_submission"]:
                sys.modules.pop(mod, None)

    total = 0.0
    for t in results.get("tests", []):
        score = t.get("score", 0.0)
        max_score = t.get("max_score", 0.0)
        total += score
        marker = "PASS" if t.get("status") == "passed" else "FAIL"
        print(f"[{marker}] {t.get('name')}")
        output = t.get("output")
        if output:
            for line in output.rstrip().splitlines():
                print(f"       {line}")

    print(f"\nTotal: {total:g}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="autobuilder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a Gradescope PyUnit autograder zip")
    p_build.add_argument("rubric", help="Path to rubric.json")
    p_build.add_argument("solution", help="Path to your correct solution .py script")
    p_build.add_argument("--inputs", help="Path to a .py file defining test input variables")
    p_build.add_argument("--output", default="autograder.zip", help="Output zip path")
    p_build.add_argument("--timeout", type=float, help="Per-run timeout (seconds) for validating the solution")
    p_build.set_defaults(func=cmd_build)

    p_grade = sub.add_parser("grade", help="Run a local self-check against a submission")
    p_grade.add_argument("rubric", help="Path to rubric.json")
    p_grade.add_argument("solution", help="Path to your correct solution .py script")
    p_grade.add_argument("submission", help="Path to a .py submission to grade")
    p_grade.add_argument("--inputs", help="Path to a .py file defining test input variables")
    p_grade.add_argument("--timeout", type=float, default=60, help="Per-run timeout in seconds")
    p_grade.set_defaults(func=cmd_grade)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
