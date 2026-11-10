import numpy as np
from scipy.optimize import fmin

# ── Strings (fixed) ───────────────────────────────────────────────────────────
method_name = "runge-kutta"
author      = "Leonhard Euler"

# ── Plain list (fixed) ───────────────────────────────────────────────────────
primes = [2, 3, 5, 7, 11]

# ── numpy arrays (all fixed) ─────────────────────────────────────────────────
weights   = np.array([0.1, 0.4, 0.3, 0.2])
grid      = np.linspace(0, 1, 5)                      # fixed
dot_check = float(np.dot(weights, np.array([1.0, 2.0, 3.0, 4.0])))

# ── RK4 step (still wrong: missing the /6 denominator) ───────────────────────
A = np.array([[0.75, 1.0],
              [-1.0, -0.5]])

def rk4_step(y0, dt):
    y0 = np.array(y0, dtype=float)
    k1 = A @ y0
    k2 = A @ (y0 + dt / 2 * k1)
    k3 = A @ (y0 + dt / 2 * k2)
    k4 = A @ (y0 + dt * k3)
    return y0 + dt * (k1 + 2 * k2 + 2 * k3 + k4)    # missing /6

# ── Maximisation (still wrong start point for f2) ────────────────────────────
f1     = lambda x: -(x - 2)**2 + 5
max_x1 = fmin(lambda x: -f1(x), 0.0, disp=False)[0]  # fixed

f2     = lambda x: -x**4 + 3 * x**2
max_x2 = fmin(lambda x: -f2(x), 0.0, disp=False)[0]  # x0=0 is a local max too -> 0.0
