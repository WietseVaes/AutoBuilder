import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# NaN values + wrong plot axis labels.
# euler_number = NaN         -> hint_nans
# fibonacci has NaN          -> hint_nans
# plot labels wrong          -> hint_tolerance (plot tests)

greeting     = "bonjour from python"
is_prime_7   = True
euler_number = float("nan")
fibonacci    = [1.0, 1.0, 2.0, float("nan"), 5.0, 8.0, 13.0]  # NaN in position 4
linspace_vec = np.linspace(0.0, 1.0, 5)
rotation_90  = np.array([[0.0, -1.0], [1.0, 0.0]])

def square(x):
    return x ** 2

def dot_product(a, b):
    return float(np.dot(a, b))

def bounds(v):
    v = np.asarray(v)
    return (float(np.min(v)), float(np.max(v)))

def plot_quadratic():
    x = np.linspace(0.0, 2.0, 21)
    y = x ** 2
    fig, ax = plt.subplots()
    ax.plot(x, y, label="data")
    # Wrong labels: "time"/"distance"/"My Plot" instead of "x"/"x²"/"Quadratic"
    ax.set_xlabel("time")
    ax.set_ylabel("distance")
    ax.set_title("My Plot")
    ax.legend()
    return ax

def plot_bar():
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 4.0]
    fig, ax = plt.subplots()
    ax.bar(categories, heights, label="")
    # Wrong labels: generic names instead of correct ones
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("histogram")
    return ax
