# Expected: 0/8 -- returns a single number instead of the [R, J] vector.
A = [0.75 1.0; -1.0 -0.5]

function rk4_step(y0, dt)
    k1 = A * y0
    k2 = A * (y0 + dt / 2 * k1)
    k3 = A * (y0 + dt / 2 * k2)
    k4 = A * (y0 + dt * k3)
    return sum(y0 + dt / 6 * (k1 + 2k2 + 2k3 + k4))
end
