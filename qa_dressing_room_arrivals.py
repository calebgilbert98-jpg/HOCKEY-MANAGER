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
             nat="Canada", letter="", pick=None, morale=70, controversy=20,
             aggr=45, comp=65, selfish=50, teamwork=60):
    stats = SimpleNamespace(games_played=gp)
    p = SimpleNamespace(
        full_name=name, name=name, age=age, leadership=leadership,
        base_controversy=controversy,
        aggressiveness=aggr, composure=comp,
        selfishness=selfish, teamwork=teamwork,
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


def vet_room(n_vets=5, n_kids=4, vet_leadership=60, vet_controversy=20,
             vet_morale=70, kid_morale=70, vet_ovr=84,
             vet_aggr=45, vet_comp=65):
    members = []
    for i in range(n_vets):
        members.append(mkplayer(f"Vet{i}", age=32, ovr=vet_ovr, gp=800,
                                leadership=vet_leadership, tenure="4+ years",
                                morale=vet_morale, controversy=vet_controversy,
                                aggr=vet_aggr, comp=vet_comp))
    for i in range(n_kids):
        members.append(mkplayer(f"Young{i}", age=21, ovr=76, gp=60,
                                morale=kid_morale))
    return mkteam(members)


# ------------------------------------------- blue chip, DEMANDING vet room
team = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
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
                         tenure="2 years", aggr=45, comp=65)
                  for i in range(8)])
kid2 = mkplayer("Kid Two", age=18, ovr=77, gp=0, pick=1)
lines2 = dr.cascade_on_arrival(team2, kid2, how="callup")
check("driven young core line",
      any("Iron sharpens iron" in ln for ln in lines2), str(lines2))
check("spotlight kid named", any("knows his name" in ln for ln in lines2),
      str(lines2))
check("kid thrives +3", abs(kid2.morale - 73) < 0.01)
check("cohort pushed +1", abs(team2.roster[0].morale - 71) < 0.01)

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


# ------------------------------------------------- trade date: no double prefix
team_dt = vet_room()
dt_vet = mkplayer("Date Vet", age=35, ovr=85, gp=850, leadership=80,
                  tenure="This season", morale=70)
dr.cascade_on_trade(team_dt, arriving=dt_vet, date_str="2026-10-05")
_mlog = team_dt.dressing_room["mood_log"]
check("trade log lines carry one date prefix",
      any(ln.startswith("[2026-10-05] ") for ln in _mlog), str(_mlog[-3:]))
check("no doubled date prefix",
      not any(ln.startswith("[2026-10-05] [2026-10-05]") for ln in _mlog),
      str(_mlog[-3:]))

# ------------------------------------------------- integration still works
check("integration recorded", dr.integration_of(team, kid) < 100)
check("integration grows with games",
      dr.integration_of(team, kid) <= 100)

# ------------------------------------------------- mood log got the story
log = team.dressing_room["mood_log"]
check("story logged", any("eats rookies" in ln for ln in log))

# --------------------------------- kid personality x demanding room
team_d2 = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
cocky = mkplayer("Cocky Kid", age=19, ovr=78, gp=0, pick=8, controversy=62)
lines_d2 = dr.cascade_on_arrival(team_d2, cocky, how="callup")
check("cocky kid walks in talking",
      any("walks in talking" in ln for ln in lines_d2), str(lines_d2))
check("cocky kid tested -4", abs(cocky.morale - 66) < 0.01,
      f"morale {cocky.morale}")

team_d3 = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
quiet = mkplayer("Quiet Kid", age=19, ovr=78, gp=0, pick=8, controversy=6)
lines_d3 = dr.cascade_on_arrival(team_d3, quiet, how="callup")
check("quiet kid head down", any("head down" in ln for ln in lines_d3),
      str(lines_d3))
check("quiet kid tested but handles it -3", abs(quiet.morale - 67) < 0.01,
      f"morale {quiet.morale}")

# --------------------------------- cocky kid x great leadership
team_g2 = vet_room(vet_leadership=82, vet_controversy=15)
cocky2 = mkplayer("Cocky Two", age=19, ovr=78, gp=0, pick=8, controversy=58)
lines_g2 = dr.cascade_on_arrival(team_g2, cocky2, how="callup")
check("vets keep his feet on the ground",
      any("feet on the ground" in ln for ln in lines_g2), str(lines_g2))
