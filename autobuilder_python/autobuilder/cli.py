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

from .build import build as build_zip, VENDOR_FILES
from .codegen import generate_test_file

PACKAGE_DIR = os.path.dirname(__file__)


def cmd_build(args):
    out = build_zip(args.rubric, args.solution, args.output, args.inputs, args.timeout)
    print(f"Wrote {out}")
    return 0


def cmd_grade(args):
    from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner
    from .build import (
        _build_all_specs, _check_language, _load_inputs_namespace, _resolve_hint_images,
        _resolve_inputs, working_directory,
    )

    with open(args.rubric, encoding="utf-8") as f:
        config = json.load(f)
    try:
        _check_language(config)
    except RuntimeError as e:
        print(e)
        return 1

    # Same time limit as the built zip: --timeout, else the rubric's, else the default.
    from .build import DEFAULT_TIMEOUT
    config["timeout"] = args.timeout if args.timeout is not None else config.get("timeout", DEFAULT_TIMEOUT)

    if args.inputs:
        inputs_ns = _load_inputs_namespace(args.inputs)
        config["test_suite"] = _resolve_inputs(config["test_suite"], inputs_ns)

    rubric_dir = os.path.dirname(os.path.abspath(args.rubric))
    config["test_suite"] = _resolve_hint_images(config["test_suite"], rubric_dir)

    submission_ext = os.path.splitext(args.submission)[1].lower()

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

        from .build import solution_as_py
        try:
            with solution_as_py(args.solution) as py_path:   # .py or .ipynb
                shutil.copy(py_path, os.path.join(tmp, "solution.py"))
        except RuntimeError as e:
            print(e)
            return 1

        # Data files sit next to the scripts, as in the Gradescope zip.
        for fname in config.get("extra_files", []):
            src = os.path.join(rubric_dir, fname)
            if not os.path.exists(src):
                print(f"extra_files: '{fname}' not found next to rubric.json (looked at {src})")
                return 1
            shutil.copy(src, os.path.join(tmp, fname))

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
            json.dump({"language": "python", "submission_path": submission_target}, f)
        with open(os.path.join(tmp, "all_test_specs.json"), "w") as f:
            json.dump(_build_all_specs(config["test_suite"]), f)
        # student_dispatch reads the time limit from here, as on Gradescope.
        with open(os.path.join(tmp, "rubric.json"), "w") as f:
            json.dump(config, f)


        with open(os.path.join(tmp, "test_rubric.py"), "w", encoding="utf-8") as f:
            f.write(generate_test_file(config["test_suite"]))

        sys.path.insert(0, tmp)
        try:
            from autobuilder import attempt_recorder
            from autobuilder.attempts import make_post_processor

            attempt_recorder.clear()

            post_processor = make_post_processor(config, {})
            stream = io.StringIO()
            # Importing test_rubric may already run solution.py, so the
            # import happens inside the data files' folder too.
            with working_directory(tmp):
                module = importlib.import_module("test_rubric")
                suite = unittest.TestLoader().loadTestsFromModule(module)
                JSONTestRunner(visibility="visible", stream=stream, buffer=False,
                                post_processor=post_processor).run(suite)
            results = json.loads(stream.getvalue())

            # Messages shown at the top on Gradescope (script crashed part-way,
            # ran out of time) -- written by student_dispatch in the temp folder.
            try:
                with open(os.path.join(tmp, "_grading_notes.json")) as f:
                    notes = json.load(f)
            except (OSError, ValueError):
                notes = []

            if args.json_out:
                with open(args.json_out, "w") as f:
                    json.dump({
                        "tests": results.get("tests", []),
                        "total": sum(t.get("score", 0.0) for t in results.get("tests", [])),
                    }, f)
        finally:
            sys.path.remove(tmp)
            os.environ.pop("AUTOBUILDER_SOURCE_DIR", None)
            os.environ.pop("AUTOBUILDER_TEST_INPUTS_PATH", None)
            for mod in ["test_rubric", "solution", "student_submission"]:
                sys.modules.pop(mod, None)

    for note in notes:
        print(note + "\n")

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
    # Test names/hints may contain characters like ≈ that a Windows console
    # (cp1252) can't encode; print a replacement instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="autobuilder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a Gradescope PyUnit autograder zip")
    p_build.add_argument("rubric", help="Path to rubric.json")
    p_build.add_argument("solution", help="Path to your correct solution (.py script or .ipynb notebook)")
    p_build.add_argument("--inputs", help="Path to a .py file defining test input variables")
    p_build.add_argument("--output", default="autograder.zip", help="Output zip path")
    p_build.add_argument("--timeout", type=float, help="Per-run timeout (seconds) for validating the solution")
    p_build.set_defaults(func=cmd_build)

    p_grade = sub.add_parser("grade", help="Run a local self-check against a submission")
    p_grade.add_argument("rubric", help="Path to rubric.json")
    p_grade.add_argument("solution", help="Path to your correct solution (.py script or .ipynb notebook)")
    p_grade.add_argument("submission", help="Path to a .py submission to grade")
    p_grade.add_argument("--inputs", help="Path to a .py file defining test input variables")
    p_grade.add_argument("--timeout", type=float, default=None,
                         help="Seconds the submission may run (default: the rubric's \"timeout\", else 10, as on Gradescope)")
    p_grade.add_argument("--json-out", help="Write structured grade results as JSON to this path")
    p_grade.set_defaults(func=cmd_grade)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
