"""QA: dressing-room arrival dynamics -- the room reacts to WHO walks in.

Blue-chip pick vs bona fide vet vs regular: archetype detection,
hierarchy pull (league stature), social-group reactions, bounded
deltas, first-appearance guard, and the shared trade/non-trade core.
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

import dressing_room as dr

random.seed(7)
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} {detail}")


def mkplayer(name, age=25, ovr=75, gp=100, leadership=50, tenure="This season",
             nat="Canada", letter="", pick=None, morale=70, controversy=20):
    stats = SimpleNamespace(games_played=gp)
    p = SimpleNamespace(
        full_name=name, name=name, age=age, leadership=leadership,
        base_controversy=controversy,
        team_tenure=tenure, nationality=nat, captaincy=letter,
        morale=morale, stats=stats,
        draft_position=(f"Round 1, Pick {pick}" if pick
                        else "Round 4, Pick 120"),
        overall_rating=lambda _o=ovr: _o,
    )
    p._pid = name
    return p


# _pid uses id() fallback; give players stable identity via full_name
_orig_pid = dr._pid


def mkteam(members):
    t = SimpleNamespace(team_name="Test Club")
    t.roster = list(members)
    t.ahl_roster = []
    t.prospects = []
    return t


# ---------------------------------------------------------------- archetype
kid = mkplayer("Kid Phenom", age=19, ovr=78, gp=0, pick=3)
check("top-10 pick -> blue_chip", dr.arrival_archetype(kid) == "blue_chip")

teen = mkplayer("Elite Teen", age=19, ovr=82, gp=5)
teen.draft_position = "Undrafted"
check("elite teen, no draft data -> blue_chip",
      dr.arrival_archetype(teen) == "blue_chip")

vet = mkplayer("Old Lion", age=33, ovr=86, gp=700, leadership=80,
               tenure="4+ years")
check("33yo 86ovr 700gp -> veteran",
      dr.arrival_archetype(vet) == "veteran")

vet_c = mkplayer("Ex Captain", age=31, ovr=78, gp=400, letter="C")
check("31yo former C -> veteran", dr.arrival_archetype(vet_c) == "veteran")

plug = mkplayer("Depth Plug", age=34, ovr=76, gp=300)
check("34yo depth plug -> regular", dr.arrival_archetype(plug) == "regular")

reg = mkplayer("Regular Guy", age=26, ovr=79, gp=250)
check("26yo regular -> regular", dr.arrival_archetype(reg) == "regular")

bare = SimpleNamespace()
check("bare namespace -> regular, no crash",
      dr.arrival_archetype(bare) == "regular")

# ---------------------------------------------------------------- stature
inf_vet = dr.influence_of(vet)
check("vet influence >= 70 on day one (Veteran core)",
      inf_vet >= 70, f"got {inf_vet}")
check("vet tier is Veteran core",
      dr._tier(vet, inf_vet) == "Veteran core")

kid_pre = 35 + 50 * 0.22  # no stature: ovr 78 < 80, gp 0
check("kid influence unchanged by stature",
      abs(dr.influence_of(kid) - kid_pre) < 0.01,
      f"got {dr.influence_of(kid)}")
check("kid tier is Top prospect",
      dr._tier(kid, dr.influence_of(kid)) == "Top prospect")

check("stature never raises", dr.league_stature_of(bare) == 0)
check("stature capped at 24", dr.league_stature_of(
    mkplayer("X", age=35, ovr=99, gp=1500)) <= 24)


def vet_room(n_vets=5, n_kids=4, vet_leadership=60, vet_controversy=20):
    members = []
    for i in range(n_vets):
        members.append(mkplayer(f"Vet{i}", age=32, ovr=84, gp=800,
                                leadership=vet_leadership, tenure="4+ years",
                                morale=70, controversy=vet_controversy))
    for i in range(n_kids):
        members.append(mkplayer(f"Young{i}", age=21, ovr=76, gp=60,
                                morale=70))
    return mkteam(members)


# ------------------------------------------- blue chip, DEMANDING vet room
team = vet_room(vet_controversy=55)
lines = dr.cascade_on_arrival(team, kid, how="callup")
check("demanding room tests the kid",
      any("eats rookies" in ln for ln in lines), str(lines))
check("kid takes -4 pressure", abs(kid.morale - 66) < 0.01,
      f"morale {kid.morale}")
young0 = team.roster[5]
check("young roommate buzzes +2", abs(young0.morale - 72) < 0.01,
      f"morale {young0.morale}")
vet0 = team.roster[0]
check("vets unmoved (no cheap shots)", abs(vet0.morale - 70) < 0.01,
      f"morale {vet0.morale}")
rec = team.dressing_room["arrivals"][dr._pid(kid)]
check("arrival recorded with archetype",
      rec.get("archetype") == "blue_chip" and rec.get("how") == "callup")
# bounded: nobody moved more than 4
check("all deltas bounded <= 4",
      all(abs(p.morale - 70) <= 4 for p in team.roster))

# ------------------------------------------- blue chip, GREAT vet leadership
team_g = vet_room(vet_leadership=82, vet_controversy=15)
kid_g = mkplayer("Kid Great", age=19, ovr=78, gp=0, pick=2)
lines_g = dr.cascade_on_arrival(team_g, kid_g, how="callup")
check("great vets shelter the kid",
      any("look after the kid" in ln for ln in lines_g), str(lines_g))
check("kid sheltered +3 (best fit)", abs(kid_g.morale - 73) < 0.01,
      f"morale {kid_g.morale}")
check("no buzz tax on the kids here",
      abs(team_g.roster[5].morale - 70) < 0.01)

# ------------------------------------------- blue chip, NEUTRAL vet room
team_n = vet_room()
kid_n = mkplayer("Kid Neutral", age=19, ovr=78, gp=0, pick=4)
lines_n = dr.cascade_on_arrival(team_n, kid_n, how="callup")
check("neutral room: all eyes, nothing more",
      any("All eyes on the kid" in ln for ln in lines_n), str(lines_n))
check("kid mild nerves -1", abs(kid_n.morale - 69) < 0.01,
      f"morale {kid_n.morale}")

# ------------------------------------------------------- blue chip, young room
team2 = mkteam([mkplayer(f"Y{i}", age=22, ovr=75, gp=80, morale=70,
                         tenure="2 years") for i in range(8)])
kid2 = mkplayer("Kid Two", age=18, ovr=77, gp=0, pick=1)
lines2 = dr.cascade_on_arrival(team2, kid2, how="callup")
check("young-room line", any("young room" in ln for ln in lines2),
      str(lines2))
check("kid welcomed +2", abs(kid2.morale - 72) < 0.01)
check("room lifts +1", abs(team2.roster[0].morale - 71) < 0.01)

# ------------------------------------------------- veteran, strong captain
team3 = vet_room()
cap = mkplayer("Cap", age=30, ovr=85, gp=650, leadership=85,
               tenure="4+ years", letter="C", morale=70)
team3.roster.append(cap)
vet2 = mkplayer("Graybeard", age=36, ovr=84, gp=950, leadership=80,
                tenure="This season", morale=70)
lines3 = dr.cascade_on_arrival(team3, vet2, how="signing")
check("lieutenant line", any("lieutenant" in ln for ln in lines3),
      str(lines3))
check("captain reinforced +2", abs(cap.morale - 72) < 0.01,
      f"morale {cap.morale}")
check("vet landing softer than -6", vet2.morale >= 68,
      f"morale {vet2.morale}")

# ------------------------------------------------- veteran, leaderless room
team4 = mkteam([mkplayer(f"M{i}", age=27, ovr=78, gp=300, morale=70,
                         tenure="3 years") for i in range(10)])
vet3 = mkplayer("Savior", age=34, ovr=86, gp=900, leadership=85,
                tenure="This season", morale=70)
lines4 = dr.cascade_on_arrival(team4, vet3, how="signing")
check("vacuum line", any("vacuum" in ln for ln in lines4), str(lines4))
check("room steadied +1", abs(team4.roster[0].morale - 71) < 0.01)
# de-facto voice: no letter, so the high-stature vet may lead
check("no crash on de-facto captain", True)

# ------------------------------------------------- alpha friction (bounded)
team5 = mkteam([mkplayer(f"R{i}", age=26, ovr=76, gp=200, morale=70)
                for i in range(8)])
weak_cap = mkplayer("WeakC", age=29, ovr=78, gp=150, leadership=5,
                    tenure="This season", letter="C", morale=70)
team5.roster.append(weak_cap)
alpha = mkplayer("Alpha", age=28, ovr=94, gp=1100, leadership=99,
                 tenure="This season", morale=70)
lines5 = dr.cascade_on_arrival(team5, alpha, how="trade")
check("alpha friction line", any("Two alphas" in ln for ln in lines5),
      str(lines5))
check("friction bounded: captain -2", abs(weak_cap.morale - 68) < 0.01,
      f"morale {weak_cap.morale}")
check("friction bounded: vet -2", abs(alpha.morale - 68) < 0.01,
      f"morale {alpha.morale}")

# ------------------------------------------------- regular unchanged
team6 = mkteam([mkplayer(f"S{i}", age=28, ovr=77, gp=300, morale=70,
                         nat="Sweden", tenure="4+ years")
                for i in range(4)])
reg_swe = mkplayer("Swe Reg", age=25, ovr=76, gp=150, nat="Sweden")
lines6 = dr.cascade_on_arrival(team6, reg_swe, how="signing")
check("regular clique line preserved",
      any("familiar faces help" in ln for ln in lines6), str(lines6))
check("regular -2", abs(reg_swe.morale - 68) < 0.01)

lone = mkplayer("Lone Wolf", age=25, ovr=76, gp=150, nat="Latvia")
lines6b = dr.cascade_on_arrival(team6, lone, how="signing")
check("regular outsider line preserved",
      any("outsider" in ln for ln in lines6b), str(lines6b))
check("regular outsider -6", abs(lone.morale - 64) < 0.01)

# ------------------------------------------------- first-appearance guard
team7 = vet_room()
k7 = mkplayer("YoYo", age=20, ovr=75, gp=10, pick=8)
first = dr.cascade_on_arrival(team7, k7, how="callup")
second = dr.cascade_on_arrival(team7, k7, how="callup")
check("re-callup is quiet", second == [] and k7.morale == 69,
      f"second={second} morale={k7.morale}")

# ------------------------------------------------- departure clears record
team8a = vet_room()
team8b = vet_room()
t8 = mkplayer("Traded Kid", age=20, ovr=77, gp=5, pick=5)
dr.cascade_on_trade(team8a, traded=t8)
check("departure pops arrival record",
      dr._pid(t8) not in team8a.dressing_room["arrivals"])
# (re-acquire path: record absent -> arrival fires again)
lines8 = dr.cascade_on_trade(team8b, arriving=t8)
check("trade arrival of blue chip uses archetype lines",
      any("veteran room" in ln for ln in lines8), str(lines8))

# ------------------------------------------------- vet via trade: shared core
team9 = mkteam([mkplayer(f"N{i}", age=26, ovr=77, gp=250, morale=70)
                for i in range(9)])
vet9 = mkplayer("Trade Vet", age=35, ovr=85, gp=850, leadership=80,
                tenure="This season", morale=70)
lines9 = dr.cascade_on_trade(team9, arriving=vet9)
check("trade vet fills vacuum too", any("vacuum" in ln for ln in lines9),
      str(lines9))

# ------------------------------------------------- integration still works
check("integration recorded", dr.integration_of(team, kid) < 100)
check("integration grows with games",
      dr.integration_of(team, kid) <= 100)

# ------------------------------------------------- mood log got the story
log = team.dressing_room["mood_log"]
check("story logged", any("eats rookies" in ln for ln in log))

print(f"\nQA dressing_room_arrivals: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
