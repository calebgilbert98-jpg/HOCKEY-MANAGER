"""QA for the 2026-09-28 playtest bug report (broken-mechanics.pdf).

Covers the production findings actioned in code:
  P-5: star-surname filter on generated players (name_safety.py)
  P-2: final-table snapshot banked before end_of_season() zeroes standings
  P-1: legacy conference_finals key verified never populated (no change)

Not covered here (by design):
  P-3: scoring levels -- owned by the in-flight superstar-scoring tune
  P-4: draft need-boost decay -- tuning change awaiting Muck's design call
  [DRIVER] items: harness-side, already fixed in the harness.

Run headless: python3 qa_playtest_bugfixes.py
"""

import random
import re
import sys

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))


print("== P-5: star-surname filter ==")
import name_safety as ns

# 1. The three reported collisions are blocked
for star in ["Rantanen", "Draisaitl", "Granlund"]:
    check(f"reported collision blocked: {star}", ns.is_blocked_surname(star))

# 2. Case/whitespace robustness
check("case-insensitive: 'mcdavid' blocked", ns.is_blocked_surname("mcdavid"))
check("case-insensitive: 'MCDAVID' blocked", ns.is_blocked_surname("MCDAVID"))

# 3. Depth surnames still legal (flavor preserved)
for depth in ["Virtanen", "Smith", "Johnson", "Nieminen", "Lindell", "Brown"]:
    check(f"depth surname legal: {depth}", not ns.is_blocked_surname(depth))

# 4. pick_surname over every nationality pool in database_generator
from database_generator import EXTENDED_LAST_NAMES
random.seed(11)
_total = 0
_leaked = []
for nat, pool in EXTENDED_LAST_NAMES.items():
    for _ in range(300):
        s = ns.pick_surname(pool)
        _total += 1
        if not isinstance(s, str) or not s:
            _leaked.append((nat, "EMPTY/NON-STR"))
        elif ns.is_blocked_surname(s):
            _leaked.append((nat, s))
check(f"database_generator pools: {_total} picks, zero star surnames",
      not _leaked, str(_leaked[:5]))

# 5. get_random_name (draft_generator path incl. ascii normalization)
from draft_generator import get_random_name, COUNTRY_DISTRIBUTION
random.seed(22)
_leaked2 = []
for _ in range(1500):
    country = random.choice(list(COUNTRY_DISTRIBUTION.keys()))
    _fn, _ln = get_random_name(country)
    if ns.is_blocked_surname(_ln):
        _leaked2.append((country, _ln))
check("draft_generator get_random_name: 1500 picks, zero star surnames",
      not _leaked2, str(_leaked2[:5]))

# 6. Termination on a pathological all-blocked pool (never hangs)
_t0 = __import__("time").time()
s = ns.pick_surname(["Rantanen", "McDavid", "Crosby"])
_dt = __import__("time").time() - _t0
check("all-blocked pool terminates gracefully",
      isinstance(s, str) and s and _dt < 2.0, f"got={s!r} dt={_dt:.2f}s")

# 7. Empty pool never raises
try:
    s = ns.pick_surname([])
    check("empty pool returns safely", s == "")
except Exception as e:
    check("empty pool returns safely", False, repr(e))

print("== P-2: final-table snapshot ==")
from game_classes import bank_final_table

# 8. Independent copy: mutating the source must not touch the snapshot
src = {"Boston Bruins": {"W": 50, "L": 25, "OTL": 7, "Points": 107},
       "Toronto Maple Leafs": {"W": 48, "L": 28, "OTL": 6, "Points": 102}}
snap = bank_final_table(src)
src["Boston Bruins"]["Points"] = 0
src["New York Rangers"] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
check("snapshot is an independent copy",
      snap["Boston Bruins"]["Points"] == 107
      and "New York Rangers" not in snap
      and snap["Toronto Maple Leafs"] == {"W": 48, "L": 28, "OTL": 6, "Points": 102})

# 9. Degenerate inputs never raise
for bad in [None, {}, {"X": None}, {"Y": {"W": 1}}]:
    try:
        r = bank_final_table(bad)
        ok = isinstance(r, dict)
    except Exception:
        ok = False
    check(f"bank_final_table({bad!r}) safe", ok)

# 10. Wiring order: banked BEFORE initialize_standings() inside end_of_season
src_text = open("game_classes.py").read()
m = re.search(r"def end_of_season\(self\):", src_text)
body = src_text[m.start(): m.start() + 30000]
_bank_pos = body.find("bank_final_table(self.standings)")
_wipe_pos = body.find("self.initialize_standings()")
check("snapshot banked before standings are zeroed",
      0 < _bank_pos < _wipe_pos,
      f"bank@{_bank_pos} wipe@{_wipe_pos}")

# 11. Ordering contract documented on end_of_season
check("ordering contract in end_of_season docstring",
      "ORDERING CONTRACT" in body[:1500] and "final_table_snapshot" in body[:1500])

print("== P-1: legacy conference_finals key (verify-only) ==")
psrc = open("playoff_system.py").read()
check("conference_finals list never appended to",
      "playoff_series['conference_finals'].append" not in psrc
      and 'playoff_series["conference_finals"].append' not in psrc)
check("_create_conference_finals routes to stanley_cup_final",
      "self.playoff_series['stanley_cup_final'].append" in psrc)
check("legacy key documented in-code",
      "legacy key" in psrc)

print(f"\n{PASS.__len__()}/{PASS.__len__() + FAIL.__len__()} passed")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
