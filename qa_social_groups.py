# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: FM24-style young social groups.

Affinity composes nationality, hometown, pre-existing relationships,
age and circumstances; the room dynamic (spirits/cohesion) feeds back
into grouping; strong leaders keep morale in check; newcomers integrate
by affinity -- dynamic, never fatal. Deterministic: fake players.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import dressing_room as dr


def make_player(name, nat="Canada", birthplace="", age=25, tenure="4+ years",
                letter="", leadership=50, morale=70, pid=None,
                relationships=None, drafted_year=None, ovr=75, gp=100,
                goalie=False, teamwork=50, selfishness=50, controversy=20,
                ambition=""):
    p = SimpleNamespace(
        id=pid if pid is not None else name,
        full_name=name, name=name,
        nationality=nat, birthplace=birthplace, age=age,
        team_tenure=tenure, captaincy=letter, leadership=leadership,
        morale=morale, relationships=dict(relationships or {}),
        drafted_year=drafted_year,
        primary_position=SimpleNamespace(value="G" if goalie else "C"),
        teamwork=teamwork, selfishness=selfishness,
        base_controversy=controversy, ambition=ambition,
        stats=SimpleNamespace(games_played=gp),
        overall_rating=lambda _o=ovr: _o,
    )
    return p


def make_team(players, name="Test Club"):
    return SimpleNamespace(team_name=name, roster=list(players), staff=[])


passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    if not cond:
        print(f"  FAIL: {label}")


# 1-8: affinity composition ----------------------------------------------
a = make_player("A", nat="Canada", age=24, birthplace="Toronto, ON")
b = make_player("B", nat="Canada", age=25, birthplace="Ottawa, ON")
c = make_player("C", nat="Sweden", age=24, birthplace="Stockholm, SE")
check("same nationality beats different",
      dr.affinity(a, b) > dr.affinity(a, c))
same_city = make_player("D", nat="Canada", age=30, birthplace="Toronto, ON")
same_region = make_player("E", nat="Canada", age=30, birthplace="Ottawa, ON")
diff = make_player("F", nat="Canada", age=30, birthplace="Calgary, AB")
check("same city tops same region",
      dr.affinity(a, same_city) > dr.affinity(a, same_region))
check("same region tops different",
      dr.affinity(a, same_region) > dr.affinity(a, diff))

close = make_player("G", age=26)
mid = make_player("H", age=29)
far = make_player("I", age=36)
check("age proximity graded", dr.affinity(a, close) > dr.affinity(a, mid) >
      dr.affinity(a, far))
kid1 = make_player("K1", age=20, nat="Latvia")
kid2 = make_player("K2", age=21, nat="Latvia")
old1 = make_player("O1", age=34, nat="Latvia")
old2 = make_player("O2", age=35, nat="Latvia")
check("kids bond extra", dr.affinity(kid1, kid2) > dr.affinity(old1, old2))

p = make_player("P", pid="p")
q = make_player("Q", pid="q", relationships={"p": 80})
r = make_player("R", pid="r", relationships={"p": -70})
check("friends closer than strangers", dr.affinity(p, q) > dr.affinity(p, a))
check("rivals farther than strangers", dr.affinity(p, r) < dr.affinity(p, a))
check("affinity bounded", all(5 <= dr.affinity(x, y) <= 97
                              for x, y in ((a, b), (p, q), (p, r))))
check("self affinity is perfect", dr.affinity(a, a) == 100)

d1 = make_player("D1", drafted_year=2022)
d2 = make_player("D2", drafted_year=2022)
d3 = make_player("D3", drafted_year=2015)
check("same draft class bonds", dr.affinity(d1, d2) > dr.affinity(d1, d3))
n1 = make_player("N1", tenure="This season", nat="Norway")
n2 = make_player("N2", tenure="This season", nat="Norway")
n3 = make_player("N3", tenure="4+ years", nat="Norway")
check("new arrivals bond", dr.affinity(n1, n2) > dr.affinity(n1, n3))

# 9-16: group formation ----------------------------------------------------
young_swe = [make_player(f"YS{i}", nat="Sweden", age=20 + i % 2,
                         tenure="This season") for i in range(4)]
