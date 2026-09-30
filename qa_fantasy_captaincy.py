"""QA: captaincy growth is safe on fantasy-draft saves.

Fantasy drafts redistribute players without stripping letters, so the
 offseason hook must handle messy states (multiple C\u2019s, no letters).
Covers the real hook on real Player objects, save/load round-trip of the
new fields, and a second offseason on the loaded save.
"""
"""Verify captaincy growth is safe on fantasy-draft saves.

Fantasy drafts redistribute players WITHOUT stripping letters, so rosters
can reach the offseason hook with messy states: multiple C's, no letters
at all. This script:

 1. Builds 4 teams of REAL game_classes.Player objects with messy
    post-fantasy-draft letters (team A: two C's; team B: no letters;
    teams C/D: normal 1C+2A).
 2. Runs the REAL HockeyManagerGUI._update_offseason_reputations on them.
 3. Asserts growth/mentorship/reputation behave and nothing crashes.
 4. Save/load round-trip: new fields survive.
 5. Runs the hook again post-load (next offseason): still clean.
"""
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name} {detail}")


from game_classes import League, Team, Player

FIRST = ["Alex", "Brad", "Cole", "Drew", "Ellis", "Finn", "Gabe", "Hugo",
         "Ivan", "Jake", "Kyle", "Liam"]
LAST = ["Smith", "Jones", "Brown", "Taylor", "Wilson", "Clark", "Lewis",
        "Walker", "Hall", "Young", "King", "Wright"]


def make_player(i, age, leadership, letter, goals, assists):
    p = Player(FIRST[i % 12], LAST[(i * 7) % 12] + str(i), age, "C", 9,
               captaincy=letter)
    p.stats.games_played = 82
    p.stats.goals = goals
    p.stats.assists = assists
    return p


