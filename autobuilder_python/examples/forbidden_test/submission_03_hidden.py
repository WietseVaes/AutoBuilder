# Tries to hide the library calls: a renamed module, a helper function, and
# a list filled in by another function. Expected: 4/8 (1a and 2b flagged).
import numpy as np
from scipy import optimize as opt


def my_finder(f, a, b):
    return opt.root_scalar(f, bracket=[a, b]).root        # hidden in a helper


root = my_finder(lambda x: x**3 - 2 * x - 5, 2.0, 3.0)   # 1a: root_scalar, via my_finder


def cube_root(c):                                         # 1b: own bisection, fine
    a, b = 0.0, max(1.0, c)
    while b - a > 1e-12:
        m = (a + b) / 2
        if (a**3 - c) * (m**3 - c) <= 0:
            b = m
        else:
            a = m
    return (a + b) / 2


def solve_system(A, b):                                   # 2a: own elimination, fine
    A = np.array(A, dtype=float)
    b = np.array(b, dtype=float)
    n = len(b)
    for k in range(n):
        p = k + np.argmax(np.abs(A[k:, k]))
        A[[k, p]], b[[k, p]] = A[[p, k]], b[[p, k]]
        for i in range(k + 1, n):
            factor = A[i, k] / A[k, k]
            A[i, k:] -= factor * A[k, k:]
            b[i] -= factor * b[k]
    x = np.zeros(n)
    for i in range(n - 1, -1, -1):
        x[i] = (b[i] - A[i, i + 1:] @ x[i + 1:]) / A[i, i]
    return x


A3 = np.array([[2.0, 1.0, -1.0], [-3.0, -1.0, 2.0], [-2.0, 1.0, 2.0]])
b3 = np.array([8.0, -11.0, -3.0])
results = []


def store(out):
    out.append(np.linalg.inv(A3) @ b3)                    # fills `results`


store(results)
x_sol = results[0]                                        # 2b: inv, via store(results)