vets_can = [make_player(f"VC{i}", nat="Canada", age=31,
                        tenure="4+ years") for i in range(5)]
lone = make_player("Lone", nat="Finland", age=29, tenure="2 years")
team = make_team(young_swe + vets_can + [lone])
groups = dr.form_cliques(team)
check("two groups form", len(groups) == 2)
names = " ".join(g["name"] for g in groups)
check("young group named young", "young" in names.lower())
check("lone floats", [f["name"] for f in dr.floaters(team)] == ["Lone"])
check("group carries leader", all(g["leader"] and g["leader_id"]
                                  for g in groups))
check("bond in range", all(0 < g["bond"] <= 0.95 for g in groups))
check("mean_age recorded",
      any(g["mean_age"] is not None and g["mean_age"] <= 23 for g in groups))

# Hometown over nationality: three Toronto boys across passports.
t1 = make_player("T1", nat="Canada", birthplace="Toronto, ON", age=27)
t2 = make_player("T2", nat="USA", birthplace="Toronto, ON", age=28)
t3 = make_player("T3", nat="Sweden", birthplace="Toronto, ON", age=26)
rest = [make_player(f"R{i}", nat="Canada", birthplace="Calgary, AB", age=30,
                    tenure="4+ years") for i in range(5)]
team2 = make_team([t1, t2, t3] + rest)
g2 = dr.form_cliques(team2)
check("hometown group forms",
      any("Toronto" in g["name"] for g in g2))

# Tightness: a loose fit doesn't dilute a tight group.
core = [make_player(f"C{i}", nat="Canada", age=30, tenure="4+ years")
        for i in range(4)]
loose = make_player("Loose", nat="Canada", age=30, tenure="This season",
                    birthplace="Vancouver, BC")
team3 = make_team(core + [loose])
g3 = dr.form_cliques(team3)
check("loose fit floats",
      [f["name"] for f in dr.floaters(team3)] == ["Loose"])
check("core stays grouped", len(g3) == 1 and len(g3[0]["members"]) == 4)

# 17-21: room dynamic -------------------------------------------------------
check("cohesion tight room high", dr.cohesion(team) > 60)
scattered = make_team([make_player(f"S{i}", nat=n, age=20 + i * 3,
                                    tenure="This season" if i % 2 else "4+ years")
                       for i, n in enumerate(
                           ["Canada", "Sweden", "Finland", "USA", "Russia",
                            "Czech Republic", "Norway", "Denmark"])])
check("cohesion scattered room low",
      dr.cohesion(scattered) < dr.cohesion(team))
atm = dr.room_atmosphere(team)
check("atmosphere labeled",
      atm["label"] in ("Electric", "Tight-knit", "Steady", "Strained",
                       "Fractured"))
check("atmosphere carries parts",
      all(k in atm for k in ("score", "mood", "cohesion")))
gloomy = make_team([make_player(f"M{i}", morale=20) for i in range(6)])
check("sour room atmosphere strained-or-worse",
      dr.room_atmosphere(gloomy)["label"] in ("Strained", "Fractured"))

# High spirits loosen circles: a borderline player joins when happy.
border = [make_player(f"B{i}", nat="Canada", age=30, tenure="4+ years")
          for i in range(4)]
edge = make_player("Edge", nat="Canada", age=30, tenure="This season")
happy_team = make_team(border + [edge])
for pl in happy_team.roster:
    pl.morale = 90
sad_team = make_team([make_player(f"B{i}", nat="Canada", age=30,
                                  tenure="4+ years") for i in range(4)] +
                     [make_player("Edge", nat="Canada", age=30,
                                  tenure="This season")])
for pl in sad_team.roster:
    pl.morale = 30
check("high spirits group more inclusively",
      len(dr.form_cliques(happy_team)) >= len(dr.form_cliques(sad_team)))

# 22-28: leaders keep morale in check ----------------------------------------
cap = make_player("Cap", letter="C", leadership=90, morale=80,
                  tenure="4+ years", ovr=85, gp=700)
