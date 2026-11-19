"""
Turns the per-test results of one run into the final Gradescope results.
Used by run_tests.py (through attempts.make_post_processor) and by
`autobuilder grade`. The Julia autobuilder has the same logic in
src/grader/scoring.jl; both read the same rubric.json fields:

  Rubric preamble
    "precheck": true          students may put `precheck = True` in their
                              file: then only the zero-point tests are run
                              and shown, the scored tests are not run, and no
                              attempts are used (earlier scores are carried
                              forward, hidden, so they are not lost)
    "combine_questions": true one Gradescope test per question (1a, 1b, 1c
                              -> 1), listing only what went wrong
    "late_penalties": [       a correct answer submitted after "after" earns
      {"after": "2026-11-20T23:59:00-08:00", "penalty": 0.1}, ...]
                              (1 - penalty) of its points, unless it was
                              already correct before (the best credit is kept)

  Per test
    "attempts": N, "allow_tries": true    (see attempts.py)
    "question": "1"                       group for combine_questions; by
                                          default the test_name without its
                                          trailing letters (1a -> 1, Q2b -> Q2)

History. Gradescope only shows the autograder the previous submission's
results, so each tracked test carries an accumulator forward in extra_data:
{"attempts_used": n, "best_score": s}. With combine_questions the
accumulators of a question's parts are stored together on the question's
row as {"parts": {test_name: accumulator}}. A test is tracked when it has an
"attempts" limit, or when the rubric has late penalties (otherwise a student
who was correct on time and resubmits late would lose points).

Everything here is defensive: missing or malformed metadata counts as a
first submission, and nothing raises.
"""
import os
import re
from datetime import datetime, timezone

# Precheck rows are marked with extra_data {"precheck": true} (results from
# before v0.8 used numbers starting with "precheck:"). They carry no history.
PRECHECK_PREFIX = "precheck:"
_FAILURE_PREFIX = "Test Failed: "


def _fmt(x):
    return f"{float(x):g}"


def _score_of(t):
    try:
        return float(t.get("score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


# ── Times ───────────────────────────────────────────────────────────────────

def parse_time(s):
    """ISO 8601 date and time WITH a UTC offset, e.g. 2026-11-20T23:59:00-08:00
    (or ...Z). Raises ValueError when it can't be read or has no offset."""
    s = str(s).strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)    # -0800 -> -08:00
    # Python 3.10 only reads 3 or 6 fraction digits.
    m = re.match(r"^(.*\.)(\d+)([+-]\d{2}:\d{2})$", s)
    if m:
        s = m.group(1) + (m.group(2) + "000000")[:6] + m.group(3)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"{s!r} has no time zone offset (add e.g. -08:00 or Z)")
    return dt


def submission_time(metadata):
    """When this submission was made: AUTOBUILDER_NOW (local testing), else
    Gradescope's created_at (so regrading later does not make everyone
    late), else the current time."""
    for source in (os.environ.get("AUTOBUILDER_NOW"), (metadata or {}).get("created_at")):
        if source:
            try:
                return parse_time(source)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


