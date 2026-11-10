using SpecialFunctions   # listed in rubric.json "requirements"
using Statistics         # standard library: always available

# Read from data.txt (listed in rubric.json "extra_files")
measurements = parse.(Float64, readlines("data.txt"))

struct Point
    x::Float64
    y::Float64
end
origin_shift = Point(1.0, -2.0)

gamma_ratio(x) = gamma(x + 1) / gamma(x)

function trapezoid(f, a, b, n)
    h = (b - a) / n
    xs = range(a, b; length=n + 1)
    return h * (sum(f, xs) - (f(a) + f(b)) / 2)
end

summary_stats(v) = (mean=mean(v), std=std(v))

column_sums(A) = vec(sum(A; dims=1))
