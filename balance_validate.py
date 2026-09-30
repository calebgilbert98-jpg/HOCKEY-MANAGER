#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Balance validation: full 1,312-game season through the real GameSim.

Checks structural invariants (from validate_season.py) PLUS NHL stat
believability bands. Writes JSON results to qa_output/balance_results.json
(gitignored -- results never commit).

Run headless, no UI needed:
    python3 balance_validate.py            # full 1,312-game season (~75 min)
    python3 balance_validate.py --smoke    # 128-game smoke (~7 min, bands only)

Release-gate rule (roadmap v3): full run must be green before any push that
touches scoring-affecting code in EITHER sim engine (simulation.py GameSim,
quick_sim.py AdvancedGameSim). Smoke is fine for daily work.
"""
import sys, os, random, json
from datetime import date
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator
from simulation import GameSim

random.seed(20260927)

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SMOKE = '--smoke' in sys.argv
GAME_CAP = 128 if SMOKE else 10**9

# NHL reference bands (2023-26 era). Soft = worth a look; hard = broken.
BANDS = {
    'team_goals_per_game':   ((2.70, 3.60), "NHL ~3.0-3.2"),
    'mean_goalie_sv':        ((0.885, 0.920), "NHL ~.900"),
    'art_ross_points':       ((90, 160), "NHL ~110-135"),
    'hundred_pt_players':    ((0, 20), "NHL ~5-12"),
    'first_place_pts':       ((95, 135), "NHL ~108-122"),
    'last_place_pts':        ((42, 85), "NHL ~55-68"),
    'playoff_cutoff_pts':    ((80, 108), "NHL ~90-98"),
    'ot_rate':               ((0.12, 0.35), "NHL ~0.22-0.26"),
    'shutout_rate':          ((0.015, 0.14), "NHL ~0.04-0.08"),
}

def build_league():
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in list(league.teams):
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
        fw = [p for p in team.roster if p.primary_position in
              (PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING)][:12]
        df = [p for p in team.roster if p.primary_position == PlayerPosition.DEFENSE][:6]
        gl = [p for p in team.roster if p.primary_position == PlayerPosition.GOALIE][:2]
        for i, p in enumerate(fw):
            team.lineup[f'F{i//3+1}_{["C", "LW", "RW"][i%3]}'] = p
        for i, p in enumerate(df):
            team.lineup[f'D{i//2+1}_{"LD" if i % 2 == 0 else "RD"}'] = p
        for i, p in enumerate(gl):
            team.lineup[f'G{i+1}'] = p
    return league

def main():
    league = build_league()
    league.generate_schedule(season_year=2026)
    games_by_date = defaultdict(list)
    for item in league.schedule:
        if isinstance(item, dict):
            d, home, away = item.get('date'), item.get('home_team'), item.get('away_team')
        elif isinstance(item, tuple) and len(item) >= 3:
            d, home, away = item[0], item[1], item[2]
        else:
            continue
        if isinstance(home, str):
            home = next((t for t in league.teams if t.team_name == home), None)
        if isinstance(away, str):
            away = next((t for t in league.teams if t.team_name == away), None)
        if d and home and away:
            games_by_date[d].append((home, away))
    dates = sorted(games_by_date.keys())

    st = {t.team_name: {'W': 0, 'L': 0, 'OTL': 0, 'GF': 0, 'GA': 0, 'GP': 0,
                       'dates': []} for t in league.teams}
    ot_games = 0
    shutout_team_games = 0
    total_games = 0
    total_goals = 0
    errors = []

    for d in dates:
        for home, away in games_by_date[d]:
            sim = GameSim(home, away)
            periods = set()
            sim.pbp_listeners.append(
                lambda ev, _p=periods: _p.add(ev.get('period', 1))
                if isinstance(ev, dict) else None)
            try:
                winner, loser, scores, _log, _notable = sim.run()
            except Exception as e:
                errors.append(f"ERROR {d} {home.team_name} vs {away.team_name}: {e}")
                continue
            hs, aws_ = scores
            total_goals += hs + aws_
            went_ot = any(p > 3 for p in periods)
            if went_ot:
                ot_games += 1
            if hs == 0:
                shutout_team_games += 1
            if aws_ == 0:
                shutout_team_games += 1
            h, a = st[home.team_name], st[away.team_name]
            h['GP'] += 1; a['GP'] += 1
            h['GF'] += hs; h['GA'] += aws_
            a['GF'] += aws_; a['GA'] += hs
            h['dates'].append(d); a['dates'].append(d)
            if winner == home:
                h['W'] += 1
                a['OTL' if went_ot else 'L'] += 1
            else:
                a['W'] += 1
                h['OTL' if went_ot else 'L'] += 1
            total_games += 1
            if total_games >= GAME_CAP:
                break
            if total_games % 200 == 0:
                print(f"  ...{total_games} games", flush=True)
        if total_games >= GAME_CAP:
            break

    # ---- structural invariants (full runs only; smoke doesn't play 82) ----
    for name, s in st.items():
        if SMOKE:
            break
        if s['GP'] != 82:
            errors.append(f"{name}: GP={s['GP']}")
        if s['W'] + s['L'] + s['OTL'] != s['GP']:
            errors.append(f"{name}: W+L+OTL != GP")
        dl = sorted(set(s['dates']))
        for i in range(len(dl) - 2):
            if (dl[i+1] - dl[i]).days == 1 and (dl[i+2] - dl[i+1]).days == 1:
                errors.append(f"{name}: 3 straight game days")
                break
    gf = sum(s['GF'] for s in st.values())
    ga = sum(s['GA'] for s in st.values())
    if gf != ga:
        errors.append(f"League GF({gf}) != GA({ga})")

    # ---- believability ----
    pts_of = lambda s: 2 * s['W'] + s['OTL']
    ranked = sorted(st.items(), key=lambda kv: (pts_of(kv[1]), kv[1]['GF'] - kv[1]['GA']),
                    reverse=True)
    # 500-shot minimum on full runs; smoke mode only plays ~4 games/team, so
    # scale the workload floor down (still ~2 games of shots against).
    _sv_floor = 50 if SMOKE else 500
    goalies = [(p.stats.save_percentage, p.stats.shots_against, p.full_name)
               for t in league.teams for p in t.roster
               if p.primary_position == PlayerPosition.GOALIE and p.stats.shots_against >= _sv_floor]
    mean_sv = sum(s for s, _, _ in goalies) / len(goalies) if goalies else 0
    skaters = sorted(
        ((p.stats.points, p.full_name, t.team_name)
         for t in league.teams for p in t.roster
         if p.primary_position != PlayerPosition.GOALIE),
        reverse=True)
    metrics = {
        'games': total_games,
        'team_goals_per_game': round(gf / (total_games * 2), 3),
        'mean_goalie_sv': round(mean_sv, 4),
        'goalies_sampled': len(goalies),
        'art_ross_points': skaters[0][0] if skaters else 0,
        'art_ross_name': skaters[0][1] if skaters else None,
        'hundred_pt_players': sum(1 for p, _, _ in skaters if p >= 100),
        'first_place_pts': pts_of(ranked[0][1]),
        'first_place_team': ranked[0][0],
        'last_place_pts': pts_of(ranked[-1][1]),
        'playoff_cutoff_pts': pts_of(ranked[16][1]),
        'ot_rate': round(ot_games / total_games, 4),
        'shutout_rate': round(shutout_team_games / (total_games * 2), 4),
        'top_scorers': [f"{n} ({tm}) {p}pts" for p, n, tm in skaters[:5]],
    }
    flags = []
    # Season-total bands (points races, standings) are meaningless in smoke
    # mode: 128 games is ~4 games/team, not an 82-game season.
    SMOKE_SKIP = {'art_ross_points', 'hundred_pt_players', 'first_place_pts',
                  'last_place_pts', 'playoff_cutoff_pts'}
    for key, ((lo, hi), ref) in BANDS.items():
        if SMOKE and key in SMOKE_SKIP:
            continue
        v = metrics[key]
        if not (lo <= v <= hi):
            flags.append(f"{key}={v} outside [{lo},{hi}] ({ref})")

    result = {'metrics': metrics, 'flags': flags, 'errors': errors,
              'invariant_ok': not errors}
    os.makedirs(os.path.join(REPO_DIR, 'qa_output'), exist_ok=True)
    with open(os.path.join(REPO_DIR, 'qa_output', 'balance_results.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print("\n=== METRICS ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("=== FLAGS ===" if flags else "=== NO BELIEVABILITY FLAGS ===")
    for fl in flags:
        print(f"  ⚠ {fl}")
    print("=== ERRORS ===" if errors else "=== INVARIANTS OK ===")
    for e in errors[:10]:
        print(f"  ✗ {e}")
    return not errors

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
