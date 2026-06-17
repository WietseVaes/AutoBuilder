using Plots

# ── Variables ────────────────────────────────────────────────────────────────

greeting    = "bonjour from julia"  # string
is_prime_7  = true                  # bool
euler_number = exp(1.0)             # float scalar
fibonacci   = [1, 1, 2, 3, 5, 8, 13]             # integer vector
linspace_vec = collect(LinRange(0.0, 1.0, 5))    # float vector
rotation_90  = [0.0 -1.0; 1.0 0.0]               # 2×2 matrix

# ── Functions ────────────────────────────────────────────────────────────────

function square(x)
    return x ^ 2
end

function dot_product(a, b)
    return sum(a .* b)
end

# Returns (min, max); rubric tests each index separately via output_index.
function bounds(v)
    return (minimum(v), maximum(v))
end

# ── Plots ────────────────────────────────────────────────────────────────────

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
