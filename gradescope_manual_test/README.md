# Manual Gradescope test: precheck, combine_questions, late penalties

One small assignment (9 points), the same in Python and Julia, to try the new
rubric options on Gradescope by hand.

| Question | Tests | Points | Attempts |
|----------|-------|--------|----------|
| Precheck | `x0` = 1.0, `h` = 0.1 (given values) | 0 | -- |
| Question 1 | `total` = 1+...+10, `squares` = squares of 1..5 | 1 + 2 | 3 each |
| Question 2 | `f(2)`, `f(-1)` for f(x) = x^2 + 1 | 2 + 1 | -- |
| Question 3 | `euler_step(1.0, 0.1)` | 3 | 5 |

The rubric sets `"precheck": true`, `"combine_questions": true`, `"grade_until_crash": true`
and `"late_penalties"`. The two "Precheck" tests use `"question": "Precheck"`; the
other questions come from the test names (`1a`, `1b` -> Question 1).

## Zips

| File | Late penalties |
|------|----------------|
| `python/autograder_on_time.zip` | 10% after Nov 30, 2026 11:59 PM PST, 50% after Dec 2, 2026 11:59 PM PST, so nothing is late yet |
| `python/autograder_already_late.zip` | 20% after Nov 15, 2026 11:59 PM PST, so every submission is late |
| `python/autograder_deadline_today.zip` | 20% after **Nov 16, 2026 5:00 PM PST**: submit before and after it (see the last section) |
| `julia/autograder_*.zip` | as above |

Use one Gradescope **Programming Assignment** per zip, and turn on "Allow resubmission"
(otherwise attempts and earlier scores are not carried over). Zips are not in git; rebuild with

```bash
cd gradescope_manual_test/python
autobuilder build rubric.json solution.py --output autograder_on_time.zip
autobuilder build rubric_already_late.json solution.py --output autograder_already_late.zip
autobuilder build rubric_deadline_today.json solution.py --output autograder_deadline_today.zip

cd ../julia
julia ../../autobuilder_julia/bin/autobuilder.jl build rubric.json solution.jl --output autograder_on_time.zip
julia ../../autobuilder_julia/bin/autobuilder.jl build rubric_already_late.json solution.jl --output autograder_already_late.zip
julia ../../autobuilder_julia/bin/autobuilder.jl build rubric_deadline_today.json solution.jl --output autograder_deadline_today.zip
```

All output is Markdown: bold title lines (**❌ Incorrect answers:**, **⚠️ Previously correct, now incorrect
(full credit kept):**, **✅ Correct, with the 20% late penalty:**, **✅ All parts correct.**), one bullet
per part ("**Part b: `squares`** — squares holds the squares of 1, ..., 5"), and under it ▸ lines with
the error, the **Hint:** and the **Attempts:**.

## Submit in this order (`submissions/`), as the same student

| # | File | On-time zip | Already-late zip |
|---|------|-------------|------------------|
| 1 | `01_precheck_ok` | 0. Note at the top: "**Precheck run:** ... In order to receive any credit, turn `precheck = False`." Only the Precheck question shows: "✅ All parts correct." | same |
| 2 | `02_precheck_mistake` | 0. Precheck question, under ❌ Incorrect answers: "Part b: `h`" with its error and hint. Nothing about total/squares/f, which are wrong too | same |
| 3 | `03_partial` | **1/9**. Q1 lists "Part b: `squares`" (Attempts: 1/3 (2 left), so the two precheck runs used no attempts); Q2 lists both `f` parts; Q3 lists `euler_step` not defined | **0.8**. Note "**Late submission:** submitted after Nov 15, 2026 at 11:59 PM PST, so a 20% late penalty applies...". Q1 also has "✅ Correct, with the 20% late penalty: Part a: `total` ... (0.8/1)" |
| 4 | `04_mixed` | **6/9**. Q1 (3/3): "⚠️ Previously correct, now incorrect (full credit kept): Part a: `total`" (it is wrong now, but was right in 03, so no error and no attempt used); Q2: "✅ All parts correct." | **4.8**. Q1: "⚠️ Previously correct, now incorrect (late credit kept): Part a: `total` ... (0.8/1)"; squares and f with 20% off |
| 5 | `05_all_correct` | **9/9**, every question "✅ All parts correct." | **7.2** (everything 20% off), plus at the top: "✅ **All questions are correct.** With the 20% late penalty included, this is the most credit you can receive (7.2/9). Further submissions will not be graded." |
| 6 | `06_after_everything` | **9**. Not graded again: "✅ **All questions have been answered correctly.** No further submissions are needed." | **7.2**. Not graded again: the same "most credit you can receive (7.2/9)" message |

Also worth a try:
- After 04, submit `01_precheck_ok` again: the precheck run shows only the Precheck question,
  but the score stays (earlier results are carried forward, hidden).
- Regrade all submissions: the late penalty is based on when each was submitted, so nothing changes.
- The Python files use `Precheck = True`; the Julia files use `precheck = true`. Any
  capitalisation of the name works.

## Question 1 on time, Questions 2 and 3 late (`autograder_deadline_today.zip`)

The deadline in `rubric_deadline_today.json` is **Nov 16, 2026 at 5:00 PM PST** (20% off after it).
To test on another day, change `"after"` and rebuild.

| # | File | When | Expected |
|---|------|------|----------|
| 1 | `07_only_question_1` | before 5:00 PM | **3/9**. Q1 "✅ All parts correct."; Q2 and Q3 under ❌ Incorrect answers (not defined) |
| 2 | `08_rest_after_deadline` | after 5:00 PM | **7.8/9**. Note "**Late submission:** submitted after Nov 16, 2026 at 5:00 PM PST ...". Q1 3/3 "✅ All parts correct." (no penalty: it was correct on time); Q2 2.4/3 and Q3 2.4/3 under "✅ Correct, with the 20% late penalty". At the top: "this is the most credit you can receive (7.8/9)" — 3 + 0.8 × 6, not 0.8 × 9 = 7.2 |
| 3 | `06_after_everything` | any time later | **7.8**. Not graded again: the same "most credit you can receive (7.8/9)" message |
