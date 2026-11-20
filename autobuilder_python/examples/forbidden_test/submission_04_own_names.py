# Own functions with library names, and renamed library functions.
# Expected: 4/8 (1b and 2b flagged).
import numpy as np
import scipy.optimize
import scipy.linalg


def brentq(f, a, b):                       # the student's OWN brentq (a bisection): fine
    while b - a > 1e-12:
        m = (a + b) / 2
        if f(a) * f(m) <= 0:
            b = m
        else:
            a = m
    return (a + b) / 2


root = brentq(lambda x: x**3 - 2 * x - 5, 2.0, 3.0)      # 1a: uses their own brentq, fine

my_method = scipy.optimize.newton          # renaming the library function does not hide it


def cube_root(c):
    return my_method(lambda x: x**3 - c, 1.0)             # 1b: newton, via my_method


def solve_system(A, b):                    # 2a: own elimination, fine
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
x_sol = scipy.linalg.solve(A3, b3)        # 2b: "solve" matches scipy's solve too
