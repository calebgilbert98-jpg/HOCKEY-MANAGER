# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: advanced metrics model + franchise records + history UI tabs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as g
from game_classes import PlayerPosition
import advanced_metrics as am
from league_history import LeagueHistory

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")

# --- Skater metrics ---
p = g.Player("Test", "Skater", 25, PlayerPosition.LEFT_WING, 85)
p.shooting = 88; p.playmaking = 80; p.passing = 82; p.puck_handling = 84
p.skating = 86; p.defensive_awareness = 75
p.stats.goals = 35; p.stats.assists = 40; p.stats.shots = 280
p.stats.games_played = 82; p.stats.blocks = 30; p.stats.penalties_in_minutes = 24
p.stats.hits = 60
p.avg_toi = "18:00"
m = am.skater_advanced(p)
check("SH% actual", abs(m.sh_pct - 12.5) < 0.01)
check("ixG positive", m.ixg > 20)
check("CF% in range", 35 <= m.cf_pct <= 65)
check("xGF% in range", 35 <= m.xgf_pct <= 65)
check("PDO near 1", 0.95 <= m.pdo <= 1.10)
check("OZ% in range", 30 <= m.oz_pct <= 70)
check("P/60 sane", 1.0 <= m.p_per60 <= 6.0)
check("Game Score positive", m.game_score > 0)
check("hits/blocks pass through", m.hits == 60 and m.blocks == 30)

# Elite vs replacement separation
rep = g.Player("Rep", "Lacement", 25, PlayerPosition.LEFT_WING, 60)
for a in ("shooting", "playmaking", "passing", "puck_handling", "skating", "defensive_awareness"):
    setattr(rep, a, 45)
rep.stats.goals = 8; rep.stats.assists = 12; rep.stats.shots = 120
rep.stats.games_played = 70; rep.avg_toi = "12:00"
mr = am.skater_advanced(rep)
check("elite beats replacement CF%", m.cf_pct > mr.cf_pct)
check("elite beats replacement xGF%", m.xgf_pct > mr.xgf_pct)

# --- Goalie metrics ---
gl = g.Player("Test", "Goalie", 30, PlayerPosition.GOALIE, 90)
gl.positioning = 90; gl.reflexes = 91; gl.rebound_control = 88
gl.consistency = 85; gl.overall = 90
gl.stats.shots_against = 1700; gl.stats.saves = 1550; gl.stats.goals_against = 150
gl.stats.games_played = 55; gl.stats.wins = 32; gl.stats.shutouts = 4
gl.stats.goals_against_avg = 150 / 55
gl.avg_toi = "57:00"
gm = am.goalie_advanced(gl)
check("GSAA sane", -30 <= gm.gsaa <= 60)
check("GSAx sane", -30 <= gm.gsax <= 60)
check("HDSV% in range", 0.700 <= gm.hdsv_pct <= 0.900)
check("QS% in range", 0.0 <= gm.qs_pct <= 1.0)
check("SV% actual", abs(gm.sv_pct - 1550/1700) < 0.001)

# Bad goalie gets negative value
bad = g.Player("Bad", "Goalie", 30, PlayerPosition.GOALIE, 70)
bad.positioning = 60; bad.reflexes = 62; bad.rebound_control = 58
bad.stats.shots_against = 1700; bad.stats.saves = 1480; bad.stats.goals_against = 220
bad.stats.games_played = 55; bad.avg_toi = "57:00"
gb = am.goalie_advanced(bad)
check("bad goalie negative GSAA", gb.gsaa < gm.gsaa)

# --- Team metrics ---
team = type('T', (), {'team_name': 'QA Team', 'roster': [p, rep, gl],
                      'goals_for': 250, 'goals_against': 230,
                      'games_played': 82, 'wins': 45, 'losses': 30,
                      'power_play_opportunities': 250, 'power_play_goals': 55,
                      'penalty_kill_opportunities': 250,
                      'penalty_kill_goals_against': 45})()
