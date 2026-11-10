using SpecialFunctions
using Statistics

measurements = [parse(Float64, line) for line in eachline("data.txt")]

struct Point
    x::Float64
    y::Float64
end
origin_shift = Point(1.0, -2.0)

gamma_ratio(x) = gamma(x + 1) / gamma(x)

function trapezoid(f, a, b, n)
    h = (b - a) / n
    total = (f(a) + f(b)) / 2
    for i in 1:n-1
        total += f(a + i * h)
    end
    return h * total
end

summary_stats(v) = (mean=mean(v), std=std(v))

column_sums(A) = [sum(A[:, j]) for j in 1:size(A, 2)]
