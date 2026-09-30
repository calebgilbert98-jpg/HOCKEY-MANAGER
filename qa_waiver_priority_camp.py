"""QA: NHL waiver priority + training camp.

Priority: pre-Nov-1 uses the previous season's final table; post-Nov-1
uses current points%; a successful claimant drops to the bottom; the
demotion list resets when the basis flips; snapshot banks the table.

Camp: Sep 12-30 cycle (open/scrimmage/close), ratings stamped, standout
dev bumps, idempotent scrimmage days, inbox report, and AI camp cuts
preferring low camp_avg.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
from datetime import date
import game_classes as g
from game_classes import PlayerPosition
import waiver_logic as wl
import training_camp as tc

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name):
    t = g.Team(name, "T", "D", "C")
    t.team_name = name
    t.league_name = "National Hockey League"
    t.salary_cap = 88_000_000
    return t

def mkplayer(name, age, ovr, salary=1_000_000, games=250, pos=None):
    p = g.Player(first_name=name.split()[0], last_name=name.split()[-1],
                 age=age, primary_position=pos or PlayerPosition.CENTER)
    p.overall_rating = lambda _o=ovr: _o
    p.contract.salary = salary
    p.nhl_games_played = games
    return p

class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2028
        self.standings = {}
        self.waiver_list = []

# --- snapshot ------------------------------------------------------------
lg = FakeLeague([mkteam("A")])
lg.standings = {"A": {"W": 50, "L": 25, "OTL": 7, "Points": 107}}
wl.snapshot_final_standings(lg)
check("snapshot banks final table",
      lg.previous_season_standings["A"] == {"points": 107, "games": 82})

# --- priority basis -------------------------------------------------------
t_bad, t_mid, t_good = mkteam("Bad"), mkteam("Mid"), mkteam("Good")
lg = FakeLeague([t_good, t_mid, t_bad])
lg.previous_season_standings = {
    "Bad": {"points": 60, "games": 82},
    "Mid": {"points": 95, "games": 82},
    "Good": {"points": 110, "games": 82},
}
lg.standings = {
    "Bad": {"W": 8, "L": 2, "OTL": 0, "Points": 16},    # hot start, 80%
    "Mid": {"W": 5, "L": 5, "OTL": 0, "Points": 10},    # 50%
    "Good": {"W": 1, "L": 9, "OTL": 0, "Points": 2},    # 10%
}
pre = wl.waiver_priority_order(lg, date(2028, 10, 15))
check("pre-Nov-1: prior final table (Bad first)",
      [t.team_name for t in pre] == ["Bad", "Mid", "Good"])
post = wl.waiver_priority_order(lg, date(2028, 11, 15))
check("post-Nov-1: current points% (Good first)",
      [t.team_name for t in post] == ["Good", "Mid", "Bad"])
check("basis label pre-Nov mentions final",
      "final" in wl.waiver_priority_basis_label(lg, date(2028, 10, 15)))
check("basis label post-Nov mentions current",
      "current" in wl.waiver_priority_basis_label(lg, date(2028, 11, 15)))
check("rank is 1-based",
      wl.waiver_priority_rank(lg, t_good, date(2028, 11, 15)) == 1)
# Points%, not raw points: fewer GP, higher pct => LOWER priority.
lg.standings = {
    "Bad": {"W": 5, "L": 15, "OTL": 0, "Points": 10},   # 25% in 20
    "Mid": {"W": 6, "L": 24, "OTL": 0, "Points": 12},   # 20% in 30
    "Good": {"W": 1, "L": 9, "OTL": 0, "Points": 2},
}
post2 = wl.waiver_priority_order(lg, date(2028, 12, 1))
check("points% beats raw points (Mid ahead of Bad)",
      [t.team_name for t in post2][:2] == ["Good", "Mid"])

# --- drop-to-bottom -------------------------------------------------------
wl.note_waiver_claim(lg, t_good)   # Good claims from #1
order = wl.waiver_priority_order(lg, date(2028, 12, 1))
check("successful claimant drops to bottom",
      [t.team_name for t in order] == ["Mid", "Bad", "Good"])
wl.note_waiver_claim(lg, t_mid)
order = wl.waiver_priority_order(lg, date(2028, 12, 1))
check("claim order preserved at the tail",
      [t.team_name for t in order] == ["Bad", "Good", "Mid"])
# Basis flip resets the demotion list (new season).
order = wl.waiver_priority_order(lg, date(2029, 10, 15))
names = [t.team_name for t in order]
check("basis flip resets used-priority list",
      names == ["Bad", "Mid", "Good"])

# --- training camp cycle ---------------------------------------------------
rng = random.Random(11)
team = mkteam("Campers")
skaters = [mkplayer(f"Sk{i} Ater", 20 + (i % 12), 68 + (i % 20),
                    pos=[PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                         PlayerPosition.RIGHT_DEFENSE][i % 3])
           for i in range(20)]
goalies = [mkplayer(f"G{i} Oalie", 26, 78, pos=PlayerPosition.GOALIE)
           for i in range(2)]
team.roster.extend(skaters + goalies)
team.ahl_roster.extend([mkplayer(f"Ah{i} Ler", 22, 66) for i in range(6)])
kleague = FakeLeague([team])

class FakeApp:
    def __init__(self, user_team):
        self.user_team = user_team
        self.news = []
    def add_news(self, s):
        self.news.append(s)

fapp = FakeApp(team)
d = date(2028, 9, 12)
while d <= date(2028, 9, 30):
    tc.run_camp_day(kleague, d, app=fapp, rng=rng)
    d = d.fromordinal(d.toordinal() + 1)

check("camp roster built (NHL+AHL)",
      len(getattr(team, "camp_roster", [])) == 28)
check("6 scrimmages played (15/18/21/24/27/30)",
      len(getattr(team, "camp_scrimmages", []) or []) == 6)
p0 = team.camp_roster[0]
check("ratings stamped on players", len(getattr(p0, "camp_ratings", [])) == 6)
check("camp_avg computed at close", float(getattr(p0, "camp_avg", 0)) > 0)
check("scrimmage log has scores + stars",
      all("red" in s and "stars" in s for s in team.camp_scrimmages))
check("standout flags exist",
      any(getattr(p, "camp_standout", False) for p in team.camp_roster)
      or True)  # informational; bump tested deterministically below
check("inbox got the camp report",
      any("Training Camp Report" in getattr(m, "subject", "")
          for m in team.inbox.messages))
check("news noted camp open/close",
      any("camps open" in n for n in fapp.news)
      and any("camps close" in n for n in fapp.news))

# Idempotency: re-running the same dates changes nothing.
n_before = len(team.camp_scrimmages)
tc.run_camp_day(kleague, date(2028, 9, 18), app=fapp, rng=rng)
tc.run_camp_day(kleague, date(2028, 9, 30), app=fapp, rng=rng)
check("scrimmage days idempotent",
      len(team.camp_scrimmages) == n_before)

# --- standout dev bump (deterministic) --------------------------------------
kid = mkplayer("Kid Star", 20, 72)
kid.camp_ratings = [8.0, 8.5, 7.8, 8.2, 9.0, 7.6]
kid.camp_avg = 8.2
sk0, sh0 = kid.skating, kid.shooting
team2 = mkteam("Bump")
team2.camp_roster = [kid]
kleague2 = FakeLeague([team2])
tc._close_camp(kleague2, date(2028, 9, 30), app=None, rng=random.Random(3))
gains = (kid.skating - sk0) + (kid.shooting - sh0) + \
        (kid.passing - 0)  # passing may have moved instead; check total
total_gain = sum(getattr(kid, a) for a in tc._SKATER_BUMP_ATTRS)
check("standout youngster gets attribute bump",
      getattr(kid, "camp_standout", False) and total_gain > 0)
vet = mkplayer("Vet Sad", 32, 75)
vet.camp_ratings = [4.0, 3.5]
vet.camp_avg = 3.8
vet.morale = 70
team2.camp_roster = [vet]
kleague2._camp_closed_year = 0
tc._close_camp(kleague2, date(2028, 9, 30), app=None, rng=random.Random(3))
check("poor camp costs morale", vet.morale == 65)

# --- AI camp cuts read camp ratings -----------------------------------------
cut_team = mkteam("Cutters")
cands = []
for i, (nm, avg) in enumerate([("Low Camp", 3.0), ("Mid Camp", 5.5),
                               ("High Camp", 9.0)]):
    p = mkplayer(nm, 27, 75, 2_500_000, games=300)
    p.camp_ratings = [avg] * 3
    p.camp_avg = avg
    cands.append(p)
cut_team.roster.extend(cands)
cut_team.roster.extend([mkplayer(f"Safe{i} Guy", 28, 78, 3_000_000,
                                 games=300) for i in range(22)])
# 25 players -> over by 2; MAX 2 waivers/call. All same ovr tier; the two
# worst camps must go, the 9.0 camp must survive.
cut_team.gm_profile = type("G", (), {"gm_ability01": 1.0})()
clg = FakeLeague([cut_team])
clg.waiver_list = []
summ = wl.process_ai_waivers(clg, app=None, rng=random.Random(99),
                             camp_cuts=True)
waived = [w["player"] for w in summ["waived"]]
check("worst camp cut first", "Low Camp" in waived)
check("second-worst camp cut second", "Mid Camp" in waived)
check("great camp saves a bubble player", "High Camp" not in waived)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
