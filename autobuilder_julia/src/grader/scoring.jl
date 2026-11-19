# Turns the per-test results of one run into the final Gradescope results.
# Same behaviour and rubric fields as the Python autobuilder (scoring.py):
#
#   Rubric preamble
#     "precheck": true          students may put `precheck = true` in their
#                               file: then only the zero-point tests are run
#                               and shown, the scored tests are not run, and
#                               no attempts are used (earlier scores are
#                               carried forward, hidden, so they are not lost)
#     "combine_questions": true one Gradescope test per question (1a, 1b, 1c
#                               -> 1), listing only what went wrong
#     "late_penalties": [       a correct answer submitted after "after" earns
#       {"after": "2026-11-20T23:59:00-08:00", "penalty": 0.1}, ...]
#                               (1 - penalty) of its points, unless it was
#                               already correct before (the best credit is kept)
#
#   Per test
#     "attempts": N, "allow_tries": true    (see attempts.jl)
#     "question": "1"                       group for combine_questions; by
#                                           default the test_name without its
#                                           trailing letters (1a -> 1, Q2b -> Q2)
#
# History: Gradescope only shows the autograder the previous submission's
# results, so each tracked test carries {"attempts_used": n, "best_score": s}
# forward in extra_data; with combine_questions the accumulators of a
# question's parts sit together on its row as {"parts": {test_name: ...}}.
# A test is tracked when it has an "attempts" limit, or when the rubric has
# late penalties.
#
# Missing or malformed metadata counts as a first submission; never throws.

using Dates

# Precheck rows are marked with extra_data {"precheck": true} (results from
# before v0.8 used numbers starting with "precheck:"). They carry no history.
const PRECHECK_PREFIX = "precheck:"

function is_precheck_row(row)
    extra = get(row, "extra_data", nothing)
    return startswith(string(get(row, "number", "")), PRECHECK_PREFIX) ||
           (extra isa AbstractDict && get(extra, "precheck", false) === true)
end

_fmt(x) = isinteger(x) ? string(Int(x)) : string(round(x; sigdigits=6))
_score_of(t) = try Float64(something(get(t, "score", 0), 0)) catch; 0.0 end

# ── Times ───────────────────────────────────────────────────────────────────

const _TIME_RE = r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?\s*(Z|z|[+-]\d{2}:?\d{2})$"

"""
    parse_time(s) -> DateTime (UTC) or nothing

ISO 8601 date and time WITH a UTC offset, e.g. 2026-11-20T23:59:00-08:00 or
...Z. `nothing` when it can't be read or has no offset.
"""
function parse_time(s)
    m = match(_TIME_RE, strip(string(s)))
    m === nothing && return nothing
    try
        y, mo, d, h, mi = (parse(Int, m.captures[i]) for i in 1:5)
        sec = m.captures[6] === nothing ? 0 : parse(Int, m.captures[6])
        ms = m.captures[7] === nothing ? 0 : parse(Int, first(rpad(m.captures[7], 3, '0'), 3))
        dt = DateTime(y, mo, d, h, mi, sec, ms)
        off = m.captures[8]
        if !(off in ("Z", "z"))
            digits = replace(off[2:end], ":" => "")
            minutes = parse(Int, digits[1:2]) * 60 + parse(Int, digits[3:4])
            dt -= Minute(off[1] == '-' ? -minutes : minutes)
        end
        return dt
    catch
        return nothing
    end
end

"""
When this submission was made: AUTOBUILDER_NOW (local testing), else
Gradescope's created_at (so regrading later does not make everyone late),
else the current time.
"""
function submission_time(metadata)
    for source in (get(ENV, "AUTOBUILDER_NOW", nothing), get(metadata, "created_at", nothing))
        source === nothing && continue
        t = parse_time(source)
        t === nothing || return t
    end
    return now(UTC)
end

const _ZONE_NAMES = Dict(-8 * 60 => "PST", -7 * 60 => "PDT", 0 => "UTC")
const _MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

