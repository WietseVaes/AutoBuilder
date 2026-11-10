# Minimal JSON reader/writer, standard library only.
#
# The grader ships inside the autograder zip and runs on Gradescope with no
# packages installed, so it cannot depend on JSON.jl. This covers everything
# the autobuilder reads and writes: rubric.json, Gradescope's
# submission_metadata.json, Jupyter notebooks, and results.json.
#
#   json_parse(str)          objects -> Dict{String,Any}, arrays -> Vector{Any},
#                            integers -> Int, other numbers -> Float64,
#                            null -> nothing
#   json_string(x; indent)   the reverse; NaN/Inf are written as null

mutable struct _JSONReader
    s::String
    i::Int
end

json_parse(s::AbstractString) = begin
    r = _JSONReader(String(s), 1)
    # Tolerate a UTF-8 byte order mark (Windows editors sometimes add one).
    if ncodeunits(r.s) >= 3 && codeunit(r.s, 1) == 0xef && codeunit(r.s, 2) == 0xbb && codeunit(r.s, 3) == 0xbf
        r.i = 4
    end
    v = _jvalue(r)
    _jskip(r)
    r.i <= ncodeunits(r.s) && _jerror(r, "unexpected trailing content")
    v
end

json_parsefile(path::AbstractString) = json_parse(read(path, String))

_jerror(r, msg) = error("Invalid JSON (byte $(r.i)): $msg")
_jpeek(r) = r.i <= ncodeunits(r.s) ? codeunit(r.s, r.i) : 0x00

function _jskip(r)
    while r.i <= ncodeunits(r.s) && codeunit(r.s, r.i) in (0x20, 0x09, 0x0a, 0x0d)
        r.i += 1
    end
end

function _jexpect(r, c::Char)
    _jskip(r)
    _jpeek(r) == UInt8(c) || _jerror(r, "expected '$c'")
    r.i += 1
end

function _jliteral(r, word::String, value)
    n = ncodeunits(word)
    if r.i + n - 1 <= ncodeunits(r.s) && view(codeunits(r.s), r.i:r.i+n-1) == codeunits(word)
        r.i += n
        return value
    end
    _jerror(r, "unexpected character")
end

function _jvalue(r)
    _jskip(r)
    c = _jpeek(r)
    c == UInt8('{') && return _jobject(r)
    c == UInt8('[') && return _jarray(r)
    c == UInt8('"') && return _jstring(r)
    c == UInt8('t') && return _jliteral(r, "true", true)
    c == UInt8('f') && return _jliteral(r, "false", false)
    c == UInt8('n') && return _jliteral(r, "null", nothing)
    # Python's json module writes these non-standard tokens; accept them.
    c == UInt8('N') && return _jliteral(r, "NaN", NaN)
    c == UInt8('I') && return _jliteral(r, "Infinity", Inf)
    (c == UInt8('-') || UInt8('0') <= c <= UInt8('9')) && return _jnumber(r)
    _jerror(r, c == 0x00 ? "unexpected end of input" : "unexpected character")
end

function _jobject(r)
    r.i += 1
    d = Dict{String,Any}()
    _jskip(r)
    if _jpeek(r) == UInt8('}')
        r.i += 1
        return d
    end
    while true
        _jskip(r)
        _jpeek(r) == UInt8('"') || _jerror(r, "expected a string key")
        k = _jstring(r)
        _jexpect(r, ':')
        d[k] = _jvalue(r)
        _jskip(r)
        c = _jpeek(r)
        r.i += 1
        c == UInt8(',') && continue
        c == UInt8('}') && return d
        r.i -= 1
        _jerror(r, "expected ',' or '}'")
    end
end

function _jarray(r)
    r.i += 1
    a = Any[]
    _jskip(r)
    if _jpeek(r) == UInt8(']')
        r.i += 1
        return a
    end
    while true
        push!(a, _jvalue(r))
        _jskip(r)
        c = _jpeek(r)
        r.i += 1
        c == UInt8(',') && continue
        c == UInt8(']') && return a
        r.i -= 1
        _jerror(r, "expected ',' or ']'")
    end
end

function _jhex4(r)
    r.i + 3 <= ncodeunits(r.s) || _jerror(r, "truncated \\u escape")
    v = tryparse(UInt32, String(codeunits(r.s)[r.i:r.i+3]); base=16)
    v === nothing && _jerror(r, "invalid \\u escape")
    r.i += 4
    return v
end

