"""QA: DoPS + officiating integration across every sim path.

Covers the full chain the units don't: the per-game officiating crew deals
a missed call -> the whiff is stashed in the live-hit shape -> post-game
DoPS review runs it through the SAME suspension-or-fine decision exactly
once -> suspension scrubs the lineup, excludes the player on every sim
path, ticks once per team game played, and clears on return.

Also asserts the playoff officiating multipliers keep their researched
shape (retaliation falls off in the playoffs, desperation penalties tick
up early) and that preseason exhibitions never touch DoPS.
"""
import random
import sys

sys.path.insert(0, ".")

from game_classes import Player, PlayerPosition, Team
import narrative_incidents as ni
import physicality as phy
import quick_sim as qs
from reputation_system import (after_whistle_penalty_mult,
                                playoff_penalty_mult)

PASS, FAIL = 0, 0
FAILURES = []


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name}")


def mk_player(first, last, pos, discipline=50, aggressiveness=50,
              controversy=30, overall=75):
    p = Player(first, last, 25, pos)
    p.discipline = discipline
    p.aggressiveness = aggressiveness
    p.controversy = controversy
    p.base_controversy = controversy
    p.overall_rating = lambda: overall
    return p


class FakeSim:
    """Minimal sim surface: crew accuracy, event log, pbp, stash."""
    def __init__(self, home, away):
        self.home_team = home
        self.away_team = away
        self._crew_accuracy = 0.0
        self._live_borderline_hits = []
        self.events = []
        self.is_playoff = False
        self.period = 2

    def _log_event(self, text, kind):
        self.events.append((kind, text))

    def _emit_pbp(self, *a, **k):
        pass


class FakeApp:
    pass


# ---------------------------------------------------------------- A. crew
sims = [FakeSim(None, None) for _ in range(200)]
accs = [phy.init_crew(s) for s in sims]
check("crew accuracy within [0.80, 1.00]",
      all(0.80 <= a <= 1.00 for a in accs))
check("crew accuracy varies game to game", len(set(round(a, 3)
                                                   for a in accs)) > 5)
check("crew_accuracy() lazily inits when unset",
      0.80 <= phy.crew_accuracy(FakeSim(None, None)) <= 1.00)

s = FakeSim(None, None)
s._crew_accuracy = 0.97
check("non-dirty infraction never a missed call",
      not any(phy.is_missed_call(s, "Hooking") for _ in range(500)))
random.seed(7)
misses = sum(phy.is_missed_call(s, "Boarding") for _ in range(2000))
check("dirty infractions sometimes whiffed (realistic miss rate)",
      0 < misses < 2000 * 0.15)

# ------------------------------------------------- B. missed call -> stash
hitter = mk_player("Dirty", "Dan", PlayerPosition.LEFT_WING,
                   discipline=20, aggressiveness=90, controversy=80,
                   overall=82)
victim = mk_player("Star", "Victim", PlayerPosition.CENTER, overall=92)
home = Team("HT", "City", "Div", "Conf")
away = Team("OT", "City", "Div", "Conf")
home.roster = [hitter] + [mk_player(f"H{i}", "D", PlayerPosition.CENTER,
                                    overall=70) for i in range(19)]
away.roster = [victim] + [mk_player(f"A{i}", "D", PlayerPosition.CENTER,
                                    overall=70) for i in range(19)]
# Dressed lineup shape the scrubber expects
home.lineup = {"Forwards": [[home.roster[0], home.roster[1],
                             home.roster[2]]],
               "Defense": [[home.roster[10], home.roster[11]]],
               "Goalies": [home.roster[19]]}

sim = FakeSim(home, away)
sim._crew_accuracy = 0.90
out = phy.apply_missed_call(sim, hitter, home, "Boarding", victim=victim)
check("missed call reports the whiff", out.get("missed") is True)
stash = sim._live_borderline_hits
check("whiff stashed in live-hit shape",
      len(stash) == 1 and stash[0].get("kind") == "controversial_hit"
      and stash[0].get("hitter") == hitter.full_name)
check("stash names the real victim player (rolled-path parity)",
      stash[0].get("victim") == victim.full_name
      and stash[0].get("victim_team") == "OT")
check("missed call logged as a no-call event",
      any("NO CALL" in t for _, t in sim.events))

# --------------------------------- C. stash -> DoPS review, exactly once
app = FakeApp()
real_random = random.random
random.random = lambda: 0.0  # force the suspension branch
try:
    drama = ni.apply_live_dops_reviews(app, sim, home, away, (3, 2),
                                       "2026-10-12", None, [])