"""
    format_time(s) -> String

A deadline for students, in its own time zone:
"2026-11-20T23:59:00-08:00" -> "Nov 20, 2026 at 11:59 PM PST".
"""
function format_time(s)
    m = match(_TIME_RE, strip(string(s)))
    m === nothing && return string(s)
    y, mo, d, h, mi = (parse(Int, m.captures[i]) for i in 1:5)
    off = m.captures[8]
    minutes = 0
    if !(off in ("Z", "z"))
        digits = replace(off[2:end], ":" => "")
        minutes = (parse(Int, digits[1:2]) * 60 + parse(Int, digits[3:4])) * (off[1] == '-' ? -1 : 1)
    end
    zone = get(_ZONE_NAMES, minutes, nothing)
    if zone === nothing
        hh, mm = divrem(abs(minutes), 60)
        zone = "UTC" * (minutes >= 0 ? "+" : "-") * string(hh) * (mm == 0 ? "" : ":" * lpad(mm, 2, '0'))
    end
    hour = h % 12 == 0 ? 12 : h % 12
    return "$(_MONTHS[mo]) $d, $y at $hour:$(lpad(mi, 2, '0')) $(h < 12 ? "AM" : "PM") $zone"
end

"""
(penalty, deadline_text): the penalty of the last "after" time `when` is
past, or (0.0, nothing). The deadline text is readable ("Nov 20, 2026 at 11:59 PM PST").
"""
function late_penalty(rubric, when)
    entries = Tuple{DateTime,Float64,String}[]
    lp = get(rubric, "late_penalties", nothing)
    lp isa AbstractVector || return (0.0, nothing)
    for e in lp
        try
            t = parse_time(e["after"])
            t === nothing || push!(entries, (t, Float64(e["penalty"]), string(e["after"])))
        catch
        end
    end
    penalty, deadline = 0.0, nothing
    for (after, p, text) in sort(entries; by=first)
        when > after && ((penalty, deadline) = (p, format_time(text)))
    end
    return (clamp(penalty, 0.0, 1.0), deadline)
end

"""
The most a test can still earn: its points minus the late penalty (a hair
less, so rounding never keeps a part from counting as done).
"""
most_credit(max_score, penalty) = round(max_score * (1 - penalty); digits=6) - 1e-9

late_maximum_message(pct, earned, possible) =
    "✅ **All questions are correct.** With the $pct% late penalty included, this is the most credit you can " *
    "receive ($(_fmt(round(earned; digits=6)))/$(_fmt(possible))). Further submissions will not be graded."

# ── Markdown (every output is shown by Gradescope with output_format "md") ──

"""Plain text, shown literally in Markdown."""
md_escape(text) = replace(string(text), r"([\\`*_\[\]<>#|])" => s"\\\1")

"""Plain text (possibly several lines) as Markdown: escaped, line breaks kept."""
function md_text(text)
    paragraphs = split(strip(string(something(text, ""))), r"\n\s*\n")
    return join([join([md_escape(rstrip(l)) for l in split(p, '\n')], "  \n")
                 for p in paragraphs if !isempty(strip(p))], "\n\n")
end

function _code_block(lines, indent="")
    fence = "```"
    while any(l -> occursin(fence, l), lines)
        fence *= "`"
    end
    return join(vcat([indent * fence], [indent * l for l in lines], [indent * fence]), "\n")
end

"""A readable error message for a malformed "late_penalties", or nothing."""
function late_penalties_problem(rubric)
    haskey(rubric, "late_penalties") || return nothing
    lp = rubric["late_penalties"]
    lp isa AbstractVector || return "\"late_penalties\" must be a list of {\"after\": ..., \"penalty\": ...}"
    for e in lp
        (e isa AbstractDict && haskey(e, "after") && haskey(e, "penalty")) ||
            return "late_penalties: every entry needs \"after\" and \"penalty\", got $(repr(e))"
        parse_time(e["after"]) === nothing &&
            return "late_penalties: cannot read \"after\": \"$(e["after"])\" (it needs a date, a time and a time zone " *
                   "offset). Use e.g. \"2026-11-20T23:59:00-08:00\"."
        p = e["penalty"]
        (p isa Real && !(p isa Bool) && 0 <= p <= 1) ||
            return "late_penalties: \"penalty\" is a fraction between 0 and 1 (0.1 = 10%), got $(repr(p))"
    end
    return nothing
end

# ── History from the previous submission ────────────────────────────────────

"""The results of the most recent previous submission (empty Dict if none)."""
function previous_results(metadata)
    try
        prev = get(metadata, "previous_submissions", nothing)
        prev isa AbstractVector || return Dict{String,Any}()
        prev = [p for p in prev if p isa AbstractDict]
        isempty(prev) && return Dict{String,Any}()
        latest = prev[1]
        times = [parse_time(get(p, "submission_time", "")) for p in prev]
        if all(t -> t !== nothing, times)
            latest = prev[argmax(times)]
        end
        results = get(latest, "results", nothing)
        return results isa AbstractDict ? results : Dict{String,Any}()
    catch
        return Dict{String,Any}()
    end