_ZONE_NAMES = {-8 * 60: "PST", -7 * 60: "PDT", 0: "UTC"}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def format_time(dt):
    """A deadline for students, in its own time zone:
    2026-11-20T23:59:00-08:00 -> "Nov 20, 2026 at 11:59 PM PST"."""
    minutes = int(dt.utcoffset().total_seconds() // 60)
    zone = _ZONE_NAMES.get(minutes)
    if zone is None:
        sign = "+" if minutes >= 0 else "-"
        h, m = divmod(abs(minutes), 60)
        zone = f"UTC{sign}{h}" + (f":{m:02d}" if m else "")
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{_MONTHS[dt.month - 1]} {dt.day}, {dt.year} at {hour}:{dt.minute:02d} {ampm} {zone}"


def late_penalty(config, when):
    """(penalty, deadline_text) for a submission made at `when`: the penalty
    of the last "after" time it is past, or (0.0, None) when on time. The
    deadline text is readable ("Nov 20, 2026 at 11:59 PM PST")."""
    penalty, deadline = 0.0, None
    entries = []
    for e in config.get("late_penalties") or []:
        try:
            entries.append((parse_time(e["after"]), float(e["penalty"])))
        except (KeyError, TypeError, ValueError):
            pass
    for after, p in sorted(entries, key=lambda x: x[0]):
        if when > after:
            penalty, deadline = p, format_time(after)
    return min(max(penalty, 0.0), 1.0), deadline


def most_credit(max_score, penalty):
    """The most a test can still earn: its points minus the late penalty
    (a hair less, so rounding never keeps a part from counting as done)."""
    return round(max_score * (1 - penalty), 6) - 1e-9


def late_maximum_message(pct, earned, possible):
    return (f"✅ **All questions are correct.** With the {pct}% late penalty included, this is the most "
            f"credit you can receive ({_fmt(round(earned, 6))}/{_fmt(possible)}). "
            "Further submissions will not be graded.")


# ── Markdown (every output is shown by Gradescope with output_format "md") ──

_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>#|])")


def md_escape(text):
    """Plain text, shown literally in Markdown."""
    return _MD_SPECIAL.sub(r"\\\1", str(text))


def md_text(text):
    """Plain text (possibly several lines) as Markdown: escaped, line breaks kept."""
    paragraphs = re.split(r"\n\s*\n", str(text or "").strip())
    return "\n\n".join("  \n".join(md_escape(l.rstrip()) for l in p.splitlines())
                       for p in paragraphs if p.strip())


def _code_block(lines, indent=""):
    fence = "```"
    while any(fence in l for l in lines):
        fence += "`"
    return "\n".join([indent + fence] + [indent + l for l in lines] + [indent + fence])


def validate_late_penalties(config):
    """Raise ValueError with a readable message for a malformed "late_penalties"."""
    entries = config.get("late_penalties")
    if entries is None:
        return
    if not isinstance(entries, list):
        raise ValueError('"late_penalties" must be a list of {"after": ..., "penalty": ...}')
    for e in entries:
        if not isinstance(e, dict) or "after" not in e or "penalty" not in e:
            raise ValueError(f'late_penalties: every entry needs "after" and "penalty", got {e!r}')
        try:
            parse_time(e["after"])
        except (TypeError, ValueError) as err:
            raise ValueError(f'late_penalties: cannot read "after": {e["after"]!r} ({err}). '
                             'Use e.g. "2026-11-20T23:59:00-08:00".')
        p = e["penalty"]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
            raise ValueError(f'late_penalties: "penalty" is a fraction between 0 and 1 '
                             f'(0.1 = 10%), got {p!r}')


# ── History from the previous submission ────────────────────────────────────

def previous_results(metadata):
    """The results of the most recent previous submission ({} if none)."""
    try:
        prev = [p for p in (metadata.get("previous_submissions") or []) if isinstance(p, dict)]
        if not prev:
            return {}
        latest = prev[0]
        try:
            latest = max(prev, key=lambda p: parse_time(p["submission_time"]))
        except (KeyError, TypeError, ValueError):
            pass
        results = latest.get("results")
        return results if isinstance(results, dict) else {}
    except AttributeError:
        return {}


def is_precheck_row(row):
    extra = row.get("extra_data")
    return (str(row.get("number", "")).startswith(PRECHECK_PREFIX)
            or (isinstance(extra, dict) and extra.get("precheck") is True))


def _accumulator(extra):
    return (int(extra["attempts_used"]), float(extra.get("best_score", 0.0) or 0.0))


def previous_accumulators(metadata):
    """{test_name: (attempts_used, best_score)} from the previous submission,
    whether it stored them per test or per combined question."""
    accs = {}
    for row in previous_results(metadata).get("tests") or []:
        try:
            if is_precheck_row(row):
                continue
            extra = row.get("extra_data") or {}
            if isinstance(extra.get("parts"), dict):
                for name, acc in extra["parts"].items():
                    if isinstance(acc, dict) and "attempts_used" in acc:
                        accs[str(name)] = _accumulator(acc)
            elif "attempts_used" in extra and row.get("number") is not None:
                accs[str(row["number"])] = _accumulator(extra)
        except (AttributeError, TypeError, ValueError):
            pass
    return accs


# ── Questions (combine_questions) ───────────────────────────────────────────

def question_key(t):
    q = t.get("question")
    if q not in (None, ""):
        return str(q)
    name = str(t["test_name"])
    m = re.match(r"^(.*\d)[ _.\-]?[A-Za-z]+$", name)
    return m.group(1) if m else name


def question_title(key):
    return f"Question {key}" if re.fullmatch(r"\d+", key) else key


def _target(t):
    ttype = t.get("type", "variable")
    if ttype != "variable" and "function_name" in t:
        return t["function_name"]
    return t.get("variable_name", t["test_name"])


def part_label(t):
    """How a test is named to students, in Markdown: "Part b: `squares`" for
    test names like 1b / Q2c, "`euler_step`" when the name is just the
    question number, otherwise the test_name as the instructor wrote it."""
    name = str(t["test_name"])
    target = f"`{_target(t)}`"
    m = re.match(r"^(.*\d)[ _.\-]?([A-Za-z]+)$", name)
    if m:
        return f"Part {md_escape(m.group(2))}: {target}"
    if re.fullmatch(r"[A-Za-z]*\d+", name):
        return target
    return md_escape(name)


def _part_heading(info):
    t = info["cfg"]
    head = f"- **{part_label(t)}**"
    if t.get("description"):
        head += f" — {md_escape(t['description'])}"
    return head


def _clean_output(text):
    lines = (text or "").strip().splitlines()
    if lines and lines[0].startswith(_FAILURE_PREFIX):
        lines[0] = lines[0][len(_FAILURE_PREFIX):]
    return lines


def _error_bullets(output, indent):
    """The failure message of a test as Markdown bullets: the error, the hint
    in bold, a hint image as is, and anything longer (a traceback) as code."""
    message, hints, images = [], [], []
    for line in _clean_output(output):
        if line.startswith("Hint: "):
            hints.append(line[len("Hint: "):])
        elif line.startswith("!["):
            images.append(line)
        else:
            message.append(line.rstrip())
    while message and not message[-1].strip():
        message.pop()
    out = []
    items = [re.match(r"^\s*- (.*)$", l) for l in message[1:]]
    if len(message) == 1:
        out.append(f"{indent}{ARROW} {md_escape(message[0])}")
    elif message and all(items):
        # "The following issues were found:" and a list: one line each.
        out.append(f"{indent}{ARROW} {md_escape(message[0])}")
        out += [f"{indent}{ARROW} {md_escape(m.group(1))}" for m in items]
    elif message:
        out.append(f"{indent}{ARROW} Error:\n\n" + _code_block(message, indent) + "\n")
    out += [f"{indent}{ARROW} **Hint:** {md_escape(h)}" for h in hints]
    out += [f"\n{indent}{img}\n" for img in images]
    return out


# Details under a part are lines starting with a triangle (not a second
# level of bullets), kept apart by Markdown hard line breaks.
ARROW = "▸"


def _lines(lines):
    return "  \n".join(lines)


def _attempts_text(info):
    if not info["limit"]:
        return None
    used = info["acc"]["attempts_used"] if info["acc"] else 0
    if info["allow_tries"]:
        return f"**Attempts:** {used} (no limit)"
    shown = min(used, info["limit"])
    return f"**Attempts:** {shown}/{info['limit']} ({info['limit'] - shown} left)"


def _status_lines(info, pct):
    """Extra lines about earlier credit or a late penalty for one test."""
    if info["previously_correct"]:
        return ["Previously correct: your earlier credit is kept."]
    if info["previous_partial"]:
        return [f"Previously earned {_fmt(info['best'])}/{_fmt(info['max'])}: your earlier credit is kept."]
    if info["late"]:
        return [f"Correct, but submitted late: {pct}% late penalty applied "
                f"({_fmt(info['best'])}/{_fmt(info['max'])})."]
    return []


# ── The whole thing ─────────────────────────────────────────────────────────

def finalize(results, config, metadata, attempted, precheck=False):
    """Rewrite `results` (Gradescope results dict with per-test rows whose
    "number" is the test_name) in place: precheck, attempts, late penalties,
    combined questions, total score and top-level notes."""
    metadata = metadata or {}
    suite = config.get("test_suite", [])
    rows = {r.get("number"): r for r in results.get("tests", [])}
    prev_accs = previous_accumulators(metadata)
    notes = []

    penalty, deadline = 0.0, None
    if precheck:
        suite = [t for t in suite if _score_of(t) == 0]
        notes.append("**Precheck run:** only the precheck questions were checked. "
                     "In order to receive any credit, turn `precheck = False`.")
    else:
        penalty, deadline = late_penalty(config, submission_time(metadata))
    pct = _fmt(round(penalty * 100, 6))
    if penalty > 0:
        notes.append(f"**Late submission:** submitted after {deadline}, so a {pct}% late penalty "
                     "applies to questions that were not already correct before.")

    track_all = bool(config.get("late_penalties"))
    infos = []
    for t in suite:
        name = t["test_name"]
        row = rows.get(name)
        if row is None:
            continue
        max_score = float(row.get("max_score", 0.0) or 0.0)
        raw = float(row.get("score", 0.0) or 0.0)
        passed = row.get("status") == "passed"
        limit = int(t.get("attempts") or 0)
        info = {"cfg": t, "row": row, "limit": limit, "allow_tries": t.get("allow_tries") is True,
                "acc": None, "passed": passed, "max": max_score, "best": raw,
                "previously_correct": False, "previous_partial": False, "late": False,
                "kept_full": False, "maxed": False}
        if not precheck and (limit or track_all):
            used, best = prev_accs.get(name, (0, 0.0))
            prev_best = best
            # The most it can still earn (full credit, or with the late penalty
            # included) is already earned: the part is done, and uses no more attempts.
            done = max_score > 0 and prev_best >= most_credit(max_score, penalty)
            if attempted.get(name, False) and not done:
                within = info["allow_tries"] or not limit or used < limit
                used += 1
                if within:
                    best = max(best, round(raw * (1 - penalty), 6))
            best = min(best, max_score)
            row["score"] = best
            info["acc"] = {"attempts_used": used, "best_score": best}
            info["best"] = best
            info["previously_correct"] = not passed and done
            info["kept_full"] = prev_best >= max_score
            info["previous_partial"] = not passed and 0 < prev_best and not done
            info["late"] = passed and penalty > 0 and prev_best < max_score and max_score > 0
            info["maxed"] = max_score <= 0 or best >= most_credit(max_score, penalty)
        infos.append(info)

    # Late, and every question has the most credit it can still get: say so
    # (later submissions are not graded, see attempts.locked_out_message).
    graded = [i for i in infos if i["acc"] is not None and i["max"] > 0]
    earned, possible = sum(i["best"] for i in graded), sum(i["max"] for i in graded)
    if penalty > 0 and graded and all(i["maxed"] for i in graded) and earned < possible:
        notes.append(late_maximum_message(pct, earned, possible))

    # Rows that belong to no rubric test (e.g. the generated tests failed to
    # import) are kept as they are, so the problem shows instead of a blank page.
    known = {t["test_name"] for t in config.get("test_suite", [])}
    unknown = [r for r in results.get("tests", []) if r.get("number") not in known]

    if config.get("combine_questions") is True:
        tests = _combined_rows(infos, pct, precheck)
    else:
        tests = [_single_row(info, pct, precheck) for info in infos]
    tests += unknown

    if precheck:
        # The graded rows of the previous submission, unchanged but hidden:
        # if this precheck submission becomes the active one, the score stays.
        for row in previous_results(metadata).get("tests") or []:
            if isinstance(row, dict) and not is_precheck_row(row):
                tests.append(dict(row, visibility="hidden"))

    results["tests"] = tests
    results["score"] = round(sum(float(r.get("score", 0.0) or 0.0) for r in tests), 6)
    for row in unknown:
        if row.get("output_format") != "md":
            text = str(row.get("output") or "").strip()
            row["output"] = _code_block(text.splitlines()) if text else ""
            row["output_format"] = "md"
    existing = md_text(results.get("output"))
    results["output"] = "\n\n".join(p for p in notes + [existing] if p)
    results["output_format"] = "md"
    return results


def _single_row(info, pct, precheck):
    row = info["row"]
    t = info["cfg"]
    row["output_format"] = "md"
    if precheck:
        row["extra_data"] = {"precheck": True}
    if info["acc"] is not None:
        row["extra_data"] = info["acc"]
    head = _status_lines(info, pct)
    if info["limit"]:
        used = info["acc"]["attempts_used"]
        shown = used if info["allow_tries"] else min(used, info["limit"])
        row["name"] = f"(attempt: {shown}/{info['limit']}) {row.get('name', t['test_name'])}"
        head = [f"**Locked score:** {_fmt(info['best'])}/{_fmt(info['max'])}"] + head
    lines = [f"{ARROW} {h}" for h in head]
    if info["previously_correct"]:
        # Full credit from before: what is wrong now no longer matters.
        row["status"] = "passed"
    else:
        lines += _error_bullets(row.get("output"), "")
    row["output"] = _lines(lines)
    return row


def _combined_rows(infos, pct, precheck):
    groups = {}
    for info in infos:
        groups.setdefault(question_key(info["cfg"]), []).append(info)

    rows = []
    for key, parts in groups.items():
        wrong = [i for i in parts if not i["passed"] and not i["previously_correct"]]
        kept = [i for i in parts if i["previously_correct"]]
        late = [i for i in parts if i["late"]]

        # Title lines, each followed by one bullet per part; the details of a
        # part are triangle lines inside its bullet.
        blocks = []
        if wrong:
            lines = ["**❌ Incorrect answers:**", ""]
            for i in wrong:
                sub = [f"  {ARROW} {s}" for s in _status_lines(i, pct)]
                sub += _error_bullets(i["row"].get("output"), "  ")
                attempts = _attempts_text(i)
                if attempts:
                    sub.append(f"  {ARROW} {attempts}")
                lines.append(_lines([_part_heading(i)] + sub))
            blocks.append("\n".join(lines))
        # Correct in an earlier submission (full credit, or the most possible
        # with the late penalty): done, whatever it says now.
        kept_full = [i for i in kept if i["kept_full"]]
        kept_late = [i for i in kept if not i["kept_full"]]
        if kept_full:
            lines = ["**⚠️ Previously correct, now incorrect (full credit kept):**", ""]
            lines += [_part_heading(i) for i in kept_full]
            blocks.append("\n".join(lines))
        if kept_late:
            lines = ["**⚠️ Previously correct, now incorrect (late credit kept):**", ""]
            lines += [f"{_part_heading(i)} ({_fmt(i['best'])}/{_fmt(i['max'])})" for i in kept_late]
            blocks.append("\n".join(lines))
        if late:
            lines = [f"**✅ Correct, with the {pct}% late penalty:**", ""]
            lines += [f"{_part_heading(i)} ({_fmt(i['best'])}/{_fmt(i['max'])})" for i in late]
            blocks.append("\n".join(lines))
        if not blocks:
            blocks.append("**✅ All parts correct.**")
        output = "\n\n".join(blocks)

        score = round(sum(float(i["row"].get("score", 0.0) or 0.0) for i in parts), 6)
        max_score = sum(i["max"] for i in parts)
        row = {
            "name": question_title(key),
            "score": score,
            "max_score": max_score,
            "status": "passed" if not wrong else "failed",
            "output": output,
            "output_format": "md",
            "visibility": "visible",
        }
        accs = {i["cfg"]["test_name"]: i["acc"] for i in parts if i["acc"] is not None}
        # No "number": Gradescope would show it in front of the name ("1) Question 1").
        if accs:
            row["extra_data"] = {"parts": accs}
        if precheck:
            row["extra_data"] = {"precheck": True}
        rows.append(row)
    return rows
