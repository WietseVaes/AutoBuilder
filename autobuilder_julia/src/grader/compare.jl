# Comparing a student's value with the reference value.
#
#   compare_values(student, reference, rtol, atol) -> (status, message)
#
# status is one of (the same five outcomes as the Python autobuilder, so the
# rubric's hint fields mean the same thing in both):
#   "pass"        values match
#   "wrong_type"  student value has the wrong kind of type
#   "wrong_size"  wrong array size / number of elements / columns / keys
#   "nans"        the student value contains NaN
#   "tolerance"   right type and size, but the values differ
#
# Numbers are close when |s - r| <= atol + rtol * |r| elementwise (the same
# rule as numpy.allclose). Messages never reveal the expected value.
#
# Supported reference values: strings, booleans, numbers (real or complex),
# numeric arrays of any dimension and numeric tuples, and -- compared element
# by element -- tuples, named tuples, dicts, arrays of anything, DataFrames,
# and structs (a struct defined in both the solution and the submission is
# matched by type name and compared field by field). Anything else must be
# equal (isequal or ==).

const PASS = ("pass", "OK")

function _type_name(x)
    T = typeof(x)
    if T isa DataType && parentmodule(T) in (Base, Core)
        return string(T)
    end
    return string(nameof(T))
end

function _describe_size(sz)
    isempty(sz) && return "a single number"
    length(sz) == 1 && return "a vector of length $(sz[1])"
    length(sz) == 2 && return "a $(sz[1])×$(sz[2]) matrix"
    return "an array of size $(join(sz, "×"))"
end

# The value as a number or numeric array, or `nothing` if it is not numeric.
function _as_numeric(x)
    x isa Number && return x
    if x isa AbstractArray
        return all(e -> e isa Number, x) ? x : nothing
    elseif x isa Tuple && !isempty(x)
        return all(e -> e isa Number, x) ? collect(x) : nothing
    end
    return nothing
end

_has_nan(x::Number) = try isnan(x) catch; false end
_has_nan(x) = any(_has_nan, x)

function _close(a, b, rtol, atol)
    a == b && return true  # also covers equal infinities
    try
        return abs(a - b) <= atol + rtol * abs(b)
    catch
        return false
    end
end
_all_close(s::Number, r::Number, rtol, atol) = _close(s, r, rtol, atol)
_all_close(s, r, rtol, atol) = all(_close(a, b, rtol, atol) for (a, b) in zip(s, r))

_is_dataframe(x) = nameof(typeof(x)) === :DataFrame

function compare_values(s, r, rtol=1e-6, atol=1e-6)
    # ── String ────────────────────────────────────────────────────────────
    if r isa AbstractString
        s isa AbstractString || return ("wrong_type", "Expected a string, but got type $(_type_name(s)).")
        return s == r ? PASS : ("tolerance", "Your string value is incorrect.")
    end

    # ── Boolean (before numbers: Bool <: Number in Julia) ─────────────────
    if r isa Bool
        s isa Bool || return ("wrong_type", "Expected a boolean (true or false), but got type $(_type_name(s)).")
        return s == r ? PASS : ("tolerance", "Your boolean value is incorrect.")
    end

    _is_dataframe(r) && return _compare_dataframe(s, r, rtol, atol)

    # ── Number / numeric array / numeric tuple ────────────────────────────
    rn = _as_numeric(r)
    if rn !== nothing
        sn = _as_numeric(s)
        sn === nothing && return ("wrong_type",
            "Expected a number or an array of numbers, but got type $(_type_name(s)).")
        size(sn) == size(rn) || return ("wrong_size",
            "Expected $(_describe_size(size(rn))), but got $(_describe_size(size(sn))).")
        _has_nan(sn) && return ("nans", "Your value contains NaN.")
        _all_close(sn, rn, rtol, atol) || return ("tolerance", "Your value is not within the required tolerance.")
        return PASS
    end

    # ── Collections: compare element by element ───────────────────────────
    if r isa Tuple || r isa AbstractArray
        what = r isa Tuple ? "a tuple" : "an array"
        (s isa Tuple || s isa AbstractArray) || return ("wrong_type",
            "Expected $what, but got type $(_type_name(s)).")
        if s isa AbstractArray && r isa AbstractArray && ndims(r) > 1
            size(s) == size(r) || return ("wrong_size",
                "Expected an array of size $(join(size(r), "×")), but got size $(join(size(s), "×")).")
        end
        length(s) == length(r) || return ("wrong_size",
            "Expected $(length(r)) elements, but got $(length(s)).")
        for (i, (a, b)) in enumerate(zip(s, r))
            st, msg = compare_values(a, b, rtol, atol)
            st == "pass" || return (st, "Element $i: $msg")
        end
        return PASS
    end

    if r isa NamedTuple
        s isa NamedTuple || return ("wrong_type", "Expected a named tuple, but got type $(_type_name(s)).")
        keys(s) == keys(r) || return ("wrong_size",
            "Expected fields $(join(keys(r), ", ")), but got fields $(join(keys(s), ", ")).")
        for k in keys(r)
            st, msg = compare_values(s[k], r[k], rtol, atol)
            st == "pass" || return (st, "Field $k: $msg")
        end
        return PASS
    end

    if r isa AbstractDict
        s isa AbstractDict || return ("wrong_type", "Expected a dictionary, but got type $(_type_name(s)).")
        Set(keys(s)) == Set(keys(r)) || return ("wrong_size",
            "Expected $(length(r)) keys, but your dictionary has different keys.")
        for k in keys(r)
            st, msg = compare_values(s[k], r[k], rtol, atol)
            st == "pass" || return (st, "Key $(repr(k)): $msg")
        end
        return PASS
    end

    # ── Anything else ─────────────────────────────────────────────────────
    nameof(typeof(s)) == nameof(typeof(r)) || return ("wrong_type",
        "Expected type $(_type_name(r)), but got type $(_type_name(s)).")
    _equal(s, r) && return PASS
    # The solution and the submission each define their own struct with the
    # same name (e.g. `struct Point`): compare field by field.
    T, S = typeof(r), typeof(s)
    if isstructtype(T) && fieldcount(T) > 0 && fieldnames(S) == fieldnames(T)
        for f in fieldnames(T)
            st, msg = compare_values(getfield(s, f), getfield(r, f), rtol, atol)
            st == "pass" || return (st, "Field $f: $msg")
        end
        return PASS
    end
    return ("tolerance", "Your value is incorrect.")
end

function _equal(s, r)
    try
        isequal(s, r) === true && return true
        return (s == r) === true
    catch
        return false
    end
end

# DataFrames are compared through their public interface (names, size,
# columns), so the grader itself does not need DataFrames.jl installed.
function _compare_dataframe(s, r, rtol, atol)
    _is_dataframe(s) || return ("wrong_type", "Expected a DataFrame, but got type $(_type_name(s)).")
    rc, sc = names(r), names(s)
    sc == rc || return ("wrong_size", "Expected columns $(rc), but got columns $(sc).")
    size(s) == size(r) || return ("wrong_size", "Expected $(size(r, 1)) rows, but got $(size(s, 1)).")
    for c in rc
        st, msg = compare_values(collect(getproperty(s, Symbol(c))), collect(getproperty(r, Symbol(c))), rtol, atol)
        st == "pass" || return (st, "Column '$c': $msg")
    end
    return PASS
end
