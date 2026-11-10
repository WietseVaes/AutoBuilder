# Turning rubric.json values (test inputs and "expected") into Julia values.
#
# JSON only has numbers, strings, booleans, null, lists and objects. They map
# to the Julia value an instructor would most likely have written:
#
#   5            -> 5 (Int)              5.0 / 1e-3  -> Float64
#   [1, 2, 3]    -> Vector{Int}          [1.0, 2, 3] -> Vector{Float64}
#   [[1, 2], [3, 4]]  -> 2×2 Matrix (each inner list is a ROW)
#   ["a", "b"]   -> Vector{String}       [true, false] -> Vector{Bool}
#   anything else (mixed lists, objects) -> Vector{Any} / Dict{String,Any}
#
# Write 1.0 rather than 1 in the rubric when the student's function expects
# floats (e.g. f(x::Vector{Float64})).
#
# A string "$name" is a reference to the variable `name` defined in the
# optional test_inputs.jl file (any Julia value, including functions).

_is_plain_real(x) = x isa Real && !(x isa Bool)

function to_julia(x)
    if x isa AbstractDict
        return Dict{String,Any}(string(k) => to_julia(v) for (k, v) in x)
    elseif !(x isa AbstractVector)
        return x
    end
    isempty(x) && return Any[]
    items = Any[to_julia(v) for v in x]
    if all(_is_plain_real, items)
        return all(v -> v isa Integer, items) ? Int[v for v in items] : Float64[v for v in items]
    elseif all(v -> v isa Bool, items)
        return Bool[v for v in items]
    elseif all(v -> v isa AbstractString, items)
        return String[v for v in items]
    elseif all(v -> v isa AbstractVector && !isempty(v) && all(_is_plain_real, v), items)
        n = length(items[1])
        if all(v -> length(v) == n, items)
            T = all(v -> all(e -> e isa Integer, v), items) ? Int : Float64
            M = Matrix{T}(undef, length(items), n)
            for (i, row) in enumerate(items)
                M[i, :] = row
            end
            return M
        end
    end
    return items
end

is_input_ref(x) = x isa AbstractString && startswith(x, "\$") && length(x) > 1

"""
    name_symbol(name)

The Symbol Julia's parser makes of a name from rubric.json. Julia normalizes
some look-alike characters in identifiers (NFC, and e.g. the micro sign `µ`
becomes Greek `μ`, which `\\mu<tab>` types), so a rubric written with either
one finds the student's variable.
"""
function name_symbol(name::AbstractString)
    ex = try
        Meta.parse(strip(name); raise=false)
    catch
        nothing
    end
    return ex isa Symbol ? ex : Symbol(name)
end

"""
    resolve_value(x, inputs_module)

Resolve a rubric input/expected value: "\$name" looks `name` up in the
test_inputs.jl module, anything else goes through `to_julia`.
"""
function resolve_value(x, inputs_module)
    if is_input_ref(x)
        name = x[2:end]
        inputs_module === nothing && error(
            "the rubric refers to $x, but no inputs file was given " *
            "(pass --inputs test_inputs.jl when building).")
        sym = name_symbol(name)
        isdefined(inputs_module, sym) || error("$x is not defined in the inputs file.")
        return getglobal(inputs_module, sym)
    end
    return to_julia(x)
end
