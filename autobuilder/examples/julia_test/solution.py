import numpy as np

# Same problem as the rk4 example, kept deliberately simple so it's easy
# to verify a Julia submission against -- strings, a scalar, an array, and
# a function, no DataFrames or plots (those aren't Julia-compatible yet).

greeting = "hello from autobuilder"

scale_factor = 2.5

squares = np.array([1.0, 4.0, 9.0, 16.0, 25.0])  # [1^2, 2^2, 3^2, 4^2, 5^2]


def add_one(x):
    return x + 1.0
