# Helper file, include()d by homework.jl.
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
