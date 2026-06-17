using Plots

# NaN values + wrong plot axis labels.
# euler_number = NaN          -> hint_nans
# fibonacci has NaN           -> hint_nans
# plot labels wrong           -> hint_tolerance (plot tests)

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

function plot_quadratic()
    x = collect(0.0:0.1:2.0)
    y = x .^ 2
    # Wrong labels: "time"/"distance"/"My Plot" instead of "x"/"x²"/"Quadratic"
    return plot(x, y, xlabel="time", ylabel="distance", title="My Plot", label="data")
end

function plot_bar()
    categories = [1, 2, 3, 4, 5]
    heights    = [2.0, 5.0, 3.0, 7.0, 4.0]
    # Wrong labels: generic names instead of correct ones
    return bar(categories, heights,
               xlabel="x", ylabel="y", title="histogram", label="")
end