finally:
    random.random = real_random
check("stash consumed exactly once", sim._live_borderline_hits == [])
check("one drama dict, marked live",
      len(drama) == 1 and drama[0].get("kind") == "controversial_hit"
      and drama[0].get("live") is True)
g = hitter.suspension_games_remaining
check("dirty repeat-risk hitter suspended", g > 0)
check("suspended_today set (service starts next game)",
      hitter.suspended_today is True)
check("suspension reason recorded",
      "Victim" in (hitter.suspension_reason or ""))
check("repeat-offender history appended",
      any(isinstance(e, dict) and e.get("type") == "suspension"
          for e in getattr(hitter, "controversy_history", [])))
check("suspended skater scrubbed from dressed lineup",
      all(p is not hitter for line in home.lineup["Forwards"]
          for p in (line or [])))
drama2 = ni.apply_live_dops_reviews(app, sim, home, away, (3, 2),
                                    "2026-10-12", None, [])
check("re-entry is a no-op (no double jeopardy)", drama2 == []
      and hitter.suspension_games_remaining == g)

# ------------------------------------------------- D. service semantics
from main import GameManager as _GM2
import main as main_mod


class FakeGM:
    def __init__(self, league_teams):
        self.league = type("L", (), {"teams": league_teams})()
        self.user_team = home
        self.news_log = []
        self.current_date = "2026-10-13"


gm = FakeGM([home, away])
G0 = hitter.suspension_games_remaining
# Team idle: no tick
_GM2._process_suspension_service(gm, {"ZZ"})
check("idle team does not serve", hitter.suspension_games_remaining == G0
      and hitter.suspended_today is True)
# Team plays: suspended_today defers the first tick, clears the flag
_GM2._process_suspension_service(gm, {"HT"})
check("issuance-day game deferred, flag cleared",
      hitter.suspension_games_remaining == G0
      and hitter.suspended_today is False)
# Remaining games tick once each
for _ in range(G0):
    _GM2._process_suspension_service(gm, {"HT"})
check("suspension fully served", hitter.suspension_games_remaining == 0)
check("reason cleared on return", hitter.suspension_reason == "")
check("user notified on return",
      any("served his suspension" in n.get("story", "")
          for n in gm.news_log))
check("away team untouched by home service",
      all((getattr(p, "suspension_games_remaining", 0) or 0) == 0
          for p in away.roster))

# -------------------------------------- E. every sim path excludes them
star = mk_player("Out", "Star", PlayerPosition.CENTER, overall=60)
star.suspension_games_remaining = 2
team = Team("ST", "City", "Div", "Conf")
team.roster = [star] + [mk_player(f"R{i}", "P", PlayerPosition.CENTER,
                                  overall=45) for i in range(19)]
dressed = {p.full_name for grp in ("Forwards", "Defense", "Goalies")
           for line in (qs.best_lines(team).get(grp) or [])
           for p in (line or []) if p is not None}
check("quick-sim best_lines excludes suspended", star.full_name not in dressed)

goalie = mk_player("Banned", "Goalie", PlayerPosition.GOALIE, overall=88)
goalie.suspension_games_remaining = 3
gteam = Team("GT", "City", "Div", "Conf")
gteam.roster = [goalie] + [mk_player(f"G{i}", "B", PlayerPosition.GOALIE,
                                    overall=70) for i in range(2)]


class FakeApp3:
    _strength_cache = {}

    def _check_player_records(self, player):
        pass

    def _select_starting_goalie(self, team):
        return main_mod.HockeyManagerGUI._select_starting_goalie(self, team)


app3 = FakeApp3()
pick = main_mod.HockeyManagerGUI._select_starting_goalie(app3, gteam)
check("suspended goalie never starts", pick is not goalie)

se_full = main_mod.HockeyManagerGUI._calculate_star_player_effects(app3, team)
star2 = mk_player("Out", "Star", PlayerPosition.CENTER, overall=60)
team2 = Team("S2", "City", "Div", "Conf")
team2.roster = [star2] + [mk_player(f"R{i}", "P", PlayerPosition.CENTER,
                                    overall=45) for i in range(19)]
se_ok = main_mod.HockeyManagerGUI._calculate_star_player_effects(app3, team2)
check("star effects present when dressed", se_ok["offensive_boost"] > 0)
check("star effects vanish when suspended",
      se_full["offensive_boost"] < se_ok["offensive_boost"])

