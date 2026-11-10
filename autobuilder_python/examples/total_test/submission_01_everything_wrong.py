import numpy as np
from scipy.optimize import fmin

# ── Strings ───────────────────────────────────────────────────────────────────
method_name = "Runge-Kutta"          # wrong capitalisation
author      = "euler"                # wrong capitalisation and missing first name

# ── Plain list ────────────────────────────────────────────────────────────────
primes = [1, 2, 3, 5, 7]            # 1 is not prime

# ── numpy arrays ──────────────────────────────────────────────────────────────
weights   = np.array([0.25, 0.25, 0.25, 0.25])   # uniform, not correct
grid      = np.linspace(0, 2, 5)                  # wrong range (0 to 2 instead of 0 to 1)
dot_check = np.dot(weights, np.array([1, 2, 3, 4]))  # dot with wrong weights -> 2.5

# ── RK4 step (using forward Euler instead) ───────────────────────────────────
A = np.array([[0.75, 1.0],
              [-1.0, -0.5]])

def rk4_step(y0, dt):
    y0 = np.array(y0, dtype=float)
    return y0 + dt * (A @ y0)       # forward Euler, not RK4

# ── Maximisation (minimising instead of maximising) ───────────────────────────
f1     = lambda x: -(x - 2)**2 + 5
max_x1 = fmin(lambda x: f1(x), 0.0, disp=False)[0]   # minimises, doesn't negate

f2     = lambda x: -x**4 + 3 * x**2
max_x2 = fmin(lambda x: f2(x), 0.0, disp=False)[0]   # same mistake
