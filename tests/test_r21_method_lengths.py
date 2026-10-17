"""R21 god-object split: regression guard for method-length reductions.

As R21 extracts helpers out of the god methods in game_manager.py /
simulation.py, this test pins the completed methods at <=200 lines and
asserts the total count of >200-line methods never grows again.

Baseline (2026-10-17, after the end_of_season + handle_contract_offer
extractions): game_manager.py has 11 methods >200 lines, simulation.py has 6.
Update the pinned baselines as further R21 chunks land.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Methods already split by R21 chunks; each must stay at/below 200 lines.
COMPLETED = {
    "game_manager.py": ["end_of_season", "handle_contract_offer"],
    "simulation.py": [],
}

# Pinned counts of methods still >200 lines (shrink as R21 progresses).
BASELINE_OVER_200 = {
    "game_manager.py": 11,
    "simulation.py": 6,
}


def _func_lengths(path):
    tree = ast.parse((REPO / path).read_text())
    return {
        n.name: n.end_lineno - n.lineno + 1
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_completed_methods_stay_under_200_lines():
    for fname, names in COMPLETED.items():
        lengths = _func_lengths(fname)
        for name in names:
            assert name in lengths, "%s missing from %s" % (name, fname)
            assert lengths[name] <= 200, (
                "%s.%s is %d lines (>200) -- R21 regression"
                % (fname, name, lengths[name])
            )


def test_over_200_count_does_not_grow():
    for fname, baseline in BASELINE_OVER_200.items():
        lengths = _func_lengths(fname)
        over = {n: ln for n, ln in lengths.items() if ln > 200}
        assert len(over) <= baseline, (
            "%s has %d methods >200 lines (baseline %d); new offenders: %s"
            % (fname, len(over), baseline,
               sorted(set(over) - set(COMPLETED.get(fname, []))))
        )