function _jstring(r)
    r.i += 1  # opening quote
    io = IOBuffer()
    s = codeunits(r.s)
    while true
        r.i <= length(s) || _jerror(r, "unterminated string")
        c = s[r.i]
        if c == UInt8('"')
            r.i += 1
            return String(take!(io))
        elseif c == UInt8('\\')
            r.i += 1
            r.i <= length(s) || _jerror(r, "unterminated string")
            e = s[r.i]
            r.i += 1
            if e == UInt8('u')
                cp = _jhex4(r)
                if 0xd800 <= cp <= 0xdbff && r.i + 1 <= length(s) && s[r.i] == UInt8('\\') && s[r.i+1] == UInt8('u')
                    r.i += 2
                    lo = _jhex4(r)
                    cp = 0x10000 + ((cp - 0xd800) << 10) + (lo - 0xdc00)
                end
                print(io, Char(cp))
            else
                ch = e == UInt8('n') ? '\n' : e == UInt8('t') ? '\t' : e == UInt8('r') ? '\r' :
                     e == UInt8('b') ? '\b' : e == UInt8('f') ? '\f' :
                     e in (UInt8('"'), UInt8('\\'), UInt8('/')) ? Char(e) :
                     _jerror(r, "invalid escape")
                print(io, ch)
            end
        else
            write(io, c)
            r.i += 1
        end
    end
end

function _jnumber(r)
    start = r.i
    s = codeunits(r.s)
    if s[r.i] == UInt8('-') && r.i + 1 <= length(s) && s[r.i+1] == UInt8('I')
        r.i += 1
        return -_jliteral(r, "Infinity", Inf)
    end
    isfloat = false
    while r.i <= length(s) && (s[r.i] in UInt8.(('-', '+', '.', 'e', 'E')) || UInt8('0') <= s[r.i] <= UInt8('9'))
        s[r.i] in UInt8.(('.', 'e', 'E')) && (isfloat = true)
        r.i += 1
    end
    txt = String(s[start:r.i-1])
    if !isfloat
        v = tryparse(Int, txt)
        v !== nothing && return v
    end
    v = tryparse(Float64, txt)
    v === nothing && _jerror(r, "invalid number '$txt'")
    return v
end

# ── Writer ────────────────────────────────────────────────────────────────

json_string(x; indent::Int=0) = sprint(io -> json_write(io, x; indent=indent))

function json_write(io::IO, x; indent::Int=0, level::Int=0)
    _jw(io, x, indent, level)
end

function _jnewline(io, indent, level)
    indent > 0 && print(io, "\n", " "^(indent * level))
end

_jw(io, ::Nothing, indent, level) = print(io, "null")
_jw(io, x::Bool, indent, level) = print(io, x ? "true" : "false")
_jw(io, x::Integer, indent, level) = print(io, x)
function _jw(io, x::Real, indent, level)
    f = Float64(x)
    isfinite(f) ? print(io, isinteger(f) && abs(f) < 1e15 ? string(f) : repr(f)) : print(io, "null")
end
_jw(io, x::Symbol, indent, level) = _jw(io, String(x), indent, level)

function _jw(io, x::AbstractString, indent, level)
    print(io, '"')
    for c in x
        if c == '"'
            print(io, "\\\"")
        elseif c == '\\'
            print(io, "\\\\")
        elseif c == '\n'
            print(io, "\\n")
        elseif c == '\r'
            print(io, "\\r")
        elseif c == '\t'
            print(io, "\\t")
        elseif c < ' '
            print(io, "\\u", string(UInt32(c), base=16, pad=4))
        else
            print(io, c)
        end
    end
    print(io, '"')
end

function _jw(io, x::AbstractDict, indent, level)
    if isempty(x)
        print(io, "{}")
        return
    end
    print(io, "{")
    first = true
    for k in sort!(collect(keys(x)); by=string)
        first || print(io, ",")
        first = false
        _jnewline(io, indent, level + 1)
        _jw(io, string(k), indent, level + 1)
        print(io, indent > 0 ? ": " : ":")
        _jw(io, x[k], indent, level + 1)
    end
    _jnewline(io, indent, level)
    print(io, "}")
end

function _jw(io, x::Union{AbstractVector,Tuple}, indent, level)
    if isempty(x)
        print(io, "[]")
        return
    end
    print(io, "[")
    for (i, v) in enumerate(x)
        i > 1 && print(io, ",")
        _jnewline(io, indent, level + 1)
        _jw(io, v, indent, level + 1)
    end
    _jnewline(io, indent, level)
    print(io, "]")
end

_jw(io, x::NamedTuple, indent, level) = _jw(io, Dict{String,Any}(string(k) => v for (k, v) in pairs(x)), indent, level)
_jw(io, x, indent, level) = _jw(io, string(x), indent, level)
