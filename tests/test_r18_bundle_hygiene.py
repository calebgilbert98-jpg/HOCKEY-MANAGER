# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""R18 bundle-hygiene tests.

1. Spec allowlist completeness + Tk-freedom: recompute the static-import
   closure of the native bundle inputs (the puck_dynasty_native entry
   script + native_ui) and assert (a) the spec's _ENGINE_ALLOWLIST is
   exactly that closure (minus the entry script itself, which PyInstaller
   bundles directly), and (b) no closure module has any static import
   (top-level OR deferred) of tkinter/customtkinter -- PyInstaller follows
   deferred imports too, and the spec hard-excludes both libraries.

2. Differential test: buyout_math.buyout_schedule (the tkinter-free
   extraction) is behaviorally identical to windows.buyout_schedule
   (the original) across a fixture matrix -- including with tkinter
   import-blocked, simulating the bundle where the Tk-only windows module
   cannot load.
"""

import ast
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

_EXCLUDED = ("tkinter", "customtkinter")


# ---------------------------------------------------------------------------
# Static-import closure analyzer (mirrors the r18 build-time analyzer).
# ---------------------------------------------------------------------------

def _module_name_for(path):
    rel = os.path.relpath(path, REPO_ROOT)[:-3]
    parts = rel.split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_local_modules():
    mods = {
        # Entry script: a closure root (its static imports seed the graph).
        # It is excluded from the allowlist itself (PyInstaller bundles the
        # entry directly; it is not a hiddenimport).
        "puck_dynasty_native": os.path.join(REPO_ROOT, "puck_dynasty_native.py"),
    }
    for f in os.listdir(REPO_ROOT):
        if f.endswith(".py") and os.path.isfile(os.path.join(REPO_ROOT, f)):
            name = f[:-3]
            if name.startswith(("qa_", "pt")):
                continue
            if name == "puck_dynasty_native":
                continue
            mods[name] = os.path.join(REPO_ROOT, f)
    for pkg in ("native_ui", "multiplayer"):
        base = os.path.join(REPO_ROOT, pkg)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for f in filenames:
                if f.endswith(".py"):
                    full = os.path.join(dirpath, f)
                    mods[_module_name_for(full)] = full
    return mods


def _static_imports(path, modname):
    """Literal import targets (import X / from X import). importlib calls
    with non-literal args are invisible to PyInstaller and ignored here."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    pkg = modname.rpartition(".")[0] if "." in modname else ""

    def _abs(name, level):
        if level == 0:
            return name
        base = pkg
        for _ in range(level - 1):
            base = base.rpartition(".")[0]
        return f"{base}.{name}" if name else base

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(_abs(node.module, node.level))
            elif node.level:
                imports.append(_abs("", node.level))
    return imports


