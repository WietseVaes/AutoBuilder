# NaN values.
# euler_number = NaN          -> hint_nans
# fibonacci has NaN           -> hint_nans

greeting     = "bonjour from julia"
is_prime_7   = true
euler_number = NaN
fibonacci    = [1.0, 1.0, 2.0, NaN, 5.0, 8.0, 13.0]  # NaN in position 4
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
