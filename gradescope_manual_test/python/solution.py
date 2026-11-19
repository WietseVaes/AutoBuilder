x0 = 1.0
h = 0.1

total = sum(range(1, 11))
squares = [k ** 2 for k in range(1, 6)]


def f(x):
    return x ** 2 + 1


def euler_step(x, h):
    return x + h * (-x)
