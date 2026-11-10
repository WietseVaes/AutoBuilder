# Expected: 10/25 -- strings, primes, weights, dot_check and total_y fixed.
using Optim
using LinearAlgebra

method_name = "runge-kutta"
author      = "Leonhard Euler"

primes    = [2, 3, 5, 7, 11]
weights   = [0.1, 0.4, 0.3, 0.2]
grid      = range(0, 1; length=6)          # wrong: 6 points instead of 5
dot_check = dot(weights, [1, 2, 3, 4])

A = [0.75 1.0; -1.0 -0.5]

rk4_step(y0, dt) = y0 + dt * (A * y0)      # still forward Euler

function rk4_solve(y0, dt, n)              # right shape, but uses the Euler step
    Y = zeros(2, n + 1)
    Y[:, 1] = y0
    for k in 1:n
        Y[:, k+1] = rk4_step(Y[:, k], dt)
    end
    return Y
end

f1     = x -> -(x - 2)^2 + 5
max_x1 = Optim.minimizer(optimize(f1, 0.0, 5.0))           # still minimising

f2     = x -> -x^4 + 3x^2
max_x2 = Optim.minimizer(optimize(x -> -f2(x), 0.0, 1.0))  # interval too small

total_y = sum(parse(Float64, split(l, ',')[2]) for l in readlines("data.csv")[2:end])
