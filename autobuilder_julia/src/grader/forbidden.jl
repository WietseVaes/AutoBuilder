# rubric.json "forbidden_functions": a test scores 0 when the code that
# produces its variable/function uses one of the listed functions.
#
#     "forbidden_functions": ["find_zero", "Roots.fzero", "LinearAlgebra.eigen", "\\"]
#
# The student's file is parsed (never run), so comments and strings are
# ignored. Starting from the tested name, the analysis follows everything that
# name depends on: the statements that assign or change it, the functions and
# structs it uses, the variables those use, and so on (files the student
# include()s too). A forbidden function used anywhere along that path fails
# the test; using it elsewhere in the file, for another problem, is fine.
#
# Matching an entry against a use in the student's code:
#   - imports are resolved: after `using Roots`, `find_zero` is Roots.find_zero;
#     `import Roots as R; R.find_zero`, `using Roots: find_zero as fz; fz(...)`
#     and `g = find_zero; g(...)` are all uses of Roots.find_zero;
#   - an entry matches when its dotted parts appear, in order, in the resolved
#     name: "find_zero" and "Roots.find_zero" both match, "Roots" bans the
#     whole package;
#   - a function the student defines themselves (`function fzero(...)`) is
#     theirs, not the package's, and is followed instead of flagged.
#
# What counts as "changing" a variable (so its statement belongs to the path):
# assigning it (also x[i] = ..., x.a = ..., x += ..., x .= ..., for x in ...),
# calling a `!` function on it as its first argument (push!(x, ...)), or
# passing it to a function the student wrote, as a statement (fill_roots(x)).
# Inside a function, the same for global names (`global x` for plain
# assignments). Statements inside if/for/while/let/try also depend on their
# conditions and loop ranges.
#
# Not detected: tricks with eval/getfield/@eval, and package functions without
# a `!` that change their arguments anyway.

const _FRef = Tuple{Symbol,String,Int,String}   # (root name, dotted name, line, file)

mutable struct ForbiddenGraph
    deps::Dict{Symbol,Set{_FRef}}
    aliases::Dict{Symbol,String}   # name bound by an import -> full dotted path
    star::Vector{String}           # modules brought in with `using M`
    bound::Set{Symbol}             # names the student defines
    modules::Set{Symbol}           # `module M ... end` written by the student
    line::Int
    file::String
end
ForbiddenGraph() = ForbiddenGraph(Dict{Symbol,Set{_FRef}}(), Dict{Symbol,String}(), String[],
                                  Set{Symbol}(), Set{Symbol}(), 0, "")

const _NOT_ASSIGN = (:(==), :(===), :(!=), :(<=), :(>=), :(=>))
_fb_is_assign(e) = e isa Expr && length(e.args) == 2 && !(e.head in _NOT_ASSIGN) &&
                   endswith(string(e.head), "=") && e.head !== :kw

function _fb_walk(f, ex)
    f(ex)
    ex isa Expr && foreach(a -> _fb_walk(f, a), ex.args)
end

"""'A.b.c' for a field/module chain rooted at a plain name, else nothing."""
function _fb_dotted(ex)
    parts = String[]
    while ex isa Expr && ex.head === :. && length(ex.args) == 2 && ex.args[2] isa QuoteNode
        pushfirst!(parts, string(ex.args[2].value))
        ex = ex.args[1]
    end
    ex isa Symbol || return nothing
    pushfirst!(parts, string(ex))
    return join(parts, ".")
end

"""The plain name at the base of x, x[i], x.a, x::T, x... (or nothing)."""
function _fb_root(ex)
    while ex isa Expr && ex.head in (:ref, :., :(::), :curly, :..., :(<:)) && !isempty(ex.args)
        ex = ex.args[1]
    end
    return ex isa Symbol ? ex : nothing
end

function _fb_target_roots(ex)
    if ex isa Expr && ex.head in (:tuple, :parameters)
        return reduce(vcat, (_fb_target_roots(a) for a in ex.args); init=Symbol[])
    end
    r = _fb_root(ex)
    return r === nothing ? Symbol[] : [r]