m1 = make_player("M1", tenure="4+ years", morale=70)
m2 = make_player("M2", tenure="4+ years", morale=70)
out = make_player("Out", nat="Sweden", tenure="This season", morale=70)
team4 = make_team([cap, m1, m2, out])
check("dampen halves ambient hit",
      dr._leader_dampen(team4, m1, -4) == -2.0)
check("dampen spares floaters", dr._leader_dampen(team4, out, -4) == -4)
cap.morale = 30
check("gloomy leader spreads gloom",
      dr._leader_dampen(team4, m1, -4) == -5.0)
cap.morale = 80
check("positive untouched", dr._leader_dampen(team4, m1, 4) == 4)

m2.morale = 42
settle_lines = dr._leaders_settle(team4)
check("leader pulls up the brink", m2.morale == 43 and settle_lines)
m2.morale = 60
check("no settle when nobody's low",
      not dr._leaders_settle(team4))
weak1 = make_player("W1", leadership=40, tenure="4+ years")
weak2 = make_player("W2", leadership=45, tenure="4+ years")
weak3 = make_player("W3", leadership=38, tenure="4+ years")
team5 = make_team([weak1, weak2, weak3])
check("weak voice doesn't dampen",
      dr._leader_dampen(team5, weak2, -4) == -4)

# 29-32: newcomer integration -------------------------------------------------
swe_vets = [make_player(f"SV{i}", nat="Sweden", age=28, tenure="4+ years",
                        leadership=85, ovr=86, gp=800, morale=75)
            for i in range(4)]
team6 = make_team(swe_vets)
kid = make_player("Kid", nat="Sweden", age=21, tenure="This season",
                  ovr=76, gp=20)
lines = dr.cascade_on_arrival(team6, kid, how="signing")
check("newcomer finds his guys",
      any("familiar faces" in ln for ln in lines))
check("strong leader takes him under wing",
      any("under his wing" in ln for ln in lines))
check("wing softens landing", kid.morale == 69)

stranger = make_player("Stranger", nat="Japan", age=26,
                       tenure="This season", ovr=74, gp=60)
lines2 = dr.cascade_on_arrival(team6, stranger, how="signing")
check("true outsider stays outsider",
      any("outsider" in ln for ln in lines2) and stranger.morale == 64)

# 33-38: great room names -------------------------------------------------
mafia = [make_player(f"SM{i}", nat="Sweden", age=27, tenure="2 years")
         for i in range(4)]
team7 = make_team(mafia + [make_player(f"ZZ{i}", nat="Canada", age=30,
                                       tenure="4+ years") for i in range(4)])
g7 = dr.form_cliques(team7)
check("the Swedish Mafia", any(g["name"] == "The Swedish Mafia" for g in g7))

tenders = [make_player(f"G{i}", nat=n, age=28 + i, tenure="4+ years",
                       birthplace="Toronto, ON", goalie=True)
           for i, n in enumerate(["Canada", "Sweden", "USA"])]
team8 = make_team(tenders + [make_player(f"SK{i}", nat="Canada", age=25)
                             for i in range(5)])
g8 = dr.form_cliques(team8)
check("the goalies' union", any(g["name"] == "The goalies' union"
                                for g in g8))

olds = [make_player(f"V{i}", nat=n, age=34 + i, tenure="4+ years",
                    drafted_year=2008)
        for i, n in enumerate(["Canada", "USA", "Finland"])]
team9 = make_team(olds)
g9 = dr.form_cliques(team9)
check("the old guard", any(g["name"] == "The old guard" for g in g9))

finns = [make_player(f"FN{i}", nat="Finland", age=26, tenure="2 years")
         for i in range(3)]
team10 = make_team(finns + [make_player(f"Q{i}", nat="Canada", age=30,
                                         tenure="4+ years")
                            for i in range(4)])
g10 = dr.form_cliques(team10)
check("the Flying Finns", any(g["name"] == "The Flying Finns"
                              for g in g10))

yanks = [make_player(f"US{i}", nat="United States", age=26,
                     tenure="2 years") for i in range(3)]
