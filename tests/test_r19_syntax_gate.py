"""R19: the CI Python 3.11 syntax gate must cover multiplayer/.

The gate in .github/workflows/build-native.yml ("Check Python 3.11 syntax
compatibility") exists because 3.12-only syntax (PEP 701 f-strings) compiles
fine in dev but makes PyInstaller's modulegraph silently drop the module from
the bundle on the 3.11 CI runner (v0.26.38-v0.26.41 incident). multiplayer/
modules are bundled via deferred imports, so they must be in the gate's scan
set -- otherwise a 3.12-only f-string there reproduces the silent drop.
"""
import glob
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO_ROOT, ".github/workflows", "build-native.yml")
SYNTAX_STEP = "Check Python 3.11 syntax compatibility"


def _syntax_step_block():
    with open(WORKFLOW, encoding="utf-8") as f:
        text = f.read()
    start = text.index(SYNTAX_STEP)
    # The step's YAML block ends at the next "- name:" entry.
    end = text.index("\n      - name:", start)
    return text[start:end]


def test_gate_mentions_multiplayer_glob():
    """The workflow's syntax step must scan multiplayer/**/*.py."""
    block = _syntax_step_block()
    assert "multiplayer/**/*.py" in block, (
        "syntax gate no longer scans multiplayer/ -- a 3.12-only construct "
        "there would silently drop the module from the bundle again"
    )


def test_gate_globs_reach_multiplayer_modules():
    """Replicating the gate's own glob expressions must include the bundled
    multiplayer modules (net_client.py is the acceptance probe target)."""
    block = _syntax_step_block()
    patterns = re.findall(r"glob\.glob\('([^']+)'", block)
    assert patterns, "no glob patterns found in the syntax step"
    prev = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        scanned = set()
        for pat in patterns:
            scanned.update(glob.glob(pat, recursive=True))
    finally:
        os.chdir(prev)
    for mod in ("multiplayer/net_client.py", "multiplayer/net_host.py",
                "multiplayer/protocol.py", "multiplayer/__init__.py"):
        assert mod in scanned, f"{mod} not reached by the syntax gate globs"


def test_acceptance_probe_is_312_only_syntax():
    """The R19 acceptance probe f"{x["y"]}" must be syntax that a 3.12+
    interpreter accepts (so it is exactly the class of construct the 3.11
    gate exists to catch). The gate itself runs on the real 3.11 runner in
    CI, where this is a SyntaxError."""
    probe = 'x = {"y": 1}\nprint(f"{x["y"]}")\n'
    if sys.version_info >= (3, 12):
        compile(probe, "<r19-probe>", "exec")  # must not raise on 3.12+
    else:
        try:
            compile(probe, "<r19-probe>", "exec")
        except SyntaxError:
            pass  # expected on 3.11: the gate catches it
        else:
            raise AssertionError("probe unexpectedly valid on <3.12")
