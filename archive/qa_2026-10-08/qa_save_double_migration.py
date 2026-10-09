# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_save_double_migration.py -- double-migration corruption triage QA.

Regression tests for the Sep-2026 save corruption: saves written with
version='1.0' + attribute_scale=100 (contradictory stamps) were migrated on
EVERY load by the version-only check, doubling already-modern attributes
toward 100 (median ovr 99). The fix makes the attribute_scale stamp
authoritative.

1. should_migrate_50_to_100(): stamp wins over version string in all cases.
2. Full restore path: a day1.hm-style save (v1.0 + scale 100, modern
   attributes) restores WITHOUT doubling; a genuine v1 save (v1.0, no stamp,
   legacy attributes) migrates exactly once and the re-saved form is stable.
3. _detect_scale_corruption(): maxed-out saves are flagged; healthy saves
   and tiny leagues are not.
"""
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# Headless: neutralize UI popups before importing the module under test.
import popup_system
popup_system.messagebox.showerror = lambda *a, **k: None
popup_system.messagebox.showwarning = lambda *a, **k: None
popup_system.messagebox.showinfo = lambda *a, **k: None

from save_load_system import (
    GameSaveManager,
    should_migrate_50_to_100,
)

print("== 1. migration decision: stamp is authoritative ==")
check("genuine v1 save (1.0, no stamp) migrates",
      should_migrate_50_to_100({'version': '1.0'}) is True)
check("contradictory save (1.0 + scale 100) does NOT migrate -- day1.hm",
      should_migrate_50_to_100({'version': '1.0', 'attribute_scale': 100}) is False)
check("modern save (2.0 + scale 100) does not migrate",
      should_migrate_50_to_100({'version': '2.0', 'attribute_scale': 100}) is False)
check("modern save (2.0, no stamp) does not migrate",
      should_migrate_50_to_100({'version': '2.0'}) is False)
check("missing version defaults to 1.0 -> migrates when unstamped",
      should_migrate_50_to_100({}) is True)
check("missing version + scale 100 does not migrate",
      should_migrate_50_to_100({'attribute_scale': 100}) is False)
check("scale 99 (below threshold) + v1.0 still migrates",
      should_migrate_50_to_100({'version': '1.0', 'attribute_scale': 99}) is True)

print("== 2. restore path: migrate exactly once, never double ==")
gm = SimpleNamespace(league=None, user_team=None, current_date=None)
sls = GameSaveManager(gm)


def _player_dict(skating, shooting=30, passing=30):
    return {'first_name': 'Test', 'last_name': 'Player', 'age': 25,
            'primary_position': 'CENTER',
            'skating': skating, 'shooting': shooting, 'passing': passing}


# 2a. day1.hm regression: contradictory stamp, modern attributes.
sls._migrate_50_to_100 = should_migrate_50_to_100(
    {'version': '1.0', 'attribute_scale': 100})
p = sls._restore_player(_player_dict(80))
check("contradictory save: 80 skating NOT doubled (was 80->100 before fix)",
      p is not None and p.skating == 80, f"got {getattr(p, 'skating', '?')}")
# Simulate a second load of the same file: still no migration.
sls._migrate_50_to_100 = should_migrate_50_to_100(
    {'version': '1.0', 'attribute_scale': 100})
p2 = sls._restore_player(_player_dict(80))
check("contradictory save: second load also leaves 80 alone",
      p2 is not None and p2.skating == 80, f"got {getattr(p2, 'skating', '?')}")

# 2b. genuine v1 save: migrates once...
sls._migrate_50_to_100 = should_migrate_50_to_100({'version': '1.0'})
p3 = sls._restore_player(_player_dict(30))
check("genuine v1 save: 30 skating doubled to 60 on first load",
      p3 is not None and p3.skating == 60, f"got {getattr(p3, 'skating', '?')}")
# ...and the re-saved form (what create_save_data stamps) is stable.
sls._migrate_50_to_100 = should_migrate_50_to_100(
    {'version': '2.0', 'attribute_scale': 100})
p4 = sls._restore_player(_player_dict(60))
check("re-saved migrated save: 60 skating untouched on next load",
      p4 is not None and p4.skating == 60, f"got {getattr(p4, 'skating', '?')}")

# 2c. clamping still bounds a genuine migration (50 -> 100, not 100+).
sls._migrate_50_to_100 = should_migrate_50_to_100({'version': '1.0'})
p5 = sls._restore_player(_player_dict(50))
check("genuine v1: 50 clamps at 100",
      p5 is not None and p5.skating == 100, f"got {getattr(p5, 'skating', '?')}")

print("== 3. corruption detection ==")


def _fake_league(mean_attr, n_players=30):
    teams = []
    per_team = max(1, n_players // 3)
    for t in range(3):
        roster = [SimpleNamespace(skating=mean_attr, shooting=mean_attr,
                                 passing=mean_attr)
                  for _ in range(per_team)]
        teams.append(SimpleNamespace(roster=roster, ahl_roster=[],
                                     prospects=[]))
    return SimpleNamespace(teams=teams)


gm2 = SimpleNamespace(league=_fake_league(100), user_team=None,
                      current_date=None)
sls2 = GameSaveManager(gm2)
sls2._detect_scale_corruption()
check("maxed-out save (mean 100) is flagged",
      sls2._scale_corruption_detected is True)

gm3 = SimpleNamespace(league=_fake_league(72), user_team=None,
                      current_date=None)
sls3 = GameSaveManager(gm3)
sls3._detect_scale_corruption()
check("healthy save (mean 72) is NOT flagged",
      sls3._scale_corruption_detected is False)

gm4 = SimpleNamespace(league=_fake_league(100, n_players=6), user_team=None,
                      current_date=None)
sls4 = GameSaveManager(gm4)
sls4._detect_scale_corruption()
check("tiny league (<20 players) does not flag (no false positive)",
      sls4._scale_corruption_detected is False)

gm5 = SimpleNamespace(league=None, user_team=None, current_date=None)
sls5 = GameSaveManager(gm5)
sls5._detect_scale_corruption()  # must not crash with no league
check("no league: detection is a safe no-op",
      sls5._scale_corruption_detected is False)

print()
print(f"{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