team_y = make_team(yanks + [make_player(f"QY{i}", nat="Canada", age=31,
                                        tenure="4+ years")
                            for i in range(4)])
gy = dr.form_cliques(team_y)
check("the Yanks", any(g["name"] == "The Yanks" for g in gy))

euro = [make_player(f"EU{i}", nat=n, age=a, tenure="2 years",
                    birthplace=f"City{i}, RG")
        for i, (n, a) in enumerate([("Sweden", 26), ("Finland", 27),
                                    ("Czechia", 28), ("Norway", 27)])]
team_eu = make_team(euro)
geu = dr.form_cliques(team_eu)
check("the Euro Corner", any(g["name"] == "The Euro Corner"
                             for g in geu))

mans = [make_player(f"TO{i}", nat=n, age=26 + i, tenure="2 years",
                    birthplace="Toronto, ON")
        for i, n in enumerate(["Canada", "United States", "Sweden"])]
team_m = make_team(mans)
gm = dr.form_cliques(team_m)
check("the Toronto Mans", any(g["name"] == "The Toronto Mans"
                              for g in gm))

# 39-46: personality-scaled affinity -----------------------------------
glue1 = make_player("Glue1", teamwork=95)
glue2 = make_player("Glue2", teamwork=95)
lone1 = make_player("Lone1", teamwork=20, selfishness=90, controversy=10)
lone2 = make_player("Lone2", teamwork=20, selfishness=90, controversy=10)
check("glue guys bond faster than loners",
      dr.affinity(glue1, glue2) > dr.affinity(lone1, lone2))
check("loner appetite below 1.0", dr._social_appetite(lone1) < 1.0)
check("glue appetite above 1.0", dr._social_appetite(glue1) > 1.0)
check("neutral appetite is 1.0",
      dr._social_appetite(make_player("Neu")) == 1.0)

home1 = make_player("Home1", birthplace="Oshawa, ON", ambition="hometown")
home2 = make_player("Home2", birthplace="Oshawa, ON", ambition="hometown")
plain1 = make_player("Plain1", birthplace="Oshawa, ON")
plain2 = make_player("Plain2", birthplace="Oshawa, ON")
check("homesick players weight hometown more",
      dr.affinity(home1, home2) > dr.affinity(plain1, plain2))
check("appetite bounded", 0.6 <= dr._social_appetite(lone1) <= 1.3)

# 47-49: hidden Easter eggs for diverse groups --------------------------
div = [make_player(f"D{i}", nat=n, age=a, tenure="2 years",
                   birthplace=f"Town{i}, ON")
       for i, (n, a) in enumerate([("Canada", 26), ("United States", 27),
                                   ("Sweden", 28), ("Finland", 27)])]
team_d = make_team(div)
gd = dr.form_cliques(team_d)
pool = list(dr._DIVERSE_SIZE_EGGS.get(4, [])) + dr._DIVERSE_EGGS
check("diverse group gets an Easter egg",
      len(gd) == 1 and gd[0]["name"] in pool)
gd2 = dr.form_cliques(team_d)
check("Easter egg deterministic", gd[0]["name"] == gd2[0]["name"])
check("no 'Group N' fallback names",
      not any(g["name"].startswith("Group ") for g in gd))

kids_mixed = [make_player(f"KM{i}", nat=n, age=20 + i, tenure="This season")
              for i, n in enumerate(["Canada", "Sweden", "USA"])]
team11 = make_team(kids_mixed + [make_player(f"W{i}", nat="Canada", age=31,
                                             tenure="4+ years")
                                 for i in range(4)])
g11 = dr.form_cliques(team11)
check("the kids", any(g["name"] == "The kids" for g in g11))

# No double-"the" in arrival lines.
team12 = make_team([make_player(f"SV{i}", nat="Sweden", age=28,
                                tenure="4+ years") for i in range(4)])
newbie = make_player("Newbie", nat="Sweden", age=24, tenure="This season")
lines12 = dr.cascade_on_arrival(team12, newbie, how="signing")
check("no double the in arrival line",
      not any("the the " in ln for ln in lines12))

print(f"\nQA social_groups: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
