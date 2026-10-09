#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""playtest_driver.py -- 5-season headless GM playtest of Puck Dynasty.

Plays as GM of the Toronto Maple Leafs across 5 full seasons, exercising:
practices, team talks, pressers, trades, waivers, extensions, entry draft
(scout/draft/sign ELCs), free agency, coaching carousel, All-Star, playoffs,
awards races, morale/dressing room, rivalry games, analytics hub.

Writes per-season JSON logs to /tmp/playtest_logs/season{N}.json.
Run: python3 playtest_driver.py [start_season] [num_seasons]
"""
import sys, os, json, random, math, traceback
from datetime import date, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as g
from game_classes import PlayerPosition
from database_generator import generate_database
from quick_sim import AdvancedGameSim, best_lines, flatten_lineup
import draft_night
import playoff_system

LOG_DIR = "/tmp/playtest_logs"
os.makedirs(LOG_DIR, exist_ok=True)

USER_TEAM_NAME = "Toronto Maple Leafs"

STRATEGIES = {
    1: "win-now",   # 2026-27: contend, buy at deadline
    2: "all-in",    # 2027-28: mortgage the future
    3: "retool",    # 2028-29: shed salary, stay competitive
    4: "rebuild",   # 2029-30: sell veterans, play the kids
    5: "win-now",   # 2030-31: young core contends
}

# ---------------------------------------------------------------- story log
class StoryLog:
    def __init__(self):
        self.events = []   # dicts: season, date, kind, engines[], headline, detail
        self.bugs = []     # dicts: where, what, fixed?, file_line
    def add(self, season, day, kind, engines, headline, detail=""):
        self.events.append({"season": season, "date": str(day), "kind": kind,
                            "engines": engines, "headline": headline,
                            "detail": detail})
    def bug(self, season, where, what, fixed, file_line=""):
        self.bugs.append({"season": season, "where": where, "what": what,
                          "fixed": fixed, "file_line": file_line})
    def dump(self, path):
        with open(path, "w") as f:
            json.dump({"events": self.events, "bugs": self.bugs}, f, indent=1,
                      default=str)

# ------------------------------------------------------------------ helpers
def nhl_teams(league):
    return [t for t in league.teams
            if getattr(t, "league_name", "") == "National Hockey League"]

def get_team(league, name):
    for t in nhl_teams(league):
        if t.team_name == name:
            return t
    return None

def ensure_lineup(team):
    try:
        team.lineup = flatten_lineup(best_lines(team))
    except Exception:
        pass

def ovr(p):
    try:
        return p.overall_rating()
    except Exception:
        return 50.0

def distribute_stats(home, away, hs, ag):
    """Credit player season stats from a simmed scoreline (driver-side,
    mirrors main.py _generate_player_stats logic)."""
    for team, tg in ((home, hs), (away, ag)):
        healthy = [p for p in team.roster if not getattr(p, "is_injured", False)]
        fw = [p for p in healthy if p.primary_position.name in
              ("LEFT_WING", "RIGHT_WING", "CENTER")][:12]
        df = [p for p in healthy if p.primary_position.name in
              ("LEFT_DEFENSE", "RIGHT_DEFENSE", "DEFENSE")][:6]
        dressed = fw + df
        if not dressed:
            continue
        weights = []
        for p in dressed:
            w = ovr(p) / 100.0
            if p.primary_position.name in ("LEFT_WING", "RIGHT_WING", "CENTER"):
                w *= 1.5
            weights.append(max(w, 0.01))
        # goals
        for _ in range(tg):
            scorer = random.choices(dressed, weights=weights)[0]
            scorer.stats.goals += 1
            scorer.stats.shots += 1
            scorer.stats.games_played += 0  # GP credited below
        # assists: 0-2 per goal, not the same distribution pass twice
        for _ in range(tg):
            n_a = random.randint(0, 2)
            helpers = random.choices(dressed, weights=weights, k=min(n_a, len(dressed)))
            for h in helpers:
                h.stats.assists += 1
        # shots (~30/team)
        for _ in range(max(tg, random.randint(25, 35))):
            s = random.choice(fw) if fw and random.random() < 0.75 else (random.choice(df) if df else None)
            if s is not None:
                s.stats.shots += 1
        # PIM
        for _ in range(random.randint(3, 6)):
            p = random.choice(dressed)
            p.stats.penalties_in_minutes += random.choice([2, 2, 2, 4, 5])
        # GP for dressed skaters
        for p in dressed:
            p.stats.games_played += 1
        # goalies: starter faces shots
        goalies = [p for p in healthy if p.primary_position.name == "GOALIE"]
        if goalies:
            st = max(goalies, key=ovr)
            # goals_against is what the OTHER team scored (opp goals charged,
            # not own: previously tg was used here, manufacturing sub-2.00 GAAs)
            opp_tg = ag if team is home else hs
            sa = max(opp_tg, int(random.normalvariate(30, 4)))
            st.stats.shots_against += sa
            st.stats.saves += max(0, sa - opp_tg)
            st.stats.goals_against += opp_tg
            st.stats.games_played += 1
            try:
                st.stats._update_goalie_stats()
            except Exception:
                pass
            if tg <= (hs if team is away else ag):
                pass
        # goalie W/L
        if goalies:
            won = (tg > (ag if team is home else hs))
            st = max(goalies, key=ovr)
            if won:
                st.stats.wins += 1
            else:
                st.stats.losses += 1

def apply_standings(league, home, away, hs, ag, went_ot=False):
    st = league.standings
    ot = (hs == ag)  # shouldn't happen (shootout decides), kept for safety
    if hs > ag:
        w, l = home, away
    else:
        w, l = away, home
    st[w.team_name]["W"] += 1
    st[w.team_name]["Points"] += 2
    if went_ot:
        # NHL: an OT/shootout loss earns a point and is tracked separately
        # from a regulation loss (previously the harness credited every
        # loss as regulation, leaving OTL at 0 league-wide).
        st[l.team_name]["OTL"] = st[l.team_name].get("OTL", 0) + 1
        st[l.team_name]["Points"] += 1
    else:
        st[l.team_name]["L"] += 1
    # track team W/L too
    for t, tag in ((w, "W"), (l, "L")):
        try:
            t.wins = getattr(t, "wins", 0) + (1 if tag == "W" else 0)
            t.losses = getattr(t, "losses", 0) + (1 if tag == "L" else 0)
        except Exception:
            pass
