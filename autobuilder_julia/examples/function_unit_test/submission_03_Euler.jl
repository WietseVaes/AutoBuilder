# Expected: 2/8 -- forward Euler instead of RK4 (only the equilibrium test B3 passes).
A = [0.75 1.0; -1.0 -0.5]

rk4_step(y0, dt) = y0 + dt * (A * y0)
