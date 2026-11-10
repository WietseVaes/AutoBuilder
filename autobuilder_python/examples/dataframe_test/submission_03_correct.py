import pandas as pd
import numpy as np

names  = ["Alice", "Bob", "Carla", "Dao", "Eve"]
scores = np.array([88.0, 72.5, 95.0, 60.0, 81.5])

grades_df = pd.DataFrame({
    "name": names,
    "score": scores,
})
grades_df["passed"] = grades_df["score"] >= 70

summary_df = grades_df.groupby("passed")["score"].mean().reset_index()
summary_df.columns = ["passed", "average_score"]
