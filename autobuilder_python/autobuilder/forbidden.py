"""
rubric.json "forbidden_functions": a test scores 0 when the code that
produces its variable/function uses one of the listed functions.

    "forbidden_functions": ["brentq", "scipy.optimize.fsolve", "numpy.linalg"]

The student's file is parsed (never run), so comments and strings are
ignored. Starting from the tested name, the analysis follows everything that
name depends on: the statements that assign or change it, the functions and
classes it uses, the variables those use, and so on (helper modules the
student submitted next to the file included). A forbidden function used
anywhere along that path fails the test; using it elsewhere in the file, for
another problem, is fine.

Matching an entry against a use in the student's code:
  - imports are resolved, so `import scipy.optimize as so; so.brentq(...)`,
    `from scipy.optimize import brentq as b; b(...)` and `f = brentq; f(...)`
    are all uses of scipy.optimize.brentq;
  - an entry matches when its dotted parts appear, in order, in the resolved
    name: "brentq" matches scipy.optimize.brentq, "optimize.brentq" too, and
    "scipy.optimize" bans the whole module;
  - a name the student defines themselves (`def brentq(...)`) is theirs, not
    the library's, and is followed instead of flagged.

What counts as "changing" a variable (so its statement belongs to the path):
assigning it (also x[i] = ..., x.a = ..., x += ..., for x in ..., with ... as
x), calling a method on it as a statement (x.append(...)), or passing it to a
function the student wrote, as a statement (fill(x)). Inside a function, the
same for module-level names (with `global x` for plain assignments).
Statements inside if/for/while/with/try also depend on their headers.

Not detected: getattr/eval/exec tricks, and library calls that change their
arguments in place (np.copyto(x, brentq(...))).
"""
import ast
import builtins
import os

_COMPOUND = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
if hasattr(ast, "TryStar"):
    _COMPOUND += (ast.TryStar,)
if hasattr(ast, "Match"):
    _COMPOUND += (ast.Match,)
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_BODY_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")
_BUILTINS = set(dir(builtins))


def _dotted(node):
    """'a.b.c' for an attribute chain rooted at a plain name, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _root(node):
    """The plain name at the base of x, x.a, x[i], x.a[i].b, ... (or None)."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _function_locals(fn):
    """Parameters and names assigned inside a function (or lambda), minus
    those declared global/nonlocal."""
    local, declared = set(), set()
    a = fn.args
    for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
        if arg is not None:
            local.add(arg.arg)
    for node in ast.walk(fn.body if isinstance(fn, ast.Lambda) else ast.Module(body=fn.body, type_ignores=[])):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
        elif isinstance(node, _DEFS):
            local.add(node.name)
    return local - declared


def _target_roots(target):
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for elt in target.elts:
            out.extend(_target_roots(elt))
        return out
    r = _root(target)
    return [r] if r else []


