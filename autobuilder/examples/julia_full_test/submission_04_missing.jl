using Plots

# Many names not defined at all.
# Triggers hint_not_defined on everything missing.

greeting     = "bonjour from julia"   # correct
# is_prime_7 missing
euler_number = exp(1.0)               # correct
# fibonacci missing
linspace_vec = collect(LinRange(0.0, 1.0, 5))  # correct
# rotation_90 missing

function square(x)
    return x ^ 2                      # correct
end
# dot_product missing
# bounds missing
# plot_quadratic missing
# plot_bar missing
