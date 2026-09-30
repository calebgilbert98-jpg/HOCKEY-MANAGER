# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: jersey-number system -- favorites, legality, arrival assignment,
preseason finalization, real retired-number seeding.
Run: python3 qa_jersey_numbers.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import immortality as im

passed, failed = [], []


def check(label, cond, detail=""):
    (passed if cond else failed).append(label)
    extra = f" -- {detail}" if detail and not cond else ""
    print(f"  {'PASS' if cond else 'FAIL'} {label}{extra}")


def make_team(name="Toronto Maple Leafs"):
    return SimpleNamespace(team_name=name, league_name="National Hockey League",
                           roster=[], ahl_roster=[], retired_numbers=[])


def make_player(pos="CENTER", number=0, pref=0, second=0, since=None,
                games=0, accolades=()):
    return SimpleNamespace(
        primary_position=SimpleNamespace(name=pos),
        jersey_number=number, preferred_number=pref, second_number=second,
        jersey_number_since=since, career_games=games,
        career_accolades=list(accolades), full_name="Test Player")


def is_goalie(p):
    return p.primary_position.name == "GOALIE"


# --- 1. favorite dealing ------------------------------------------------------
for _ in range(50):
    pref, sec = im.deal_favorite_numbers(False)
    assert pref != sec and pref != 99 and sec != 99
    assert pref not in (1, 30) and sec not in (1, 30)
check("skater favorites: distinct, never 99/1/30 (50 deals)", True)
gnums = set()
for _ in range(60):
    pref, sec = im.deal_favorite_numbers(True)
    assert pref != sec and pref != 99
    gnums.add(pref)
check("goalie favorites come from goalie pool",
      gnums <= {30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 29, 1,
                60, 70, 72, 73},
      f"got {sorted(gnums)}")

# --- 2. seeding ----------------------------------------------------------------
t = make_team()
added = im.seed_retired_numbers(t)
check("Toronto seeds 13 real + 99", added == 14, f"added={added}")
check("99 is retired league-wide", im.is_number_retired(t, 99))
check("13 retired (Sundin)", im.is_number_retired(t, 13))
check("93 retired (Gilmour)", im.is_number_retired(t, 93))
check("seeding is idempotent", im.seed_retired_numbers(t) == 0
      and len(t.retired_numbers) == 14)
t2 = make_team("Seattle Kraken")
im.seed_retired_numbers(t2)
check("Kraken: 99 + 32 (fans)", len(t2.retired_numbers) == 2
      and im.is_number_retired(t2, 32))
tW = make_team("Winnipeg Jets")
im.seed_retired_numbers(tW)
check("Jets: only 99 (original-Jets banners honored, not retired)",
      len(tW.retired_numbers) == 1)

# --- 3. selectability -----------------------------------------------------------
t3 = make_team()
im.seed_retired_numbers(t3)
check("retired number blocked", not im.number_selectable(t3, 13, False))
check("99 blocked for everyone", not im.number_selectable(t3, 99, True))
check("#1 blocked for skater", not im.number_selectable(t3, 1, False))
check("#30 blocked for skater", not im.number_selectable(t3, 30, False))
tSea = make_team("Seattle Kraken")
im.seed_retired_numbers(tSea)
check("#1 allowed for goalie", im.number_selectable(tSea, 1, True))
check("#30 allowed for goalie", im.number_selectable(tSea, 30, True))
check("free number allowed", im.number_selectable(t3, 91, False))
p_dup = make_player(number=91)
t3.roster.append(p_dup)
check("duplicate on NHL roster blocked",
      not im.number_selectable(t3, 91, False))
p_dup2 = make_player(number=42)
t3.ahl_roster.append(p_dup2)
check("duplicate in AHL pool blocked",
      not im.number_selectable(t3, 42, False))
check("0 and 99+ rejected", not im.number_selectable(t3, 0, False)
      and not im.number_selectable(t3, 99, False))

