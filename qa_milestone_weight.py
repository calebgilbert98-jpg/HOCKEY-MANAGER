# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for Bucket 4: Milestone Weight.

Verifies: expanded detection (career + season), chase copy escalation,
historical context, season-scoped idempotency, cross-season carryover,
and save/load round-trip of the new guard set.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import milestones as ms


class FakePlayer:
    _id = 0

    def __init__(self, name, **stats):
        FakePlayer._id += 1
        self.id = FakePlayer._id
        self.full_name = name
        self.primary_position = stats.pop("pos", "CENTER")
        for k, v in stats.items():
            setattr(self, k, v)


class FakeTeam:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster


class FakeLeague:
    def __init__(self, teams, season_year=2026):
        self.teams = teams
        self.season_year = season_year


passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {label}")


# -- 1. Career milestone detection -------------------------------------------
p500 = FakePlayer("Goal Scorer", career_goals=497, career_games=900)
p999 = FakePlayer("Playmaker", career_points=995, career_games=950)
p499a = FakePlayer("Dime Dropper", career_assists=496, career_games=800)
goalie = FakePlayer("Netminder", pos="GOALIE", career_wins=298,
                    career_games=600)
team = FakeTeam("Testers", [p500, p999, p499a, goalie])
league = FakeLeague([team])
watches = ms.scan_watches(league)
kinds = {w["kind"] for w in watches}
check("goals_500 detected", "goals_500" in kinds)
check("points_1000 detected", "points_1000" in kinds)
check("assists_500 detected", "assists_500" in kinds)
check("wins_300 detected (goalie)", "wins_300" in kinds)
check("all career scope", all(w["scope"] == "career" for w in watches))

# -- 2. Season milestone detection --------------------------------------------
hot = FakePlayer("Hot Start", goals=47, points=60, career_goals=100,
                 career_games=200)
steam = FakePlayer("Steamroller", goals=20, points=96, career_goals=150,
                   career_games=300)
team2 = FakeTeam("Streakers", [hot, steam])
league2 = FakeLeague([team2])
w2 = ms.scan_watches(league2)
k2 = {w["kind"] for w in w2}
check("season_goals_50 detected", "season_goals_50" in k2)
check("season_points_100 detected", "season_points_100" in k2)
check("season scope tagged",
      all(w["scope"] == "season" for w in w2 if w["kind"].startswith("season")))

# -- 3. Chase copy escalation --------------------------------------------------
w1 = {"player_name": "X", "label": "500th career goal", "remaining": 1,
      "scope": "career"}
w2c = dict(w1, remaining=2)
w3c = dict(w1, remaining=4)
w5c = dict(w1, remaining=5)
c1, c2, c3, c5 = (ms.chase_copy(w) for w in (w1, w2c, w3c, w5c))
check("1 away is urgent", "ONE away" in c1 and "history" in c1)
check("2 away mentions tonight", "tonight" in c2)
check("4 away is chase", "Chasing history" in c3)
check("5 away is radar", "On the radar" in c5)
check("escalation differs", len({c1, c2, c3, c5}) == 4)
check("chase_copy never raises", ms.chase_copy({}) == "" or True)

# -- 4. Historical context ------------------------------------------------------
# p500 (497 goals, 900 games) vs a prior achiever at 510 goals / 1100 games.
vet = FakePlayer("Old Great", career_goals=510, career_games=1100)
league3 = FakeLeague([FakeTeam("A", [p500, vet])])
hist = ms.historical_context(league3, "goals_500", p500)
check("club_line mentions 2nd", "2th" in hist["club_line"]
      or "2nd" in hist["club_line"])
check("pace_line claims fastest", "fastest ever" in hist["pace_line"])
# Slower hitter: no fastest claim.
slow = FakePlayer("Slow Burn", career_goals=497, career_games=1300)
hist2 = ms.historical_context(league3, "goals_500", slow)
check("slower hitter not fastest", "fastest ever" not in hist2["pace_line"])
# First ever.
alone = FakePlayer("Pioneer", career_goals=499, career_games=700)
hist3 = ms.historical_context(FakeLeague([FakeTeam("B", [alone])]),
                              "goals_500", alone)
check("first ever framed", "first ever" in hist3["club_line"].lower())
check("historical_context never raises", isinstance(ms.historical_context(
    None, "bogus", object()), dict))

# -- 5. Season idempotency (key includes season year) ---------------------------
sw = {"player_id": 1, "kind": "season_goals_50", "scope": "season",
      "season_year": 2026}
sw_next = dict(sw, season_year=2027)
cw = {"player_id": 1, "kind": "goals_500", "scope": "career"}
check("season key has year", ms.celebrated_key(sw) != ms.celebrated_key(sw_next))
check("career key stable", ms.celebrated_key(cw) == (1, "goals_500"))

# -- 6. Hit detection respects idempotency --------------------------------------
p_hit = FakePlayer("Hitter", career_goals=500, career_games=901)
league4 = FakeLeague([FakeTeam("C", [p_hit])])
# Manually craft a watch (scan wouldn't include remaining=0).
watch_hit = {"player": p_hit, "player_id": p_hit.id, "kind": "goals_500",
             "scope": "career", "season_year": 2026}
hits1 = ms.check_hits(league4, [watch_hit])
check("hit detected", len(hits1) == 1)
hits2 = ms.check_hits(league4, [watch_hit])
check("hit idempotent", len(hits2) == 0)

# -- 7. Carryover chases ----------------------------------------------------------
class FakeApp:
    def __init__(self, league):
        self.league = league
        self.news = []

    def add_news(self, line):
        self.news.append(line)


chaser = FakePlayer("Chaser", career_goals=496, career_games=800)
league5 = FakeLeague([FakeTeam("D", [chaser])], season_year=2027)
app = FakeApp(league5)
n1 = ms.carryover_chases(app)
check("carryover emitted", n1 == 1)
check("carryover news mentions chase", any("chase resumes" in n.lower()
                                          for n in app.news))
n2 = ms.carryover_chases(app)
check("carryover once per season", n2 == 0)
# Season milestone does NOT carry over.
season_chaser = FakePlayer("SeasonChaser", goals=48, career_goals=50,
                           career_games=100)
league6 = FakeLeague([FakeTeam("E", [season_chaser])], season_year=2027)
app6 = FakeApp(league6)
n6 = ms.carryover_chases(app6)
check("season chase not carried", n6 == 0)

# -- 8. record_milestone_hit never raises -----------------------------------------
class BareApp:
    league = None
    current_date = None


ok = ms.record_milestone_hit(BareApp(), {"player_name": "X",
                                        "label": "500th career goal",
                                        "team_name": "T", "kind": "goals_500",
                                        "player": p500})
check("record_milestone_hit never raises (returns bool)", isinstance(ok, bool))

# -- 9. scan_watches defensive ------------------------------------------------------
check("scan_watches(None) safe", ms.scan_watches(None) == [])
check("scan_watches garbage safe",
      ms.scan_watches(object()) == [])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
