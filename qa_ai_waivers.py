"""QA: AI waiver management (BUG-019).

Covers: cap-casualty waivers for over-cap AI clubs; NMC blocking
placement; franchise pieces (86+) never waived; the user's club never
touched; wire state (on_waivers + 2-day clock + wire list); roster trim
toward 23 for bloated clubs; camp cuts (exempt kids straight to the AHL,
eligible veterans through the wire); the June dead month skipping the
scan; waiver eligibility parity (25+ or 160+ NHL games).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
import game_classes as g
from game_classes import PlayerPosition
import waiver_logic as wl

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=88_000_000, user=False):
    t = g.Team(name, "T", "D", "C")
    t.team_name = name
    t.league_name = "National Hockey League"
    t.salary_cap = cap
    t.is_user_team = user
    t.gm_profile = type("G", (), {"gm_ability01": 0.9})()
    return t

def mkplayer(name, age, ovr, salary, games=250, nmc=False, yrs=2):
    p = g.Player(first_name=name.split()[0], last_name=name.split()[-1],
                 age=age, primary_position=PlayerPosition.CENTER)
    # overall_rating() reads skills; pin it directly for determinism
    p.overall_rating = lambda _o=ovr: _o
    p.contract.salary = salary
    p.contract.years_remaining = yrs
    p.contract.no_movement_clause = nmc
    p.nhl_games_played = games
    return p

class FakeLeague:
    def __init__(self, teams, user):
        self.teams = teams; self.user_team = user; self.season_year = 2027

# --- eligibility parity ------------------------------------------------
check("eligible: 30yo vet", wl.is_waiver_eligible(mkplayer("A B", 30, 75, 1_000_000)))
check("eligible: 22yo, 200 NHL games",
      wl.is_waiver_eligible(mkplayer("C D", 22, 75, 1_000_000, games=200)))
check("exempt: 21yo, 40 games",
      not wl.is_waiver_eligible(mkplayer("E F", 21, 75, 900_000, games=40)))

# --- cap compliance ----------------------------------------------------
fringe = mkplayer("Fringe Vet", 30, 74, 3_500_000)
nmc_guy = mkplayer("NMC Guy", 33, 73, 4_000_000, nmc=True)
star = mkplayer("Star Man", 27, 90, 11_000_000)
filler = [mkplayer(f"Fill{i} Er", 28, 76, 3_200_000) for i in range(22)]
over = mkteam("OverCap")
over.roster.extend([fringe, nmc_guy, star] + filler)
anchor = mkplayer("Anchor Old", 34, 75, 9_000_000)
over.roster.append(anchor)  # pushes payroll over the cap
user = mkteam("User", user=True)
user.roster.extend([mkplayer(f"U{i} Ser", 28, 78, 3_000_000) for i in range(20)])
league = FakeLeague([over, user], user)

summary = wl.process_ai_waivers(league, app=None, rng=random.Random(7))
names = [w["player"] for w in summary["waived"]]
check("biggest cap casualty waived first (Anchor)", "Anchor Old" in names)
check("NMC blocks placement", "NMC Guy" not in names)
check("franchise piece (90) never waived", "Star Man" not in names)
check("user club untouched",
      all(w["team"] != "User" for w in summary["waived"]))
check("wire state set", anchor.on_waivers and anchor.waiver_days == 2)
check("wire list populated",
      len(league.waiver_list) == len(summary["waived"]))
check("no duplicate wire entries",
      len({id(p) for p in league.waiver_list}) == len(league.waiver_list))

# --- roster trim (AHL shuttle) ------------------------------------------
bloat = mkteam("Bloat")
bloat.roster.extend(mkplayer(f"Vet{i} Ran", 29, 72 + (i % 5), 1_200_000)
                            for i in range(26))
league2 = FakeLeague([bloat], None)
s2 = wl.process_ai_waivers(league2, app=None, rng=random.Random(3))
n_active = sum(1 for p in bloat.roster if not p.on_waivers)
check("bloated roster trimmed toward 23", n_active < 26)
check("trim reason is AHL assignment",
      all(w["reason"] == "AHL assignment" for w in s2["waived"]))

# --- camp cuts -----------------------------------------------------------
camp = mkteam("Camp")
camp.roster.extend(mkplayer(f"Kid{i} Young", 20, 74, 850_000, games=30)
                   for i in range(20))
camp.roster.extend(mkplayer(f"Cvet{i} Old", 28, 75, 1_500_000)
                   for i in range(8))
league3 = FakeLeague([camp], None)
s3 = wl.process_ai_waivers(league3, app=None, rng=random.Random(3),
                           camp_cuts=True)
n_nhl = sum(1 for p in camp.roster if not p.on_waivers)
n_wire = sum(1 for p in camp.roster if p.on_waivers)
check("camp: trimmed to 23", n_nhl <= 23)
check("camp: exempt kids assigned straight to AHL", len(camp.ahl_roster) > 0)
check("camp: only exempt kids assigned directly",
      all(p.age < 25 and p.nhl_games_played < 160
          for p in camp.ahl_roster))
check("camp: eligible vets go through the wire", n_wire > 0)

# --- June dead month -----------------------------------------------------
from datetime import date
import transaction_windows as tw
ok, _ = tw.check_window("waiver_place", date(2027, 6, 20))
check("June: waiver_place window closed", not ok)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
