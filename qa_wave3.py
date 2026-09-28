"""QA for Wave 3 remainder: crowd scaling, milestones, grudge week,
immortality (retirement/HOF/numbers/era/ceremonies). Headless."""
import random
import sys

sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


# --- arena_atmosphere -------------------------------------------------------
import arena_atmosphere as aa

n = aa.pregame_crowd(None, None)
check("neutral energy in range", 8 <= n["energy"] <= 97)
check("neutral mood positive", n["mood"] > 0)
check("neutral not big game", n["big_game"] is False)

g7 = aa.pregame_crowd(None, None, is_playoff=True, series_game=7,
                      elimination_game=True)
check("game7 louder", g7["energy"] > n["energy"] + 15)
check("game7 big game", g7["big_game"] is True)
check("game7 drivers mention it",
      any("Game 7" in d for d in g7["drivers"]))

hm, am = aa.crowd_effects(95, 90, away_avg_age=24.0)
check("loud home lift bounded", 1.0 < hm <= 1.03)
check("young visitors rattled", 0.97 <= am < 1.0)
hm2, am2 = aa.crowd_effects(95, 90, away_avg_age=31.0)
check("veterans shrug", am2 == 1.0)
hm3, _ = aa.crowd_effects(80, -70, away_avg_age=29.0)
check("toxic crowd drags home", hm3 < 1.0)
check("effects symmetric clamp",
      all(0.97 <= x <= 1.03 for x in (hm, am, hm2, am2, hm3)))

st = dict(g7)
aa.live_crowd_update(st, True, 1, 3, 3)   # home cuts deficit in 3rd
check("comeback erupts", st["energy"] > g7["energy"] and st["mood"] > g7["mood"])
st2 = dict(g7)
aa.live_crowd_update(st2, False, 1, 2, 3)  # visitors take late lead
check("nervous building", st2["mood"] < g7["mood"])

hype = aa.crowd_hype_for_tension(90, 80)
check("hype scale sane", 70 <= hype <= 100)
check("hype default ~50", 40 <= aa.crowd_hype_for_tension(38, 30) <= 60)

# --- tension breakdown crowd_hype -------------------------------------------
import reputation_system as rs
b0 = rs.game_tension_breakdown(None, None, [])
b1 = rs.game_tension_breakdown(None, None, [], crowd_hype=90.0)
check("crowd hype raises tension", b1["tension"] > b0["tension"])
check("crowd driver labeled",
      any("crowd" in d["label"].lower() for d in b1["drivers"]))
b2 = rs.game_tension_breakdown(None, None, [], crowd_hype=10.0)
check("flat crowd cools", b2["tension"] <= b0["tension"])
# default 0 = old behavior unchanged
check("crowd_hype=0 default", b0 == rs.game_tension_breakdown(None, None, []))

# --- impact_system crowd ----------------------------------------------------
import impact_system as imp


class FakeP:
    def __init__(self):
        self.overall = 85
        self.shooting = 80
        self.shooting_power = 80
        self.shooting_accuracy = 80


ctx = imp.ImpactContext(crowd_energy=95.0, crowd_mood=90.0)
check("nudge favors loud+supportive", imp._crowd_tier_nudge(ctx) > 1.0)
ctx2 = imp.ImpactContext(crowd_energy=95.0, crowd_mood=-90.0)
check("nudge punishes hostile", imp._crowd_tier_nudge(ctx2) < 1.0)
ctx3 = imp.ImpactContext()
check("nudge neutral ~1", abs(imp._crowd_tier_nudge(ctx3) - 1.0) < 0.05)
# classifiers run with crowd fields
t = imp.classify_shot_impact(FakeP(), ctx)
check("shot classifier tier valid", t in (imp.TIRED, imp.NORMAL, imp.BIG))

# --- milestones --------------------------------------------------------------
import milestones as ms


class MP:
    _i = 0

    def __init__(self, goals, games, age=30, goalie=False):
        MP._i += 1
        self.id = MP._i
        self.full_name = f"Player {MP._i}"
        self.career_goals = goals
        self.career_games = games
        self.career_wins = 0
        self.age = age
        self.primary_position = type("P", (), {"name": "GOALIE" if goalie else "CENTER"})()


class MT:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster


class ML:
    def __init__(self, teams):
        self.teams = teams


p1 = MP(498, 900)   # 2 away from 500 goals
p2 = MP(100, 999)   # 1 away from 1000 games
p3 = MP(10, 50)     # nothing
league = ML([MT("AAA", [p1, p3]), MT("BBB", [p2])])
watches = ms.scan_watches(league)
check("two watches found", len(watches) == 2)
check("sorted closest first", watches[0]["remaining"] == 1)
check("tonight teams", ms.watch_teams_tonight(watches) == {"AAA", "BBB"})
note = ms.venue_note(watches[0], MT("BBB", []), MT("AAA", []), None)
check("venue note home", "at home" in note)

