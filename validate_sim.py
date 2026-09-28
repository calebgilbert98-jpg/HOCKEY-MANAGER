"""
Deterministic validation harness for Puck Dynasty sim.

Seeds database generation once, reuses the same league, seeds each game
independently. Reports: goals, SOG, attempts, xG, high-danger chances,
penalties, PP opportunities/conversion, shutouts, blowouts, shot disparity.

Usage: python3 validate_sim.py [--games N] [--seed S]
Output: JSON report to stdout + human-readable summary to stderr.
"""

import sys
import os
import json
import random
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_generator import DatabaseGenerator, DATABASE_CONFIGURATIONS
from simulation import GameSim


def run_validation(n_games=50, seed=20260928):
    # Seed ONCE for database generation -- same league every run.
    random.seed(seed)
    dg = DatabaseGenerator(DATABASE_CONFIGURATIONS["Small"])
    league = dg.generate_comprehensive_database()
    # Use only NHL teams -- mixing AHL teams in creates false
    # blowouts/shutouts from cross-league talent gaps.
    teams = [t for t in league.teams
             if len(t.roster) >= 18
             and 'National Hockey League' in getattr(t, 'league_name', '')]
    if not teams:  # fallback if league_name isn't set
        teams = [t for t in league.teams if len(t.roster) >= 18]

    results = {
        'games': n_games,
        'seed': seed,
        'goals': [],
        'sog': [],
        'penalties': [],
        'pp_opps': [],
        'pp_goals': [],
        'xg': [],
        'shutouts': 0,
        'blowouts': 0,  # 5+ goal margin
        'ot_games': 0,
        'en_goals': 0,
        'pulls': 0,
    }

    for i in range(n_games):
        # Independent seed per game -- reproducible, no cross-game state.
        game_seed = seed * 1000 + i
        random.seed(game_seed)
        h, a = random.sample(teams, 2)
        # Re-seed after sampling so team choice doesn't consume game RNG
        random.seed(game_seed)
        sim = GameSim(h, a)
        sim.run()

        total_goals = sim.home_score + sim.away_score
        results['goals'].append(total_goals)

        # SOG from game stats
        sog = sum(v.get('shots_on_goal', 0) for v in sim.game_stats.values())
        results['sog'].append(sog)
        attempts = sum(v.get('shot_attempts', 0)
                       for v in sim.game_stats.values())
        results.setdefault('attempts', []).append(attempts)

        # Penalties from log
        pens = sum(1 for l in sim.game_log if '[PENALTY]' in str(l))
        results['penalties'].append(pens)

        # xG
        xg_h = getattr(sim, 'expected_goals_for', {}).get(h.team_name, 0)
        xg_a = getattr(sim, 'expected_goals_for', {}).get(a.team_name, 0)
        results['xg'].append(xg_h + xg_a)

        # Shutouts, blowouts, OT
        if sim.home_score == 0 or sim.away_score == 0:
            results['shutouts'] += 1
        if abs(sim.home_score - sim.away_score) >= 5:
            results['blowouts'] += 1
        if getattr(sim, 'overtime', False) or sim.period > 3:
            results['ot_games'] += 1

        # EN goals and pulls
        for line in sim.game_log:
            ls = str(line)
            if 'GOALIE_PULLED' in ls:
                results['pulls'] += 1
            if 'EMPTY NET' in ls.upper() and 'GOAL' in ls.upper():
                results['en_goals'] += 1

    # Summary stats
    def avg(lst):
        return sum(lst) / len(lst) if lst else 0

    summary = {
        'games': n_games,
        'seed': seed,
        'goals_per_game': round(avg(results['goals']), 2),
        'sog_per_game': round(avg(results['sog']), 2),
        'attempts_per_game': round(avg(results.get('attempts', [])), 2),
        'penalties_per_game': round(avg(results['penalties']), 2),
        'xg_per_game': round(avg(results['xg']), 2),
        'shutouts': results['shutouts'],
        'blowouts': results['blowouts'],
        'ot_games': results['ot_games'],
        'pulls': results['pulls'],
        'en_goals': results['en_goals'],
    }
    return summary, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=50)
    ap.add_argument('--seed', type=int, default=20260928)
    args = ap.parse_args()

    summary, _ = run_validation(args.games, args.seed)

    # Human-readable to stderr
    print("=" * 50, file=sys.stderr)
    print("PUCK DYNASTY SIM VALIDATION", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(f"Games: {summary['games']} (seed {summary['seed']})", file=sys.stderr)
    print(f"Goals/game:     {summary['goals_per_game']}", file=sys.stderr)
    print(f"SOG/game:       {summary['sog_per_game']}", file=sys.stderr)
    print(f"Attempts/game:  {summary['attempts_per_game']}", file=sys.stderr)
    print(f"Penalties/game: {summary['penalties_per_game']}", file=sys.stderr)
    print(f"xG/game:        {summary['xg_per_game']}", file=sys.stderr)
    print(f"Shutouts:       {summary['shutouts']}", file=sys.stderr)
    print(f"Blowouts (5+):  {summary['blowouts']}", file=sys.stderr)
    print(f"OT games:       {summary['ot_games']}", file=sys.stderr)
    print(f"Goalie pulls:   {summary['pulls']}", file=sys.stderr)
    print(f"EN goals:       {summary['en_goals']}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # JSON to stdout
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