class _Graph:
    def __init__(self):
        self.deps = {}          # name -> set of (root, dotted, line, file)
        self.aliases = {}       # name bound by an import -> dotted module path
        self.star = []          # modules imported with `from m import *`
        self.bound = set()      # names the student defines (not imports)
        self.helper_modules = set()

    # -- references -------------------------------------------------------
    def _refs(self, node, fname, out=None, local=frozenset()):
        """Names used in `node`, skipping names local to a function, lambda
        or comprehension inside it (a parameter `x` is not the module's `x`)."""
        if out is None:
            out = set()
        if isinstance(node, ast.Attribute):
            d = _dotted(node)
            if d:
                if d.split(".")[0] not in local:
                    out.add((d.split(".")[0], d, node.lineno, fname))
                return out
        elif isinstance(node, ast.Name):
            if node.id not in local:
                out.add((node.id, node.id, node.lineno, fname))
            return out
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            for d in a.defaults + [d for d in a.kw_defaults if d is not None]:
                self._refs(d, fname, out, local)
            if not isinstance(node, ast.Lambda):
                for d in node.decorator_list:
                    self._refs(d, fname, out, local)
                if node.returns is not None:
                    self._refs(node.returns, fname, out, local)
            inner = local | _function_locals(node)
            for s in (node.body if isinstance(node.body, list) else [node.body]):
                self._refs(s, fname, out, inner)
            return out
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = set(local)
            for gen in node.generators:
                self._refs(gen.iter, fname, out, frozenset(inner))
                inner.update(n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name))
                for cond in gen.ifs:
                    self._refs(cond, fname, out, frozenset(inner))
            elts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            for e in elts:
                self._refs(e, fname, out, frozenset(inner))
            return out
        for child in ast.iter_child_nodes(node):
            self._refs(child, fname, out, local)
        return out

    def _add(self, name, refs):
        self.deps.setdefault(name, set()).update(refs)

    # -- imports ----------------------------------------------------------
    def _imports(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.aliases[a.asname] = a.name
                    else:
                        top = a.name.split(".")[0]
                        self.aliases[top] = top
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for a in node.names:
                    if a.name == "*":
                        self.star.append(node.module)
                    else:
                        self.aliases[a.asname or a.name] = node.module + "." + a.name

    def _student_names(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, _DEFS):
                self.bound.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                self.bound.add(node.id)

    # -- what a statement changes ------------------------------------------
    def _is_student_callable(self, func):
        r = _root(func)
        return r is not None and r in self.bound and r not in self.aliases

    def _changed(self, stmt, local=None):
        """Names a simple statement may change. `local`: names local to the
        enclosing function (not module-level) -- ignored."""
        out = []
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                out.extend(_target_roots(t))
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)):
            out.extend(_target_roots(stmt.target))
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute):
                r = _root(call.func.value)
                if r:
                    out.append(r)
            if self._is_student_callable(call.func):
                for a in list(call.args) + [k.value for k in call.keywords]:
                    r = _root(a)
                    if r:
                        out.append(r)
        for node in ast.walk(stmt):
            if isinstance(node, ast.NamedExpr):
                out.append(node.target.id)
        if local is not None:
            out = [n for n in out if n not in local]
        return out

    # -- statements ---------------------------------------------------------
    def _stmt(self, stmt, ctx, fname):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            return
        if isinstance(stmt, _DEFS):
            refs = self._refs(stmt, fname) | ctx
            self._add(stmt.name, refs)
            if not isinstance(stmt, ast.ClassDef):
                me = {(stmt.name, stmt.name, stmt.lineno, fname)}
                for name in self._changed_by_function(stmt):
                    self._add(name, me)
            return
        if isinstance(stmt, _COMPOUND):
            header = set()
            for field, value in ast.iter_fields(stmt):
                if field in _BODY_FIELDS:
                    continue
                for v in (value if isinstance(value, list) else [value]):
                    if isinstance(v, ast.AST):
                        self._refs(v, fname, header)
            inner = ctx | header
            if isinstance(stmt, (ast.For, ast.AsyncFor)):
                for n in _target_roots(stmt.target):
                    self._add(n, inner)
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars is not None:
                        for n in _target_roots(item.optional_vars):
                            self._add(n, inner)
            for field in _BODY_FIELDS:
                for child in getattr(stmt, field, None) or []:
                    if isinstance(child, ast.ExceptHandler):
                        if child.name:
                            self._add(child.name, inner)
                        for s in child.body:
                            self._stmt(s, inner, fname)
                    elif hasattr(ast, "match_case") and isinstance(child, ast.match_case):
                        case_ctx = inner | self._refs(child.pattern, fname)
                        if child.guard is not None:
                            case_ctx |= self._refs(child.guard, fname)
                        for s in child.body:
                            self._stmt(s, case_ctx, fname)
                    else:
                        self._stmt(child, inner, fname)
            return
        refs = self._refs(stmt, fname) | ctx
        for name in self._changed(stmt):
            self._add(name, refs)

    def _changed_by_function(self, fdef):
        """Module-level names a function may change when it runs."""
        declared_global = set()
        for node in ast.walk(fdef):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                declared_global.update(node.names)
        local = _function_locals(fdef)
        out = set()
        for node in ast.walk(fdef):
            if isinstance(node, ast.stmt) and not isinstance(node, _DEFS + _COMPOUND):
                out.update(self._changed(node, local))
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) \
                    and node.id in declared_global:
                out.add(node.id)
        return out

    def add_file(self, source, fname):
        tree = ast.parse(source, filename=fname)
        self._imports(tree)
        self._student_names(tree)
        return tree

    def build(self, trees):
        for tree, fname in trees:
            for stmt in tree.body:
                self._stmt(stmt, set(), fname)

    # -- matching -------------------------------------------------------------
    def _resolutions(self, root, dotted):
        """[(parts, first_matchable_index)] for one use in the code."""
        parts = dotted.split(".")
        if root in self.aliases:
            return [(self.aliases[root].split(".") + parts[1:], 0)]
        if root in self.bound:
            return [(parts, 1)]        # the student's own name: only its attributes
        out = [(parts, 0)]
        for m in self.star:
            out.append((m.split(".") + parts, 0))
        return out

    @staticmethod
    def _matches(entry, parts, start):
        e = entry.split(".")
        for i in range(start, len(parts) - len(e) + 1):
            if parts[i:i + len(e)] == e:
                return True
        return False

    def find(self, target, forbidden):
        """[(entry, line, file)] for each forbidden entry used on the way to
        `target` (first use found per entry), in rubric order."""
        hits = {}
        seen, stack = set(), [target]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            for root, dotted, line, fname in sorted(self.deps.get(name, ()), key=lambda r: (r[3], r[2])):
                resolutions = self._resolutions(root, dotted)
                full = resolutions[0][0]
                if full and full[0] in self.helper_modules:
                    stack.extend(full[1:])      # the student's own module: follow
                    continue
                for entry in forbidden:
                    if entry not in hits and any(self._matches(entry, p, s) for p, s in resolutions):
                        hits[entry] = (line, fname)
                if root in self.bound and root not in self.aliases:
                    stack.append(root)
        return [(e,) + hits[e] for e in forbidden if e in hits]


def build_graph(main_path, helpers_dir=None):
    """Dependency graph of the student's file plus any helper .py modules
    submitted next to it. Raises SyntaxError if the main file does not parse."""
    g = _Graph()
    trees = []
    with open(main_path, encoding="utf-8", errors="replace") as f:
        trees.append((g.add_file(f.read(), main_path), main_path))
    if helpers_dir and os.path.isdir(helpers_dir):
        for name in sorted(os.listdir(helpers_dir)):
            if not name.endswith(".py"):
                continue
            path = os.path.join(helpers_dir, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    trees.append((g.add_file(f.read(), path), path))
                g.helper_modules.add(name[:-3])
            except (OSError, SyntaxError, ValueError):
                pass
    g.build(trees)
    return g


def forbidden_uses(graph, target, forbidden):
    return graph.find(target, [str(e).strip() for e in forbidden if str(e).strip()])


def forbidden_message(hits, main_path=None, show_lines=True):
    """'Do not use brentq for this problem (line 12).'"""
    names = [h[0] for h in hits]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
    msg = f"Do not use {listed} for this problem"
    if show_lines:
        where = []
        for _e, line, fname in hits:
            if main_path and os.path.abspath(fname) == os.path.abspath(main_path):
                where.append(f"line {line}")
            else:
                where.append(f"line {line} of {os.path.basename(fname)}")
        msg += " (" + ", ".join(dict.fromkeys(where)) + ")"
    return msg + "."
