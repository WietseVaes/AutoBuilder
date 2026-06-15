"""
Runs in a fresh subprocess. Executes a student's Python script and pickles
whatever subset of its global namespace the rubric cares about, plus any
error encountered. This is the unit of isolation: one student script run,
captured once, with everything downstream working off the captured dict.
"""
import sys
import json
import pickle
import traceback


def main():
    script_path, output_path, varnames_json = sys.argv[1], sys.argv[2], sys.argv[3]
    varnames = json.loads(varnames_json)

    ns = {}
    error = None
    try:
        with open(script_path) as f:
            code = f.read()
        compiled = compile(code, script_path, "exec")
        exec(compiled, ns)
    except Exception:
        error = traceback.format_exc()

    result = {"_error": error, "values": {}, "_missing": []}
    for name in varnames:
        if name in ns:
            result["values"][name] = ns[name]
        else:
            result["_missing"].append(name)

    with open(output_path, "wb") as f:
        pickle.dump(result, f)


if __name__ == "__main__":
    main()