end

_acc(extra) = (Int(extra["attempts_used"]), Float64(something(get(extra, "best_score", 0.0), 0.0)))

"""Dict test_name => (attempts_used, best_score) from the previous submission."""
function previous_accumulators(metadata)
    accs = Dict{String,Tuple{Int,Float64}}()
    rows = get(previous_results(metadata), "tests", nothing)
    rows isa AbstractVector || return accs
    for row in rows
        try
            number = string(get(row, "number", ""))
            is_precheck_row(row) && continue
            extra = get(row, "extra_data", nothing)
            extra isa AbstractDict || continue
            parts = get(extra, "parts", nothing)
            if parts isa AbstractDict
                for (name, a) in parts
                    a isa AbstractDict && haskey(a, "attempts_used") && (accs[string(name)] = _acc(a))
                end
            elseif haskey(extra, "attempts_used") && !isempty(number)
                accs[number] = _acc(extra)
            end
        catch
        end
    end
    return accs
end

# ── Questions (combine_questions) ───────────────────────────────────────────

function question_key(t)
    q = get(t, "question", nothing)
    (q === nothing || q == "") || return string(q)
    name = string(t["test_name"])
    m = match(r"^(.*\d)[ _.\-]?[A-Za-z]+$", name)
    return m === nothing ? name : String(m.captures[1])
end

question_title(key) = occursin(r"^\d+$", key) ? "Question $key" : key

function _target(t)
    get(t, "type", "variable") != "variable" && haskey(t, "function_name") && return t["function_name"]
    return get(t, "variable_name", t["test_name"])
end

"""
How a test is named to students, in Markdown: "Part b: `squares`" for test
names like 1b / Q2c, "`euler_step`" when the name is just the question
number, otherwise the test_name as the instructor wrote it.
"""
function part_label(t)
    name = string(t["test_name"])
    target = "`$(_target(t))`"
    m = match(r"^(.*\d)[ _.\-]?([A-Za-z]+)$", name)
    m === nothing || return "Part $(md_escape(m.captures[2])): $target"
    occursin(r"^[A-Za-z]*\d+$", name) && return target
    return md_escape(name)
end

function _part_heading(info)
    head = "- **$(part_label(info.cfg))**"
    desc = get(info.cfg, "description", nothing)
    desc === nothing || desc == "" || (head *= " — " * md_escape(desc))
    return head
end

"""
The failure message of a test as Markdown bullets: the error, the hint in
bold, a hint image as is, and anything longer (a traceback) as code.
"""
function _error_bullets(output, indent)
    message, hints, images = String[], String[], String[]
    for line in split(strip(string(something(output, ""))), '\n')
        if startswith(line, "Hint: ")
            push!(hints, line[length("Hint: ")+1:end])
        elseif startswith(line, "![")
            push!(images, line)
        else
            push!(message, rstrip(line))
        end
    end
    while !isempty(message) && isempty(strip(message[end]))
        pop!(message)
    end
    out = String[]
    items = [match(r"^\s*- (.*)$", l) for l in message[min(2, end + 1):end]]
    if length(message) == 1
        push!(out, "$indent$ARROW $(md_escape(message[1]))")
    elseif !isempty(message) && all(m -> m !== nothing, items)
        # "The following issues were found:" and a list: one line each.
        push!(out, "$indent$ARROW $(md_escape(message[1]))")
        append!(out, ["$indent$ARROW $(md_escape(m.captures[1]))" for m in items])
    elseif !isempty(message)
        push!(out, "$indent$ARROW Error:\n\n" * _code_block(message, indent) * "\n")
    end
    append!(out, ["$indent$ARROW **Hint:** $(md_escape(h))" for h in hints])
    append!(out, ["\n$indent$img\n" for img in images])
    return out
end

# Details under a part are lines starting with a triangle (not a second
# level of bullets), kept apart by Markdown hard line breaks.
const ARROW = "▸"
_lines(lines) = join(lines, "  \n")

function _attempts_text(info)
    info.limit == 0 && return nothing
    used = info.acc === nothing ? 0 : info.acc["attempts_used"]
    info.allow_tries && return "**Attempts:** $used (no limit)"
    shown = min(used, info.limit)
    return "**Attempts:** $shown/$(info.limit) ($(info.limit - shown) left)"
end

function _status_lines(info, pct)
    info.previously_correct && return ["Previously correct: your earlier credit is kept."]
    info.previous_partial && return ["Previously earned $(_fmt(info.best))/$(_fmt(info.max)): your earlier credit is kept."]
    info.late && return ["Correct, but submitted late: $pct% late penalty applied ($(_fmt(info.best))/$(_fmt(info.max)))."]
    return String[]
