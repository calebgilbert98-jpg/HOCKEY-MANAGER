"""QA: lore survives save/load -- retired players, retired numbers, pending
ceremonies, and the milestone idempotency set must round-trip.

Bug history: immortality.py generated retired_players / retired_numbers /
_pending_ceremony in memory, but save_load_system.py never serialized them:
every load deleted retired players from the universe, re-issued retired
numbers to rookies, dropped queued ceremonies, and re-fired every past
milestone celebration.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from types import SimpleNamespace

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


def make_gm():
    from game_classes import League, Team
    league = League("NHL")
    league.season_year = 2028
    t = Team("Testers", "Testville", "Atlantic", "Eastern")
    league.teams = [t]
    # Lore state, as immortality.py / milestones.py would leave it.
    league.retired_players = [{
        "name": "Gordie Howe II", "position": "RW", "number": 9,
        "games": 1600, "points": 1500, "cups": 2,
        "awards": ["Hart"], "ballot_years": 2, "inducted": False,
    }]
    league._milestone_celebrated = {(101, "500_goals"), (202, "1000_games")}
    t.retired_numbers = [{"number": 9, "player": "Gordie Howe II",
                          "year": 2028}]
    t._pending_ceremony = {"kind": "jersey_retirement",
                           "info": {"player": "Gordie Howe II",
                                    "number": 9}}
    gm = SimpleNamespace(league=league, league_history=None,
                         narrative_ledger=None)
    return gm


from save_load_system import GameSaveManager as SaveLoadSystem

gm = make_gm()
saver = SaveLoadSystem(gm)

tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "lore_test.save")
check("save succeeds", saver.save_game(path), path)

# Load into a fresh manager and verify the lore came back.
gm2 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
loader = SaveLoadSystem(gm2)
check("load succeeds", loader.load_game(path), path)

lg2 = gm2.league
rp = getattr(lg2, "retired_players", None) or []
check("retired players survive", len(rp) == 1 and rp[0]["name"] == "Gordie Howe II"
      and rp[0]["ballot_years"] == 2, str(rp))

mc = getattr(lg2, "_milestone_celebrated", None)
check("milestone idempotency set survives",
      isinstance(mc, set) and (101, "500_goals") in mc and (202, "1000_games") in mc,
      str(mc))

t2 = (lg2.teams or [None])[0]
rn = getattr(t2, "retired_numbers", None) or []
check("retired numbers survive",
      len(rn) == 1 and rn[0]["number"] == 9
      and rn[0]["player"] == "Gordie Howe II", str(rn))

pc = getattr(t2, "_pending_ceremony", None)
check("pending ceremony survives",
      isinstance(pc, dict) and pc.get("kind") == "jersey_retirement"
      and (pc.get("info") or {}).get("number") == 9, str(pc))

# Old-save tolerance: keys absent -> graceful defaults, no crash.
gm3 = make_gm()
s3 = SaveLoadSystem(gm3)
data = s3._serialize_league()
tdata = data["teams"][0]
for k in ("retired_players", "_milestone_celebrated"):
    data.pop(k, None)
for k in ("retired_numbers", "_pending_ceremony"):
    tdata.pop(k, None)
gm4 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
s4 = SaveLoadSystem(gm4)
try:
    from game_classes import League as _L
    gm4.league = _L("NHL")
    gm4.league.teams = []
    s4._restore_league(data)
    lg4 = gm4.league
    check("old save: retired_players defaults to empty",
          getattr(lg4, "retired_players", None) == [], str(getattr(lg4, "retired_players", None)))
    check("old save: milestone set defaults to empty",
          getattr(lg4, "_milestone_celebrated", None) == set())
    t4 = (lg4.teams or [None])[0]
    check("old save: retired_numbers defaults to empty",
          getattr(t4, "retired_numbers", None) == [])
    check("old save: pending ceremony defaults to None",
          getattr(t4, "_pending_ceremony", "X") is None)
except Exception as e:  # noqa: BLE001
    check("old save restores without new keys", False, str(e))

print(f"\n{'='*60}\nQA lore_save_load: {PASS} passed, {FAIL} failed")
for f in FAILURES:
    print(f"  FAIL: {f}")
sys.exit(1 if FAIL else 0)