# hit detection + idempotency
p2.career_games = 1000
hits = ms.check_hits(league, watches)
check("hit detected", len(hits) == 1 and hits[0]["player_name"] == p2.full_name)
hits2 = ms.check_hits(league, watches)
check("no double celebration", hits2 == [])

# --- immortality --------------------------------------------------------------
import immortality as im

check("no retire under line", im.retire_probability(30, False) == 0.0)
check("retire rises with age",
      im.retire_probability(44, False) > im.retire_probability(37, False))
check("goalies later",
      im.retire_probability(37, True) == 0.0 and im.retire_probability(37, False) > 0)


class RP:
    _i = 0

    def __init__(self, age, goals, games, cups=0, goalie=False):
        RP._i += 1
        self.id = RP._i
        self.full_name = f"Vet {RP._i}"
        self.age = age
        self.career_goals = goals
        self.career_games = games
        self.career_assists = goals
        self.career_points = goals * 2
        self.career_wins = 0
        self.career_shutouts = 0
        self.stanley_cups = cups
        self.awards_won = []
        self.jersey_number = 19
        self.primary_position = type("P", (), {"name": "GOALIE" if goalie else "CENTER"})()


class RT:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster
        self.city = name


random.seed(7)
oldies = [RP(41, 500, 1300, cups=2), RP(28, 150, 400), RP(39, 50, 900)]
rleague = ML([RT("AAA", oldies)])
retired = im.process_retirements(rleague, 2026)
check("old star retires", any(s["name"] == "Vet 1" for s in retired))
check("youngster stays", any(p.full_name == "Vet 2" for p in rleague.teams[0].roster))
check("snapshots on league", len(rleague.retired_players) == len(retired))

star = next(s for s in retired if s["name"] == "Vet 1")
sc = im.career_score(star)
check("star scores high", sc >= 60)
check("number worthy", im.number_worthy(star))
team = rleague.teams[0]
check("retire number", im.retire_number(team, star, 2026) is True)
check("number blocked", im.is_number_retired(team, 19) is True)
check("no double retire", im.retire_number(team, star, 2026) is False)
check("ceremony queued", getattr(team, "_pending_ceremony", None) is not None)
num = im.assign_jersey_number(team, RP(22, 0, 0))
check("new number avoids retired", num != 19)


class FakeHist:
    def __init__(self):
        self.hall_of_fame = []
        self._seasons = []

    def induct(self, player, year):
        rec = {"name": player.full_name, "year_inducted": year}
        self.hall_of_fame.append(rec)
        return rec

    def champions_list(self):
        return list(self._seasons)


# ballot: 3-year wait
hist = FakeHist()
rep = im.hof_ballot(rleague, hist, 2026)
check("waiting period respected", rep["waiting"] >= 1 and not rep["inducted"])
# age the snapshot past the wait
for s in rleague.retired_players:
    s["retired_year"] = 2022
random.seed(11)
rep2 = im.hof_ballot(rleague, hist, 2026)
check("star inducted after wait", any(i["name"] == "Vet 1" for i in rep2["inducted"]))
check("history has him", any(h["name"] == "Vet 1" for h in hist.hall_of_fame))


class FakeApp:
    def __init__(self):
        self.news = []

    def add_news(self, line):
        self.news.append(line)


class FakeSim:
    def __init__(self):
        self.team_boost = {"AAA": 1.0}


app = FakeApp()
sim = FakeSim()
check("ceremony consumed", im.consume_ceremony(app, team, sim) is True)
check("ceremony news", len(app.news) == 1 and "rafters" in app.news[0])
check("ceremony boost bounded", sim.team_boost["AAA"] == 1.02)
check("ceremony cleared", getattr(team, "_pending_ceremony", None) is None)

# era arguments
hist._seasons = [
    {"year": 2026, "champion": "AAA",
     "standings": [{"team": "AAA", "points": 130, "gf": 300, "ga": 180}],
     "series_score": "4-0"},
    {"year": 2025, "champion": "BBB",
     "standings": [{"team": "BBB", "points": 100, "gf": 250, "ga": 230}],
     "series_score": "4-3"},
]
arg = im.era_argument(hist)
check("coronation fires", arg is not None and arg["verdict"] == "coronation")
check("era news has two sides", "Greatest team ever?" in im.era_argument_news(arg))
hist._seasons[0]["standings"][0].update({"points": 80, "gf": 240, "ga": 250})
hist._seasons[0]["series_score"] = "4-3"
arg2 = im.era_argument(hist)
check("weak champ gets no argument", arg2 is None)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