end

# ── The whole thing ─────────────────────────────────────────────────────────

"""
    finalize_results!(results, rubric, metadata, attempted; precheck=false)

Rewrite `results` (Gradescope results Dict whose rows are numbered by
test_name) in place: precheck, attempt limits, late penalties, combined
questions, total score and top-level notes. `attempted[test_name]` says
whether the student defined the name this time.

With the environment variable AUTOBUILDER_PLAIN=1 (the solution check in
`build`), questions are not combined and there are no late penalties.
"""
function finalize_results!(results, rubric, metadata, attempted; precheck=false)
    metadata isa AbstractDict || (metadata = Dict{String,Any}())
    plain = get(ENV, "AUTOBUILDER_PLAIN", "") == "1"
    suite = get(rubric, "test_suite", Any[])
    rows = Dict(string(r["number"]) => r for r in results["tests"])
    prev_accs = previous_accumulators(metadata)
    notes = String[]

    penalty, deadline = 0.0, nothing
    if precheck
        suite = [t for t in suite if _score_of(t) == 0]
        push!(notes, "**Precheck run:** only the precheck questions were checked. " *
                     "In order to receive any credit, turn `precheck = false`.")
    elseif !plain
        penalty, deadline = late_penalty(rubric, submission_time(metadata))
    end
    pct = _fmt(round(penalty * 100; digits=6))
    penalty > 0 && push!(notes, "**Late submission:** submitted after $deadline, so a $pct% late penalty " *
                                "applies to questions that were not already correct before.")

    track_all = !plain && get(rubric, "late_penalties", nothing) isa AbstractVector && !isempty(rubric["late_penalties"])
    infos = []
    for t in suite
        name = t["test_name"]
        row = get(rows, name, nothing)
        row === nothing && continue
        max_score = Float64(get(row, "max_score", 0))
        raw = Float64(get(row, "score", 0))
        passed = get(row, "status", "") == "passed"
        limit = Int(something(get(t, "attempts", 0), 0))
        allow_tries = get(t, "allow_tries", false) === true
        acc = nothing
        best = raw
        previously_correct = previous_partial = late = kept_full = maxed = false
        if !precheck && (limit > 0 || track_all)
            used, best = get(prev_accs, name, (0, 0.0))
            prev_best = best
            # The most it can still earn (full credit, or with the late penalty
            # included) is already earned: the part is done, and uses no more attempts.
            done = max_score > 0 && prev_best >= most_credit(max_score, penalty)
            if get(attempted, name, false) && !done
                within = allow_tries || limit == 0 || used < limit
                used += 1
                within && (best = max(best, round(raw * (1 - penalty); digits=6)))
            end
            best = min(best, max_score)
            row["score"] = best
            acc = Dict{String,Any}("attempts_used" => used, "best_score" => best)
            previously_correct = !passed && done
            kept_full = prev_best >= max_score
            previous_partial = !passed && 0 < prev_best && !done
            late = passed && penalty > 0 && prev_best < max_score && max_score > 0
            maxed = max_score <= 0 || best >= most_credit(max_score, penalty)
        end
        push!(infos, (cfg=t, row=row, limit=limit, allow_tries=allow_tries, acc=acc, passed=passed,
                      max=max_score, best=best, previously_correct=previously_correct,
                      previous_partial=previous_partial, late=late, kept_full=kept_full, maxed=maxed))
    end

    # Late, and every question has the most credit it can still get: say so
    # (later submissions are not graded, see locked_out_message).
    graded = [i for i in infos if i.acc !== nothing && i.max > 0]
    earned = sum(i.best for i in graded; init=0.0)
    possible = sum(i.max for i in graded; init=0.0)
    if penalty > 0 && !isempty(graded) && all(i -> i.maxed, graded) && earned < possible
        push!(notes, late_maximum_message(pct, earned, possible))
    end

    tests = (!plain && get(rubric, "combine_questions", false) === true) ?
        _combined_rows(infos, pct, precheck) : Any[_single_row(i, pct, precheck) for i in infos]

    if precheck
        # The graded rows of the previous submission, unchanged but hidden:
        # if this precheck submission becomes the active one, the score stays.
        prev_rows = get(previous_results(metadata), "tests", nothing)
        if prev_rows isa AbstractVector
            for row in prev_rows
                row isa AbstractDict || continue
                is_precheck_row(row) && continue
                hidden = Dict{String,Any}(row)
                hidden["visibility"] = "hidden"
                push!(tests, hidden)
            end
        end
    end

    results["tests"] = tests
    results["score"] = round(sum(Float64(something(get(r, "score", 0.0), 0.0)) for r in tests; init=0.0); digits=6)
    existing = md_text(get(results, "output", ""))   # plain notes (crash, file choice) from run.jl
    isempty(existing) || push!(notes, existing)
    results["output"] = join(notes, "\n\n")
    results["output_format"] = "md"
    return results
