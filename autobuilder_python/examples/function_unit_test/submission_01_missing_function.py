import numpy as np

A = np.array([[0.75, 1.0], [-1.0, -0.5]])


# Oops -- named the function `rk4` instead of `rk4_step`
def rk4(y0, dt):
    y0 = np.array(y0, dtype=float)
    k1 = A @ y0
    k2 = A @ (y0 + dt / 2 * k1)
    k3 = A @ (y0 + dt / 2 * k2)
    k4 = A @ (y0 + dt * k3)
    return y0 + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
