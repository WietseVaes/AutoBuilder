# Expected: 25/25.
using Optim
using LinearAlgebra

method_name = "runge-kutta"
author      = "Leonhard Euler"

primes    = [2, 3, 5, 7, 11]
weights   = [0.1, 0.4, 0.3, 0.2]
grid      = range(0, 1; length=5)
dot_check = dot(weights, [1.0, 2.0, 3.0, 4.0])

A = [0.75 1.0; -1.0 -0.5]

function rk4_step(y0, dt)
    k1 = A * y0
    k2 = A * (y0 + dt / 2 * k1)
    k3 = A * (y0 + dt / 2 * k2)
    k4 = A * (y0 + dt * k3)
    return y0 + dt / 6 * (k1 + 2k2 + 2k3 + k4)
end

function rk4_solve(y0, dt, n)
    Y = zeros(2, n + 1)
    Y[:, 1] = y0
    for k in 1:n
        Y[:, k+1] = rk4_step(Y[:, k], dt)
    end
    return Y
end

f1     = x -> -(x - 2)^2 + 5
max_x1 = Optim.minimizer(optimize(x -> -f1(x), 0.0, 5.0))

f2     = x -> -x^4 + 3x^2
max_x2 = Optim.minimizer(optimize(x -> -f2(x), 0.0, 2.0))

total_y = sum(parse(Float64, split(l, ',')[2]) for l in readlines("data.csv")[2:end])
