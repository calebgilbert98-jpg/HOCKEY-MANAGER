"""Integration: the real GameManager._update_offseason_reputations() wires
captaincy growth, Cup-captain reputation, and mentorship correctly.

7 checks:
 1. Cup-winning young C: leadership grows, tenure advances.
 2. Cup C banks +4 MORE reputation than a letter-less roster-mate (+8 champ).
 3. A on a mediocre team: tenure reinforcement banked in the carry.
 4. Young letter-less kid on an elite Cup room: mentorship banked.
 5. 35-year-old letter-less vet: untouched (no mentorship, no letter path).
 6. Cup-captain rep bonus is season-idempotent on rerun.
 7. FULL rerun: leadership/reputation/carry identical after a second pass.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name}")


class StubStats:
    def __init__(self, points=60, games=82, goals=20, assists=40):
        self.points = points
        self.games_played = games
        self.goals = goals
        self.assists = assists


class P:
    _id = 0

    def __init__(self, name, age, leadership, letter,
                 determination=70, teamwork=70, points=60):
        P._id += 1
        self.id = P._id
        self.full_name = name
        self.age = age
        self.leadership = leadership
        self.captaincy = letter
        self.determination = determination
        self.teamwork = teamwork
        self.stats = StubStats(points=points)
        self.game_stars = {"first": 2, "second": 3, "third": 4}
        self.reputation = 60
        self.reputation_history = []
        self.controversy_history = []
        self.career_accolades = []


class Team:
    _id = 0

    def __init__(self, name, roster):
        Team._id += 1
        self.id = Team._id
        self.team_name = name
        self.roster = roster
        self.head_coach = None


# Champs: elite young C (92), prime A, high-character kid, old vet.
champ_c = P("Champ C", 24, 92, "C", points=95)
champ_a = P("Champ A", 29, 75, "A", points=70)
kid = P("Kid", 20, 55, None, determination=88, teamwork=84, points=45)
vet = P("Vet", 35, 80, None, points=50)
champs = Team("Champs", [champ_c, champ_a, kid, vet])

# Mids: mediocre team, prime C and A.
mid_c = P("Mid C", 28, 72, "C", points=55)
mid_a = P("Mid A", 29, 74, "A", points=58)
mids = Team("Mids", [mid_c, mid_a])


class Bracket:
    stanley_cup_champion = champs
    playoff_series = {}


class League:
    teams = [champs, mids]
    season_year = 2028
    playoff_bracket = Bracket()
    standings = {
        "Champs": {"W": 50, "L": 25, "OTL": 7},
        "Mids": {"W": 35, "L": 40, "OTL": 7},
    }


class FakeManager:
    league = League()
    open_windows = {}
    app = None


import main as _main

mgr = FakeManager()
_main.HockeyManagerGUI._update_offseason_reputations(mgr)

# 1. Cup-winning young C grows; tenure advances.
check("Cup C leadership grew", champ_c.leadership > 92)
check("Cup C tenure == 1", champ_c.captain_tenure_years == 1)

# 2. Cup C banks both bonuses, exactly once (markers stamped by the hook).
check("Cup C rep markers stamped",
      2028 in getattr(champ_c, "_cup_captain_rep_seasons", set())
      and 2028 in getattr(champ_c, "_championship_rep_seasons", set()))
check("Cup C outgains letter-less mate",
      (champ_c.reputation - 60) > (kid.reputation - 60))

# 3. A on a mediocre team banks tenure reinforcement.
check("mid A carry banked",
      float(getattr(mid_a, "_leadership_carry", 0.0) or 0.0) > 0.2)
check("mid A tenure == 1", mid_a.alternate_tenure_years == 1)

# 4. Kid absorbs mentorship from the elite Cup room.
check("kid mentorship banked",
      float(getattr(kid, "_leadership_carry", 0.0) or 0.0) > 0.3)

# 5. Old letter-less vet untouched.
check("vet leadership unchanged", vet.leadership == 80)
check("vet carry empty",
      float(getattr(vet, "_leadership_carry", 0.0) or 0.0) == 0.0)

# Snapshot for the rerun comparison.
snap = {}
for t in League.teams:
    for p in t.roster:
        snap[p.full_name] = (
            p.leadership, p.reputation,
            float(getattr(p, "_leadership_carry", 0.0) or 0.0),
            getattr(p, "captain_tenure_years", 0),
            getattr(p, "alternate_tenure_years", 0),
        )

_main.HockeyManagerGUI._update_offseason_reputations(mgr)

# 6. Cup-captain bonus not double-paid.
check("Cup C rep unchanged on rerun",
      champ_c.reputation == snap["Champ C"][1])

# 7. Full second pass changes nothing.
stable = True
for t in League.teams:
    for p in t.roster:
        now = (
            p.leadership, p.reputation,
            float(getattr(p, "_leadership_carry", 0.0) or 0.0),
            getattr(p, "captain_tenure_years", 0),
            getattr(p, "alternate_tenure_years", 0),
        )
        if now != snap[p.full_name]:
            stable = False
            print(f"   drift: {p.full_name} {snap[p.full_name]} -> {now}")
check("full rerun is stable", stable)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
