import numpy as np

A = np.array([[0.75, 1.0], [-1.0, -0.5]])


def rk4_step(y0, dt):
    # (mistakenly implemented forward Euler instead of RK4)
    y0 = np.array(y0, dtype=float)
    return y0 + dt * (A @ y0)