st = Team("PT", "City", "Div", "Conf")
banned = mk_player("Banned", "Winger", PlayerPosition.LEFT_WING, overall=85)
banned.suspension_games_remaining = 2
st.roster = [banned] + [mk_player(f"S{i}", "K", PlayerPosition.LEFT_WING,
                                  overall=60) for i in range(13)] + \
            [mk_player(f"D{i}", "K", PlayerPosition.LEFT_DEFENSE,
                       overall=60) for i in range(8)] + \
            [mk_player(f"GL{i}", "K", PlayerPosition.GOALIE,
                       overall=60) for i in range(2)]
gp_before = {p.id: p.stats.games_played for p in st.roster}
g_before = {p.id: p.stats.goals for p in st.roster}
random.seed(1234)
main_mod.HockeyManagerGUI._generate_player_stats(app3, st, away, 4, 2)
check("suspended skater gets no GP",
      st.roster[0].stats.games_played == gp_before[st.roster[0].id])
check("suspended skater scores no goals",
      st.roster[0].stats.goals == g_before[st.roster[0].id])
check("dressed skaters still credited",
      sum(p.stats.games_played - gp_before[p.id] for p in st.roster) > 0)

# --------------------------------------- F. playoff officiating shape
check("regular season: whistle untouched",
      after_whistle_penalty_mult(False, 1) == 1.0
      and playoff_penalty_mult(False, 1) == 1.0)
aw = [after_whistle_penalty_mult(True, g) for g in (1, 4, 7)]
check("playoff retaliation penalties fall off with series depth",
      aw[0] > aw[1] > aw[2] >= 0.25)
pp = [playoff_penalty_mult(True, g) for g in (1, 2, 7)]
check("playoff desperation penalties run hot early, cool by game 7",
      pp[0] >= 1.0 >= pp[2] and pp[0] > pp[2])

# --------------------------------------- G. goalie-run incidents
# G1. probability shape: rare at base, up in playoffs / heat / chippiness
_p = ni._goalie_run_probability
check("goalie-run base rate is rare (10% of controversial hits)",
      abs(_p(False, 0.0, 30.0) - 0.10) < 1e-9)
check("playoffs lift the goalie-run rate",
      abs(_p(True, 0.0, 30.0) - 0.15) < 1e-9)
check("rivalry heat lifts the goalie-run rate",
      _p(False, 75.0, 30.0) > _p(False, 0.0, 30.0))
check("chippy (high-intensity) rooms lift the goalie-run rate",
      _p(False, 0.0, 80.0) > _p(False, 0.0, 30.0))
check("goalie-run rate is capped",
      _p(True, 200.0, 100.0) == 0.35)

# G2. victim picker: best healthy goalie, never a skater, None when empty
gr_home = Team("GH", "City", "Div", "Conf")
gr_away = Team("GA", "City", "Div", "Conf")
g1 = mk_player("Starter", "Goalie", PlayerPosition.GOALIE, overall=88)
g2 = mk_player("Backup", "Goalie", PlayerPosition.GOALIE, overall=80)
g1.is_injured = True
gr_away.roster = ([mk_player(f"S{i}", "K", PlayerPosition.CENTER, overall=70)
                   for i in range(18)] + [g1, g2])
gr_home.roster = ([mk_player("Goon", "H", PlayerPosition.LEFT_WING,
                             discipline=20, aggressiveness=95,
                             controversy=80, overall=78)]
                  + [mk_player(f"H{i}", "K", PlayerPosition.CENTER,
                               overall=70) for i in range(17)]
                  + [mk_player("Home", "Goalie", PlayerPosition.GOALIE,
                               overall=85)])
check("goalie-run victim is the healthy goalie",
      ni._pick_goalie_victim(gr_away) is g2)
check("no goalie on roster -> no goalie-run victim",
      ni._pick_goalie_victim(Team("GX", "City", "Div", "Conf")) is None)

# G3. rolled path: forced goalie run wires through the whole chain
rivalries_g = []
real_random = random.random
random.random = lambda: 0.0  # force p_hit and the goalie-run roll
try:
    rolled = ni._roll_incidents(gr_home, gr_away, 3, 2, rivalries_g,
                                None, False, 0)
finally:
    random.random = real_random
ghits = [d for d in rolled["incident_details"]
         if d.get("kind") == "controversial_hit"]
