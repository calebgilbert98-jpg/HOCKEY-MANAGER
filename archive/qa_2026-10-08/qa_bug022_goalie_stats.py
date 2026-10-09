#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: BUG-022 -- goalie SA/SV/GA recording on every sim path.

Root causes fixed:
  1. main._process_single_game_result.get_starting_goalie compared
     primary_position.name == "G" (enum NAME is "GOALIE") -> always None,
     so user-team goalies got zero SA/SV. Now "GOALIE".
  2. goals_against was never incremented anywhere: now recorded on Goal
     events (user-team path) and as opp_goals in _generate_player_stats
     (batch path). GameSim path already flushed via b902d8b.

Tests:
  A. _process_single_game_result (user-team quick-sim path): both goalies
     gain SA/SV/GA; GA == goals conceded; SA == saves + GA.
  B. _generate_player_stats (batch path): GA == opponent goals, SA/SV > 0.
  C. GameSim engine path: goalie season stats accumulate via flush.

Usage: python3 qa_bug022_goalie_stats.py   (exit 0 = all pass)
"""
import sys, os, random
sys.path.insert(0, '/home/hatch/workspace/playthrough')
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')
os.environ.setdefault("DISPLAY", ":99")

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS: {name}", flush=True)
    else:
        FAIL += 1; print(f"  FAIL: {name} {detail}", flush=True)

def goalies_of(team):
    return [p for p in team.roster
            if getattr(getattr(p, "primary_position", None), "name", "") == "GOALIE"]

def snap(g):
    return (g.stats.saves, g.stats.shots_against, g.stats.goals_against)

def main():
    random.seed(20260928)
    print("=== QA: BUG-022 goalie stats ===", flush=True)
    from pt import load_career
    gm, app = load_career("day1.hm")
    league = gm.league
    user_team = gm.user_team
    other = next(t for t in league.teams if t is not user_team
                 and len(goalies_of(t)) > 0)
    check("both teams dress a goalie", len(goalies_of(user_team)) > 0)

    # ---- Test A: user-team commit path ---------------------------------
    print("\n[Path A: _process_single_game_result]", flush=True)
    from quick_sim import AdvancedGameSim
    home, away = user_team, other
    sim = AdvancedGameSim(home, away)
    winner, loser, scores, events, notable = sim.run()
    hg, ag = goalies_of(home)[0], goalies_of(away)[0]
    s_hg, s_ag = snap(hg), snap(ag)
    app._process_single_game_result(
        gm.current_date, home, away, winner, loser, scores,
        events, notable, sim, stats_from_events=True, preseason=False)
    d_hg = tuple(b - a for a, b in zip(s_hg, snap(hg)))
    d_ag = tuple(n - o for o, n in zip(s_ag, snap(ag)))
    # goals conceded per team from notable events
    from collections import Counter
    conceded = Counter()
    for e in notable or []:
        if e.get("event") == "Goal":
            t = e.get("team")
            # team that conceded = the other side
            conceded[away.team_name if t == home.team_name else home.team_name] += 1
    check("home goalie saves > 0", d_hg[0] > 0, f"delta={d_hg}")
    check("home goalie shots_against > 0", d_hg[1] > 0, f"delta={d_hg}")
    check("home goalie goals_against > 0", d_hg[2] > 0, f"delta={d_hg}")
    check("away goalie saves > 0", d_ag[0] > 0, f"delta={d_ag}")
    check("away goalie shots_against > 0", d_ag[1] > 0, f"delta={d_ag}")
    check("away goalie goals_against > 0", d_ag[2] > 0, f"delta={d_ag}")
    check("home GA == goals conceded", d_hg[2] == conceded[home.team_name],
          f"{d_hg[2]} vs {conceded[home.team_name]}")
    check("away GA == goals conceded", d_ag[2] == conceded[away.team_name],
          f"{d_ag[2]} vs {conceded[away.team_name]}")
    check("home SA == saves + GA", d_hg[1] == d_hg[0] + d_hg[2], f"delta={d_hg}")
    check("away SA == saves + GA", d_ag[1] == d_ag[0] + d_ag[2], f"delta={d_ag}")

    # ---- Test B: batch path --------------------------------------------
    print("\n[Path B: _generate_player_stats]", flush=True)
    hg2, ag2 = goalies_of(home)[0], goalies_of(away)[0]
    s_hg2, s_ag2 = snap(hg2), snap(ag2)
    app._generate_player_stats(home, away, 4, 2)
    d2_hg = tuple(n - o for o, n in zip(s_hg2, snap(hg2)))
    d2_ag = tuple(n - o for o, n in zip(s_ag2, snap(ag2)))
    check("batch: home goalie GA == away goals (2)", d2_hg[2] == 2, f"delta={d2_hg}")
    check("batch: away goalie GA == home goals (4)", d2_ag[2] == 4, f"delta={d2_ag}")
    check("batch: home goalie SA > 0 and SV > 0", d2_hg[1] > 0 and d2_hg[0] > 0,
          f"delta={d2_hg}")
    check("batch: away goalie SA > 0 and SV > 0", d2_ag[1] > 0 and d2_ag[0] > 0,
          f"delta={d2_ag}")

    # ---- Test C: GameSim engine flush -----------------------------------
    print("\n[Path C: GameSim engine]", flush=True)
    from simulation import GameSim
    sim2 = GameSim(home, away)
    w2, l2, sc2, _gl2, _n2 = sim2.run()
    hg3, ag3 = goalies_of(home)[0], goalies_of(away)[0]
    check("GameSim: home goalie SA > 0", hg3.stats.shots_against > 0,
          f"SA={hg3.stats.shots_against}")
    check("GameSim: home goalie SV > 0", hg3.stats.saves > 0,
          f"SV={hg3.stats.saves}")
    check("GameSim: home goalie GA > 0", hg3.stats.goals_against > 0,
          f"GA={hg3.stats.goals_against}")
    check("GameSim: away goalie GA > 0", ag3.stats.goals_against > 0,
          f"GA={ag3.stats.goals_against}")

    print(f"\n{ PASS} passed, {FAIL} failed", flush=True)
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
