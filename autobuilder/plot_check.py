"""
Plot verification by inspecting a matplotlib Axes object's properties --
never by comparing rendered pixels (which is brittle across machines:
fonts, DPI, anti-aliasing all differ).

A rubric "plot" test specifies which properties to check via "plot_checks",
a list of strings naming what to verify. Each maps to a comparison against
the same property read off solution.py's Axes object (or a hardcoded
"expected" dict).

Supported checks:
  "xlabel", "ylabel", "title"   -- exact string match
  "xlim", "ylim"                -- numeric tuple, tolerance-based
  "n_lines"                     -- number of Line2D artists (line plots)
  "line_data"                   -- xdata/ydata of each line, tolerance-based
  "n_bars"                      -- number of bar patches (bar charts)
  "bar_heights"                 -- heights of bar patches, tolerance-based
  "legend_labels"                -- exact list of legend label strings
"""
import numpy as np


def extract_axes_info(ax, checks):
    """Pull the requested properties off a matplotlib Axes object into a
    plain dict of JSON/numeric-safe values."""
    info = {}
    for check in checks:
        if check == "xlabel":
            info["xlabel"] = ax.get_xlabel()
        elif check == "ylabel":
            info["ylabel"] = ax.get_ylabel()
        elif check == "title":
            info["title"] = ax.get_title()
        elif check == "xlim":
            info["xlim"] = list(ax.get_xlim())
        elif check == "ylim":
            info["ylim"] = list(ax.get_ylim())
        elif check == "n_lines":
            info["n_lines"] = len(ax.get_lines())
        elif check == "line_data":
            info["line_data"] = [
                [line.get_xdata().tolist(), line.get_ydata().tolist()]
                for line in ax.get_lines()
            ]
        elif check == "n_bars":
            info["n_bars"] = len(ax.patches)
        elif check == "bar_heights":
            info["bar_heights"] = [p.get_height() for p in ax.patches]
        elif check == "legend_labels":
            legend = ax.get_legend()
            info["legend_labels"] = [t.get_text() for t in legend.get_texts()] if legend else []
    return info


def compare_axes_info(student_info, ref_info, rtol=1e-2, atol=1e-2):
    """Compare two extract_axes_info() dicts. Returns (status, message)
    for the first mismatched key, same status vocabulary as comparator.compare."""
    for key, ref_val in ref_info.items():
        student_val = student_info.get(key)

        if key in ("xlabel", "ylabel", "title"):
            if student_val != ref_val:
                return "tolerance", f"'{key}' does not match (expected non-empty: {bool(ref_val)})."

        elif key == "legend_labels":
            if student_val != ref_val:
                return "tolerance", "Legend labels do not match."

        elif key in ("n_lines", "n_bars"):
            if student_val != ref_val:
                return "wrong_size", f"Expected {ref_val} for '{key}', but got {student_val}."

        elif key in ("xlim", "ylim", "bar_heights"):
            try:
                s = np.asarray(student_val, dtype=float)
                r = np.asarray(ref_val, dtype=float)
            except (TypeError, ValueError):
                return "wrong_type", f"'{key}' could not be read as numeric."
            if s.shape != r.shape:
                return "wrong_size", f"'{key}' has the wrong number of values."
            if np.any(np.isnan(s)):
                return "nans", f"'{key}' contains NaN."
            if not np.allclose(s, r, rtol=rtol, atol=atol):
                return "tolerance", f"'{key}' is not within the required tolerance."

        elif key == "line_data":
            if len(student_val or []) != len(ref_val):
                return "wrong_size", "Number of plotted lines does not match."
            for i, (s_line, r_line) in enumerate(zip(student_val, ref_val)):
                try:
                    sx, sy = np.asarray(s_line[0], dtype=float), np.asarray(s_line[1], dtype=float)
                    rx, ry = np.asarray(r_line[0], dtype=float), np.asarray(r_line[1], dtype=float)
                except (TypeError, ValueError, IndexError):
                    return "wrong_type", f"Line {i} data could not be read as numeric."
                if sx.shape != rx.shape or sy.shape != ry.shape:
                    return "wrong_size", f"Line {i} has the wrong number of data points."
                if np.any(np.isnan(sx)) or np.any(np.isnan(sy)):
                    return "nans", f"Line {i} contains NaN values."
                if not (np.allclose(sx, rx, rtol=rtol, atol=atol) and np.allclose(sy, ry, rtol=rtol, atol=atol)):
                    return "tolerance", f"Line {i}'s data does not match within tolerance."

    return "pass", "OK"