check("rolled controversial hit occurred", len(ghits) == 1)
gd = ghits[0] if ghits else {}
check("forced roll flags the goalie run", gd.get("goalie_run") is True)
check("rolled goalie-run victim is the healthy away goalie",
      gd.get("victim") == g2.full_name)
check("rolled goalie-run hitter is a skater (never a goalie)",
      gd.get("hitter") == gr_home.roster[0].full_name)
check("rivalry record carries the goalie run",
      any(r.get("kind") == "team_team"
          and any("ran" in (i.get("detail") or "")
                  and "goalie" in (i.get("detail") or "")
                  for i in r.get("incidents", []))
          for r in rivalries_g))

# G4. DoPS review resolves a goalie victim: injury + star escalators fire
gd4 = {"kind": "controversial_hit",
       "hitter": gr_home.roster[0].full_name, "hitter_team": "GH",
       "victim": g2.full_name, "victim_team": "GA",
       "hitter_controversy": 80, "goalie_run": True}
g2.is_injured = True
g2.overall_rating = lambda: 92
real_random = random.random
random.random = lambda: 0.0  # force the suspension branch
try:
    res4 = ni._dops_suspension_review(FakeApp(), gd4, gr_home, gr_away,
                                      "2026-10-12", [])
finally:
    random.random = real_random
    g2.is_injured = False
    g2.overall_rating = lambda: 80
check("hurt star goalie victim escalates the suspension (1+1+1+1)",
      res4.get("games", 0) >= 4)
check("suspension reason names the goalie victim",
      g2.full_name in (gr_home.roster[0].suspension_reason or ""))

# G5. live path: heat-scaled goalie victim, offender stays a skater
import simulation as sim_mod


class HeatSim(FakeSim):
    def _get_on_ice(self, team):
        return [p for p in team.roster
                if p.primary_position != PlayerPosition.GOALIE]

    def _lineup_player(self, team, key):
        if key == "G1":
            gs = [p for p in team.roster
                  if p.primary_position == PlayerPosition.GOALIE]
            return gs[0] if gs else None
        return None


ga2 = Team("GA2", "City", "Div", "Conf")
gg = mk_player("Net", "Minder", PlayerPosition.GOALIE, overall=86)
ga2.roster = [gg] + [mk_player(f"X{i}", "K", PlayerPosition.CENTER,
                               overall=70) for i in range(18)]
hsim = HeatSim(gr_home, gr_away)
hsim.away_team = ga2
hsim._live_heat = 40.0
real_random = random.random
random.random = lambda: 0.0  # force the goalie-victim roll at max heat
try:
    v_hot = sim_mod.GameSim._resolve_missed_call_victim(hsim, gr_home)
finally:
    random.random = real_random
check("max heat can make the goalie the missed-call victim",
      v_hot is gg)
hsim._live_heat = 0.0
real_random = random.random
random.random = lambda: 0.99  # cold game: no goalie-victim roll
try:
    v_cold = sim_mod.GameSim._resolve_missed_call_victim(hsim, gr_home)
finally:
    random.random = real_random
check("cold game keeps the missed-call victim a skater",
      v_cold is not None
      and v_cold.primary_position != PlayerPosition.GOALIE)

# G6. stash carries the goalie_run flag for the consequence pass
sim2 = FakeSim(gr_home, gr_away)
phy.apply_missed_call(sim2, gr_home.roster[0], gr_home, "Charging",
                      victim=g2)
phy.apply_missed_call(sim2, gr_home.roster[0], gr_home, "Charging",
                      victim=gr_away.roster[0])
st_goalie, st_skater = sim2._live_borderline_hits[-2:]
check("goalie victim stashed with goalie_run=True",
      st_goalie.get("victim") == g2.full_name
      and st_goalie.get("goalie_run") is True)
check("skater victim stashed with goalie_run=False",
      st_skater.get("goalie_run") is False)

# G7. consequence pass: the room seethes about the goalie run
gd7 = dict(gd4)
gd7["victim"] = g2.full_name
gr_away.dynamics_log = []
ni.apply_incident_consequences(FakeApp(), gr_home, gr_away,
                               ["controversial_hit"], [gd7], False,
                               (3, 2), "2026-10-12", None, [])
check("seething team event names the goalie run",
      any("ran" in (e.get("text") or "")
          and "goalie" in (e.get("text") or "")
          for e in (gr_away.dynamics_log or [])))

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print(f" - {f}")
    sys.exit(1)