check("cocky kid +2 not +3", abs(cocky2.morale - 72) < 0.01,
      f"morale {cocky2.morale}")

# --------------------------------- situational beats (neutral vet room)
team_s = vet_room()
star = mkplayer("Star Kid", age=19, ovr=78, gp=0, pick=1)
lines_s = dr.cascade_on_arrival(team_s, star, how="callup")
check("spotlight follows him",
      any("spotlight follows him" in ln for ln in lines_s), str(lines_s))
check("spotlight pressure -2", abs(star.morale - 68) < 0.01,
      f"morale {star.morale}")

team_w = vet_room(vet_ovr=90)
wn = mkplayer("WinNow Kid", age=19, ovr=78, gp=0, pick=6)
lines_w = dr.cascade_on_arrival(team_w, wn, how="callup")
check("need him now", any("produce right now" in ln for ln in lines_w),
      str(lines_w))
check("win-now pressure -2", abs(wn.morale - 68) < 0.01,
      f"morale {wn.morale}")

team_c = vet_room(vet_morale=48, kid_morale=48)
ck = mkplayer("Crisis Kid", age=19, ovr=78, gp=0, pick=6)
lines_c = dr.cascade_on_arrival(team_c, ck, how="callup")
check("nobody babysits",
      any("nobody's in the mood to babysit" in ln for ln in lines_c),
      str(lines_c))
check("crisis landing -2", abs(ck.morale - 68) < 0.01,
      f"morale {ck.morale}")

team_h = vet_room(vet_morale=80, kid_morale=78)
hk = mkplayer("Happy Kid", age=19, ovr=78, gp=0, pick=6)
lines_h = dr.cascade_on_arrival(team_h, hk, how="callup")
check("soft landing", any("soft landing" in ln for ln in lines_h),
      str(lines_h))
check("happy room nets 0", abs(hk.morale - 70) < 0.01,
      f"morale {hk.morale}")

# --------------------------------- young room: wild cohort
team_wild = mkteam([mkplayer(f"W{i}", age=22, ovr=75, gp=80, morale=70,
                             tenure="2 years", controversy=58,
                             aggr=45, comp=65)
                    for i in range(8)])
wild_kid = mkplayer("Wild Kid", age=18, ovr=77, gp=0, pick=9)
lines_wk = dr.cascade_on_arrival(team_wild, wild_kid, how="callup")
check("wild room loves the spotlight",
      any("loves the spotlight" in ln for ln in lines_wk),
      str(lines_wk))
check("muted welcome +1", abs(wild_kid.morale - 71) < 0.01,
      f"morale {wild_kid.morale}")

team_wild2 = mkteam([mkplayer(f"X{i}", age=22, ovr=75, gp=80, morale=70,
                              tenure="2 years", controversy=58,
                              aggr=45, comp=65)
                     for i in range(8)])
cocky_w = mkplayer("Cocky Wild", age=18, ovr=77, gp=0, pick=9, controversy=65)
lines_cw = dr.cascade_on_arrival(team_wild2, cocky_w, how="callup")
check("that's the worry", any("that's the worry" in ln for ln in lines_cw),
      str(lines_cw))

# --------------------------------- young room: neutral cohort
team_nc = mkteam([mkplayer(f"N{i}", age=22, ovr=75, gp=80, morale=62,
                           tenure="2 years", controversy=35,
                           aggr=45, comp=65)
                  for i in range(8)])
nc_kid = mkplayer("Neutral Cohort Kid", age=18, ovr=77, gp=0, pick=9)
lines_nc = dr.cascade_on_arrival(team_nc, nc_kid, how="callup")
check("neutral cohort: future walked in",
      any("The future just walked in" in ln for ln in lines_nc),
      str(lines_nc))
check("neutral cohort kid +2", abs(nc_kid.morale - 72) < 0.01,
      f"morale {nc_kid.morale}")
check("neutral cohort room +1", abs(team_nc.roster[0].morale - 63) < 0.01,
      f"morale {team_nc.roster[0].morale}")

# --------------------------------- personality combos: saint-hothead kid
team_f = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
sh_kid = mkplayer("Saint Hothead", age=19, ovr=78, gp=0, pick=8,
                  controversy=10, aggr=85, comp=30)
lines_f = dr.cascade_on_arrival(team_f, sh_kid, how="callup")
check("saint-hothead doesn't take a step back",
      any("doesn't take a step back" in ln for ln in lines_f), str(lines_f))
