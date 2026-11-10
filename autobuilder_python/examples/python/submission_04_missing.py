import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Many names not defined at all.
# Triggers hint_not_defined on everything missing.

greeting     = "bonjour from python"   # correct
# is_prime_7 missing
euler_number = float(np.exp(1.0))      # correct
# fibonacci missing
linspace_vec = np.linspace(0.0, 1.0, 5)  # correct
# rotation_90 missing

def square(x):
    return x ** 2                       # correct

# dot_product missing
# bounds missing
# plot_quadratic missing
# plot_bar missing