# --- 4. arrival assignment -------------------------------------------------------
t4 = make_team()
im.seed_retired_numbers(t4)
yr = 2026
a = make_player(pref=91, second=19)
n = im.assign_arrival_number(t4, a, yr)
check("arrival gets preferred when free", n == 91 and a.jersey_number == 91)
check("arrival stamps jersey_number_since", a.jersey_number_since == 2026)
t4.roster.append(a)
b = make_player(pref=91, second=22)
n2 = im.assign_arrival_number(t4, b, yr)
check("preferred taken -> second choice", n2 == 22, f"got {n2}")
t4.roster.append(b)
c = make_player(pref=91, second=22)
n3 = im.assign_arrival_number(t4, c, yr)
check("both taken -> first free legal", n3 not in (91, 19) and n3 != 99
      and n3 not in (1, 30), f"got {n3}")
d = make_player(pref=13, second=99)  # 13 retired in Toronto, 99 league
n4 = im.assign_arrival_number(t4, d, yr)
check("retired/99 favorites skipped", n4 not in (13, 99), f"got {n4}")
g = make_player(pos="GOALIE", pref=30, second=1)
n5 = im.assign_arrival_number(t4, g, yr)
check("goalie gets #30", n5 == 30, f"got {n5}")

# --- 5. preseason finalization ----------------------------------------------------
t5 = make_team()
im.seed_retired_numbers(t5)
# Veteran wearing 61, prefers 91 (free), no legacy -> switches.
vet = make_player(number=61, pref=91, second=19, since=2025, games=400)
t5.roster.append(vet)
# Legacy: wearing 61 since 2022, prefers 91 -> stays.
leg = make_player(number=62, pref=91, second=19, since=2022, games=900)
t5.roster.append(leg)
# Grandfathered old-save player (since None) -> stays.
old = make_player(number=63, pref=91, second=19, since=None, games=700)
t5.roster.append(old)
# Won a Cup wearing 64 in 2025 -> legacy -> stays.
cup = make_player(number=64, pref=91, second=19, since=2025, games=300,
                  accolades=[{"award": "stanley_cup", "year": "2025-26"}])
t5.roster.append(cup)
# Skater illegally wearing 30 -> repaired.
ill = make_player(pos="CENTER", number=30, pref=77, second=78, since=2025)
t5.roster.append(ill)
# Duplicate numbers -> one repaired.
d1 = make_player(number=55, pref=56, second=57, since=2025)
d2 = make_player(number=55, pref=58, second=59, since=2025)
t5.roster.extend([d1, d2])
sw = im.finalize_team_numbers(t5, 2026)
by = {id(s["player"]): s for s in sw}
check("no-legacy veteran switches to freed favorite",
      by.get(id(vet), {}).get("new") == 91, f"got {by.get(id(vet))}")
check("3-year legacy keeps number", id(leg) not in by)
check("grandfathered (old save) keeps number", id(old) not in by)
check("Cup-winner keeps number", id(cup) not in by)
check("skater in #30 repaired",
      by.get(id(ill), {}).get("reason") == "repair"
      and ill.jersey_number not in (30,), f"got {ill.jersey_number}")
check("duplicate repaired to unique",
      d1.jersey_number != d2.jersey_number)
check("all numbers legal after finalize",
      all(im.number_selectable(t5, 0, False) is False for _ in [0])  # noop
      and len({p.jersey_number for p in t5.roster}) == len(t5.roster)
      and all(p.jersey_number not in (1, 30) or is_goalie(p)
              for p in t5.roster))

# --- 6. initial assignment: seniority first ---------------------------------------
t6 = make_team()
im.seed_retired_numbers(t6)
rook = make_player(pref=91, second=19, games=0)
star = make_player(pref=91, second=19, games=900)
t6.roster.extend([rook, star])
im.initial_number_assignment(t6, 2026)
check("veteran wins the favorite", star.jersey_number == 91
      and rook.jersey_number != 91,
      f"star={star.jersey_number} rook={rook.jersey_number}")

# --- 7. Player dataclass deals favorites -------------------------------------------
from game_classes import Player, PlayerPosition
pl = Player(first_name="A", last_name="B", age=20,
            primary_position=PlayerPosition.CENTER)
check("Player dealt distinct favorites",
      pl.preferred_number != pl.second_number
      and pl.preferred_number not in (0, 99, 1, 30))
pg = Player(first_name="C", last_name="D", age=20,
            primary_position=PlayerPosition.GOALIE)
check("goalie dealt goalie-pool favorite",
      pg.preferred_number in {30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                              40, 41, 29, 1, 60, 70, 72, 73},
      f"got {pg.preferred_number}")

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
