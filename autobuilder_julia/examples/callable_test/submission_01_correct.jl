# Expected: 5/5.
function apply_twice(f, x)
    y = f(x)
    return f(y)
end
