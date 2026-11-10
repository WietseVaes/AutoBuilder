import pandas as pd
import numpy as np

# A small "student grades" dataset, built directly in code.
names  = ["Alice", "Bob", "Carla", "Dao", "Eve"]
scores = np.array([88.0, 72.5, 95.0, 60.0, 81.5])

grades_df = pd.DataFrame({
    "name": names,
    "score": scores,
})

# Derived DataFrame: add a pass/fail column (pass = score >= 70)
grades_df["passed"] = grades_df["score"] >= 70

# Summary DataFrame: average score per pass/fail group
summary_df = grades_df.groupby("passed")["score"].mean().reset_index()
summary_df.columns = ["passed", "average_score"]
