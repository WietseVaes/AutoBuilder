import numpy as np
from scipy.optimize import fmin

# ── Strings ───────────────────────────────────────────────────────────────────
method_name = "runge-kutta"
author      = "Leonhard Euler"

# ── Plain list ────────────────────────────────────────────────────────────────
primes = [2, 3, 5, 7, 11]

# ── numpy arrays ──────────────────────────────────────────────────────────────
weights   = np.array([0.1, 0.4, 0.3, 0.2])
grid      = np.linspace(0, 1, 5)
dot_check = float(np.dot(weights, np.array([1.0, 2.0, 3.0, 4.0])))

# ── RK4 step function ─────────────────────────────────────────────────────────
A = np.array([[0.75, 1.0],
              [-1.0, -0.5]])

def rk4_step(y0, dt):
    """One RK4 step for y' = A y."""
    y0 = np.array(y0, dtype=float)
    k1 = A @ y0
    k2 = A @ (y0 + dt / 2 * k1)
    k3 = A @ (y0 + dt / 2 * k2)
    k4 = A @ (y0 + dt * k3)
    return y0 + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

# ── Maximisation function ─────────────────────────────────────────────────────
def find_max(f, x0):
    """Find the maximiser of f by minimising -f from starting point x0.
    Returns the scalar x* that maximises f."""
    result = fmin(lambda x: -f(x), x0, disp=False)
    return float(result[0])

# ── Maximisation results (tested as variables so f can be defined here) ───────
f1     = lambda x: -(x - 2)**2 + 5       # max at x = 2
max_x1 = find_max(f1, 0.0)

f2     = lambda x: -x**4 + 3 * x**2      # max at x = sqrt(1.5)
max_x2 = find_max(f2, 1.0)
