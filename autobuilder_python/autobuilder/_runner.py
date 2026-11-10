"""
Runs in a fresh subprocess. Executes a script once, then for each requested
test either:
  - "variable": pulls a named variable out of the resulting global namespace
  - "function": calls a named function with given inputs and captures its
    return value (optionally indexing into the result for multi-output
    functions via "output_index")

Results are appended to the output file as a sequence of pickled records,
each written (and flushed) as soon as it is known -- so if the student's code
hangs on test 7 and the subprocess is killed at the timeout, tests 1-6 keep
their results:

    {"kind": "script_error", "detail": traceback}   the script itself crashed;
                                                     everything it defined
                                                     before that is still graded
    {"kind": "value", "name": test_name, "value": v}
    {"kind": "missing", "name": test_name}          variable/function never defined
    {"kind": "call_error", "name": test_name, "detail": traceback}
    {"kind": "done"}

AUTOBUILDER_STUDENT_HELPERS_DIR, if set, is added to sys.path before the
script runs -- lets a student's entry-point file import a sibling module
they submitted alongside it (see templates/prepare_submission.py).
"""
import os
import sys
import json
import pickle
import traceback
import importlib.util
import tokenize

from inputs import convert_inputs as _convert_inputs, resolve_callable_inputs as _resolve_callable


def _emit(out, record):
    try:
        data = pickle.dumps(record)
    except Exception as e:
        # e.g. a generator or a lambda: it exists, but can't be sent back.
        data = pickle.dumps({
            "kind": "call_error", "name": record.get("name"),
            "detail": f"TypeError: the value could not be returned for grading ({type(e).__name__}: {e})",
        })
    out.write(data)
    out.flush()


def main():
    script_path, output_path, tests_json = sys.argv[1], sys.argv[2], sys.argv[3]
    tests = json.loads(tests_json)

    try:
        import test_inputs as _test_inputs_mod
    except ImportError:
        _path = os.environ.get("AUTOBUILDER_TEST_INPUTS_PATH")
        if _path and os.path.isfile(_path):
            _spec = importlib.util.spec_from_file_location("test_inputs", _path)
            _test_inputs_mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_test_inputs_mod)
        else:
            _test_inputs_mod = None

    helpers_dir = os.environ.get("AUTOBUILDER_STUDENT_HELPERS_DIR")
    if helpers_dir and os.path.isdir(helpers_dir):
        sys.path.insert(0, helpers_dir)

    with open(output_path, "ab") as out:
        ns = {}
        try:
            with tokenize.open(script_path) as f:   # UTF-8 (or the file's coding line), like import
                code = f.read()
            compiled = compile(code, script_path, "exec")
            exec(compiled, ns)
        except (Exception, SystemExit):
            # Keep going: whatever the script defined before the error is graded.
            _emit(out, {"kind": "script_error", "detail": traceback.format_exc()})

        for t in tests:
            name = t["name"]

            if t["type"] == "variable":
                varname = t["variable_name"]
                if varname in ns:
                    _emit(out, {"kind": "value", "name": name, "value": ns[varname]})
                else:
                    _emit(out, {"kind": "missing", "name": name})

            elif t["type"] == "function":
                fname = t["function_name"]
                if fname not in ns or not callable(ns[fname]):
                    _emit(out, {"kind": "missing", "name": name})
                    continue
                try:
                    inputs = _convert_inputs(_resolve_callable(t.get("inputs", []), _test_inputs_mod))
                    output = ns[fname](*inputs)
                    if t.get("output_index") is not None:
                        output = output[t["output_index"]]
                    _emit(out, {"kind": "value", "name": name, "value": output})
                except (Exception, SystemExit):
                    _emit(out, {"kind": "call_error", "name": name, "detail": traceback.format_exc()})

        _emit(out, {"kind": "done"})


if __name__ == "__main__":
    main()
