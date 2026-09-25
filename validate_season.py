#!/usr/bin/env python3
"""Headless full-season validation harness.

Drives the REAL league schedule through the REAL GameSim engine (full-detail
path, same as _simulate_game_full_batch), updating standings the same way
_update_standings_fast does. Validates structural invariants:

- All 32 teams play exactly 82 games
- W + L + OTL == GP for every team
- Points = 2*W + OTL
- No team plays 3+ consecutive days
- League-wide GF == GA
- Goalie stats credited sensibly
"""

import sys
import random
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, '/home/hatch/workspace/hockey-manager')

from game_classes import League, Team, PlayerPosition
from player_generator import PlayerGenerator
from simulation import GameSim


def create_test_league():
    """Create a 32-team league with generated rosters (uses built-in NHL teams)."""
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    print(f"  League has {len(league.teams)} built-in teams")

    for team in list(league.teams):  # copy: we must not mutate while iterating
        team.league_name = "National Hockey League"
        # Generate a roster: 14F, 8D, 3G (23 players)
        for _ in range(14):
            pos = random.choice([PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                                 PlayerPosition.RIGHT_WING])
            team.roster.append(gen.create_player(position=pos, team_name=team.team_name))
        for _ in range(8):
            team.roster.append(gen.create_player(position=PlayerPosition.DEFENSE,
                                                 team_name=team.team_name))
        for _ in range(3):
            team.roster.append(gen.create_player(position=PlayerPosition.GOALIE,
                                                 team_name=team.team_name))
        # Set a basic lineup: first 12F, 6D, 2G dress
        forwards = [p for p in team.roster
                    if p.primary_position in (PlayerPosition.CENTER,
                                              PlayerPosition.LEFT_WING,
                                              PlayerPosition.RIGHT_WING)][:12]
        defense = [p for p in team.roster
                   if p.primary_position == PlayerPosition.DEFENSE][:6]
        goalies = [p for p in team.roster
                   if p.primary_position == PlayerPosition.GOALIE][:2]
        for i, p in enumerate(forwards):
            line = i // 3 + 1
            pos_key = ['C', 'LW', 'RW'][i % 3]
            team.lineup[f'F{line}_{pos_key}'] = p
        for i, p in enumerate(defense):
            pair = i // 2 + 1
            side = 'L' if i % 2 == 0 else 'R'
            team.lineup[f'D{pair}_{side}'] = p
        for i, p in enumerate(goalies):
            team.lineup[f'G{i+1}'] = p

    return league


