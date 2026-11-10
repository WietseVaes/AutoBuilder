# Wrong answers and an error part-way through the script.
using Statistics

measurements = [1.5, 2.0, 3.25]           # only 3 of the 4 numbers

struct Point
    x::Float64
    y::Float64
end
origin_shift = Point(1.0, 2.0)            # wrong sign

summary_stats(v) = (mean(v), std(v))      # plain tuple, not a named tuple

column_sums(A) = vec(sum(A; dims=2))      # row sums instead of column sums

trapezoid(f, a, b, n) = undefined_helper(f, a, b, n)   # calls something that doesn't exist

# gamma is used without `using SpecialFunctions`, so the script stops here;
# everything defined above is still graded.
gamma_ratio = gamma(5.5) / gamma(4.5)
