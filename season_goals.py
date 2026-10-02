"""Start-of-season player goals: set in preseason, paid off at season end.

The GM sets a concrete target for each player at season start (e.g.
"score 30 goals", "70 points", "25 wins"). At season end, players who
hit their goals earn major boosts: +4 to two relevant attributes and
+5 potential, plus a morale surge. Young players (<24) who smash their
goal can also jump a potential grade.

Missing a goal costs a little morale (-5) but no attribute penalty --
the system rewards ambition, it doesn't punish it.

Storage: player.season_goal = {
    'type': str,       # e.g. 'goals', 'points', 'wins', 'shutouts'
    'target': int,     # the number to hit
    'set_date': date,  # when the GM set it
}

Goal types by position:
  Skaters: goals, assists, points, hits, blocked_shots, takeaways,
           games_played
  Goalies: wins, shutouts, save_pct (as 910 = .910), gaa (as 250 = 2.50;
           lower-is-better)
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

# Goal type -> (stat field, label, higher_is_better, reward attributes)
SKATER_GOALS = {
    "goals": ("goals", "Goals", True, ["shooting_accuracy", "shooting_power"]),
    "assists": ("assists", "Assists", True, ["passing_accuracy", "vision"]),
    "points": ("points", "Points", True, ["shooting_accuracy", "passing_accuracy"]),
    "hits": ("hits", "Hits", True, ["bodycheck", "aggressiveness"]),
    "blocked_shots": ("blocked_shots", "Blocked Shots", True,
                      ["shot_blocking", "positioning"]),
    "takeaways": ("takeaways", "Takeaways", True,
                  ["pokecheck", "defensive_awareness"]),
    "games_played": ("games_played", "Games Played", True,
                     ["endurance", "durability"]),
}

GOALIE_GOALS = {
    "wins": ("wins", "Wins", True, ["positioning", "composure"]),
    "shutouts": ("shutouts", "Shutouts", True,
                 ["rebound_control", "focus"]),
    "save_pct": ("save_percentage", "Save %", True,
                 ["glove_hand", "reflexes"]),
    "gaa": ("goals_against_avg", "GAA", False,
            ["positioning", "rebound_control"]),
}

ALL_GOAL_TYPES = {**SKATER_GOALS, **GOALIE_GOALS}


def is_goalie(player) -> bool:
    try:
        from game_classes import PlayerPosition as _PP
        return getattr(player, "primary_position", None) == _PP.GOALIE
    except Exception:
        return False


def available_goal_types(player) -> Dict[str, tuple]:
    """Goal types valid for this player's position."""
    return GOALIE_GOALS if is_goalie(player) else SKATER_GOALS


def set_season_goal(player, goal_type: str, target: int,
                    on_date=None, team=None) -> Tuple[bool, str]:
    """Set a season goal. Returns (ok, message).

    One player per goal type per team: if a teammate already holds this
    goal type, the set is rejected (clear theirs first). Pass ``team``
    (with a .roster) to enforce; without it the check is skipped.
    """
    valid = available_goal_types(player)
    if goal_type not in valid:
        return False, f"Invalid goal type for this player: {goal_type}"
    try:
        target = int(target)
    except (TypeError, ValueError):
        return False, "Target must be a number."
    if target <= 0:
        return False, "Target must be positive."
    # One-per-type per team: the award chase belongs to one player.
    if team is not None:
        try:
            for mate in (getattr(team, "roster", None) or []):
                if mate is player:
                    continue
                mg = get_season_goal(mate)
                if mg and mg.get("type") == goal_type:
                    return False, (
                        f"{getattr(mate, 'full_name', 'A teammate')} already "
                        f"holds the {valid[goal_type][1]} goal. Clear theirs "
                        f"first to reassign it.")
        except Exception:
            pass
    try:
        _, label, _, _ = valid[goal_type]
        player.season_goal = {
            "type": goal_type,
            "target": target,
            "set_date": on_date or date.today(),
        }
        return True, (f"{getattr(player, 'full_name', 'Player')}: "
                      f"{label} target set to {target}.")
    except Exception as exc:
        return False, str(exc)