end

"""Names a plain assignment declares: x = ..., (a, b) = ..., x::T = ..."""
function _fb_plain_names(ex)
    ex isa Symbol && return [ex]
    ex isa Expr || return Symbol[]
    ex.head === :(::) && length(ex.args) == 2 && return _fb_plain_names(ex.args[1])
    ex.head === :... && return _fb_plain_names(ex.args[1])
    ex.head in (:tuple, :parameters) &&
        return reduce(vcat, (_fb_plain_names(a) for a in ex.args); init=Symbol[])
    return Symbol[]
end

function _fb_sig_call(sig)
    while sig isa Expr && sig.head in (:where, :(::)) && !isempty(sig.args)
        sig = sig.args[1]
    end
    return sig
end

_fb_is_shortdef(e) = e isa Expr && e.head === :(=) && length(e.args) == 2 &&
                     (c = _fb_sig_call(e.args[1]); c isa Expr && c.head === :call)

"""Name of the function defined by a signature like f(x), f(x)::T, f(x) where T, Base.show(io, x)."""
function _fb_func_name(sig)
    c = _fb_sig_call(sig)
    (c isa Expr && c.head === :call) || return nothing
    n = c.args[1]
    n isa Expr && n.head === :curly && (n = n.args[1])
    n isa Symbol && return n
    d = _fb_dotted(n)
    return d === nothing ? nothing : Symbol(last(split(d, ".")))
end

function _fb_param!(out, a)
    if a isa Symbol
        push!(out, a)
    elseif a isa Expr
        if a.head === :(::)
            length(a.args) == 2 && _fb_param!(out, a.args[1])
        elseif a.head in (:kw, :(=), :...)
            _fb_param!(out, a.args[1])
        elseif a.head in (:parameters, :tuple)
            foreach(x -> _fb_param!(out, x), a.args)
        end
    end
end

function _fb_params(sig)
    out = Symbol[]
    s = sig
    while s isa Expr && s.head in (:where, :(::)) && !isempty(s.args)
        if s.head === :where
            for tv in s.args[2:end]
                r = _fb_root(tv)
                r === nothing || push!(out, r)
            end
        end
        s = s.args[1]
    end
    if s isa Expr && s.head === :call
        foreach(a -> _fb_param!(out, a), s.args[2:end])
    else
        _fb_param!(out, s)          # x -> ..., (x, y) -> ..., function (x) ... end
    end
    return out
end

"""Parameters and names assigned inside a function or lambda, minus those declared global."""
function _fb_locals(fn::Expr)
    local_ = Set{Symbol}(_fb_params(fn.args[1]))
    declared = Set{Symbol}()
    length(fn.args) >= 2 || return local_
    _fb_walk(fn.args[2]) do e
        e isa Expr || return
        if e.head === :global
            for a in e.args
                union!(declared, _fb_plain_names(_fb_is_assign(a) ? a.args[1] : a))
            end
        elseif e.head === :function || _fb_is_shortdef(e)
            n = _fb_func_name(e.args[1])
            n === nothing || push!(local_, n)
        elseif _fb_is_assign(e)
            union!(local_, _fb_plain_names(e.args[1]))
        elseif e.head === :local
            for a in e.args
                union!(local_, _fb_plain_names(_fb_is_assign(a) ? a.args[1] : a))
            end
        end
    end
    return setdiff(local_, declared)
end

# ── References ─────────────────────────────────────────────────────────────