def _tk_import_lines(path):
    """Lines with problematic references to excluded libs.

    - `import X` / `from X import ...` (any depth): ALWAYS a problem --
      PyInstaller follows every static import, so the excluded lib would
      be pulled into the bundle graph.
    - `__import__("X")` / `importlib.import_module("X")` with a literal
      excluded-lib name: only a problem if UNGUARDED at module level
      (it would raise at import time). Guarded uses (try/except
      ImportError, e.g. the R18 lazy-import pattern) are intentional and
      allowed.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    # Collect Try nodes whose handlers catch ImportError (guarded regions).
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                if h.type is None:
                    guarded.add(id(node))
                    break
                names = []
                if isinstance(h.type, ast.Name):
                    names = [h.type.id]
                elif isinstance(h.type, ast.Tuple):
                    names = [e.id for e in h.type.elts
                             if isinstance(e, ast.Name)]
                if "ImportError" in names or "Exception" in names:
                    guarded.add(id(node))
                    break

    # Map each node to its enclosing Try (if guarded).
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node

    def _is_guarded(node):
        cur = node
        while id(cur) in parent:
            cur = parent[id(cur)]
            if isinstance(cur, ast.Try) and id(cur) in guarded:
                return True
        return False

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in _EXCLUDED:
                    hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _EXCLUDED:
                hits.append(node.lineno)
        elif isinstance(node, ast.Call):
            func = node.func
            is_dyn = False
            if isinstance(func, ast.Name) and func.id == "__import__":
                is_dyn = True
            elif (isinstance(func, ast.Attribute)
                  and func.attr == "import_module"
                  and isinstance(func.value, ast.Name)
                  and func.value.id == "importlib"):
                is_dyn = True
            if (is_dyn and node.args
                    and isinstance(node.args[0], ast.Constant)):
                arg = node.args[0].value
                # Only module-level unguarded dynamic imports are
                # dangerous (they execute at import time). Function-level
                # calls are deferred and safe; guarded calls (try/except
                # ImportError) are the intentional R18 pattern.
                if (isinstance(arg, str)
                        and arg.split(".")[0] in _EXCLUDED
                        and not _is_guarded(node)
                        and _is_module_level(tree, node)):
                    hits.append(node.lineno)
    return hits


def _is_module_level(tree, target):
    """True if target is at module level (not inside a FunctionDef)."""
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    cur = target
    while id(cur) in parent:
        cur = parent[id(cur)]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
    return True


def _closure(mods, roots):
    seen, stack = set(), list(roots)
    while stack:
        m = stack.pop()
        if m in seen or m not in mods:
            continue
        seen.add(m)
        for imp in _static_imports(mods[m], m):
            cand = imp
            while cand:
                if cand in mods and cand not in seen:
                    stack.append(cand)
                    break
                cand = cand.rpartition(".")[0]
    return seen


def _spec_allowlist():
    src = open(os.path.join(REPO_ROOT, "puck_dynasty_native.spec"),
               encoding="utf-8").read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_ENGINE_ALLOWLIST":
                    return ast.literal_eval(node.value)
    raise AssertionError("spec has no _ENGINE_ALLOWLIST")


# ---------------------------------------------------------------------------
# 1. Allowlist completeness + Tk-freedom
# ---------------------------------------------------------------------------

def test_allowlist_matches_static_closure():
    mods = _iter_local_modules()
    roots = {"puck_dynasty_native"}
    roots.update(m for m in mods
                 if m == "native_ui" or m.startswith("native_ui."))
    closure = _closure(mods, roots)
    # The entry script seeds the graph but is not itself a hiddenimport.
    closure.discard("puck_dynasty_native")
    allow = _spec_allowlist()
    assert set(allow) == closure, (
        "allowlist/closure mismatch: "
        f"missing={sorted(closure - set(allow))[:10]} "
        f"extra={sorted(set(allow) - closure)[:10]}"
    )


def test_no_closure_module_statically_imports_excluded_libs():
    mods = _iter_local_modules()
    roots = {"puck_dynasty_native"}
    roots.update(m for m in mods
                 if m == "native_ui" or m.startswith("native_ui."))
    closure = _closure(mods, roots)
    offenders = {}
    for m in sorted(closure):
        lines = _tk_import_lines(mods[m])
        if lines:
            offenders[m] = lines
    assert not offenders, (
        "closure modules with static tkinter/customtkinter imports: "
        + str(offenders)
    )


# ---------------------------------------------------------------------------
# 2. buyout_schedule differential test
# ---------------------------------------------------------------------------

class _Contract:
    def __init__(self, salary, years_remaining):
        self.salary = salary
        self.years_remaining = years_remaining


class _Player:
    def __init__(self, age, salary, years_remaining):
        self.age = age
        self.contract = _Contract(salary, years_remaining)


_FIXTURES = [
    # (age, salary, years_remaining)
    (24, 5_000_000, 4),     # under-26 -> 1/3
    (25, 5_000_000, 4),     # boundary: 25 < 26 -> 1/3
    (26, 5_000_000, 4),     # boundary: 26 -> 2/3
    (34, 8_000_000, 2),     # veteran 2/3
    (20, 925_000, 3),       # ELC
    (38, 1_000_000, 1),     # minimum term
    (30, 10_500_000, 7),    # max term, big money
    (29, 0, 3),             # zero salary -> zeros
    (29, 4_000_000, 0),     # zero years -> zeros
    (22, 1, 8),             # tiny salary
]


def _reference_buyout_schedule(player):
    """Independent reference implementation of the NHL buyout rule, written
    from the documented behavior (not copied from either module)."""
    salary = player.contract.salary
    years = player.contract.years_remaining
    if years <= 0 or salary <= 0:
        return 0, 0, 0, []
    fraction = 1 / 3 if player.age < 26 else 2 / 3
    total_cost = salary * years * fraction
    buyout_years = 2 * years
    annual = total_cost / buyout_years
    rows = []
    for i in range(1, buyout_years + 1):
        savings = salary - annual if i <= years else -annual
        rows.append((i, annual, savings))
    return total_cost, annual, buyout_years, rows


def _results(fn):
    out = []
    for age, salary, years in _FIXTURES:
        p = _Player(age, salary, years)
        total, annual, buyout_years, rows = fn(p)
        out.append((total, annual, buyout_years, [tuple(r) for r in rows]))
    return out


def test_buyout_schedule_matches_reference_implementation():
    import buyout_math
    assert _results(buyout_math.buyout_schedule) == \
        _results(_reference_buyout_schedule)


def test_windows_buyout_schedule_delegates_to_buyout_math():
    """The legacy windows.buyout_schedule path must resolve to the same
    implementation the bundle ships (criterion 4: identical source/bundle)."""
    import buyout_math
    import windows
    assert windows._buyout_schedule_impl is buyout_math.buyout_schedule
    p = _Player(30, 6_000_000, 3)
    assert windows.buyout_schedule(p) == buyout_math.buyout_schedule(p)


def test_buyout_math_importable_with_tkinter_blocked():
    """Simulate the bundle: tkinter/customtkinter cannot be imported."""
    import builtins
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name.split(".")[0] in _EXCLUDED:
            raise ImportError(f"blocked for test: {name}")
        return real_import(name, *args, **kwargs)

    for mod in list(sys.modules):
        if mod.split(".")[0] in ("buyout_math", "windows"):
            del sys.modules[mod]
    builtins.__import__ = _blocked
    try:
        import buyout_math
        importlib.reload(buyout_math)
        p = _Player(30, 6_000_000, 3)
        total, annual, years, rows = buyout_math.buyout_schedule(p)
        assert total == 6_000_000 * 3 * (2 / 3)
        assert years == 6
        assert len(rows) == 6
    finally:
        builtins.__import__ = real_import
