using Plots

# Wrong types and wrong sizes.
# greeting: number instead of string          -> hint_wrong_type
# is_prime_7: string instead of bool          -> hint_wrong_type
# euler_number: 1-element vector not scalar   -> hint_wrong_size
# fibonacci: only 5 elements not 7            -> hint_wrong_size
# linspace_vec: 10 elements not 5             -> hint_wrong_size
# rotation_90: flat vector not 2x2 matrix     -> hint_wrong_size
# square: returns vector not scalar           -> hint_wrong_size
# dot_product: returns element-wise vector    -> hint_wrong_size
# plot_quadratic: two lines not one           -> hint_wrong_size (n_lines)
# plot_bar: three bars not five               -> hint_wrong_size (n_bars)

greeting     = 42
is_prime_7   = "yes"
euler_number = [exp(1.0)]                       # wrapped in a vector
fibonacci    = [1, 1, 2, 3, 5]                 # only first 5
linspace_vec = collect(LinRange(0.0, 1.0, 10)) # 10 points not 5
rotation_90  = [0.0, -1.0, 1.0, 0.0]           # flat 1D, not 2x2

function square(x)
    return [x ^ 2]                             # wrapped in a vector
end

function dot_product(a, b)
    return a .* b                              # element-wise, not scalar
end

function bounds(v)
    return (minimum(v), maximum(v))            # correct
end

function plot_quadratic()
    x  = collect(0.0:0.1:2.0)
    y1 = x .^ 2
    y2 = x .^ 3
    # Two lines instead of one
    return plot(x, [y1 y2], xlabel="x", ylabel="x²", title="Quadratic",
                label=["y = x²" "y = x³"])
end

function plot_bar()
    # Three bars instead of five
    categories = [1, 2, 3]
    heights    = [2.0, 5.0, 3.0]
    return bar(categories, heights,
               xlabel="Category", ylabel="Value", title="Bar Chart", label="")
end