"""Names used in `ex`, skipping names local to a function, lambda or
comprehension inside it (a parameter `x` is not the global `x`)."""
function _fb_refs!(g::ForbiddenGraph, out::Set{_FRef}, ex, local_::Set{Symbol})
    if ex isa LineNumberNode
        g.line = ex.line
        return out
    elseif ex isa Symbol
        ex in local_ || push!(out, (ex, string(ex), g.line, g.file))
        return out
    elseif !(ex isa Expr)
        return out                 # literals, strings, :symbols, field names
    end
    h = ex.head
    if h === :. && length(ex.args) == 2 && ex.args[2] isa QuoteNode
        d = _fb_dotted(ex)
        if d === nothing
            _fb_refs!(g, out, ex.args[1], local_)
        else
            root = Symbol(first(split(d, ".")))
            root in local_ || push!(out, (root, d, g.line, g.file))
        end
        return out
    elseif h in (:function, :->) || _fb_is_shortdef(ex)
        inner = union(local_, _fb_locals(ex))
        foreach(a -> _fb_refs!(g, out, a, inner), ex.args)
        return out
    elseif h === :generator
        vars = Set{Symbol}()
        for spec in ex.args[2:end]
            _fb_walk(spec) do e
                e isa Expr && e.head === :(=) && union!(vars, _fb_plain_names(e.args[1]))
            end
        end
        inner = union(local_, vars)
        foreach(a -> _fb_refs!(g, out, a, inner), ex.args)
        return out
    elseif h === :kw
        length(ex.args) == 2 && _fb_refs!(g, out, ex.args[2], local_)
        return out
    end
    foreach(a -> _fb_refs!(g, out, a, local_), ex.args)
    return out
end

_fb_add!(g, name, refs) = union!(get!(g.deps, name, Set{_FRef}()), refs)

# ── What a statement changes ──────────────────────────────────────────────

_fb_student_callable(g, f) = (r = _fb_root(f); r !== nothing && r in g.bound && !haskey(g.aliases, r))

function _fb_call_changes(g, call::Expr)
    out = Symbol[]
    f = call.args[1]
    fname = f isa Symbol ? string(f) : _fb_dotted(f)
    positional = [a for a in call.args[2:end] if !(a isa Expr && a.head in (:parameters, :kw))]
    if fname !== nothing && endswith(fname, "!") && !isempty(positional)
        append!(out, _fb_target_roots(positional[1]))
    end
    if _fb_student_callable(g, f)
        for a in call.args[2:end]
            if a isa Expr && a.head === :parameters
                for k in a.args
                    append!(out, _fb_target_roots(k isa Expr && k.head === :kw ? k.args[2] : k))
                end
            elseif a isa Expr && a.head === :kw
                append!(out, _fb_target_roots(a.args[2]))
            else
                append!(out, _fb_target_roots(a))
            end
        end
    end
    return out
end

function _fb_changed(g, ex)
    out = Symbol[]
    e = ex
    while _fb_is_assign(e)                  # a = b = ...
        append!(out, _fb_target_roots(e.args[1]))
        e = e.args[2]
    end
    e isa Expr && e.head === :call && append!(out, _fb_call_changes(g, e))
    return out
end

"""Global names a function may change when it runs."""
function _fb_changed_by_function(g, fn::Expr)
    out = Set{Symbol}()
    length(fn.args) >= 2 || return out
    local_ = _fb_locals(fn)
    _fb_walk(fn.args[2]) do e
        e isa Expr || return
        if _fb_is_assign(e) && !_fb_is_shortdef(e)
            for r in _fb_target_roots(e.args[1])
                r in local_ || push!(out, r)
            end
        elseif e.head === :call
            for r in _fb_call_changes(g, e)
                r in local_ || push!(out, r)
            end
        end
    end
    return out
end

# ── Statements ─────────────────────────────────────────────────────────────

