# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: player accolades (permanent trophy case).

Covers: idempotent banking (no duplicates), grouping format
("Hart Trophy Winner: 2021, 2025"), Cup-first ordering, key
normalization (lady_byng -> byng), junk-input safety, old-save
getattr safety, and save/load round-trip. Headless.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import accolades as acc

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def mk_player():
    return SimpleNamespace(career_accolades=[])


print("== banking ==")
p = mk_player()
check("bank hart 2021", acc.bank_accolade(p, "hart", "2021") is True)
check("bank hart 2025", acc.bank_accolade(p, "hart", "2025") is True)
check("re-bank hart 2021 = dup rejected",
      acc.bank_accolade(p, "hart", "2021") is False)
check("exactly 2 entries", acc.accolade_count(p) == 2,
      acc.accolade_count(p))
check("lady_byng normalizes",
      acc.bank_accolade(p, "lady_byng", "2024") is True and
      p.career_accolades[-1]["award"] == "byng")
check("empty key/year rejected",
      acc.bank_accolade(p, "", "2024") is False and
      acc.bank_accolade(p, "hart", "") is False)
check("None player safe", acc.bank_accolade(None, "hart", "2021") is False)

print("== grouping ==")
p2 = mk_player()
acc.bank_accolade(p2, "hart", "2021")
acc.bank_accolade(p2, "rocket", "2021")
acc.bank_accolade(p2, "hart", "2025")
acc.bank_accolade(p2, "stanley_cup", "2021-22")
acc.bank_accolade(p2, "stanley_cup", "2022-23")
acc.bank_accolade(p2, "stanley_cup", "2023-24")
g = acc.group_accolades(p2)
check("3 groups", len(g) == 3, g)
check("cup first", g[0][0] == "Stanley Cup", g[0])
check("cup years", g[0][1] == ["2021-22", "2022-23", "2023-24"], g[0])
lines = [f"{label} Winner: {', '.join(years)}" for label, years in g]
check("Muck format hart",
      "Hart Trophy Winner: 2021, 2025" in lines, lines)
check("Muck format rocket",
      "Rocket Richard Trophy Winner: 2021" in lines, lines)
check("Muck format cup",
      "Stanley Cup Winner: 2021-22, 2022-23, 2023-24" in lines, lines)

print("== old-save / junk safety ==")
bare = SimpleNamespace()  # no career_accolades attr (old save)
check("getattr default empty", acc.group_accolades(bare) == [])
check("bank backfills attr",
      acc.bank_accolade(bare, "vezina", "2026") is True and
      bare.career_accolades[0]["award"] == "vezina")
weird = SimpleNamespace(career_accolades=[None, "junk", {"award": "hart"}])
check("junk entries skipped", acc.group_accolades(weird) == [])

print("== save round-trip ==")
try:
    from game_classes import Player, PlayerPosition
    from save_load_system import GameSaveManager
    pl = Player("Test", "Kid", 21, PlayerPosition.CENTER)
    pl.career_accolades = [{"award": "hart", "year": "2025"},
                           {"award": "stanley_cup", "year": "2024-25"}]
    mgr = GameSaveManager.__new__(GameSaveManager)
    back = mgr._restore_player(mgr._serialize_player(pl))
    check("accolades survive save/load",
          getattr(back, "career_accolades", None) == pl.career_accolades,
          getattr(back, "career_accolades", None))
except Exception as e:
    check("accolades survive save/load", False, str(e))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
