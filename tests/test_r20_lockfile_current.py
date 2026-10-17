"""R20 — Pin all dependencies: lockfile currency check.

Stdlib only, so CI can run it with plain `python` (no pytest install needed):

    python tests/test_r20_lockfile_current.py

Checks:
  1. requirements-lock.txt pins every dependency to an EXACT version
     (no `>=` ranges, no bare names) — the "lock" is a lock.
  2. Every non-commented entry in requirements.txt has a locked version that
     satisfies its specifier. So if someone bumps requirements.txt without
     regenerating the lock, this fails — the lock is the single source of
     truth CI installs.
  3. Every GitHub workflow (*.yml and *.yaml, recursively) installs Python
     packages ONLY from the lockfile. Only `run:` step bodies are scanned
     (`run:`/`- run:` with optional step anchors/tags, quoted keys, and
     space before the colon; inline / `|` / `>` forms; multi-line plain
     scalars folded; step names and descriptions are not shell — non-`run`
     block scalars are skipped; flow-style `- {run: ...}`,
     `steps: [{...}, {run: ...}]` (single- or multi-line, bare or quoted
     `run` keys) fail closed).
     Inline `run:` values get YAML comments
     stripped quote-aware, then one layer of YAML scalar quoting stripped. shlex-tokenized with
     backslash continuations joined, `;`/`&&`/`||`/`|`-separated commands
     checked individually, and Windows backslash paths preserved; heredoc
     bodies are skipped only for known data-consumers (cat/grep/...),
     scanned for interpreters (bash/python/...) and fail-closed when
     unterminated; YAML anchors/tags/aliases and flow-style mappings on
     `run:` fail closed rather than being silently skipped. A `pip ...
     install` is recognized with the pip token
     (pip/pip3/pip3.11/pip.exe/pipx, path-qualified, any case; `uv`/`uvx`
     `pip` likewise) at command position — optionally behind shell
     keywords/grouping (`if`/`then`/`do`/`!`/`(`/`{`/case-patterns, which
     never change what is executed) and launcher prefixes (sudo/env/nice/
     stdbuf/exec with their flags — including `env -S/--split-string`,
     whose value is argv and gets expanded, not skipped; command/setsid/time
     with flag-only options; bare VAR= assignments; builtin/nohup/coproc
     (bash NAME rule: the word after coproc is a name only when a compound
     command follows it); python[3[.x]]/py -m with general interpreter
     flags; uv/uvx with global options). Backslash-escaped command words
     and ANSI-C $'...' quoting are normalized to what the shell executes.
     pip reached via xargs fails closed (stdin can supply args).
     — and the FIRST `install` token after it is the subcommand, so
     global options cannot hide it. The argument list is parsed, not
     substring-matched: only `--upgrade pip` and
     `-r/--requirement[=] requirements-lock.txt` are allowed, solely.
     `;`/`&&`/`||`/`|`-separated commands are split quote-aware before
     tokenizing, so attached separators neither hide installs nor
     false-flag legit lines.
  4. Every setup-python step pins an exact Python version matching the
     interpreter declared in the lockfile header (quoted keys and
     space-before-colon spellings count; `python-version-file` targets are
     read and compared, missing file fails closed).
  5. Every workflow that installs Python packages really contains a
     "Verify lockfile is current" step (a comment mentioning it is not
     enough).

Known limits (documented, not bugs): the scan cannot see through deliberate
evasion (shell-variable indirection, command substitution, eval,
runtime-generated scripts, delegated execution like `sh -c`/`find -exec`)
— the threat model is accidental drift, and every change batch still gets
3-reviewer + Copilot review. Transitive deps are intentionally NOT pinned:
the R20 item scopes to the named loose direct pins; pip resolves transitives
at install time.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "requirements-lock.txt"
REQS = REPO / "requirements.txt"
WORKFLOWS = REPO / ".github" / "workflows"

_PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-+*!]+)$")
_REQ_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(.*)$")
_SPEC_CLAUSE_RE = re.compile(r"^(>=|<=|==|!=|~=|>|<)\s*([A-Za-z0-9_.\-+*!]+)$")


def _vparts(version):
    # ("6.12.0") -> (6, 12, 0). Non-numeric tails (rc1, +local) sort as strings
    # after their numeric prefix; only numeric versions are compared here.
    parts = []
    for p in re.split(r"[.\-+_]", version):
        parts.append(int(p) if p.isdigit() else p)
    return tuple(parts)


def _cmp(a, b):
    a, b = _vparts(a), _vparts(b)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    for x, y in zip(a, b):
        if type(x) is not type(y):
            x, y = str(x), str(y)
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def _satisfies(version, spec):
    """True if `version` satisfies a PEP-440-ish specifier string."""
    spec = spec.strip().rstrip(";").strip()
    if not spec:
        return True
    for clause in spec.split(","):
        clause = clause.strip()
        m = _SPEC_CLAUSE_RE.match(clause)
        assert m, f"unsupported specifier clause: {clause!r}"
        op, want = m.group(1), m.group(2)
        c = _cmp(version, want)
        if op == "==":
            ok = c == 0
        elif op == "!=":
            ok = c != 0
        elif op == ">=":
            ok = c >= 0
        elif op == "<=":
            ok = c <= 0
        elif op == ">":
            ok = c > 0
        elif op == "<":
            ok = c < 0
        elif op == "~=":  # >= want, == want's prefix (e.g. ~=1.4 -> >=1.4, ==1.*)
            wp = _vparts(want)
            vp = _vparts(version)
            ok = c >= 0 and vp[: len(wp) - 1] == wp[: len(wp) - 1]
        else:  # pragma: no cover — regex above is exhaustive
            raise AssertionError(op)
        if not ok:
            return False
    return True


def _parse_lock(lock_path):
    locked = {}
    for lineno, raw in enumerate(lock_path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _PIN_RE.match(line)
        assert m, (
            f"{lock_path.name}:{lineno}: not an exact pin: {raw!r} "
            "(lockfile entries must be `name==version`)"
        )
        name = m.group(1).lower()
        assert name not in locked, f"{lock_path.name}:{lineno}: duplicate {name}"
        locked[name] = m.group(2)
    assert locked, f"{lock_path.name} has no pinned entries"
    return locked


def _parse_requirements(reqs_path):
    reqs = {}
    for lineno, raw in enumerate(reqs_path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _REQ_RE.match(line)
        assert m, f"{reqs_path.name}:{lineno}: unparseable line: {raw!r}"
        reqs[m.group(1).lower()] = m.group(2).strip()
    return reqs


def _check_lock_satisfies_requirements(lock_path, reqs_path, locked, reqs):
    for name, spec in reqs.items():
        assert name in locked, (
            f"{reqs_path.name} names {name}{spec} but {lock_path.name} has no pin for it"
        )
        assert _satisfies(locked[name], spec), (
            f"{lock_path.name} pins {name}=={locked[name]} which does not satisfy "
            f"{reqs_path.name} specifier {spec!r} — regenerate the lock"
        )


def _workflow_files(workflows_dir):
    return sorted(workflows_dir.rglob("*.yml")) + sorted(
        workflows_dir.rglob("*.yaml")
    )


_PIP_NAME_RE = re.compile(r"^pip(\d+(\.\d+)*)?(\.exe)?$", re.IGNORECASE)
_PY_LAUNCHER_RE = re.compile(r"^python(\d+(\.\d+)*)?$", re.IGNORECASE)
_HEREDOC_RE = re.compile(
    r"<<-?\s*(?:'([A-Za-z_][A-Za-z0-9_-]*)'|"
    r'"([A-Za-z_][A-Za-z0-9_-]*)"|'
    r"([A-Za-z_][A-Za-z0-9_-]*))"
)
# C7/1: accept `- run:`, `- run :`, `- &anchor run:`, `- "run":` spellings —
# all valid YAML that Actions executes.
_RUN_RE = re.compile(
    r"^(\s*)(?:-\s+)?(?:[&!]\S+\s+)*(?:\"run\"|'run'|run)\s*:(.*)$"
)
# Non-run block scalars (C7/3a): `description: |` etc. — their bodies are
# not shell and must be skipped, not scanned.
_BLOCK_SCALAR_RE = re.compile(r"^(\s*)\S.*:\s*[|>][+-]?\d*\s*(?:#.*)?$")

# `run` key inside flow mappings (C10): bare `run:` or quoted `"run":` /
# `'run':` — YAML parses both to the same key, and Actions executes them.
# The bare form must not be preceded by a word char or quote, so a string
# value like `'run: x'` is not mistaken for a key.
_FLOW_RUN_KEY_RE = re.compile(r"""(?:"run"|'run'|(?<![\w'"])run)\s*:""")
_VERIFY_STEP_RE = re.compile(
    r"(?m)^\s*-\s*(?:[&!]\S+\s+)*(?:\"name\"|'name'|name)\s*:"
    r".*[Vv]erify lockfile is current"
)
# Heredoc consumers that treat the body as DATA (inert). Anything else
# (bash/sh/python/unknown...) gets its body scanned as shell — fail-closed.
_INERT_HEREDOC_COMMANDS = {
    "cat", "tee", "grep", "egrep", "fgrep", "sed", "awk", "gawk",
    "head", "tail", "wc", "sort", "uniq", "tr", "cut", "paste",
    "join", "comm", "diff", "patch", "column", "expand", "unexpand",
    "fold", "less", "more", "nl", "od", "xxd", "base64",
}
# Value-taking options for launcher prefixes (C3/5). Unknown flags are
# treated as flags; only these consume the following token.
_LAUNCHER_VALUE_OPTS = {
    "sudo": {
        "-u", "--user", "-g", "--group", "-p", "--prompt",
        "-D", "--chdir", "-C", "--close-from", "-r", "--role",
        "-t", "--type", "-T", "--command-timeout", "-U", "--other-user",
    },
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "xargs": {
        "-d", "--delimiter", "-n", "--max-args", "-P", "--max-procs",
        "-I", "--replace", "-a", "--arg-file", "-E", "--eof", "-e",
        "-s", "--max-chars", "-L", "--max-lines", "--process-slot-var",
    },
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},  # A6/2
    "exec": {"-a"},  # A6/2: `exec -a name cmd`
}
# Shell keywords / grouping that may precede the command word in ordinary
# CI shell (`if ...; then pip install ...; fi`, `(pip install ...)`,
# `{ pip install ...; }`, `! pip install ...`). Stripped before the
# command-position check (C5) — they never change WHAT is executed.
_SHELL_KEYWORDS = {
    "if", "then", "elif", "else", "fi", "for", "while", "until",
    "do", "done", "esac", "in", "!",
}
_BARE_LAUNCHERS = {"builtin", "nohup"}  # genuinely flagless (A6/2)
_FLAG_LAUNCHERS = {"command", "setsid", "time"}  # flags take no values (A6/2)


def _split_shell_commands(shell):
    """Split a shell line into commands at ; && || | & (C4/1).

    Quote-aware: separators inside single/double quotes or backslash-escaped
    do not split. shlex alone cannot do this — it leaves `;` glued to words
    (`'echo ok; pip install x'` -> `['echo', 'ok;', 'pip', ...]`), which hid
    real installs and false-flagged legit `lock; echo done` lines.
    """
    segs, cur, q = [], [], None
    i, n = 0, len(shell)
    while i < n:
        c = shell[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < n:
                cur.append(shell[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in ("'", '"'):
            q = c
            cur.append(c)
        elif c == "\\" and i + 1 < n:
            cur.append(c)
            cur.append(shell[i + 1])
            i += 1
        elif shell.startswith("&&", i) or shell.startswith("||", i):
            segs.append("".join(cur))
            cur = []
            i += 1
        elif c in ";|&":
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [s for s in segs if s.strip()]


def _shell_unescape(tok):
    r"""Undo POSIX backslash unescaping for one shlex token (C8/1).

    The caller doubles backslashes before shlex (to protect Windows paths),
    so an UNQUOTED `in\stall` arrives here with one backslash while a
    single-quoted `'in\stall'` arrives with two. Collapsing `\c` -> `c`
    therefore reproduces what the shell really executes for unquoted words
    (`p\ip` -> `pip`) without resurrecting quoted ones.
    """
    return re.sub(r"\\(.)", r"\1", tok, flags=re.DOTALL)


def _expand_ansi_c_quotes(s):
    """Expand bash ANSI-C quoting `$'...'` before shlex (C8/7).

    shlex does not understand `$'...'`, so `pip $'install' x` would tokenize
    opaquely and hide the install. Expansion runs on the raw command text;
    the result flows through the normal backslash-doubling + shlex path.
    """
    import codecs

    out = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == "$" and i + 1 < n and s[i + 1] == "'":
            j = i + 2
            buf = []
            closed = False
            while j < n:
                c = s[j]
                if c == "\\" and j + 1 < n:
                    buf.append(c)
                    buf.append(s[j + 1])
                    j += 2
                elif c == "'":
                    closed = True
                    break
                else:
                    buf.append(c)
                    j += 1
            if closed:
                try:
                    expanded = codecs.decode("".join(buf), "unicode_escape")
                except Exception:
                    expanded = "".join(buf)
                expanded = expanded.replace("\\e", "\x1b").replace(
                    "\\E", "\x1b"
                )
                out.append(expanded)
                i = j + 1
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _is_pip_token(tok):
    base = re.split(r"[/\\]", tok)[-1]  # strip path qualifiers (C2/B)
    if _PIP_NAME_RE.match(base):  # pip/pip3/pip3.11/pip.exe (C2/C,H5,H10)
        return True
    # C8/1: `p\\ip` — also try the shell-unescaped view.
    base_u = re.split(r"[/\\]", _shell_unescape(tok))[-1]
    return bool(_PIP_NAME_RE.match(base_u))


# Sentinel: pip found but its args are unverifiable (C8/6: xargs stdin).
_UNVERIFIABLE = object()
# uv global options that take a separate value (C8/3).
_UV_VALUE_OPTS = {
    "--python", "-p", "--project", "--directory", "--cache-dir",
    "--python-preference", "--color", "--config-file",
}


def _skip_options(toks, i, value_opts):
    n = len(toks)
    while i < n:
        t = toks[i]
        if not t.startswith("-") or t == "-":
            return i
        name = t.split("=", 1)[0]
        i += 1 if ("=" in t or name not in value_opts) else 2
    return i


def _is_compound_start(tok):
    """Does this token start a compound command? (C6/1, coproc NAME rule)"""
    if not tok:
        return False
    if tok[0] in "({":
        return True
    tl = tok.lower()
    return (
        tl in ("if", "for", "while", "until", "case", "select")
        or tok.startswith("((")
        or tok.startswith("[[")
    )


def _denoise_tokens(toks):
    """Strip shell keywords/grouping that precede the command word (C5).

    `if`, `then`, `do`, `!`, `(`, `{`, case-patterns (`x)`) never change
    WHAT is executed — removing them lets the command-position check see
    `pip install` in ordinary constructs like
    `if true; then pip install x; fi` or `(pip install x)`.
    """
    out = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        while len(t) > 1 and t[0] in "({":
            # Don't eat brace-group values like `{}` (xargs -I {}) — A6/1.
            if t[1:].strip(")}") == "":
                break
            t = t[1:]  # `(pip` -> `pip`
        tl = t.lower()
        if tl == "coproc":
            # bash: `coproc [NAME] compound-cmd` | `coproc simple-cmd`.
            # NAME exists only when a compound command follows the next
            # word — `coproc MYNAM touch` actually tries to RUN `MYNAM`
            # (verified against bash), so only skip the word after coproc
            # when the word after THAT starts a compound command (C6/1).
            out.append(t)
            i += 1
            nxt = toks[i] if i < n else ""
            nxt2 = toks[i + 1] if i + 1 < n else ""
            if nxt and _is_compound_start(nxt2) and not _is_compound_start(nxt):
                i += 1  # skip NAME
            continue
        if tl == "case":
            i += 1  # skip `case WORD in`
            if i < n:
                i += 1
            if i < n and toks[i].lower() == "in":
                i += 1
            continue
        if tl in _SHELL_KEYWORDS or t in ("(", ")", "{", "}"):
            i += 1
            continue
        if t.endswith(")") and t.strip("(){}") != "" and "=" not in t:
            i += 1  # case pattern `x)` / `x|y)` — never a command word
            continue
        out.append(t)
        i += 1
    return out


def _expand_env_options(toks, env_idx):
    """Expand `env -S/--split-string` values into argv (C6/2).

    GNU env -S splits its value into words and splices them as arguments,
    so `env -S'pip install x'` really executes `pip install x` — skipping
    the value would hide the install. Expansion is done in place so the
    spliced words go through normal option processing afterwards.
    Returns (new_tokens, next_index) with next_index past env's options.
    Terminates: every -S handling strictly reduces total token chars
    (shlex.split drops quote chars), other branches advance the index.
    """
    import shlex

    words = list(toks)
    i = env_idx + 1
    while i < len(words):
        tok = words[i]
        if tok in ("-S", "--split-string"):
            if i + 1 < len(words):
                words[i : i + 2] = shlex.split(words[i + 1])
            else:
                del words[i]
            continue  # re-examine spliced words
        if tok.startswith("--split-string="):
            words[i : i + 1] = shlex.split(tok.split("=", 1)[1])
            continue
        if tok.startswith("-S") and not tok.startswith("--") and len(tok) > 2:
            # attached form: -S'...' (shlex glued the quoted value)
            words[i : i + 1] = shlex.split(tok[2:])
            continue
        if tok.startswith("-") and tok != "-":
            # ordinary env option: skip it (+ its value if value-taking)
            name = tok.split("=", 1)[0]
            i += 1
            if "=" not in tok and name in _LAUNCHER_VALUE_OPTS["env"]:
                i += 1
            continue
        break
    return words, i


def _find_pip_install(toks):
    """Locate `pip ... install <args>` in one command's shlex tokens.

    Shell keyword/grouping noise is stripped first (C5); then the pip token
    must be at command position (optionally behind launcher prefixes:
    sudo/env/nice/xargs with their flags, bare VAR= assignments,
    command/builtin/exec/time/nohup/setsid/stdbuf, python[3[.x]]/py -m with
    general interpreter flags (C8/2), uv/uvx with global options (C8/3)) so
    `echo pip install x` is not flagged. Comparisons use the shell-unescaped
    token view (C8/1: `p\\ip` really runs pip). The FIRST `install`
    token after it is the subcommand — global options (flag- or
    value-taking, C2/A) between them cannot hide it.
    Returns the arg list after `install`, the _UNVERIFIABLE sentinel when
    pip is reached via xargs (stdin can supply arbitrary args, C8/6), or
    None.
    """
    toks = _denoise_tokens(toks)
    # Comparisons below use the shell-unescaped view (C8/1: `p\ip` really
    # runs `pip`); _is_pip_token takes the raw token and tries both views
    # internally so Windows paths (`venv\Scripts\pip.exe`) still match.
    n = len(toks)
    saw_xargs = False
    i = 0
    while i < n:
        t = _shell_unescape(toks[i]).lower()
        if t in _BARE_LAUNCHERS or t == "coproc":  # coproc NAME resolved above
            i += 1
            continue
        if t in _FLAG_LAUNCHERS:
            i = _skip_options(toks, i + 1, set())
            continue
        if t == "env":
            toks, i = _expand_env_options(toks, i)
            n = len(toks)
            while i < n and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=",
                                     _shell_unescape(toks[i])):
                i += 1
            continue
        if t in _LAUNCHER_VALUE_OPTS:
            if t == "xargs":
                saw_xargs = True
            i = _skip_options(toks, i + 1, _LAUNCHER_VALUE_OPTS[t])
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", _shell_unescape(toks[i])):
            i += 1  # bare VAR=value prefix (C3/3: `FOO=1 pip install ...`)
            continue
        if _PY_LAUNCHER_RE.match(t) or t == "py":  # C3/2: python3.12, py -3
            j = i + 1
            if t == "py":
                while j < n and re.match(r"^-\d+(\.\d+)?$",
                                         _shell_unescape(toks[j])):
                    j += 1
            # C8/2: skip general interpreter flags (`python -W ignore
            # -m pip ...`). -W/-X/-Q take a separate value; -c/-- end
            # option scanning (what follows is not `python -m pip`).
            while j < n:
                fj = _shell_unescape(toks[j])
                if fj == "-m":
                    break
                if not fj.startswith("-") or fj == "-":
                    return None
                if fj in ("-c", "--"):
                    return None
                j += 1
                if fj in ("-W", "-X", "-Q"):
                    j += 1  # skip the flag's value too
            if j < n and _shell_unescape(toks[j]) == "-m":
                i = j + 1
                continue
            return None
        if t in ("uv", "uvx"):  # C4/4: `uv pip install ...`
            j = i + 1
            # C8/3: skip uv global options (`uv -q pip install ...`).
            while j < n:
                fj = _shell_unescape(toks[j])
                if not fj.startswith("-") or fj == "-":
                    break
                j += 1
                name = fj.split("=", 1)[0]
                if "=" not in fj and name in _UV_VALUE_OPTS:
                    j += 1  # skip the option's value too
            if j < n and _is_pip_token(toks[j]):
                i = j  # j already points at the pip token
                continue
            return None
        break
    if i >= n or not (_is_pip_token(toks[i])
                      or _shell_unescape(toks[i]).lower() == "pipx"):
        # pipx's `install` subcommand takes the same allowlist (C4/4)
        return None
    if saw_xargs:
        # xargs appends stdin-supplied args: even `xargs pip install -r
        # requirements-lock.txt` can install extra packages, so the args
        # are unverifiable — fail closed (C8/6).
        return _UNVERIFIABLE
    for k in range(i + 1, n):
        if _shell_unescape(toks[k]).lower() == "install":
            # Return the shell's real view of the args: `pip install -r
            # requi\rements-lock.txt` really installs from the lockfile.
            return [_shell_unescape(a) for a in toks[k + 1:]]
    return None


def _install_args_allowed(rest):
    # Exact allowlist on the parsed argument list (C/H2,H3 — no substrings).
    return rest == ["--upgrade", "pip"] or rest in (
        ["-r", "requirements-lock.txt"],
        ["--requirement", "requirements-lock.txt"],
        ["--requirement=requirements-lock.txt"],  # `=` form (C2/FP1)
        ["-rrequirements-lock.txt"],  # attached short form (C2/FP2)
    )


def _heredoc_body_is_inert(opener_text):
    """True if the heredoc body is data, not code (C2/E)."""
    import shlex

    try:
        toks = shlex.split(opener_text, comments=True, posix=True)
    except ValueError:
        return False  # fail closed
    for tok in toks:
        tl = tok.lower()
        if tl == "sudo":
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            continue
        base = re.split(r"[/\\]", tok)[-1].lower()
        return base in _INERT_HEREDOC_COMMANDS
    return False


def _strip_yaml_comment(s):
    """Strip a YAML `#` comment, quote-aware (C7/2).

    `#` starts a comment at line start, after whitespace, or right after a
    closed quoted scalar (`'pip install x'#evil` — PyYAML drops `#evil`).
    Inside quotes it is literal. Must run BEFORE `_unquote_yaml_scalar`,
    or a trailing comment blocks unquoting and hides the install.
    """
    out = []
    i, n = 0, len(s)
    q = None
    while i < n:
        c = s[i]
        if q == "'":
            out.append(c)
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    out.append("'")
                    i += 1
                else:
                    q = None
        elif q == '"':
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 1
            elif c == '"':
                q = None
        elif c in ("'", '"'):
            q = c
            out.append(c)
        elif c == "#":
            prev = out[-1] if out else " "
            if not out or prev in " \t'\"":
                break
            out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def _unquote_yaml_scalar(s):
    """Strip one layer of YAML scalar quoting from an inline `run:` value.

    In `- run: '! pip install x'` the quotes are YAML syntax — the shell
    actually receives `! pip install x`. Without this, shlex sees one big
    quoted token and the install is invisible (C5 follow-up).
    """
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == "'":
            return inner.replace("''", "'")
        return (
            inner.replace("\\\\", "\\")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
        )
    return s


def _run_block_shell_lines(yml_text):
    """Yield (file_lineno, shell_text) from `run:` steps only (C2/FP3).

    Handles `run: <inline>`, `- run: <inline>`, `run: |` (literal) and
    `run: >` (folded — paragraphs joined with spaces per YAML `>`
    semantics, C2/G). Yields real workflow file line numbers (A3 note).
    """
    lines = yml_text.splitlines()
    i = 0
    while i < len(lines):
        m = _RUN_RE.match(lines[i])
        if not m:
            # Skip non-run block-scalar bodies (C7/3a): a `description: |`
            # block containing a `run:`-looking line is documentation, not
            # shell — without this the inner line is misread as a step.
            if lines[i].lstrip()[:1] not in ("#", ""):
                bm = _BLOCK_SCALAR_RE.match(lines[i])
                if bm:
                    b_indent = len(bm.group(1))
                    j = i + 1
                    while j < len(lines):
                        bl = lines[j]
                        if bl.strip() and len(bl) - len(bl.lstrip()) <= b_indent:
                            break
                        j += 1
                    i = j
                    continue
            # Flow-style fail-closed checks (C4/3, C8/8, C9/1). `run:` step
            # lines are handled above (their content is shell-scanned, so no
            # line matches both), and `#` comment lines cannot be steps
            # (C9/2). Trailing comments are stripped first so a commented
            # `[{run: ...}]` cannot false-positive.
            if lines[i].lstrip()[:1] not in ("#", ""):
                noc = _strip_yaml_comment(lines[i])
                if re.match(r"^\s*-\s*\{", noc) and _FLOW_RUN_KEY_RE.search(noc):
                    # C4/3: `- {run: "..."}` — valid YAML/Actions but this
                    # scanner cannot parse it; refuse to silently skip it.
                    raise AssertionError(
                        f"flow-style mapping with run: key is not supported "
                        f"by the lockfile scanner (line {i + 1}): expand it "
                        f"to block style"
                    )
                fb = re.search(r":\s*\[\s*\{", noc)
                if fb and _FLOW_RUN_KEY_RE.search(noc[fb.end():]):
                    # C8/8 + C9/1: `steps: [{...}, {run: ...}]` — `run:` in
                    # ANY flow mapping after the `[{`, not just the first.
                    raise AssertionError(
                        f"flow-style sequence with run: key is not supported "
                        f"by the lockfile scanner (line {i + 1}): expand it "
                        f"to block style"
                    )
                if re.match(r"^\s*\{", noc) and _FLOW_RUN_KEY_RE.search(noc):
                    # C9/1: multi-line flow sequence — `{run: ...}` on its
                    # own line. (`run:` block bodies are consumed above, so
                    # a line-start `{` with a `run:` key here can only be a
                    # flow mapping.)
                    raise AssertionError(
                        f"flow-style mapping with run: key is not supported "
                        f"by the lockfile scanner (line {i + 1}): expand it "
                        f"to block style"
                    )
            i += 1
            continue
        base_indent = len(m.group(1))
        # Strip a trailing YAML comment BEFORE unquoting (C7/2):
        # `'pip install x' # comment` must unquote to the install.
        rest = _strip_yaml_comment(m.group(2).strip())
        if rest and rest[0] in "&*!":
            # YAML anchor/tag/alias on run: (C4/2) — e.g. `run: &anchor |`.
            # The block body that follows would otherwise be silently
            # skipped; fail closed instead.
            raise AssertionError(
                f"anchor/tag/alias on run: is not supported by the lockfile "
                f"scanner (line {i + 1}): {rest[:40]!r}"
            )
        if not rest or rest[0] not in "|>":
            if rest:  # `run: <inline command>`
                # A plain scalar value may continue on following lines that
                # are more indented (YAML folds them with spaces) — e.g.
                # `run: pip install -r lock` / `  numpy` really installs
                # numpy. Gather those lines; stop at dedent, a new `- `
                # step, a `key:` line (`: ` terminates plain scalars), or
                # a blank line. (C6 follow-up.)
                parts = [rest]
                j = i + 1
                while j < len(lines):
                    bl = lines[j]
                    if bl.strip() == "":
                        break
                    cur_ind = len(bl) - len(bl.lstrip())
                    if cur_ind <= base_indent:
                        break
                    s = bl.strip()
                    if (
                        s.startswith("- ")
                        or s.startswith("-#")
                        or re.search(r":(\s|$)", s)
                    ):
                        break
                    if s.startswith("#"):
                        j += 1
                        continue  # comment: contributes nothing, ends nothing
                    parts.append(s)
                    j += 1
                folded = " ".join(parts)
                for sub in _unquote_yaml_scalar(folded).split("\n"):
                    yield (i + 1, sub)
                i = j
                continue
        style = rest[0]
        block_indent = None
        j = i + 1
        paragraph, para_lineno = [], 0
        while j < len(lines):
            bl = lines[j]
            if bl.strip() == "":
                if paragraph and style == ">":
                    yield (para_lineno, " ".join(paragraph))
                    paragraph = []
                j += 1
                continue
            cur_ind = len(bl) - len(bl.lstrip())
            if block_indent is None:
                if cur_ind <= base_indent:
                    break
                block_indent = cur_ind
            if cur_ind < block_indent:
                break
            content = bl[block_indent:]
            if style == ">":
                if not paragraph:
                    para_lineno = j + 1
                paragraph.append(content.strip())
            else:
                yield (j + 1, content)
            j += 1
        if paragraph:
            yield (para_lineno, " ".join(paragraph))
        i = j


def _check_workflows_install_only_from_lock(workflows_dir):
    import shlex

    ymls = _workflow_files(workflows_dir)
    assert ymls, f"no workflow files in {workflows_dir}"
    for yml in ymls:
        text = yml.read_text()
        # Phase 1: join backslash continuations, resolve heredocs.
        logical = []  # (file_lineno, text)
        buf, buf_lineno = "", 0
        heredoc_end, heredoc_opener_lineno = None, 0
        for file_lineno, phys in _run_block_shell_lines(text):
            if heredoc_end is not None:
                if phys.strip() == heredoc_end:
                    heredoc_end = None
                continue
            m = _HEREDOC_RE.search(phys)
            if m:
                marker = m.group(1) or m.group(2) or m.group(3)
                rest = phys[m.end() :]
                # Marker must be followed by EOL/whitespace/`;`/`|`/`&` —
                # excludes shell arithmetic like `echo $((a << b))` (A2/F1).
                if rest == "" or rest[0] in " \t;|&":
                    if _heredoc_body_is_inert(phys):
                        heredoc_end = marker
                        heredoc_opener_lineno = file_lineno
                    # else: body is code (bash/python <<EOF) — keep scanning it
            stripped = phys.rstrip()
            if not buf:
                buf_lineno = file_lineno
            if stripped.endswith("\\") and heredoc_end is None:
                buf += stripped[:-1] + " "
                continue
            logical.append((buf_lineno, buf + phys))
            buf = ""
        if buf:
            logical.append((buf_lineno, buf))
        if heredoc_end is not None:
            # Fail closed (A2/F2): an unterminated heredoc must not silently
            # swallow the rest of the file.
            raise AssertionError(
                f"{yml.name}:{heredoc_opener_lineno}: unterminated heredoc "
                f"<<{heredoc_end} — refusing to scan past it"
            )
        # Phase 2: split into ;-separated commands, tokenize, enforce allowlist.
        has_pip_install = False
        for file_lineno, shell in logical:
            for cmd in _split_shell_commands(shell):
                # Expand ANSI-C $'...' quoting first: shlex does not
                # understand it, so `pip $'install' x` would hide (C8/7).
                # Double backslashes next: POSIX shlex would otherwise mangle
                # Windows paths like venv\Scripts\pip.exe (C3/6). This only
                # affects escape fidelity for detection, not the reported text.
                try:
                    toks = shlex.split(
                        _expand_ansi_c_quotes(cmd).replace("\\", "\\\\"),
                        comments=True,
                        posix=True,
                    )
                    rest = _find_pip_install(toks)
                except ValueError:
                    raise AssertionError(
                        f"{yml.name}:{file_lineno}: unparseable shell line: "
                        f"{shell.strip()!r}"
                    )
                if rest is None:
                    continue
                if rest is _UNVERIFIABLE:
                    raise AssertionError(
                        f"{yml.name}:{file_lineno}: pip invoked via xargs - "
                        f"stdin can supply unverifiable args: "
                        f"{shell.strip()!r}"
                    )
                has_pip_install = True
                if not _install_args_allowed(rest):
                    raise AssertionError(
                        f"{yml.name}:{file_lineno}: pip install bypasses "
                        f"the lockfile: {shell.strip()!r} — install from "
                        "requirements-lock.txt instead"
                    )
        if has_pip_install:
            # The verify step itself must really exist as a step (C2/F) —
            # a comment mentioning it does not count.
            assert _VERIFY_STEP_RE.search(text), (
                f"{yml.name}: installs Python packages but has no "
                "'Verify lockfile is current' step"
            )
def _check_python_version_pinned(lock_path, workflows_dir):
    m = re.search(r"CPython (\d+\.\d+)", lock_path.read_text())
    assert m, f"{lock_path.name} header must declare the build interpreter (CPython X.Y)"
    declared = m.group(1)
    root = workflows_dir.parent.parent
    for yml in _workflow_files(workflows_dir):
        for lineno, line in enumerate(yml.read_text().splitlines(), 1):
            # C8/4: accept quoted keys and space before the colon, like
            # _RUN_RE does — `"python-version": "3.12"` is valid YAML.
            # Must not match `python-version-file:` (handled below).
            pm = re.search(
                r"""["']?python-version["']?\s*:\s*["']?([^"'\s]+)["']?""",
                line,
            )
            if pm:
                assert pm.group(1) == declared, (
                    f"{yml.name}:{lineno}: python-version {pm.group(1)!r} != "
                    f"lock-declared {declared!r}"
                )
            # C8/5: setup-python also accepts `python-version-file`
            # (e.g. `.python-version`) — verify its content matches.
            pfm = re.search(
                r"""["']?python-version-file["']?\s*:\s*["']?([^"'\s]+)["']?""",
                line,
            )
            if pfm:
                ver_path = root / pfm.group(1)
                assert ver_path.is_file(), (
                    f"{yml.name}:{lineno}: python-version-file "
                    f"{pfm.group(1)!r} not found — cannot verify interpreter"
                )
                ver_text = ver_path.read_text().strip().split()
                ver_text = ver_text[0] if ver_text else ""
                assert ver_text == declared or ver_text.startswith(
                    declared + "."
                ), (
                    f"{yml.name}:{lineno}: python-version-file "
                    f"{ver_text!r} != lock-declared {declared!r}"
                )


def verify_lockfile(repo_root=None):
    root = Path(repo_root).resolve() if repo_root else REPO
    lock_path, reqs_path = root / "requirements-lock.txt", root / "requirements.txt"
    workflows_dir = root / ".github" / "workflows"
    assert lock_path.exists(), f"missing {lock_path}"
    assert reqs_path.exists(), f"missing {reqs_path}"
    locked = _parse_lock(lock_path)
    _check_lock_satisfies_requirements(
        lock_path, reqs_path, locked, _parse_requirements(reqs_path)
    )
    _check_workflows_install_only_from_lock(workflows_dir)
    _check_python_version_pinned(lock_path, workflows_dir)
    print(f"R20 lockfile check OK: {len(locked)} exact pins; CI installs only from the lock.")
    return locked


def test_lockfile_is_current():
    verify_lockfile()


if __name__ == "__main__":
    verify_lockfile()
    print("PASS")
