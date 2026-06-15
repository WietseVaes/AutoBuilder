"""
Command-line entrypoint, installed as `autobuilder`.

    autobuilder build RUBRIC REFERENCE --output autograder.zip [--submission-filename HW6.py] [--timeout 10]
    autobuilder grade RUBRIC REFERENCE SUBMISSION [--timeout 10]

`build` produces a Gradescope-ready autograder zip.
`grade` runs the same grading code locally against a submission, for local
self-checks before building/uploading -- or for testing the rubric itself.
"""
import argparse
import sys

from .build import build as build_zip
from .grader import grade_python_submission, load_reference, load_rubric


def cmd_build(args):
    out = build_zip(args.rubric, args.reference, args.output, args.submission_filename, args.timeout)
    print(f"Wrote {out}")
    return 0


def cmd_grade(args):
    rubric = load_rubric(args.rubric)
    reference = load_reference(args.reference)
    result = grade_python_submission(args.submission, rubric, reference, timeout=args.timeout)

    for t in result["tests"]:
        marker = "PASS" if t["status"] == "pass" else "FAIL"
        print(f"[{marker}] {t['name']} ({t['score']:g}/{t['max_score']:g}) - {t['description']}")
        if t["status"] != "pass":
            print(f"       {t['message']}")
            if t["hint"]:
                print(f"       Hint: {t['hint']}")

    print(f"\nTotal: {result['score']:g}/{result['max_score']:g}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="autobuilder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a Gradescope autograder zip")
    p_build.add_argument("rubric", help="Path to rubric.json")
    p_build.add_argument("reference", help="Path to reference_values dump (pickle)")
    p_build.add_argument("--output", default="autograder.zip", help="Output zip path")
    p_build.add_argument("--submission-filename", help="Expected name of the student's submission file")
    p_build.add_argument("--timeout", type=float, help="Per-run timeout in seconds")
    p_build.set_defaults(func=cmd_build)

    p_grade = sub.add_parser("grade", help="Run a local self-check against a submission")
    p_grade.add_argument("rubric", help="Path to rubric.json")
    p_grade.add_argument("reference", help="Path to reference_values dump (pickle)")
    p_grade.add_argument("submission", help="Path to a .py submission to grade")
    p_grade.add_argument("--timeout", type=float, default=10, help="Per-run timeout in seconds")
    p_grade.set_defaults(func=cmd_grade)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
