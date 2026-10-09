"""QA: Roster Performance column shows last-10-games average, never overall.

Muck 2026-10-01 directive: the Performance column leaked overall (+/-6 via
overall +/- morale). It must show the last-10-games average from the
recent_game_grades ledger instead.

Covers:
  1. Display shows last-10 average (not overall)
  2. Fewer than 10 games -> average + count (e.g. "72 (5)")
  3. No games -> "—"
  4. Missing ledger (old saves) -> "—", never raises
  5. Display does not leak overall rating
  6. record_performance writes grades on both paths (skater + goalie)
  7. GameSim passes save stats for goalies (simulation.py call site)
  8. Garbage input never raises

Run: python3 qa_perf_column.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DISPLAY", ":99")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------- mocks
class MockPlayer:
    """Minimal player with a grade ledger and a hidden overall."""

    def __init__(self, overall=85, grades=None, has_ledger=True):
        self._overall = overall
        if has_ledger:
            self.recent_game_grades = list(grades or [])

    def overall_rating(self):
        return self._overall


# Import the display method (unbound -- it never touches self).
import windows as _w

_calc = _w.RosterView.calculate_performance_rating
_DUMMY_SELF = object()


def perf(player):
    return _calc(_DUMMY_SELF, player)


# 1: last-10 average, not overall -------------------------------------------
p = MockPlayer(overall=92, grades=[80.0] * 12)
check("avg_last_10_not_overall", perf(p) == "80", f"got {perf(p)!r}")

# only the last 10 count when more than 10 banked
p = MockPlayer(overall=60, grades=[20.0] * 5 + [90.0] * 10)
check("avg_window_is_last_10", perf(p) == "90", f"got {perf(p)!r}")

# a 92-overall star in a slump shows the slump, not the talent
p = MockPlayer(overall=95, grades=[30.0] * 10)
check("slump_star_shows_slump", perf(p) == "30", f"got {perf(p)!r}")

# a 65-overall grinder on a heater shows the heater
p = MockPlayer(overall=65, grades=[88.0] * 10)
check("heater_grinder_shows_heater", perf(p) == "88", f"got {perf(p)!r}")

# 2: fewer than 10 games -> average + count ---------------------------------
p = MockPlayer(overall=75, grades=[70.0, 74.0, 72.0, 76.0, 68.0])
check("short_sample_shows_count", perf(p) == "72 (5)", f"got {perf(p)!r}")

p = MockPlayer(overall=75, grades=[91.0])
check("single_game_shows_count", perf(p) == "91 (1)", f"got {perf(p)!r}")

# 3: no games -> em dash -----------------------------------------------------
p = MockPlayer(overall=80, grades=[])
check("no_games_em_dash", perf(p) == "—", f"got {perf(p)!r}")

# 4: missing ledger (old saves) -> graceful ----------------------------------
p = MockPlayer(overall=80, has_ledger=False)
check("missing_ledger_graceful", perf(p) == "—", f"got {perf(p)!r}")

p = MockPlayer(overall=80, grades=None, has_ledger=True)
p.recent_game_grades = None
check("none_ledger_graceful", perf(p) == "—", f"got {perf(p)!r}")

# 5: no overall leak ----------------------------------------------------------
# Two players with identical grades but wildly different overalls must
# render identically.
lo = MockPlayer(overall=55, grades=[70.0] * 10)
hi = MockPlayer(overall=97, grades=[70.0] * 10)
check("no_overall_leak", perf(lo) == perf(hi) == "70",
      f"lo={perf(lo)!r} hi={perf(hi)!r}")
check("no_overall_digits_in_output",
      all(str(ov) not in perf(MockPlayer(overall=ov, grades=[50.0] * 10))
          for ov in (55, 73, 88, 97)))

# 6: record_performance writes the ledger -------------------------------------
import mesh_system as _mesh


class MockSkater:
    primary_position = None
    def __init__(self):
        self.recent_game_grades = []


class MockGoalie:
    def __init__(self):
        # game_classes.PlayerPosition.GOALIE comparison happens inside;
        # emulate via a stub below instead.
        self.recent_game_grades = []


sk = MockSkater()
_mesh.record_performance(sk, 2, 1)
check("skater_grade_appended", len(sk.recent_game_grades) == 1
      and 0.0 <= sk.recent_game_grades[0] <= 100.0,
      f"got {sk.recent_game_grades!r}")

# ledger caps at 15 entries
for _ in range(20):
    _mesh.record_performance(sk, 0, 0)
check("ledger_capped_15", len(sk.recent_game_grades) == 15,
      f"got {len(sk.recent_game_grades)}")

# goalie graded on save%: .933 over 30 shots -> well above 50
import game_classes as _gc

g = MockGoalie()
g.primary_position = _gc.PlayerPosition.GOALIE
_mesh.record_performance(g, 0, 0, saves=28, shots_against=30)
check("goalie_savepct_grade",
      len(g.recent_game_grades) == 1 and g.recent_game_grades[0] > 70,
      f"got {g.recent_game_grades!r}")

# goalie who faced no shots gets no grade
g2 = MockGoalie()
g2.primary_position = _gc.PlayerPosition.GOALIE
_mesh.record_performance(g2, 0, 0, saves=0, shots_against=0)
check("goalie_no_shots_no_grade", g2.recent_game_grades == [])

# 7: GameSim call site passes save stats ---------------------------------------
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "simulation.py")) as f:
    sim_src = f.read()
check("gamesim_passes_saves",
      "saves=_sv" in sim_src and "shots_against=_sa" in sim_src)

# 8: garbage never raises -------------------------------------------------------
for bad in (None, object(), "grades"):
    try:
        out = perf(bad)
        ok = isinstance(out, str)
    except Exception as e:  # noqa: BLE001
        ok = False
        check(f"garbage_{type(bad).__name__}", False, repr(e))
        break
    if not ok:
        check(f"garbage_{type(bad).__name__}_str", False, f"got {out!r}")
        break
else:
    check("garbage_never_raises", True)

# malformed grades list
p = MockPlayer(overall=80, grades=["x", None, 70.0])
check("malformed_grades_never_raises", perf(p) == "—", f"got {perf(p)!r}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
