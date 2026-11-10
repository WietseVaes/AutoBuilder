import pandas as pd

df = pd.read_csv("data.csv")
total_y = float(df["y"].sum())
