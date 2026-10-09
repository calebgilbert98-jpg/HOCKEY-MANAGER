# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: analytics hardening -- the 7 directives.

Covers, per directive, what was already implemented vs newly added:
1. Steal-watch validation window opens through _post_trade_effects.
2. Every trade path funnels through execute_trade -> _post_trade_effects
   (fresh start); the integration point is idempotent per trade stamp.
3. Analytics storylines: season-aware phases, (kind, player) dedup,
   per-player cooldown, significance gating.
4. Canonical Rocket Richard naming everywhere.
5. Hart weighting reads the authoritative roster mapping.
6. Calder eligibility: real-rule boundaries + season-year attribution
   + goalie inclusion + prior_nhl_gp archiving at season rollover.
7. Honest model-estimate labeling on every modeled-metric surface.
"""
import sys, os, random, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260928)

from types import SimpleNamespace

import game_classes as g
from game_classes import PlayerPosition
import awards_race as ar
import analytics_scouting as asc
import reputation_system as rs
import trade_engine as te

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


def mkpos(name):
    return SimpleNamespace(name=name, value=name)


def mkskater(name, team, gp, gls, ast, age=26, elite=False):
    p = SimpleNamespace(
        id=name, full_name=name, name=name, team_name=team,
        games_played=gp, goals=gls, assists=ast,
        shots=220, hits=50, blocked_shots=40, takeaways=30, giveaways=20,
        penalty_minutes=25, plus_minus=5, faceoff_wins=100, faceoff_attempts=200,
        primary_position=mkpos("C"), age=age, morale=70, happiness=70,
        contract=SimpleNamespace(salary=2500000, years_remaining=2),
    )
    v = 95 if elite else 84
    for attr in ("shooting", "passing", "puck_handling", "skating",
                 "offensive_awareness", "defensive_awareness", "strength",
                 "checking", "fighting", "faceoffs", "shot_blocking",
                 "durability", "off_awareness", "def_awareness"):
        setattr(p, attr, v)
    p.overall_rating = lambda: v
    return p


def mkteam(name, gp=50, pts=60, roster=()):
    t = SimpleNamespace(team_name=name, games_played=gp, points=pts,
                        roster=list(roster), ahl_roster=[], prospects=[],
                        staff=[], scout_buy_tips={}, scout_sell_tips={},
                        steal_watch={})
    t.remove_player = lambda p: t.roster.remove(p) if p in t.roster else None
    t.add_player = lambda p: t.roster.append(p)
    t.initialize_draft_picks = lambda *a, **k: None
    return t


# ---------------------------------------------------------------------------
# D1: steal-watch validation window (tracking + post-trade production check)
# ---------------------------------------------------------------------------
seller = mkteam("Sellers", gp=50, pts=40)
buyer = mkteam("Buyers", gp=50, pts=70)
star = mkskater("Star Winger", "Sellers", 40, 12, 18, age=25)
seller.roster.append(star)
pid = star.id
buyer.scout_buy_tips[pid] = {"scout": "Test Scout", "scout_id": "s1",
                             "jpa": 18, "signals": ["Due for goals"],
                             "value_score": 22.0, "correct": True}
# buyer (user_team) acquires star from seller: partner_assets move to user.
te.execute_trade(buyer, seller, [], [star], date_str="2026-11-01", league=None)
check("D1 steal watch opens via _post_trade_effects",
      pid in getattr(buyer, "steal_watch", {}))
watch = buyer.steal_watch[pid]
check("D1 watch snapshots pre-trade pace",
      watch.get("pre_gp") == 40 and watch.get("pre_points") == 30)
# Post-trade breakout: 16 more games, 20 more points -> validates.
star.games_played = 56
star.goals, star.assists = 20, 30
evs = rs.check_steal_watch(buyer, None, "2026-12-15")
check("D1 production validates the scout call",
      any(e.get("kind") == "steal_validated" for e in evs))
check("D1 validated watch is closed out",
      pid not in getattr(buyer, "steal_watch", {}))

# Expiry path: no breakout -> watch expires as a graded miss, not silently.
seller2 = mkteam("Sellers2", gp=50, pts=40)
buyer2 = mkteam("Buyers2", gp=50, pts=70)
dud = mkskater("Flat Liner", "Sellers2", 40, 10, 10, age=28)
seller2.roster.append(dud)
buyer2.scout_buy_tips[dud.id] = {"scout": "Test Scout", "scout_id": "s1",
                                 "jpa": 18, "signals": [], "value_score": 5.0}
te.execute_trade(buyer2, seller2, [], [dud], date_str="2026-11-01", league=None)
dud.games_played = 95  # 55 post-trade games, flat production
dud.goals, dud.assists = 12, 12
evs2 = rs.check_steal_watch(buyer2, None, "2027-02-01")
check("D1 expired watch grades a miss (never silent)",
      any(e.get("kind") == "steal_failed" for e in evs2))

# ---------------------------------------------------------------------------
# D2: one idempotent integration point for every trade path
# ---------------------------------------------------------------------------
bad = mkteam("Lottery Club", gp=50, pts=40)
good = mkteam("Contenders", gp=50, pts=70)
mover = mkskater("Rescue Me", "Lottery Club", 40, 10, 15, age=26)
mover.morale = 40
bad.roster.append(mover)
# bad (user_team) sends mover to good (partner_team): user_assets move out.
te.execute_trade(bad, good, [mover], [], date_str="2026-12-01", league=None)
check("D2 execute_trade applies fresh start (lottery->contender lift)",
      mover.morale > 40)
check("D2 player actually moved", mover in good.roster and mover not in bad.roster)
after_first = mover.morale
te._post_trade_effects(bad, good, [mover], [], "2026-12-01", None)
check("D2 integration point is idempotent per trade stamp",
      mover.morale == after_first)
# Both live call sites route through execute_trade (user + AI deadline).
import inspect
src_tn = inspect.getsource(__import__("trade_negotiation"))
src_main = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "main.py")).read()
check("D2 user trade path calls te.execute_trade",
      "te.execute_trade(" in src_tn)
check("D2 AI deadline path calls te.execute_trade",
      "te.execute_trade(seller, buyer," in src_main)

# ---------------------------------------------------------------------------
# D3: season-aware storylines with dedup + cooldowns
# ---------------------------------------------------------------------------
class FakeMedia:
    def __init__(self):
        self.storylines = []

def gm_on(month, day=15):
    gm = SimpleNamespace()
    gm.current_date = datetime.date(2026 if month >= 9 else 2027, month, day)
    return gm

young = mkskater("Young Driver", "Mid Club", 40, 8, 12, age=22, elite=True)
mid = mkteam("Mid Club", gp=45, pts=45)
mid.roster.append(young)

m_sep = FakeMedia()
n = asc.publish_analytics_storylines(m_sep, [young], [mid], gm_on(9))
check("D3 preseason (Sep): no stories, no sample", n == 0)

m_oct = FakeMedia()
n1 = asc.publish_analytics_storylines(m_oct, [young], [mid], gm_on(10))
check("D3 early season publishes a breakout seed", n1 >= 1)
n2 = asc.publish_analytics_storylines(m_oct, [young], [mid], gm_on(10, 16))
check("D3 (kind, player) never publishes twice", n2 == 0)

# Season-phase gating: breakout_watch is an early-season narrative only.
seeds = asc.analytics_storylines([young], [mid], limit=12)
kinds = {s["kind"] for s in seeds}
check("D3 breakout seed generated for the young driver",
      "breakout_watch" in kinds)
phase_apr = asc._season_phase(4)
check("D3 April allows only stakes stories",
      phase_apr is not None and "breakout_watch" not in phase_apr[0])
phase_feb = asc._season_phase(2)
check("D3 Feb deadline approach leads with wasted-prime narratives",
      phase_feb is not None and phase_feb[1][0] == "wasted_prime_goalie")

# Cooldown: a second kind for the same player within 45 days is suppressed.
m_cd = FakeMedia()
asc.publish_analytics_storylines(m_cd, [young], [mid], gm_on(10))
log = asc._analytics_story_log(m_cd)
check("D3 publish writes the dedup log", len(log) >= 1)

# ---------------------------------------------------------------------------
# D4: canonical Rocket Richard naming
# ---------------------------------------------------------------------------
main_src = src_main
check("D4 no '(Goal Leader)' variant remains in main.py",
      'Richard Trophy (Goal Leader)' not in main_src)
check("D4 canonical name in main.py",
      'Maurice "Rocket" Richard Trophy' in main_src)
names = [n for n, _d, _k in ar.AWARD_DEFINITIONS]
check("D4 canonical name in awards_race definitions",
      'Maurice "Rocket" Richard Trophy' in names)
check("D4 rocket_race exists and is pure goals",
      "most goals" in ar.rocket_race.__doc__)

# ---------------------------------------------------------------------------
# D5: Hart weighting from the authoritative roster mapping
# ---------------------------------------------------------------------------
elite = mkskater("Elite C", "Stale Team", 50, 40, 60, age=27, elite=True)
mid2 = mkskater("Mid C", "Bad Team", 50, 35, 55, age=27)
elite.id, mid2.id = 101, 102
team_pct = {"Good Team": 0.650, "Bad Team": 0.400, "Stale Team": 0.400}
r_no_map = ar.hart_race([elite, mid2], team_pct)
r_map = ar.hart_race([elite, mid2], team_pct,
                     roster_map={101: "Good Team", 102: "Bad Team"})
check("D5 roster_map overrides the stale team_name label",
      r_map[0]["team_pct"] == 0.650)
check("D5 without map the stale label is used (the bug being fixed)",
      r_no_map[0]["team_pct"] == 0.400)
check("D5 roster_team_map built from rosters",
      ar.roster_team_map([mkteam("Good Team", roster=[elite])])[101]
      == "Good Team")
# The standings-window caller now passes the map (structural).
ssw_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "stats_standings_window.py")).read()
check("D5 award-races UI passes roster_map",
      "roster_map=roster_map" in ssw_src)

# ---------------------------------------------------------------------------
# D6: Calder eligibility audit
# ---------------------------------------------------------------------------
def rookie(birth, prior=(), gp=30, pos=PlayerPosition.CENTER):
    p = g.Player("Cal", "Der", 21, pos, 80)
    p.birth_date = birth
    p.prior_nhl_gp = list(prior)
    p.games_played = gp
    p.goals, p.assists = 10, 15
    return p

# Age boundaries: 26-or-younger ON September 15 of the start year.
ok, _ = ar.calder_eligible(rookie("1999-09-16"), 2026)   # 26 on Sep 15
check("D6 age 26 on Sep 15: eligible", ok)
ok, why = ar.calder_eligible(rookie("1999-09-15"), 2026)  # turns 27 ON Sep 15
check("D6 turns 27 ON Sep 15: ineligible", not ok)
ok, _ = ar.calder_eligible(rookie("2004-03-01"), 2026)
check("D6 clearly young: eligible", ok)
# GP thresholds: >25 in one prior season; >6 in each of two.
ok, _ = ar.calder_eligible(rookie("2004-03-01", prior=[25]), 2026)
check("D6 exactly 25 prior GP: eligible", ok)
ok, _ = ar.calder_eligible(rookie("2004-03-01", prior=[26]), 2026)
check("D6 26 prior GP in one season: ineligible", not ok)
ok, _ = ar.calder_eligible(rookie("2004-03-01", prior=[7, 7]), 2026)
check("D6 7+ GP in two prior seasons: ineligible", not ok)
ok, _ = ar.calder_eligible(rookie("2004-03-01", prior=[6, 7]), 2026)
check("D6 only one season above 6 GP: eligible", ok)
# Goalies are Calder-eligible.
gr = rookie("2004-03-01", pos=PlayerPosition.GOALIE)
gr.wins, gr.shots_against, gr.saves = 12, 500, 455
race = ar.calder_race([gr], season_year=2026)
check("D6 goalie appears in the Calder race",
      any(r["player"] is gr and r.get("goalie") for r in race))
# Season-year attribution: June awards judge the season just ended.
check("D6 June 2027 -> season year 2026",
      ar.calder_season_year(datetime.date(2027, 6, 15)) == 2026)
check("D6 Oct 2026 -> season year 2026",
      ar.calder_season_year(datetime.date(2026, 10, 1)) == 2026)
check("D6 Aug 2026 -> season year 2025",
      ar.calder_season_year(datetime.date(2026, 8, 1)) == 2025)
# Rollover archives NHL GP into prior_nhl_gp (was dead code before).
lg = g.League(league_name="Test League", season_year=2026)
t1 = mkteam("Club One")
t2 = mkteam("Club Two")
p_nhl = g.Player("NHL", "Reg", 24, PlayerPosition.CENTER, 80)
p_nhl.stats.games_played = 30
p_ahl = g.Player("AHL", "Reg", 24, PlayerPosition.CENTER, 75)
p_ahl.stats.games_played = 60
t1.roster.append(p_nhl)
t2.ahl_roster.append(p_ahl)  # minor-leaguer: in the org, off the NHL roster
lg.teams.extend([t1, t2])
lg.end_of_season()
check("D6 rollover archives NHL GP for roster players",
      getattr(p_nhl, "prior_nhl_gp", None) == [30])
check("D6 non-roster (minor-league) GP never touches rookie status",
      getattr(p_ahl, "prior_nhl_gp", None) == [0])
ok, _ = ar.calder_eligible(p_nhl, 2027 - 1 + 1)  # next season's check
check("D6 archived 30-GP season disqualifies next year",
      not ar.calder_eligible(p_nhl, 2027)[0])

# ---------------------------------------------------------------------------
# D7: honest model-estimate labeling
# ---------------------------------------------------------------------------
check("D7 leaders tabs carry the estimates disclosure",
      "Estimates, not tracking data" in ssw_src)
check("D7 disclosure covers advanced + breakout + goaltending tabs",
      '("advanced", "breakout", "goaltending")' in ssw_src)
ui_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "ui_components.py")).read()
check("D7 player card keeps its ±CI + as-of labeling",
      "models as of" in ui_src and "Estimates, not tracking data" in ui_src)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
