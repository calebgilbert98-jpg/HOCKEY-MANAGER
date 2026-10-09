# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for All-Star roster selection (true to real criteria).

Covers: 4 division teams; fan-vote captain per division; 9 skaters
(captain included) + 2 goalies on first-half merit -- 11 per division,
44 league-wide; EVERY team represented; >=2 defensemen per
division; accolades stamped once (idempotent); save-safe ID persistence
+ resolve_rosters; all_star_game_date lookup; exhibition result and
skills winners are presentation-only (no stat mutation).
"""

import json
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, ".")

import all_star as AS

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))


_pid = [0]


def mkplayer(name, pos, gp, goals, assists, overall=80, reputation=50,
             sv=0.0, wins=0):
    _pid[0] += 1
    st = SimpleNamespace(goals=goals, assists=assists,
                         points=goals + assists, games_played=gp,
                         save_percentage=sv, wins=wins)
    return SimpleNamespace(id=_pid[0], name=name,
                           primary_position=SimpleNamespace(value=pos),
                           stats=st, overall=overall, reputation=reputation,
                           career_accolades=[])


def mkcoach(name):
    return SimpleNamespace(id=abs(hash(name)) % 10**6, full_name=name,
                           name=name, role="HEAD_COACH")


def mkteam(name, division, players):
    coach = mkcoach(f"Coach {name}")
    t = SimpleNamespace(team_name=name, league_name="National Hockey League",
                        division=division, roster=players,
                        staff=[coach])
    t.get_staff_by_role = lambda role, _c=coach: [_c]
    return t


DIVS = ["Atlantic", "Metropolitan", "Central", "Pacific"]
teams = []
for di, div in enumerate(DIVS):
    for ti in range(8):
        tname = f"{div} Team {ti + 1}"
        players = []
        # 12 forwards, 6 D, 2 G with graded production.
        for i in range(12):
            players.append(mkplayer(f"{tname} F{i}", "C", 40, 20 - i, 25 - i,
                                    overall=82 - i, reputation=40 + i))
        for i in range(6):
            players.append(mkplayer(f"{tname} D{i}", "D", 40, 5, 15 - i,
                                    overall=78 - i, reputation=35))
        players.append(mkplayer(f"{tname} G1", "G", 30, 0, 0, overall=85,
                                sv=0.920, wins=18))
        players.append(mkplayer(f"{tname} G2", "G", 20, 0, 0, overall=80,
                                sv=0.905, wins=10))
        teams.append(mkteam(tname, div, players))

# Atlantic Team 1: a runaway superstar -- fan vote must crown him.
for t in teams:
    if t.team_name == "Atlantic Team 1":
        star = mkplayer("Super Star", "C", 40, 35, 45, overall=97,
                        reputation=99)
        t.roster.append(star)

asg_date = date(2027, 2, 7)
# Standings: make "{div} Team 1" the leader of each division.
_standings = {}
for t in teams:
    ti = int(t.team_name.rsplit(" ", 1)[1])
    _standings[t.team_name] = {"W": 40 - ti, "L": 10, "OTL": 2,
                               "Points": 82 - 2 * ti}
league = SimpleNamespace(
    teams=teams, season_year=2026, all_star_rosters={},
    standings=_standings,
    schedule=[(asg_date, "NHL_EVENT", {"type": "all_star_game"})])

rng = random.Random(7)
rosters = AS.select_all_star_rosters(league, rng=rng)

check("4 division teams", set(rosters.keys()) == set(DIVS), str(rosters.keys()))
for div in DIVS:
    r = rosters.get(div)
    if not r:
        check(f"{div} present", False)
        continue
    check(f"{div}: captain is a skater", not AS._is_goalie(r["captain"]))
    check(f"{div}: 8 skaters + captain = 9 total",
          len(r["skaters"]) == 8, str(len(r["skaters"])))
    check(f"{div}: 2 goalies", len(r["goalies"]) == 2, str(len(r["goalies"])))
    dmen = [p for p in [r["captain"]] + r["skaters"] if AS._is_dman(p)]
    check(f"{div}: >=2 defensemen", len(dmen) >= 2, str(len(dmen)))
    # every team in the division represented
    tnames = {t.team_name for t in teams if t.division == div}
    covered = set()
    id2team = {}
    for t in teams:
        for p in t.roster:
            id2team[p.id] = t.team_name
    for p in [r["captain"]] + r["skaters"] + r["goalies"]:
        covered.add(id2team.get(p.id))
    check(f"{div}: every team represented", tnames <= covered,
          str(tnames - covered))
    # no duplicates
    ids = [p.id for p in [r["captain"]] + r["skaters"] + r["goalies"]]
    check(f"{div}: no duplicate picks", len(ids) == len(set(ids)))

atl_cap = rosters["Atlantic"]["captain"]
check("fan vote crowns the superstar", atl_cap.name == "Super Star",
      atl_cap.name)

# Merit: the top scorer of a division must be in (non-captain path still
# picks on points -- check a top-3 scorer is selected).
met = rosters["Metropolitan"]
top3 = sorted([p for t in teams if t.division == "Metropolitan"
               for p in t.roster if not AS._is_goalie(p)],
              key=AS._skater_score, reverse=True)[:3]
sel_ids = {p.id for p in [met["captain"]] + met["skaters"]}
check("top-3 metropolitan scorer selected",
      any(p.id in sel_ids for p in top3))

# Goalies: best SV% starter picked.
cen_g = rosters["Central"]["goalies"]
check("top goalie by SV% picked",
      any("G1" in p.name for p in cen_g), str([p.name for p in cen_g]))

# Accolades stamped exactly once with the ceremony year (2027 for the
# 2026-27 season -- the individual-award convention in accolades.py).
n_acc = sum(1 for t in teams for p in t.roster
            for a in p.career_accolades
            if a.get("award") == "all_star" and a.get("year") == "2027")
n_picks = sum(1 + len(r["skaters"]) + len(r["goalies"])
              for r in rosters.values())
check("accolade per pick, none duplicated", n_acc == n_picks,
      f"{n_acc} vs {n_picks}")
check("44 selections league-wide (11 x 4)", n_picks == 44, str(n_picks))

# The player card renders the trophy case via group_accolades.
import accolades as _accmod
star = rosters["Atlantic"]["captain"]
groups = dict(_accmod.group_accolades(star))
check("card shows 'NHL All-Star' label", "NHL All-Star" in groups, str(groups))
check("card shows ceremony year", groups.get("NHL All-Star") == ["2027"],
      str(groups.get("NHL All-Star")))

# Idempotent: second call is a no-op.
again = AS.select_all_star_rosters(league, rng=rng)
check("second call is a no-op", again == {})
n_acc2 = sum(1 for t in teams for p in t.roster
             for a in p.career_accolades if a.get("award") == "all_star")
check("no double-stamped accolades", n_acc2 == n_acc)

# Save-safe: stored form is plain JSON-able IDs; resolve works.
stored = league.all_star_rosters.get("2026-27")
check("stored under season label", stored is not None)
try:
    json.dumps(stored)
    check("stored form is JSON-serializable", True)
except TypeError as e:
    check("stored form is JSON-serializable", False, str(e))
resolved = AS.resolve_rosters(league, "2026-27")
check("resolve_rosters recovers 4 divisions", len(resolved) == 4)
check("resolved captain matches",
      resolved["Atlantic"]["captain"].id == rosters["Atlantic"]["captain"].id)

# Game-date lookup.
check("all_star_game_date found", AS.all_star_game_date(league) == asg_date)
check("None when absent",
      AS.all_star_game_date(SimpleNamespace(schedule=[])) is None)

# Exhibition result: presentation only.
before = [(p.stats.points, p.stats.wins) for t in teams for p in t.roster]
res = AS.play_all_star_game(rosters, random.Random(3))
after = [(p.stats.points, p.stats.wins) for t in teams for p in t.roster]
check("champion is a division", res.get("champion") in DIVS, str(res))
check("score looks like 3v3", "-" in res.get("score", ""), str(res))
check("exhibition touches no stats", before == after)

# Skills: 3 events, distinct winners, from the rosters.
sw = AS.skills_winners(rosters, random.Random(11))
check("3 skills events", len(sw) == 3, str(sw))
check("distinct winners", len({w[1] for w in sw}) == 3, str(sw))
roster_names = {p.name for r in rosters.values()
                for p in [r["captain"]] + r["skaters"]}
check("winners from the rosters", all(w[1] in roster_names for w in sw))

# Announcement copy names all four divisions + captains.
copy = AS.announcement_copy(rosters, "2026-27")
check("copy names all divisions", all(d in copy for d in DIVS))
check("copy names the superstar captain", "Super Star" in copy)

# Coaches: the division leaders' head coaches (the real rule).
coaches = AS.select_all_star_coaches(league)
from game_classes import StaffRole
for div in DIVS:
    leader = max([t for t in teams if t.division == div],
                 key=lambda t: (league.standings[t.team_name]["Points"],
                                league.standings[t.team_name]["W"]))
    hc = leader.get_staff_by_role(StaffRole.HEAD_COACH)[0]
    check(f"{div} coach is the leader's HC", coaches[div] is hc,
          f"{getattr(coaches[div], 'full_name', None)} vs {hc.full_name}")
    check(f"{div} roster carries coach", rosters[div]["coach"] is hc)
    check(f"{div} coach name persisted",
          league.all_star_rosters["2026-27"][div]["coach_name"] == hc.full_name)
check("copy names the coaches", "Behind the benches" in copy and
      all(f"Coach {div} Team 1" in copy for div in DIVS))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