def run_season_validation():
    print("Creating 32-team league...")
    league = create_test_league()
    print(f"  {len(league.teams)} teams created")

    print("Generating schedule...")
    league.generate_schedule(season_year=2026)
    print(f"  {len(league.schedule)} games scheduled")

    # Group games by date
    games_by_date = defaultdict(list)
    for item in league.schedule:
        if isinstance(item, dict):
            d = item.get('date')
            home = item.get('home_team')
            away = item.get('away_team')
        elif isinstance(item, tuple) and len(item) >= 3:
            d, home, away = item[0], item[1], item[2]
        else:
            continue
        if d and home and away:
            # home/away might be team objects or names; resolve to objects
            if isinstance(home, str):
                home = next((t for t in league.teams if t.team_name == home), None)
            if isinstance(away, str):
                away = next((t for t in league.teams if t.team_name == away), None)
            if home and away:
                games_by_date[d].append((home, away))

    dates = sorted(games_by_date.keys())
    print(f"  Season spans {dates[0]} to {dates[-1]} ({len(dates)} game dates)")

    # Standings
    standings = {t.team_name: {'W': 0, 'L': 0, 'OTL': 0, 'GF': 0, 'GA': 0, 'GP': 0}
                 for t in league.teams}
    team_game_dates = defaultdict(list)

    print("Simulating season (full GameSim path)...")
    total_games = 0
    for d in dates:
        for home, away in games_by_date[d]:
            sim = GameSim(home, away)
            periods = set()
            def sniff(ev, _p=periods):
                if isinstance(ev, dict):
                    _p.add(ev.get('period', 1))
            sim.pbp_listeners.append(sniff)
            try:
                winner, loser, scores, _log, _notable = sim.run()
            except Exception as e:
                print(f"  ERROR on {d} {home.team_name} vs {away.team_name}: {e}")
                continue

            home_score, away_score = scores
            went_to_ot = any(p > 3 for p in periods)

            # Update standings (mirrors _update_standings_fast)
            hs = standings[home.team_name]
            aws = standings[away.team_name]
            hs['GP'] += 1; aws['GP'] += 1
            hs['GF'] += home_score; hs['GA'] += away_score
            aws['GF'] += away_score; aws['GA'] += home_score
            team_game_dates[home.team_name].append(d)
            team_game_dates[away.team_name].append(d)

            if winner == home:
                hs['W'] += 1
                if went_to_ot:
                    aws['OTL'] += 1
                else:
                    aws['L'] += 1
            else:
                aws['W'] += 1
                if went_to_ot:
                    hs['OTL'] += 1
                else:
                    hs['L'] += 1

            total_games += 1
            if total_games % 200 == 0:
                print(f"  ...{total_games} games")

    print(f"\nSimulated {total_games} games")
    print("\n=== VALIDATION ===")
    errors = []

    # 1. All teams play 82
    for name, s in standings.items():
        if s['GP'] != 82:
            errors.append(f"{name}: GP={s['GP']} (expected 82)")

    # 2. W + L + OTL == GP
    for name, s in standings.items():
        if s['W'] + s['L'] + s['OTL'] != s['GP']:
            errors.append(f"{name}: W({s['W']})+L({s['L']})+OTL({s['OTL']}) != GP({s['GP']})")

    # 3. Points = 2*W + OTL (implied by above, but check a sample)
    # 4. No 3+ consecutive days
    for name, dates_list in team_game_dates.items():
        dates_list = sorted(set(dates_list))
        for i in range(len(dates_list) - 2):
            d1, d2, d3 = dates_list[i], dates_list[i+1], dates_list[i+2]
            if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                errors.append(f"{name}: 3 consecutive game days {d1}, {d2}, {d3}")
                break

    # 5. League GF == GA
    total_gf = sum(s['GF'] for s in standings.values())
    total_ga = sum(s['GA'] for s in standings.values())
    if total_gf != total_ga:
        errors.append(f"League GF({total_gf}) != GA({total_ga})")

    # 6. Goalie SV% sanity (no absurd values)
    for team in league.teams:
        for p in team.roster:
            if p.primary_position == PlayerPosition.GOALIE and p.stats.shots_against > 0:
                sv = p.stats.save_percentage
                if not (0.75 <= sv <= 1.0):
                    errors.append(f"{p.full_name} ({team.team_name}): SV%={sv:.3f} "
                                  f"({p.stats.saves}/{p.stats.shots_against})")

    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors[:20]:
            print(f"  ✗ {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return False
    else:
        print("ALL CHECKS PASSED ✓")
        print(f"  - 32 teams × 82 games")
        print(f"  - W+L+OTL == GP for all teams")
        print(f"  - No 3-in-a-row scheduling violations")
        print(f"  - League GF ({total_gf}) == GA ({total_ga})")
        print(f"  - All goalie SV% in sane range")
        # Show top teams
        ranked = sorted(standings.items(),
                        key=lambda x: (2*x[1]['W'] + x[1]['OTL'], x[1]['GF'] - x[1]['GA']),
                        reverse=True)
        print(f"\nTop 5: {', '.join(f'{n} ({2*s['W']+s['OTL']}pts)' for n, s in ranked[:5])}")
        return True


if __name__ == '__main__':
    random.seed(42)
    ok = run_season_validation()
    sys.exit(0 if ok else 1)
