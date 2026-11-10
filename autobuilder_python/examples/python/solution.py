import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Variables ─────────────────────────────────────────────────────────────────

greeting     = "bonjour from python"
is_prime_7   = True
euler_number = float(np.exp(1.0))
fibonacci    = [1, 1, 2, 3, 5, 8, 13]
linspace_vec = np.linspace(0.0, 1.0, 5)
rotation_90  = np.array([[0.0, -1.0], [1.0, 0.0]])

# ── Functions ─────────────────────────────────────────────────────────────────

def square(x):
    return x ** 2

def dot_product(a, b):
    return float(np.dot(a, b))

def bounds(v):
    v = np.asarray(v)
    return (float(np.min(v)), float(np.max(v)))

# ── Plots ─────────────────────────────────────────────────────────────────────

def plot_quadratic():
    x = np.linspace(0.0, 2.0, 21)
    y = x ** 2
    fig, ax = plt.subplots()
    ax.plot(x, y, label="y = x²")
    ax.set_xlabel("x")
    ax.set_ylabel("x²")
    ax.set_title("Quadratic")
    ax.legend()
    return ax

def plot_bar():
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 4.0]
    fig, ax = plt.subplots()
    ax.bar(categories, heights, label="")
    ax.set_xlabel("Category")
    ax.set_ylabel("Value")
    ax.set_title("Bar Chart")
    return ax