end

function _single_row(info, pct, precheck)
    row = info.row
    row["output_format"] = "md"
    precheck && (row["extra_data"] = Dict{String,Any}("precheck" => true))
    info.acc === nothing || (row["extra_data"] = info.acc)
    head = _status_lines(info, pct)
    if info.limit > 0
        used = info.acc["attempts_used"]
        shown = info.allow_tries ? used : min(used, info.limit)
        row["name"] = "(attempt: $shown/$(info.limit)) $(get(row, "name", info.cfg["test_name"]))"
        head = vcat(["**Locked score:** $(_fmt(info.best))/$(_fmt(info.max))"], head)
    end
    lines = ["$ARROW " * h for h in head]
    if info.previously_correct
        # Full credit from before: what is wrong now no longer matters.
        row["status"] = "passed"
    else
        append!(lines, _error_bullets(get(row, "output", ""), ""))
    end
    row["output"] = _lines(lines)
    return row
end

function _combined_rows(infos, pct, precheck)
    keys_in_order = String[]
    groups = Dict{String,Vector{Any}}()
    for info in infos
        k = question_key(info.cfg)
        haskey(groups, k) || (push!(keys_in_order, k); groups[k] = Any[])
        push!(groups[k], info)
    end

    rows = Any[]
    for key in keys_in_order
        parts = groups[key]
        wrong = [i for i in parts if !i.passed && !i.previously_correct]
        kept = [i for i in parts if i.previously_correct]
        late = [i for i in parts if i.late]

        # Title lines, each followed by one bullet per part; the details of a
        # part are triangle lines inside its bullet.
        blocks = String[]
        if !isempty(wrong)
            lines = ["**❌ Incorrect answers:**", ""]
            for i in wrong
                sub = ["  $ARROW " * s for s in _status_lines(i, pct)]
                append!(sub, _error_bullets(get(i.row, "output", ""), "  "))
                attempts = _attempts_text(i)
                attempts === nothing || push!(sub, "  $ARROW " * attempts)
                push!(lines, _lines(vcat([_part_heading(i)], sub)))
            end
            push!(blocks, join(lines, "\n"))
        end
        # Correct in an earlier submission (full credit, or the most possible
        # with the late penalty): done, whatever it says now.
        kept_full = [i for i in kept if i.kept_full]
        kept_late = [i for i in kept if !i.kept_full]
        if !isempty(kept_full)
            push!(blocks, join(vcat(["**⚠️ Previously correct, now incorrect (full credit kept):**", ""],
                                    [_part_heading(i) for i in kept_full]), "\n"))
        end
        if !isempty(kept_late)
            push!(blocks, join(vcat(["**⚠️ Previously correct, now incorrect (late credit kept):**", ""],
                                    ["$(_part_heading(i)) ($(_fmt(i.best))/$(_fmt(i.max)))" for i in kept_late]), "\n"))
        end
        if !isempty(late)
            push!(blocks, join(vcat(["**✅ Correct, with the $pct% late penalty:**", ""],
                                    ["$(_part_heading(i)) ($(_fmt(i.best))/$(_fmt(i.max)))" for i in late]), "\n"))
        end
        isempty(blocks) && push!(blocks, "**✅ All parts correct.**")

        row = Dict{String,Any}(
            "name" => question_title(key),
            "score" => round(sum(Float64(i.row["score"]) for i in parts); digits=6),
            "max_score" => sum(i.max for i in parts),
            "status" => isempty(wrong) ? "passed" : "failed",
            "output" => join(blocks, "\n\n"),
            "output_format" => "md",
            "visibility" => "visible",
        )
        accs = Dict{String,Any}(i.cfg["test_name"] => i.acc for i in parts if i.acc !== nothing)
        # No "number": Gradescope would show it in front of the name ("1) Question 1").
        isempty(accs) || (row["extra_data"] = Dict{String,Any}("parts" => accs))
        precheck && (row["extra_data"] = Dict{String,Any}("precheck" => true))
        push!(rows, row)
    end
    return rows
end
