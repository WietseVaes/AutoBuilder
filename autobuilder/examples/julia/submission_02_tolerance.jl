using Plots

# Wrong values — correct types and sizes, but numerically off.
# Triggers hint_tolerance on every test.

greeting     = "hello from julia"               # wrong word
is_prime_7   = false                            # 7 IS prime
euler_number = 2.7                              # close but not exp(1)
fibonacci    = [1, 1, 2, 3, 5, 8, 12]          # last element wrong (12 vs 13)
linspace_vec = collect(LinRange(0.0, 1.0, 5)) .+ 0.1   # shifted by 0.1
rotation_90  = [1.0 0.0; 0.0 1.0]              # identity, not rotation

function square(x)
    return x ^ 2 + 1                           # off by 1
end

function dot_product(a, b)
    return sum(a .* b) + 0.5                   # off by 0.5
end

function bounds(v)
    return (minimum(v) - 1, maximum(v) + 1)   # bounds too wide
end

function plot_quadratic()
    x = collect(0.0:0.1:2.0)
    y = x .^ 2 .+ 1.0                         # y-shifted by 1
    return plot(x, y, xlabel="x", ylabel="x²", title="Quadratic", label="y = x²")
end

function plot_bar()
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 5.0]   # last bar 5.0 instead of 4.0
    return bar(categories, heights,
               xlabel="Category", ylabel="Value", title="Bar Chart", label="")
end
