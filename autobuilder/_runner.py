"""
Runs in a fresh subprocess. Executes a script once, then for each requested
test either:
  - "variable": pulls a named variable out of the resulting global namespace
  - "function": calls a named function with given inputs and captures its
    return value (optionally indexing into the result for multi-output
    functions via "output_index")

Pickles a result dict:
    {
        "_error": str | None,            # traceback if the script itself crashed
        "values": {test_name: value},    # successfully captured values
        "_missing": [test_name, ...],    # variable/function never defined
        "_call_errors": {test_name: tb}, # function raised when called
    }

This is the unit of isolation: one script execution, captured once, with
everything downstream working off this dict.
"""
import os
import sys
import json
import pickle
import traceback
import importlib.util

from inputs import convert_inputs as _convert_inputs, resolve_callable_inputs as _resolve_callable


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

    ns = {}
    error = None
    try:
        with open(script_path) as f:
            code = f.read()
        compiled = compile(code, script_path, "exec")
        exec(compiled, ns)
    except Exception:
        error = traceback.format_exc()

    result = {"_error": error, "values": {}, "_missing": [], "_call_errors": {}}

    for t in tests:
        name = t["name"]

        if t["type"] == "variable":
            varname = t["variable_name"]
            if varname in ns:
                result["values"][name] = ns[varname]
            else:
                result["_missing"].append(name)

        elif t["type"] == "function":
            fname = t["function_name"]
            if fname not in ns or not callable(ns[fname]):
                result["_missing"].append(name)
                continue
            try:
                inputs = _convert_inputs(_resolve_callable(t.get("inputs", []), _test_inputs_mod))
                output = ns[fname](*inputs)
                if t.get("output_index") is not None:
                    output = output[t["output_index"]]
                result["values"][name] = output
            except Exception:
                result["_call_errors"][name] = traceback.format_exc()

    with open(output_path, "wb") as f:
        pickle.dump(result, f)


if __name__ == "__main__":
    main()