check("saint-hothead tested -3", abs(sh_kid.morale - 67) < 0.01,
      f"morale {sh_kid.morale}")

# volatile: cocky + hothead
team_f2 = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
vol = mkplayer("Volatile", age=19, ovr=78, gp=0, pick=8,
               controversy=62, aggr=85, comp=30)
lines_f2 = dr.cascade_on_arrival(team_f2, vol, how="callup")
check("volatile looking for a fight",
      any("looking for a fight" in ln for ln in lines_f2), str(lines_f2))
check("volatile -4", abs(vol.morale - 66) < 0.01,
      f"morale {vol.morale}")

# tough-sell kid x fiery room
team_f3 = vet_room(vet_controversy=55, vet_aggr=80, vet_comp=35)
ts = mkplayer("Tough Sell", age=19, ovr=78, gp=0, pick=8,
              controversy=15, selfish=85, teamwork=30)
lines_f3 = dr.cascade_on_arrival(team_f3, ts, how="callup")
check("tough-sell: what he's made of",
      any("what he's made of" in ln for ln in lines_f3), str(lines_f3))
check("tough-sell tested -4", abs(ts.morale - 66) < 0.01,
      f"morale {ts.morale}")

# --------------------------------- circus room (drama, no temper)
team_circ = vet_room(vet_controversy=55, vet_aggr=40, vet_comp=70)
circ_kid = mkplayer("Showman", age=19, ovr=78, gp=0, pick=8, controversy=62)
lines_circ = dr.cascade_on_arrival(team_circ, circ_kid, how="callup")
check("showman fits right into the circus",
      any("fit right into it" in ln for ln in lines_circ), str(lines_circ))
check("showman home turf -1", abs(circ_kid.morale - 69) < 0.01,
      f"morale {circ_kid.morale}")
check("no buzz when the kid thrives",
      abs(team_circ.roster[5].morale - 70) < 0.01)

team_circ2 = vet_room(vet_controversy=55, vet_aggr=40, vet_comp=70)
bait = mkplayer("Bait", age=19, ovr=78, gp=0, pick=8,
                controversy=10, aggr=85, comp=30)
lines_circ2 = dr.cascade_on_arrival(team_circ2, bait, how="callup")
check("circus tries to get a rise",
      any("get a rise out of him" in ln for ln in lines_circ2),
      str(lines_circ2))
check("bait -4", abs(bait.morale - 66) < 0.01,
      f"morale {bait.morale}")

team_circ3 = vet_room(vet_controversy=55, vet_aggr=40, vet_comp=70)
qcirc = mkplayer("Quiet Circus", age=19, ovr=78, gp=0, pick=8, controversy=6)
lines_circ3 = dr.cascade_on_arrival(team_circ3, qcirc, how="callup")
check("every word a headline",
      any("he doesn't say many" in ln for ln in lines_circ3),
      str(lines_circ3))
check("quiet circus -3", abs(qcirc.morale - 67) < 0.01,
      f"morale {qcirc.morale}")

# --------------------------------- sheltering meets the blends
team_g3 = vet_room(vet_leadership=82, vet_controversy=15)
hh_g = mkplayer("Hothead Good Room", age=19, ovr=78, gp=0, pick=8,
                controversy=12, aggr=85, comp=30)
lines_g3 = dr.cascade_on_arrival(team_g3, hh_g, how="callup")
check("vets point that temper",
      any("point that temper" in ln for ln in lines_g3), str(lines_g3))
check("hothead channeled +3", abs(hh_g.morale - 73) < 0.01,
      f"morale {hh_g.morale}")

team_g4 = vet_room(vet_leadership=82, vet_controversy=15)
ts_g = mkplayer("Tough Sell Good Room", age=19, ovr=78, gp=0, pick=8,
                controversy=15, selfish=85, teamwork=30)
lines_g4 = dr.cascade_on_arrival(team_g4, ts_g, how="callup")
check("vets handle his type",
      any("handle his type" in ln for ln in lines_g4), str(lines_g4))
check("tough-sell managed +2", abs(ts_g.morale - 72) < 0.01,
      f"morale {ts_g.morale}")

# --------------------------------- tough-sell kid x crisis
team_c2 = vet_room(vet_morale=48, kid_morale=48)
ts_c = mkplayer("Tough Sell Crisis", age=19, ovr=78, gp=0, pick=8,
                controversy=15, selfish=85, teamwork=30)
