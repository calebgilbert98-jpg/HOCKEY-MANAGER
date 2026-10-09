# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: legacy counters fire -- stanley_cups increments idempotently on Cup
banking; snapshots read individual awards from career_accolades (Cups
excluded, counted via stanley_cups); number_worthy clears for legends.
Run: python3 qa_legacy_counters.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import accolades as acc
import immortality as im

passed, failed = [], []


def check(label, cond, detail=""):
    (passed if cond else failed).append(label)
    extra = f" -- {detail}" if detail and not cond else ""
    print(f"  {'PASS' if cond else 'FAIL'} {label}{extra}")


def make_player(**kw):
    p = SimpleNamespace(
        id="p1", full_name="Test Legend", first_name="Test", last_name="Legend",
        primary_position=SimpleNamespace(name="CENTER"),
        jersey_number=91, age=38,
        career_games=1100, career_goals=380, career_assists=570,
        career_points=950, career_wins=0, career_shutouts=0,
        stanley_cups=0, career_accolades=[], awards_won=[])
    for k, v in kw.items():
        setattr(p, k, v)
    return p


# --- 1. Cup banking increments stanley_cups, idempotently --------------------
p = make_player()
added = acc.bank_accolade(p, "stanley_cup", "2026-27")
if added:
    p.stanley_cups = int(getattr(p, "stanley_cups", 0) or 0) + 1
check("first Cup bank returns True and increments", added and p.stanley_cups == 1)
added2 = acc.bank_accolade(p, "stanley_cup", "2026-27")
if added2:
    p.stanley_cups = int(getattr(p, "stanley_cups", 0) or 0) + 1
check("re-run does not double count", not added2 and p.stanley_cups == 1)
added3 = acc.bank_accolade(p, "stanley_cup", "2027-28")
if added3:
    p.stanley_cups = int(getattr(p, "stanley_cups", 0) or 0) + 1
check("next season's Cup increments again", added3 and p.stanley_cups == 2)

# --- 2. snapshot awards -------------------------------------------------------
p2 = make_player(stanley_cups=5)
for yr in ("2021", "2023"):
    acc.bank_accolade(p2, "hart", yr)
for yr in ("2022", "2024", "2025", "2026", "2027"):
    acc.bank_accolade(p2, "stanley_cup", yr)
snap = im.snapshot_player(p2, "Test Club", 2028)
check("snapshot cups = 5", snap["cups"] == 5)
check("snapshot awards are individual only (2 harts)",
      snap["awards"] == ["hart", "hart"], f"got {snap['awards']}")
check("5x Cup legend is number_worthy", im.number_worthy(snap) is True)
check("legend career score >= 65", im.career_score(snap) >= 65.0)

# --- 3. fallback for old data -------------------------------------------------
p3 = make_player(awards_won=["norris"])
del p3.career_accolades
snap3 = im.snapshot_player(p3, "Test Club", 2028)
check("falls back to awards_won", snap3["awards"] == ["norris"])

# --- 4. role player with Cups does NOT get number retired ----------------------
p4 = make_player(career_games=700, career_goals=90, career_assists=160,
                 career_points=250, stanley_cups=5)
snap4 = im.snapshot_player(p4, "Test Club", 2028)
check("role player not number_worthy", im.number_worthy(snap4) is False)

# --- 5. retire_number end-to-end ----------------------------------------------
team = SimpleNamespace(team_name="Test Club", retired_numbers=[])
check("retire_number hangs the number",
      im.retire_number(team, snap, 2028) is True
      and im.is_number_retired(team, 91))
check("duplicate retirement refused",
      im.retire_number(team, snap, 2028) is False
      and len(team.retired_numbers) == 1)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