function _fb_stmt!(g::ForbiddenGraph, ex, ctx::Set{_FRef})
    if ex isa LineNumberNode
        g.line = ex.line
        return
    end
    ex isa Expr || return
    h = ex.head
    if h in (:toplevel, :block, :const, :global, :local)
        foreach(a -> _fb_stmt!(g, a, ctx), ex.args)
    elseif h in (:using, :import)
        return
    elseif h === :module
        _fb_stmt!(g, ex.args[end], ctx)
    elseif h === :macrocall
        inner = copy(ctx)
        _fb_refs!(g, inner, ex.args[1], Set{Symbol}())
        foreach(a -> _fb_stmt!(g, a, inner), ex.args[2:end])
    elseif h in (:function, :macro) || _fb_is_shortdef(ex)
        name = _fb_func_name(ex.args[1])
        h === :macro && name !== nothing && (name = Symbol("@", name))
        name === nothing && return
        line = g.line
        _fb_add!(g, name, union(_fb_refs!(g, Set{_FRef}(), ex, Set{Symbol}()), ctx))
        me = Set{_FRef}([(name, string(name), line, g.file)])
        foreach(n -> _fb_add!(g, n, me), _fb_changed_by_function(g, ex))
    elseif h in (:struct, :abstract, :primitive)
        name = _fb_root(ex.args[h === :struct ? 2 : 1])
        name === nothing || _fb_add!(g, name, union(_fb_refs!(g, Set{_FRef}(), ex, Set{Symbol}()), ctx))
    elseif h in (:if, :elseif, :for, :while, :let, :try)
        header = Set{_FRef}()
        blocks = Any[]
        for (i, a) in enumerate(ex.args)
            if (i == 1 && h !== :try) || !(a isa Expr && a.head in (:block, :elseif))
                _fb_refs!(g, header, a, Set{Symbol}())
            else
                push!(blocks, a)
            end
        end
        inner = union(ctx, header)
        bound_here = Symbol[]
        if h in (:for, :let)
            specs = ex.args[1] isa Expr && ex.args[1].head === :block ? ex.args[1].args : [ex.args[1]]
            for s in specs
                _fb_is_assign(s) && append!(bound_here, _fb_target_roots(s.args[1]))
            end
        elseif h === :try && length(ex.args) >= 2 && ex.args[2] isa Symbol
            push!(bound_here, ex.args[2])
        end
        foreach(n -> _fb_add!(g, n, inner), bound_here)
        foreach(b -> _fb_stmt!(g, b, inner), blocks)
    else
        refs = union(_fb_refs!(g, Set{_FRef}(), ex, Set{Symbol}()), ctx)
        foreach(n -> _fb_add!(g, n, refs), _fb_changed(g, ex))
    end
    return
end

# ── Imports and names the student defines ──────────────────────────────────

_fb_modpath(e) = e isa Expr && e.head === :. ?
    join([string(a) for a in e.args if a !== :.], ".") : string(e)

function _fb_imports!(g, ex)
    for a in ex.args
        if a isa Expr && a.head === :(:)              # using M: a, b as c
            mod = _fb_modpath(a.args[1])
            for item in a.args[2:end]
                if item isa Expr && item.head === :as
                    g.aliases[item.args[2]] = mod * "." * _fb_modpath(item.args[1])
                else
                    name = _fb_modpath(item)
                    g.aliases[Symbol(last(split(name, ".")))] = mod * "." * name
                end
            end
        elseif a isa Expr && a.head === :as           # import M as N
            g.aliases[a.args[2]] = _fb_modpath(a.args[1])
        elseif a isa Expr && a.head === :.            # using M / import M / import M.f
            path = _fb_modpath(a)
            isempty(path) && continue
            g.aliases[Symbol(last(split(path, ".")))] = path
            ex.head === :using && push!(g.star, path)
        end
    end
end

function _fb_prepass!(g, tree)
    _fb_walk(tree) do e
        e isa Expr || return
        if e.head in (:using, :import)
            _fb_imports!(g, e)
        elseif e.head === :function || _fb_is_shortdef(e)
            n = _fb_func_name(e.args[1])
            n === nothing || push!(g.bound, n)
        elseif e.head === :macro
            n = _fb_func_name(e.args[1])
            n === nothing || push!(g.bound, Symbol("@", n))
        elseif e.head === :struct
            n = _fb_root(e.args[2])
            n === nothing || push!(g.bound, n)
        elseif e.head === :module
            e.args[2] isa Symbol && push!(g.modules, e.args[2])
        elseif _fb_is_assign(e)
            union!(g.bound, _fb_plain_names(e.args[1]))
        end
    end
