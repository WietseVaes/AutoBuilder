import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Wrong types and wrong sizes.
# greeting: number instead of string              -> hint_wrong_type
# is_prime_7: string instead of bool             -> hint_wrong_type
# euler_number: 1-element array not scalar       -> hint_wrong_size
# fibonacci: only 5 elements not 7              -> hint_wrong_size
# linspace_vec: 10 elements not 5               -> hint_wrong_size
# rotation_90: flat 1D array not 2x2 matrix     -> hint_wrong_size
# square: returns array not scalar              -> hint_wrong_size
# dot_product: returns element-wise array       -> hint_wrong_size
# plot_quadratic: two lines not one             -> hint_wrong_size (n_lines)
# plot_bar: three bars not five                 -> hint_wrong_size (n_bars)

greeting     = 42
is_prime_7   = "yes"
euler_number = np.array([np.exp(1.0)])           # wrapped in array
fibonacci    = [1, 1, 2, 3, 5]                  # only first 5
linspace_vec = np.linspace(0.0, 1.0, 10)        # 10 points not 5
rotation_90  = np.array([0.0, -1.0, 1.0, 0.0])  # flat 1D, not 2x2

def square(x):
    return np.array([x ** 2])                   # wrapped in array

def dot_product(a, b):
    return np.array(a) * np.array(b)            # element-wise, not scalar

def bounds(v):
    v = np.asarray(v)
    return (float(np.min(v)), float(np.max(v))) # correct

def plot_quadratic():
    x  = np.linspace(0.0, 2.0, 21)
    y1 = x ** 2
    y2 = x ** 3
    fig, ax = plt.subplots()
    ax.plot(x, y1, label="y = x²")
    ax.plot(x, y2, label="y = x³")             # two lines instead of one
    ax.set_xlabel("x")
    ax.set_ylabel("x²")
    ax.set_title("Quadratic")
    ax.legend()
    return ax

def plot_bar():
    categories = [1, 2, 3]                     # three bars instead of five
    heights    = [2.0, 5.0, 3.0]
    fig, ax = plt.subplots()
    ax.bar(categories, heights, label="")
    ax.set_xlabel("Category")
    ax.set_ylabel("Value")
    ax.set_title("Bar Chart")
    return ax
