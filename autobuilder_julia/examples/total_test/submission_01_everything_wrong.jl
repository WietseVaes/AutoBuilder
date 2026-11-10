# Expected: 0/25 -- every test fails, each for a different reason.
using Optim
using LinearAlgebra

# ── Strings ───────────────────────────────────────────────────────────────────
method_name = "Runge-Kutta"          # wrong capitalisation
author      = "euler"                # wrong capitalisation, missing first name

# ── Vectors ───────────────────────────────────────────────────────────────────
primes    = [1, 2, 3, 5, 7]          # 1 is not prime
weights   = [0.25, 0.25, 0.25, 0.25] # uniform, not correct
grid      = range(0, 2; length=5)    # wrong range (0 to 2 instead of 0 to 1)
dot_check = weights .* [1, 2, 3, 4]  # elementwise product: a vector, not a number

# ── RK4 (forward Euler instead) ───────────────────────────────────────────────
A = [0.75 1.0; -1.0 -0.5]

rk4_step(y0, dt) = y0 + dt * (A * y0)   # forward Euler, not RK4

# Returns the transpose: (n+1)×2 instead of 2×(n+1)
function rk4_solve(y0, dt, n)
    Y = zeros(n + 1, 2)
    Y[1, :] = y0
    for k in 1:n
        Y[k+1, :] = rk4_step(Y[k, :], dt)
    end
    return Y
end

# ── Maximisation (minimises instead of maximising) ────────────────────────────
f1     = x -> -(x - 2)^2 + 5
max_x1 = Optim.minimizer(optimize(f1, 0.0, 5.0))   # forgot the minus sign

f2     = x -> -x^4 + 3x^2
max_x2 = [Optim.minimizer(optimize(x -> -f2(x), 0.0, 2.0))]   # wrapped in a vector

# ── Data file ─────────────────────────────────────────────────────────────────
total_y = NaN   # never got round to it
