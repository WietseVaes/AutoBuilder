using Plots

# All correct — should score 19/19.

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

function plot_quadratic()
    x = collect(0.0:0.1:2.0)
    y = x .^ 2
    return plot(x, y, xlabel="x", ylabel="x²", title="Quadratic", label="y = x²")
end

function plot_bar()
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 4.0]
    return bar(categories, heights,
               xlabel="Category", ylabel="Value", title="Bar Chart", label="")
end
