import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Wrong values — correct types and sizes, but numerically off.
# Triggers hint_tolerance on every test.

greeting     = "hello from python"               # wrong word
is_prime_7   = False                             # 7 IS prime
euler_number = 2.7                               # close but not exp(1)
fibonacci    = [1, 1, 2, 3, 5, 8, 12]           # last element wrong (12 vs 13)
linspace_vec = np.linspace(0.0, 1.0, 5) + 0.1   # shifted by 0.1
rotation_90  = np.array([[1.0, 0.0], [0.0, 1.0]])  # identity, not rotation

def square(x):
    return x ** 2 + 1                            # off by 1

def dot_product(a, b):
    return float(np.dot(a, b)) + 0.5            # off by 0.5

def bounds(v):
    v = np.asarray(v)
    return (float(np.min(v)) - 1, float(np.max(v)) + 1)  # bounds too wide

def plot_quadratic():
    x = np.linspace(0.0, 2.0, 21)
    y = x ** 2 + 1.0                            # y-shifted by 1
    fig, ax = plt.subplots()
    ax.plot(x, y, label="y = x²")
    ax.set_xlabel("x")
    ax.set_ylabel("x²")
    ax.set_title("Quadratic")
    ax.legend()
    return ax

def plot_bar():
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 5.0]    # last bar 5.0 instead of 4.0
    fig, ax = plt.subplots()
    ax.bar(categories, heights, label="")
    ax.set_xlabel("Category")
    ax.set_ylabel("Value")
    ax.set_title("Bar Chart")
    return ax
