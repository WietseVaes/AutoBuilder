using Optim          # listed in rubric.json "requirements"
using LinearAlgebra  # standard library: always available

# ── Strings ───────────────────────────────────────────────────────────────────
method_name = "runge-kutta"
author      = "Leonhard Euler"

# ── Vectors ───────────────────────────────────────────────────────────────────
primes    = [2, 3, 5, 7, 11]
weights   = [0.1, 0.4, 0.3, 0.2]
grid      = range(0, 1; length=5)
dot_check = dot(weights, [1.0, 2.0, 3.0, 4.0])

# ── RK4 for y' = A y ──────────────────────────────────────────────────────────
A = [0.75 1.0; -1.0 -0.5]

function rk4_step(y0, dt)
    k1 = A * y0
    k2 = A * (y0 + dt / 2 * k1)
    k3 = A * (y0 + dt / 2 * k2)
    k4 = A * (y0 + dt * k3)
    return y0 + dt / 6 * (k1 + 2k2 + 2k3 + k4)
end

# n RK4 steps; column k+1 holds the state after k steps (a 2×(n+1) matrix).
function rk4_solve(y0, dt, n)
    Y = zeros(2, n + 1)
    Y[:, 1] = y0
    for k in 1:n
        Y[:, k+1] = rk4_step(Y[:, k], dt)
    end
    return Y
end

# ── Maximisation with Optim (Brent's method on an interval) ───────────────────
find_max(f, lo, hi) = Optim.minimizer(optimize(x -> -f(x), lo, hi))

f1     = x -> -(x - 2)^2 + 5          # max at x = 2
max_x1 = find_max(f1, 0.0, 5.0)

f2     = x -> -x^4 + 3x^2             # max at x = sqrt(1.5) ≈ 1.2247
max_x2 = find_max(f2, 0.0, 2.0)

# ── Data file (listed in rubric.json "extra_files") ───────────────────────────
rows    = [split(line, ',') for line in readlines("data.csv")[2:end]]
total_y = sum(parse(Float64, r[2]) for r in rows)
