# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: fan hate -- betrayals the fanbase doesn't forgive.

- Award races now spark at intensity 10 (much less base).
- Defecting to a franchise rival turns the old fans (fan_player record).
- Joining the team that just eliminated your old club turns the old fans.
- A blindsiding trade demand (fan favourite asking out) turns the fans.
- fan_favourite_score reads the hate when handed the store.
- First game back in the old barn: hostile homecoming fires exactly once.
"""
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")
import reputation_system as rs

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} {detail}")


class FakePlayer:
    _n = 0

    def __init__(self, name="Winger", **kw):
        FakePlayer._n += 1
        self.id = 1000 + FakePlayer._n
        self.full_name = f"{name} {FakePlayer._n}"
        self.primary_position = "LW"
        self.games_played = kw.get("games_played", 82)
        self.points = kw.get("points", 90)
        self.reputation = kw.get("reputation", 60)
        self.leadership = kw.get("leadership", 70)
        self.captaincy = kw.get("captaincy", "")
        self.controversy = kw.get("controversy", 30)
        self.age = kw.get("age", 27)
        self.discipline = 60
        self.composure = 60
        self.aggressiveness = 60
        self.teamwork = 60
        self.selfishness = 40


class FakeTeam:
    def __init__(self, name):
        self.team_name = name
        self.roster = []
        self.gm_name = f"GM {name}"


def rivals(a, b, intensity):
    r = {"a": ("team", a.team_name), "b": ("team", b.team_name),
         "a_name": a.team_name, "b_name": b.team_name, "kind": "team_team",
         "intensity": intensity, "origin": "regional", "story": "x",
         "grudge": 75, "career_cost": 0,
         "date": date.today().isoformat()}
    return r


def fan_hate_of(store, player, team):
    out = [r for r in rs.get_rivalries_for(store, player)
           if r.get("kind") == "fan_player"
           and (r["b"] if r.get("a") == ("player", player.id)
                else r.get("a")) == ("team", team.team_name)]
    return out


# ------------------------------------------------------- award race base
random.seed(7)
store = []
pa = FakePlayer("HotheadA")
pb = FakePlayer("HotheadB")
pa.base_controversy = pb.base_controversy = 60  # takes-it-personally gate
r = rs.record_award_race(store, pa, pb, "Hart Trophy")
check("award race sparks at intensity 10", r.get("intensity") == 10,
      f"got {r.get('intensity')}")
saint1, saint2 = FakePlayer("SaintA"), FakePlayer("SaintB")
saint1.base_controversy = saint2.base_controversy = 10
check("saints still gate out",
      rs.record_award_race(store, saint1, saint2, "Hart Trophy") == {})

# ------------------------------------------------------- rival defection
random.seed(11)
store = []
old, new = FakeTeam("Bruins"), FakeTeam("Canadiens")
store.append(rivals(old, new, 62))  # franchise rivals
star = FakePlayer("Star")
rs.on_player_transfer(store, star, from_team=old, to_team=new)
hate = fan_hate_of(store, star, old)
check("defecting to a franchise rival turns the old fans", len(hate) == 1,
      f"got {len(hate)}")
check("defection origin + heat",
      hate and hate[0]["origin"] == "defection"
      and hate[0]["intensity"] == 55, str(hate and hate[0]))
check("hate record starts un-faced",
      hate and hate[0].get("faced") is False)
# the NEW team's fans don't hate him
check("new fans don't hate him", fan_hate_of(store, star, new) == [])

# mild rivalry: no betrayal narrative
store2 = []
mild_a, mild_b = FakeTeam("MildA"), FakeTeam("MildB")
store2.append(rivals(mild_a, mild_b, 30))
role = FakePlayer("Role")
rs.on_player_transfer(store2, role, from_team=mild_a, to_team=mild_b)
check("mild rivalry move: no fan hate",
      fan_hate_of(store2, role, mild_a) == [])

# ------------------------------------------------------- eliminator defection
store3 = []
elim_old, elim_new = FakeTeam("Leafs"), FakeTeam("Panthers")
rs.record_playoff_series(store3, elim_new, elim_old, games=7, upset=True)
w = FakePlayer("Winger")
rs.on_player_transfer(store3, w, from_team=elim_old, to_team=elim_new)
hate3 = fan_hate_of(store3, w, elim_old)
check("joining the eliminator turns the old fans",
      len(hate3) == 1 and hate3[0]["origin"] == "elimination_defection",
      str([h.get("origin") for h in hate3]))
# wrong direction: no hate (he didn't join the team that beat his)
store3b = []
rs.record_playoff_series(store3b, elim_new, elim_old, games=5)
w2 = FakePlayer("Winger")
rs.on_player_transfer(store3b, w2, from_team=elim_new, to_team=elim_old)
check("joining the eliminated team: no hate",
      fan_hate_of(store3b, w2, elim_new) == [])
# stale series (>1yr): no hate
store3c = []
rs.record_playoff_series(store3c, elim_new, elim_old, games=7)
for _r in store3c:
    _r["date"] = (date.today() - timedelta(days=500)).isoformat()
w3 = FakePlayer("Winger")
rs.on_player_transfer(store3c, w3, from_team=elim_old, to_team=elim_new)
check("year-old elimination: no hate",
      fan_hate_of(store3c, w3, elim_old) == [])

# ------------------------------------------------------- trade demand
store4 = []
dem_team = FakeTeam("DemTeam")
beloved = FakePlayer("Beloved", points=100, reputation=80, leadership=85,
                     captaincy="C")
base = rs.fan_favourite_score(beloved, dem_team)["score"]
check("test star is a fan favourite", base >= 70, f"score {base}")
rs.record_fan_hate(store4, beloved, dem_team, "trade_demand",
                   "Beloved 1 blindsided the DemTeam faithful with a trade demand.",
                   intensity=40, grudge=55)
hated = rs.fan_favourite_score(beloved, dem_team, rivalries=store4)
check("fan hate tanks the score",
      hated["score"] < base - 15,
      f"{base} -> {hated['score']}")
check("hate reason is legible",
      any("trade demand" in x for x in hated["reasons"]),
      str(hated["reasons"]))
# without the store, no penalty (old call sites unchanged)
plain = rs.fan_favourite_score(beloved, dem_team)
check("no store, no penalty", plain["score"] == base)
# fringe malcontent demanding out: no blindsiding (gate is fan favourite)
fringe = FakePlayer("Fringe", points=20, reputation=20, leadership=40)
check("fringe player is not a fan favourite",
      not rs.is_fan_favourite(fringe, dem_team))

# ------------------------------------------------------- homecoming
store5 = []
barn, road = FakeTeam("Barn"), FakeTeam("Road")
store5.append(rivals(barn, road, 70))
ret = FakePlayer("Returnee")
road.roster.append(ret)
rs.on_player_transfer(store5, ret, from_team=barn, to_team=road)
check("defection recorded for homecoming", len(fan_hate_of(store5, ret, barn)) == 1)
# tension driver sees it (read-only)
bd = rs.game_tension_breakdown(barn, road, rivalries=store5)
check("tension driver flags the hostile homecoming",
      any("Hostile homecoming" in d["label"] for d in bd["drivers"]),
      str([d["label"] for d in bd["drivers"]]))
# consume: fires once
hits = rs.consume_homecomings(store5, barn, road)
check("homecoming consumed once", len(hits) == 1 and hits[0]["player"] is ret)
hits2 = rs.consume_homecomings(store5, barn, road)
check("second game back is just a game", hits2 == [])
bd2 = rs.game_tension_breakdown(barn, road, rivalries=store5)
check("driver gone after the homecoming",
      not any("Hostile homecoming" in d["label"] for d in bd2["drivers"]))
# trade-demand hate does NOT make a homecoming (no barn to return to)
store6 = []
t6 = FakeTeam("T6")
grump = FakePlayer("Grump")
rs.record_fan_hate(store6, grump, t6, "trade_demand", "demanded out",
                   intensity=40, grudge=55)
t6b = FakeTeam("T6b")
t6b.roster.append(grump)
check("trade demand is not a homecoming",
      rs.consume_homecomings(store6, t6, t6b) == [])

print(f"\nQA fan_hate: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
