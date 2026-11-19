# Mixed-deadline test: submit AFTER the deadline. Everything is right.
x0 = 1.0
h = 0.1

total = 55
squares = [1, 4, 9, 16, 25]
f(x) = x^2 + 1
euler_step(x, h) = x + h * (-x)