tm = am.team_advanced(team)
check("team CF% sane", 40 <= tm.cf_pct <= 60)
check("team PDO sane", 0.94 <= tm.pdo <= 1.06)
check("PP% actual", abs(tm.pp_pct - 22.0) < 0.01)
check("PK% actual", abs(tm.pk_pct - 82.0) < 0.01)

# --- League leaders ---
leaders = am.league_leaders_advanced([p, rep], "ixg", minimum_gp=5)
check("leaders sorted", leaders[0]["name"] == "Test Skater")
check("leaders goalie filter", am.league_leaders_advanced([gl], "gsax", minimum_gp=5)[0]["name"] == "Test Goalie")
check("glossary non-empty", len(am.GLOSSARY) >= 15)

# --- Franchise records ---
h = LeagueHistory()
recs = h.franchise_records.update_from_season(team, "2025-26")
check("records created", len(recs) > 0)
cr = h.franchise_records.get_career_records("QA Team")
check("career goals leader", cr["goals"]["value"] == 35)
sr = h.franchise_records.get_season_records("QA Team")
check("season points leader", sr["points"]["value"] == 75)
# Second season: totals accumulate, records update
p.stats.goals = 40; p.stats.assists = 45; p.stats.shots = 300
p.stats.games_played = 82; p.stats.penalties_in_minutes = 20; p.stats.blocks = 25; p.stats.hits = 55
recs2 = h.franchise_records.update_from_season(team, "2026-27")
cr2 = h.franchise_records.get_career_records("QA Team")
check("career accumulates", cr2["goals"]["value"] == 75)
check("season record broken", h.franchise_records.get_season_records("QA Team")["goals"]["value"] == 40)
# Streaks
check("streak recorded", h.franchise_records.record_streak("QA Team", "win", 10, "2026-27"))
check("streak not beaten", not h.franchise_records.record_streak("QA Team", "win", 8, "2027-28"))
check("streak in team records", h.franchise_records.get_team_records("QA Team")["streak_win"]["length"] == 10)
# Persistence
h2 = LeagueHistory.from_dict(h.to_dict())
check("records survive save/load",
      h2.franchise_records.get_career_records("QA Team")["goals"]["value"] == 75)
check("old saves backfill", True)  # from_dict({}) must not crash
h3 = LeagueHistory.from_dict({})
check("empty dict backfill", h3.franchise_records.get_career_records("X") == {})




# --- Franchise historical seeding (real NHL records) ---
from franchise_records_seed import FRANCHISE_RECORDS_SEED

h = LeagueHistory()
fr = h.franchise_records
check("seed covers 32+ teams", len(fr.season_records) >= 32)
gretzky = fr.season_records.get("Edmonton Oilers", {}).get("goals", {})
check("Gretzky 92 seeded",
      gretzky.get("player") == "Wayne Gretzky" and gretzky.get("value") == 92)
brodeur = fr.goalie_career_records.get("New Jersey Devils", {}).get("wins", {})
check("Brodeur 688 seeded",
      brodeur.get("player") == "Martin Brodeur" and brodeur.get("value") == 688)
# Simulated record beats historical
p = g.Player("Test", "Breaker", 24, PlayerPosition.CENTER, 95)
p.goals = 95; p.assists = 0; p.shots = 300; p.games_played = 82
p.penalty_minutes = 10
t = g.Team("Edmonton Oilers", "Edmonton", "Pacific", "Western")
t.roster = [p]
fr.update_from_season(t, "2026-27")
rec = fr.season_records["Edmonton Oilers"]["goals"]
check("95 beats Gretzky 92",
      rec["value"] == 95 and "Breaker" in rec["player"])
# Re-seeding does not clobber the simulated mark
fr.seed_historical_records(FRANCHISE_RECORDS_SEED)
rec = fr.season_records["Edmonton Oilers"]["goals"]
check("reseed keeps simulated record", rec["value"] == 95)
# Old-save backfill: empty from_dict gets seeded
h2 = LeagueHistory.from_dict({"seasons": [], "franchise_records": {}})
check("from_dict backfills seed",
      len(h2.franchise_records.season_records) >= 32)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
