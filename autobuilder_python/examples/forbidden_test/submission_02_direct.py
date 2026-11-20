# Uses the library functions directly everywhere. All values are right,
# but every test is flagged. Expected: 0/8.
import numpy as np
from scipy.optimize import brentq, fsolve

root = brentq(lambda x: x**3 - 2 * x - 5, 2.0, 3.0)        # 1a: brentq


def cube_root(c):
    return fsolve(lambda x: x**3 - c, 1.0)[0]             # 1b: fsolve


def solve_system(A, b):
    return np.linalg.solve(A, b)                          # 2a: solve


A3 = np.array([[2.0, 1.0, -1.0], [-3.0, -1.0, 2.0], [-2.0, 1.0, 2.0]])
b3 = np.array([8.0, -11.0, -3.0])
x_sol = solve_system(A3, b3)                              # 2b: solve, through solve_system
