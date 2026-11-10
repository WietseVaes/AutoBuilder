import numpy as np

# ── RK4 test inputs ───────────────────────────────────────────────────────────
rk4_y0_1 = np.array([-1.0, 4.0])
rk4_dt_1 = 0.1

rk4_y0_2 = np.array([2.0, -3.0])
rk4_dt_2 = 0.05

# ── Expected values for string/list/array checks ─────────────────────────────
# (Using $-references for these keeps the rubric clean and easy to update.)
expected_primes    = [2, 3, 5, 7, 11]
expected_weights   = np.array([0.1, 0.4, 0.3, 0.2])
expected_grid      = np.linspace(0, 1, 5)
expected_dot_check = float(np.dot(np.array([0.1, 0.4, 0.3, 0.2]),
                                   np.array([1.0, 2.0, 3.0, 4.0])))