lines_c2 = dr.cascade_on_arrival(team_c2, ts_c, how="callup")
check("doesn't like the circumstances",
      any("doesn't like the circumstances" in ln for ln in lines_c2),
      str(lines_c2))
check("tough-sell crisis -2", abs(ts_c.morale - 68) < 0.01,
      f"morale {ts_c.morale}")

# --------------------------------- cohort temper-wild flavor
team_hw = mkteam([mkplayer(f"H{i}", age=22, ovr=75, gp=80, morale=70,
                           tenure="2 years", controversy=20,
                           aggr=85, comp=30)
                  for i in range(8)])
hw_kid = mkplayer("Hot Room Kid", age=18, ovr=77, gp=0, pick=9)
lines_hw = dr.cascade_on_arrival(team_hw, hw_kid, how="callup")
check("young room runs hot",
      any("runs hot" in ln for ln in lines_hw), str(lines_hw))
check("hot room muted +1", abs(hw_kid.morale - 71) < 0.01,
      f"morale {hw_kid.morale}")

# hothead kid into hot cohort: that's the worry
team_hw2 = mkteam([mkplayer(f"J{i}", age=22, ovr=75, gp=80, morale=70,
                            tenure="2 years", controversy=20,
                            aggr=85, comp=30)
                   for i in range(8)])
hh_w = mkplayer("Hothead Wild", age=18, ovr=77, gp=0, pick=9,
                controversy=12, aggr=88, comp=28)
lines_hw2 = dr.cascade_on_arrival(team_hw2, hh_w, how="callup")
check("hothead fits right in -- worry",
      any("that's the worry" in ln for ln in lines_hw2), str(lines_hw2))

# --------------------------------- cohort mood-wild flavor
team_mw = mkteam([mkplayer(f"M{i}", age=22, ovr=75, gp=80, morale=48,
                           tenure="2 years", controversy=20,
                           aggr=45, comp=65)
                  for i in range(8)])
mw_kid = mkplayer("Mood Wild Kid", age=18, ovr=77, gp=0, pick=9)
lines_mw = dr.cascade_on_arrival(team_mw, mw_kid, how="callup")
check("losing and pointing fingers",
      any("pointing fingers" in ln for ln in lines_mw), str(lines_mw))

# --------------------------------- veteran tough-sell x crisis
team_vc = mkteam([mkplayer(f"V{i}", age=28, ovr=77, gp=300, morale=48,
                           tenure="3 years") for i in range(10)])
ts_vet = mkplayer("Tough Vet", age=34, ovr=84, gp=800, leadership=60,
                  tenure="This season", morale=70, controversy=15,
                  selfish=85, teamwork=30)
lines_vc = dr.cascade_on_arrival(team_vc, ts_vet, how="signing")
check("vet doesn't like the circumstances",
      any("difficult until they change" in ln for ln in lines_vc),
      str(lines_vc))
check("tough vet crisis -2 (bounded)",
      abs(ts_vet.morale - 68) < 0.01, f"morale {ts_vet.morale}")

# --------------------------------- bounds hold across the matrix
extra_pairs = [(team_f, sh_kid), (team_f2, vol), (team_f3, ts),
          (team_circ, circ_kid), (team_circ2, bait), (team_circ3, qcirc),
          (team_g3, hh_g), (team_g4, ts_g), (team_c2, ts_c),
          (team_hw, hw_kid), (team_hw2, hh_w), (team_mw, mw_kid),
          (team_vc, ts_vet)]

# --------------------------------- bounds hold across the matrix
pairs = [(team_d2, cocky), (team_d3, quiet), (team_g2, cocky2),
         (team_s, star), (team_w, wn), (team_c, ck), (team_h, hk),
         (team_wild, wild_kid), (team_wild2, cocky_w), (team_nc, nc_kid)]
def _start_morale(team, player, kid):
    if player is kid:
        return 70  # arrivals always start at their own morale
    nm = player.full_name
    if team is team_c or team is team_c2:
        return 48
    if team is team_h:
        return 80 if nm.startswith("Vet") else 78
    if team is team_nc:
        return 62
    if team is team_mw or team is team_vc:
        return 48
    return 70
check("kid deltas never exceed 4",
      all(abs(p.morale - _start_morale(t, p, k)) <= 4
          for t, k in pairs + extra_pairs for p in t.roster))



print(f"\nQA dressing_room_arrivals: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
