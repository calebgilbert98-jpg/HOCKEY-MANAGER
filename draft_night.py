"""Draft night systems for Puck Dynasty: ticker, pick valuation, draft grades.

Pure logic, no GUI. Powers the Entry Draft war room.
"""
from __future__ import annotations

import random
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Ticker commentary
# ---------------------------------------------------------------------------

TICKER_TEMPLATES = [
    "Pick #{pick}: {team} select {player} ({pos}).",
    "#{pick} — {player} is off the board to {team}.",
    "{team} take {player} at #{pick}.",
    "With the #{pick} pick, {team} grab {pos} {player}.",
    "{player} heads to {team} at #{pick}.",
    "Draft floor buzz: {team} love {player}'s upside at #{pick}.",
    "#{pick}: {team} go with {player}.",
]

STEAL_TEMPLATES = [
    "{player} at #{pick} could be the steal of the draft for {team}.",
    "Great value for {team}: {player} slips to #{pick}.",
]

REACH_TEMPLATES = [
    "Bold move: {team} reach for {player} at #{pick}.",
    "A surprise at #{pick} — {team} take {player} earlier than expected.",
]


def ticker_line(overall: int, team_name: str, player, round_num: int,
                reach: bool = False, steal: bool = False) -> str:
    try:
        pos = player.primary_position.value
    except Exception:
        pos = "?"
    name = getattr(player, 'full_name', str(player))
    if steal:
        tpl = random.choice(STEAL_TEMPLATES)
    elif reach:
        tpl = random.choice(REACH_TEMPLATES)
    else:
        tpl = random.choice(TICKER_TEMPLATES)
    return tpl.format(pick=overall, team=team_name, player=name, pos=pos,
                      round=round_num)


# ---------------------------------------------------------------------------
# Pick + player valuation for grades and draft-day trades
# ---------------------------------------------------------------------------

def pick_slot_value(overall: int) -> int:
    """Expected value of a draft slot by overall pick number."""
    if overall < 1:
        return 50
    return max(20, int(3000 * (0.965 ** (overall - 1))))


_POT_VALUES = {'F': 60, 'D': 170, 'C-': 320, 'C': 520, 'C+': 850,
               'B-': 1250, 'B': 1850, 'B+': 2650,
               'A-': 3700, 'A': 5100, 'A+': 7200}


def drafted_player_value(player) -> int:
    grade = getattr(player, 'potential_grade', 'C') or 'C'
    base = _POT_VALUES.get(grade.strip(), 520)
    try:
        base += max(0, (player.overall_rating() - 35) * 8)
    except Exception:
        pass
    return base


def draft_grades(picks_made: List[Tuple[str, int, object]]) -> List[Tuple[str, str, float]]:
    """Grade every team's draft. Returns [(team, grade, score)] sorted best-first."""
    by_team: Dict[str, List[Tuple[int, object]]] = {}
    for team_name, overall, player in picks_made:
        by_team.setdefault(team_name, []).append((overall, player))
    ratios = []
    for team_name, picks in by_team.items():
        expected = sum(pick_slot_value(o) for o, _ in picks)
        actual = sum(drafted_player_value(p) for _, p in picks)
        ratios.append((team_name, (actual / expected) if expected else 1.0))
    ratios.sort(key=lambda r: r[1], reverse=True)
    # Curve grades by percentile so the spread is always meaningful
    n = len(ratios)
    results = []
    for i, (team_name, ratio) in enumerate(ratios):
        pct = i / max(1, n - 1)
        if pct <= 0.10:
            grade = 'A+'
        elif pct <= 0.30:
            grade = 'A'
        elif pct <= 0.45:
            grade = 'B+'
        elif pct <= 0.60:
            grade = 'B'
        elif pct <= 0.75:
            grade = 'C'
        elif pct <= 0.90:
            grade = 'D'
        else:
            grade = 'F'
        results.append((team_name, grade, ratio))
    return results


def grade_color(grade: str) -> str:
    return {'A+': '#46c93a', 'A': '#46c93a', 'B+': '#7bd747', 'B': '#a3d84b',
            'C': '#e8b93c', 'D': '#d97f3c', 'F': '#e74c3c'}.get(grade, '#e8ecf4')
