# Expected: 0/10 -- threshold 80 instead of 70: the passed column and the group averages are wrong.
using DataFrames
using Statistics

# A small "student grades" dataset, built directly in code.
names_  = ["Alice", "Bob", "Carla", "Dao", "Eve"]
scores_ = [88.0, 72.5, 95.0, 60.0, 81.5]

grades_df = DataFrame(name = names_, score = scores_)

# Derived column: pass = score >= 70
grades_df.passed = grades_df.score .>= 80

# Summary: average score per pass/fail group (false first, then true)
summary_df = combine(groupby(grades_df, :passed; sort=true), :score => mean => :average_score)
