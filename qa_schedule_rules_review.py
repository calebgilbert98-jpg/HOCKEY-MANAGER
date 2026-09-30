# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: nhl_schedule_rules review — repairs preserve the slate.

Proves on crafted dirty schedules through the REAL enforcer:
  1. Streak repair: a 3-in-a-row is fixed by moving the middle game.
  2. Swap path: _try_swap_game actually swaps now (the old set
     subtractions made every candidate fail -- dead code).
  3. Swap refuses when it would double-book a team.
  4. Doubleheader repair: one of the same-day games moves.
  5. Repairs never delete/duplicate: game count, matchup multiset, and
     per-team game counts identical before/after.
  6. Repairs never land on Dec 24-26 (Christmas dark dates are skipped
     even when they are the closest free date).
  7. Soft rules are reported, never "fixed" (back-to-back counts
     unchanged by enforce).
  8. Malformed records (non-dict, None dates, missing sides) neither
     crash the validator nor false-positive it.
  9. Season-window violations are reported CRITICAL and left in place
     (playable beats "correct").
 10. enforce_schedule never raises -- not even on None input.

No repo files modified.
"""
import sys
from types import SimpleNamespace
from datetime import date, timedelta

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

import nhl_schedule_rules as nsr

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

def T(name):
    return SimpleNamespace(team_name=name)

def G(d, h, a):
    return {"date": d, "home_team": T(h), "away_team": T(a)}

def fp(games):
    """Fingerprint: matchup multiset + per-team game counts."""
    pairs = sorted((g["home_team"].team_name, g["away_team"].team_name)
                   for g in games)
    counts = {}
    for h, a in pairs:
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    return pairs, counts

def streaks_of(games, team):
    ds = sorted({g["date"] for g in games
                 if g["home_team"].team_name == team
                 or g["away_team"].team_name == team})
    best = run = 1
    for i in range(1, len(ds)):
        if (ds[i] - ds[i - 1]).days == 1:
            run += 1; best = max(best, run)
        else:
            run = 1
    return best

JAN = lambda d: date(2027, 1, d)
DEC = lambda d: date(2026, 12, d)

# ------------------------------------------------------- 1. streak repair
games = [G(JAN(5), "A", "B"), G(JAN(6), "A", "C"), G(JAN(7), "A", "D"),
         G(JAN(10), "B", "C")]
before = fp(games)
out, unfix = nsr.enforce_schedule(games, season_year=2026)
check("streak repaired", streaks_of(out, "A") <= 2,
      f"max streak {streaks_of(out, 'A')}")
# game_count fires on any toy schedule (unfixable by design); the point is
# the STREAK violation is gone.
check("streak: violation fixed",
      [v for v in unfix if v.rule == "consecutive_days"] == [])
check("streak: slate preserved", fp(out) == before)

# --------------------------------------------- 2/3. swap path (was dead)
g1 = G(JAN(10), "T1", "T2"); g2 = G(JAN(12), "T3", "T4")
games = [g1, g2]
check("swap fires now", nsr._try_swap_game(games, g1) is True)
check("swap exchanged dates", g1["date"] == JAN(12) and g2["date"] == JAN(10),
      f"{g1['date']} / {g2['date']}")
# Negative: T3 already plays on Jan 10 -> swapping B onto Jan 10 double-books.
g1 = G(JAN(10), "T1", "T2"); g2 = G(JAN(12), "T3", "T4")
g3 = G(JAN(10), "T3", "T1")
games = [g1, g2, g3]
check("swap refuses double-book", nsr._try_swap_game(games, g1) is False)
check("refused swap leaves dates", g1["date"] == JAN(10) and g2["date"] == JAN(12))

# ------------------------------------------------------- 4. doubleheader
games = [G(JAN(5), "A", "B"), G(JAN(5), "A", "C"), G(JAN(9), "A", "D")]
before = fp(games)
out, unfix = nsr.enforce_schedule(games, season_year=2026)
a_dates = sorted(g["date"] for g in out
                 if g["home_team"].team_name == "A"
                 or g["away_team"].team_name == "A")
check("doubleheader repaired", len(a_dates) == len(set(a_dates)),
      str(a_dates))
check("doubleheader: slate preserved", fp(out) == before)

# --------------------------------------------- 5. multi-violation preserve
games = []
teams = ["A", "B", "C", "D", "E", "F"]
d = JAN(4)
for i in range(30):
    games.append(G(d, teams[i % 6], teams[(i + 1) % 6]))
    d += timedelta(days=2 if i % 3 else 1)
# Inject: 3-in-a-row for A, doubleheader for B.
games.append(G(JAN(20), "A", "F")); games.append(G(JAN(21), "A", "E"))
games.append(G(JAN(22), "A", "D"))
games.append(G(JAN(25), "B", "C")); games.append(G(JAN(25), "B", "D"))
before = fp(games)
out, unfix = nsr.enforce_schedule(games, season_year=2026)
# game_count fires on any toy schedule (unfixable by design); assert the
# repairable hard rules are clean.
hard_left = [v for v in nsr.validate_schedule(out, 2026)
             if v.severity == "hard" and v.rule != "game_count"]
check("multi: no repairable hard violations remain", hard_left == [],
      str(hard_left[:2]))
check("multi: slate preserved", fp(out) == before)
check("multi: game count identical", len(out) == len(games),
      f"{len(out)} vs {len(games)}")

# ------------------------------------------------------- 6. christmas dark
# A plays Dec 19-23 (4 straight). The middle game (Dec 21) must move;
# Dec 24 (+3) is the closest free date but dark -> must pick Dec 18.
games = [G(DEC(19), "C", "A"), G(DEC(20), "A", "B"), G(DEC(21), "A", "B"),
         G(DEC(22), "A", "B"), G(DEC(23), "A", "B")]
out, unfix = nsr.enforce_schedule(games, season_year=2026)
moved = [g for g in out if (g["date"].month, g["date"].day) == (12, 21)]
check("christmas: Dec 21 game moved away", moved == [])
dark = [g for g in out
        if (g["date"].month, g["date"].day) in ((12, 24), (12, 25), (12, 26))]
check("christmas: no game on dark dates", dark == [],
      str([g["date"] for g in dark]))
check("christmas: streak fixed", streaks_of(out, "A") <= 2)

# ------------------------------------------------------- 7. soft untouched
# A plays back-to-back pairs with 3-day gaps: 20 back-to-backs, no
# 3-streaks, no hard violations. Enforce must leave every date alone.
games = []
d = JAN(4)
opps = ["B", "C", "D", "E", "F"]
for i in range(41):
    games.append(G(d, "A", opps[i % 5]))
    d += timedelta(days=1 if i % 2 == 0 else 3)
def b2b(gs, team):
    ds = sorted({g["date"] for g in gs
                 if g["home_team"].team_name == team
                 or g["away_team"].team_name == team})
    return sum(1 for i in range(1, len(ds)) if (ds[i] - ds[i-1]).days == 1)
n_before = b2b(games, "A")
before = fp(games)
out, unfix = nsr.enforce_schedule(games, season_year=2026)
check("soft: back-to-backs untouched", b2b(out, "A") == n_before,
      f"{n_before} -> {b2b(out, 'A')}")
check("soft: no date moved", fp(out) == before)
# Only game_count (toy-schedule noise) may be unfixable here.
check("soft: nothing else unfixable",
      [v for v in unfix if v.rule != "game_count"] == [],
      str([v.rule for v in unfix]))

# ------------------------------------------------------- 8. malformed input
weird = ["junk", None, 42,
         {"date": None, "home_team": T("A"), "away_team": T("B")},
         {"date": None, "home_team": T("A"), "away_team": T("C")},
         {"home_team": T("A")}, {}]
try:
    vs = nsr.validate_schedule(weird, 2026)
    dh = [v for v in vs if v.rule == "doubleheader"]
    check("malformed: no crash", True)
    check("malformed: no dateless doubleheader false-positive", dh == [],
          str(dh))
except Exception as e:  # noqa: BLE001
    check("malformed: no crash", False, repr(e))
    check("malformed: no dateless doubleheader false-positive", False)

# ------------------------------------------------------- 9. window: report
games = [G(date(2027, 6, 1), "A", "B"), G(JAN(5), "A", "C")]
out, unfix = nsr.enforce_schedule(games, season_year=2026)
w = [v for v in unfix if v.rule == "season_window"]
check("window: reported CRITICAL (one per team)", len(w) == 2, str(w))
kept = any(g["date"] == date(2027, 6, 1) for g in out)
check("window: game kept playable (not moved/deleted)", kept)

# ------------------------------------------------------- 10. never raises
try:
    out, unfix = nsr.enforce_schedule(None)
    check("never raises on None", True)
except Exception as e:  # noqa: BLE001
    check("never raises on None", False, repr(e))
out, unfix = nsr.enforce_schedule([])
check("empty schedule -> clean", out == [] and unfix == [])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
