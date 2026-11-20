import numpy as np


# Question 1: root finding with our own bisection
def bisection(f, a, b, tol=1e-12):
    fa = f(a)
    while b - a > tol:
        m = (a + b) / 2
        fm = f(m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
    return (a + b) / 2


root = bisection(lambda x: x**3 - 2 * x - 5, 2.0, 3.0)


def cube_root(c):
    return bisection(lambda x: x**3 - c, 0.0, max(1.0, c))


# Question 2: linear systems with our own Gaussian elimination
def solve_system(A, b):
    A = np.array(A, dtype=float)
    b = np.array(b, dtype=float)
    n = len(b)
    for k in range(n):
        p = k + np.argmax(np.abs(A[k:, k]))      # partial pivoting
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
x_sol = solve_system(A3, b3)