end

"""Parsed files: the main file plus files it include()s with a literal path."""
function _fb_parse_files(path)
    files = Tuple{Expr,String}[]
    seen = Set{String}()
    todo = [abspath(path)]
    while !isempty(todo)
        p = popfirst!(todo)
        (p in seen || !isfile(p)) && continue
        push!(seen, p)
        tree = Meta.parseall(read(p, String); filename=basename(p))
        push!(files, (tree, p))
        _fb_walk(tree) do e
            if e isa Expr && e.head === :call && length(e.args) == 2 && e.args[1] === :include &&
               e.args[2] isa String
                push!(todo, abspath(joinpath(dirname(p), e.args[2])))
            end
        end
    end
    return files
end

"""Dependency graph of a student's file (and the files it includes)."""
function forbidden_graph(path)
    g = ForbiddenGraph()
    files = _fb_parse_files(path)
    for (tree, _) in files
        _fb_prepass!(g, tree)
    end
    for (tree, p) in files
        g.file = p
        g.line = 0
        _fb_stmt!(g, tree, Set{_FRef}())
    end
    return g
end

# ── Matching ───────────────────────────────────────────────────────────────

"""[(parts, first matchable index)] for one use in the code."""
function _fb_resolutions(g, root::Symbol, dotted::String)
    parts = String.(split(dotted, "."))
    haskey(g.aliases, root) && return [(vcat(String.(split(g.aliases[root], ".")), parts[2:end]), 1)]
    root in g.bound && return [(parts, 2)]     # the student's own name: only its fields
    out = [(parts, 1)]
    for m in g.star
        push!(out, (vcat(String.(split(m, ".")), parts), 1))
    end
    return out
end

function _fb_matches(entry, parts, start)
    e = String.(split(entry, "."))
    for i in start:(length(parts) - length(e) + 1)
        parts[i:i+length(e)-1] == e && return true
    end
    return false
end

"""[(entry, line, file)] for each forbidden entry used on the way to `target`, in rubric order."""
function forbidden_uses(g::ForbiddenGraph, target::AbstractString, forbidden)
    entries = [strip(string(e)) for e in forbidden if !isempty(strip(string(e)))]
    hits = Dict{String,Tuple{Int,String}}()
    seen = Set{Symbol}()
    stack = Symbol[Symbol(target)]
    while !isempty(stack)
        name = pop!(stack)
        name in seen && continue
        push!(seen, name)
        refs = sort!(collect(get(g.deps, name, Set{_FRef}())); by=r -> (r[4], r[3]))
        for (root, dotted, line, file) in refs
            res = _fb_resolutions(g, root, dotted)
            if root in g.modules                      # the student's own module: follow
                append!(stack, Symbol.(res[1][1][2:end]))
                continue
            end
            for e in entries
                haskey(hits, e) && continue
                any(r -> _fb_matches(e, r[1], r[2]), res) && (hits[e] = (line, file))
            end
            root in g.bound && !haskey(g.aliases, root) && push!(stack, root)
        end
    end
    return [(e, hits[e]...) for e in entries if haskey(hits, e)]
end

"""'Do not use find_zero for this problem (line 12).'"""
function forbidden_message(hits, main_path=nothing; show_lines=true)
    names = [h[1] for h in hits]
    listed = length(names) == 1 ? names[1] : join(names[1:end-1], ", ") * " or " * names[end]
    msg = "Do not use $listed for this problem"
    if show_lines
        where_ = String[]
        for (_, line, file) in hits
            w = main_path !== nothing && abspath(file) == abspath(main_path) ?
                "line $line" : "line $line of $(basename(file))"
            w in where_ || push!(where_, w)
        end
        msg *= " (" * join(where_, ", ") * ")"
    end
    return msg * "."
end
