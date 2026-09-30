# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Analytics hub (roadmap F6).

Expected-goals model, momentum graphs, zone/shot maps, and generated
analyst reports — the visible surface for the sim's depth.
"""

from collections import defaultdict
from typing import Dict, List


# Base xG by shot location (NHL-calibrated-ish; tuned against sim output)
LOCATION_XG = {
    'crease': 0.35,
    'low_slot': 0.22,
    'high_slot': 0.12,
    'left_circle': 0.10,
    'right_circle': 0.10,
    'point': 0.05,
    'left_wing': 0.04,
    'right_wing': 0.04,
    'behind_net': 0.02,
}


def shot_xg(location, shooter_quality=50, situation='even'):
    """Expected goals for one shot.

    location: ShotLocation value string.
    shooter_quality: 1-100 (shooting attribute blend).
    situation: 'even', 'pp', 'sh', 'empty_net'.
    """
    base = LOCATION_XG.get(str(location).lower(), 0.05)
    # Shooter quality: 50 = average (1.0x); scales 0.7x-1.4x
    q_mult = 0.7 + (shooter_quality / 100) * 0.7
    xg = base * q_mult
    if situation == 'pp':
        xg *= 1.15  # more time/space
    elif situation == 'sh':
        xg *= 0.85
    elif situation == 'empty_net':
        xg = 0.95  # basically a goal
    return round(min(0.98, xg), 3)


def game_xg(pbp_events):
    """Total xG per team from a game's PBP shot events."""
    totals = defaultdict(float)
    shots = defaultdict(int)
    for e in pbp_events:
        if e.get('event') != 'shot':
            continue
        team = e.get('attacking_team', 'unknown')
        xg = shot_xg(e.get('location', 'point'),
                     e.get('shooter_quality', 50),
                     e.get('situation', 'even'))
        totals[team] += xg
        shots[team] += 1
    return {t: {'xg': round(totals[t], 2), 'shots': shots[t]}
            for t in totals}


def momentum_series(momentum_history):
    """Convert momentum_history to a plottable series.

    Returns list of (timestamp, value) where value is -3..+3
    (negative = away, positive = home).
    """
    mapping = {
        'heavily_favoring_home': 3, 'favoring_home': 2,
        'slightly_favoring_home': 1, 'neutral': 0,
        'slightly_favoring_away': -1, 'favoring_away': -2,
        'heavily_favoring_away': -3,
    }
    series = []
    for entry in momentum_history or []:
        if isinstance(entry, dict):
            val = entry.get('momentum', 'neutral')
            ts = entry.get('timestamp', 0)
        else:
            val, ts = entry, 0
        v = val.value if hasattr(val, 'value') else str(val)
        series.append((ts, mapping.get(v, 0)))
    return series


def shot_map(pbp_events, team_name):
    """Shot locations for one team: {location: count}."""
    counts = defaultdict(int)
    for e in pbp_events:
        if e.get('event') == 'shot' and e.get('attacking_team') == team_name:
            counts[str(e.get('location', 'unknown'))] += 1
    return dict(counts)


def analyst_report(game_data):
    """Generate a natural-language analyst summary of a game.

    game_data: dict with home_team, away_team, home_score, away_score,
               pbp_events, momentum_history.
    """
    home = game_data.get('home_team', 'Home')
    away = game_data.get('away_team', 'Away')
    hs = game_data.get('home_score', 0)
    aws = game_data.get('away_score', 0)
    pbp = game_data.get('pbp_events', [])

    xg = game_xg(pbp)
    hx = xg.get(home, {}).get('xg', 0)
    ax = xg.get(away, {}).get('xg', 0)

    lines = [
        f"Final: {home} {hs}, {away} {aws}.",
        f"Expected goals: {home} {hx:.2f}, {away} {ax:.2f}.",
    ]
    # Deserved-to-win?
    if (hs > aws and hx < ax) or (aws > hs and ax < hx):
        lines.append("The score flattered the winner — the underlying "
                     "numbers favored the loser.")
    elif abs(hx - ax) < 0.3:
        lines.append("An even game by the numbers; goaltending or "
                     "finishing decided it.")
    else:
        leader = home if hx > ax else away
        lines.append(f"{leader} controlled chance quality.")

    # Shot map summary
    hmap = shot_map(pbp, home)
    amap = shot_map(pbp, away)
    hslot = hmap.get('low_slot', 0) + hmap.get('high_slot', 0)
    aslot = amap.get('low_slot', 0) + amap.get('high_slot', 0)
    lines.append(f"Slot shots: {home} {hslot}, {away} {aslot}.")

    # Momentum
    series = momentum_series(game_data.get('momentum_history', []))
    if series:
        swings = sum(1 for i in range(1, len(series))
                     if abs(series[i][1] - series[i-1][1]) >= 2)
        lines.append(f"Momentum swung hard {swings} time(s).")

    return "\n".join(lines)
