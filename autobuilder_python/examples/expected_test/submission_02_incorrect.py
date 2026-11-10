import numpy as np

reviews = np.array([
    [8.5, 7.64, 7.65],
    [3.0, 3.5, 3.61],
    [4.5, 4.0, 4.5],
    [3.0, 3.0, 3.06],
])

# Forgot to divide by the number of categories
final_scores = reviews.sum(axis=1)
