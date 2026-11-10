# Values for the "$name" references in rubric.json (pass --inputs test_inputs.jl).

# ── RK4 test inputs ───────────────────────────────────────────────────────────
rk4_y0_1 = [-1.0, 4.0]
rk4_dt_1 = 0.1

rk4_y0_2 = [2.0, -3.0]
rk4_dt_2 = 0.05

# ── Expected values for string/list/array checks ──────────────────────────────
expected_primes    = [2, 3, 5, 7, 11]
expected_weights   = [0.1, 0.4, 0.3, 0.2]
expected_grid      = collect(range(0, 1; length=5))
expected_dot_check = sum([0.1, 0.4, 0.3, 0.2] .* [1.0, 2.0, 3.0, 4.0])
