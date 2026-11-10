import numpy as np
from scipy.optimize import fmin

# ── Strings (fixed) ───────────────────────────────────────────────────────────
method_name = "runge-kutta"
author      = "Leonhard Euler"

# ── Plain list (fixed) ───────────────────────────────────────────────────────
primes = [2, 3, 5, 7, 11]

# ── numpy arrays (still wrong) ───────────────────────────────────────────────
weights   = np.array([0.1, 0.4, 0.3, 0.2])           # correct now
grid      = np.linspace(0, 1, 6)                      # wrong: 6 points instead of 5
dot_check = np.dot(weights, np.array([1, 2, 3, 4]))  # correct

# ── RK4 step (still forward Euler) ───────────────────────────────────────────
A = np.array([[0.75, 1.0],
              [-1.0, -0.5]])

def rk4_step(y0, dt):
    y0 = np.array(y0, dtype=float)
    return y0 + dt * (A @ y0)       # still Euler

# ── Maximisation (still minimising) ──────────────────────────────────────────
f1     = lambda x: -(x - 2)**2 + 5
max_x1 = fmin(lambda x: f1(x), 0.0, disp=False)[0]

f2     = lambda x: -x**4 + 3 * x**2
max_x2 = fmin(lambda x: f2(x), 0.0, disp=False)[0]