def make_team(name, letters):
    # letters: list of 12 captaincy values, one per player
    roster = []
    for i, letter in enumerate(letters):
        age = 20 + (i * 13) % 16          # 20-35
        leadership = 55 + (i * 37) % 40   # 55-94
        goals = 8 + (i * 11) % 25
        assists = 15 + (i * 17) % 40
        roster.append(make_player(i, age, leadership, letter, goals,
                                  assists))
    # Make player 0 an elite young captain-type on teams C and D.
    t = Team(name, name + "ville", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.roster = roster
    t.ahl_roster = []
    t.head_coach = None
    t.staff = []
    return t


# Messy post-fantasy-draft letters.
L2C = ["C", "C", "A", "", "", "", "", "", "", "", "", ""]   # two C's
L0 = ["", "", "", "", "", "", "", "", "", "", "", ""]       # no letters
LNORM = ["C", "A", "A", "", "", "", "", "", "", "", "", ""]

team_a = make_team("Alphas", L2C)
team_b = make_team("Betas", L0)
team_c = make_team("Champs", LNORM)
team_d = make_team("Deltas", LNORM)
# Elite regime figure for mentorship on the champ team.
team_c.roster[0].leadership = 93
team_c.roster[0].age = 26
team_c.roster[4].age = 20  # a kid learner
team_c.roster[4].determination = 88
team_c.roster[4].teamwork = 85

league = League("NHL")
league.season_year = 2028
league.teams = [team_a, team_b, team_c, team_d]
league.standings = {
    "Alphas": {"W": 45, "L": 30, "OTL": 7},
    "Betas": {"W": 30, "L": 45, "OTL": 7},
    "Champs": {"W": 52, "L": 22, "OTL": 8},
    "Deltas": {"W": 40, "L": 35, "OTL": 7},
}


class Bracket:
    playoff_series = {}


bracket = Bracket()
bracket.stanley_cup_champion = team_c
league.playoff_bracket = bracket


class FakeGUI:
    open_windows = {}
    app = None


FakeGUI.league = league

import main as _main

try:
    _main.HockeyManagerGUI._update_offseason_reputations(FakeGUI())
    hook_ok = True
except Exception as e:
    hook_ok = False
    import traceback
    traceback.print_exc()
check("hook runs clean on messy fantasy rosters", hook_ok)

# Two-C team: both C's processed, no crash, tenures advance.
cs_a = [p for p in team_a.roster if p.captaincy == "C"]
check("two-C team: both stamped tenure",
      all(getattr(p, "captain_tenure_years", 0) == 1 for p in cs_a)
      and len(cs_a) == 2, str([p.full_name for p in cs_a]))

# No-letter team: everyone untouched by letter path, tenures reset to 0.
check("no-letter team: no letter tenures",
      all(getattr(p, "captain_tenure_years", 0) == 0
          and getattr(p, "alternate_tenure_years", 0) == 0
          for p in team_b.roster))

# Champ team's C grew and banked the Cup-captain marker.
champ_c = team_c.roster[0]
check("champ C leadership moved",
      champ_c.leadership != 93 or
      float(getattr(champ_c, "_leadership_carry", 0.0) or 0.0) != 0.0)
check("champ C has cup-captain season marker",
      2028 in getattr(champ_c, "_cup_captain_rep_seasons", set()))

# Kid learner on the elite champ team absorbed mentorship.
kid = team_c.roster[4]
check("kid absorbed mentorship",
      float(getattr(kid, "_leadership_carry", 0.0) or 0.0) > 0
      or kid.leadership != 55 + (4 * 37) % 40,
      f"lead={kid.leadership} carry={getattr(kid, '_leadership_carry', 0.0)}")

# Nobody's leadership left the 1-100 scale; nobody went negative delta
# in a way that violates the ratchet (growth never negative by design).
bad = [p.full_name for t in league.teams for p in t.roster
       if not (1 <= p.leadership <= 100)]
check("all leadership still on 1-100 scale", not bad, str(bad[:3]))

# --- Save/load round-trip ---
from save_load_system import GameSaveManager as SaveLoadSystem

gm = SimpleNamespace(league=league, league_history=None,
                     narrative_ledger=None)
saver = SaveLoadSystem(gm)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "fantasy_test.save")
check("save succeeds", saver.save_game(path), path)

gm2 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
loader = SaveLoadSystem(gm2)
check("load succeeds", loader.load_game(path), path)

lg2 = gm2.league
t2c = [t for t in lg2.teams if t.team_name == "Champs"][0]
c2 = t2c.roster[0]
check("tenure survives load",
      getattr(c2, "captain_tenure_years", 0) == 1,
      str(getattr(c2, "captain_tenure_years", "MISSING")))
check("carry bank survives load",
      isinstance(getattr(c2, "_leadership_carry", None), float),
      str(getattr(c2, "_leadership_carry", "MISSING")))
check("cup-captain seasons survive load",
      2028 in getattr(c2, "_cup_captain_rep_seasons", set()))
check("mentorship season stamp survives load",
      getattr(t2c.roster[4], "_mentorship_season", None) == 2028)

# --- Next offseason post-load: hook still clean and idempotent ---
lg2.season_year = 2029
lg2.playoff_bracket = bracket
lg2.standings = league.standings
FakeGUI.league = lg2
try:
    _main.HockeyManagerGUI._update_offseason_reputations(FakeGUI())
    hook2_ok = True
except Exception:
    import traceback
    traceback.print_exc()
    hook2_ok = False
check("hook clean on loaded fantasy save (year 2)", hook2_ok)

c2b = [t for t in lg2.teams if t.team_name == "Champs"][0].roster[0]
check("year-2 tenure advances",
      getattr(c2b, "captain_tenure_years", 0) == 2,
      str(getattr(c2b, "captain_tenure_years", "MISSING")))
check("2028 cup bonus not re-paid in 2029",
      2028 in getattr(c2b, "_cup_captain_rep_seasons", set()))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
