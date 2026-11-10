# All correct — should score 13/13.

greeting     = "bonjour from julia"
is_prime_7   = true
euler_number = exp(1.0)
fibonacci    = [1, 1, 2, 3, 5, 8, 13]
linspace_vec = collect(LinRange(0.0, 1.0, 5))
rotation_90  = [0.0 -1.0; 1.0 0.0]

function square(x)
    return x ^ 2
end

function dot_product(a, b)
    return sum(a .* b)
end

function bounds(v)
    return (minimum(v), maximum(v))
end
