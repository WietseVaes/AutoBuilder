import pandas as pd

# Regression test for reading extra_files via a relative path: this must
# work whether "autobuilder build"/"grade" is invoked from this folder or
# from anywhere else (Gradescope always runs from /autograder/source).
df = pd.read_csv("data.csv")
total_y = float(df["y"].sum())
