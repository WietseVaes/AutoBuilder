x0 = 1.0
h = 0.1

total = sum(1:10)
squares = [k^2 for k in 1:5]

f(x) = x^2 + 1

euler_step(x, h) = x + h * (-x)