def clear_season_goal(player) -> None:
    try:
        player.season_goal = None
    except Exception:
        pass


def get_season_goal(player) -> Optional[dict]:
    try:
        return getattr(player, "season_goal", None)
    except Exception:
        return None


def goal_progress(player) -> Optional[dict]:
    """Current progress toward the goal: {type, target, current, pct, hit}."""
    goal = get_season_goal(player)
    if not goal:
        return None
    gtype = goal.get("type")
    target = goal.get("target", 0)
    spec = ALL_GOAL_TYPES.get(gtype)
    if not spec or not target:
        return None
    field, label, higher_is_better, _ = spec
    try:
        stats = getattr(player, "stats", None)
        current = getattr(stats, field, 0) or 0
        # save_percentage is 0-1 decimal; goal target is 910-style.
        if gtype == "save_pct":
            current = int(round(float(current) * 1000))
        elif gtype == "gaa":
            current = int(round(float(current) * 100))
        if higher_is_better:
            pct = min(100, int(100 * current / target)) if target else 0
            hit = current >= target
        else:
            pct = min(100, int(100 * target / current)) if current else 0
            hit = 0 < current <= target
        return {"type": gtype, "label": label, "target": target,
                "current": current, "pct": pct, "hit": hit}
    except Exception:
        return None


def evaluate_season_goals(players) -> List[dict]:
    """Season-end: check every goal, apply rewards. Returns a report list.

    Hit: +4 to two relevant attributes, +5 potential, morale +10.
    Young (<24) + smashed by 20%: potential grade bump (probabilistic).
    Miss: morale -5, no attribute penalty.
    """
    report = []
    for p in players or []:
        prog = goal_progress(p)
        if not prog:
            continue
        name = getattr(p, "full_name", "?")
        if prog["hit"]:
            _, _, _, reward_attrs = ALL_GOAL_TYPES[prog["type"]]
            gains = {}
            for attr in reward_attrs[:2]:
                try:
                    cur = getattr(p, attr, 50) or 50
                    new = min(100, cur + 4)
                    setattr(p, attr, new)
                    gains[attr] = 4
                except Exception:
                    pass
            try:
                p.potential = min(100, int(getattr(p, "potential", 50) or 50) + 5)
            except Exception:
                pass
            try:
                p.morale = min(100.0, float(getattr(p, "morale", 70) or 70) + 10)
            except Exception:
                pass
            # Young breakout: smashed the goal by 20%+ -> grade bump chance.
            grade_bump = False
            try:
                age = int(getattr(p, "age", 30) or 30)
                smashed = prog["current"] >= prog["target"] * 1.2
                if age < 24 and smashed:
                    import random
                    ladder = getattr(p, "POTENTIAL_LADDER", ["F", "D", "C", "B", "A"])
                    cur_g = (getattr(p, "potential_grade", "C") or "C").strip().upper()
                    if cur_g in ladder:
                        idx = ladder.index(cur_g)
                        if idx < len(ladder) - 1 and random.random() < 0.5:
                            p.potential_grade = ladder[idx + 1]
                            grade_bump = True
            except Exception:
                pass
            report.append({"player": name, "goal": prog["label"],
                           "target": prog["target"], "actual": prog["current"],
                           "hit": True, "gains": gains,
                           "grade_bump": grade_bump})
        else:
            try:
                p.morale = max(1.0, float(getattr(p, "morale", 70) or 70) - 5)
            except Exception:
                pass
            report.append({"player": name, "goal": prog["label"],
                           "target": prog["target"], "actual": prog["current"],
                           "hit": False, "gains": {},
                           "grade_bump": False})
        # Clear the goal -- new season, new goals.
        clear_season_goal(p)
    return report
