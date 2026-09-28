"""Adaptive Rivals: AI teams scout the user and adjust tactics.

Each AI team has a base tactical identity (set from roster strengths at
season start). Before a game vs the user's team, the AI scouts the user's
recent tendencies and shifts tactics 1 step to counter:

- User scores a lot (high GF/GP) -> AI plays more Defensive
- User defends well (low GA/GP) -> AI plays more Offensive
- User draws many penalties -> AI plays more disciplined (less aggressive)
- User has strong PP -> AI avoids penalties (Conservative PK)

The adjustment is temporary (for that game only); tactics revert to base
identity afterwards. This is purely additive — the sim engine is untouched.

Engine boundary: reads tactics, never changes sim math.
"""

from typing import Any, Dict, List, Optional, Tuple


# Tactic scales (ordered from defensive to offensive)
ES_SCALE = ["Very Defensive", "Defensive", "Balanced", "Offensive", "Very Offensive"]
PP_SCALE = ["Conservative", "Balanced", "Offensive", "Very Offensive"]
PK_SCALE = ["Very Defensive", "Defensive", "Balanced", "Aggressive"]
MATCHING_SCALE = ["Conservative", "Standard", "Aggressive"]


def _shift(tactic: str, scale: List[str], steps: int) -> str:
    """Shift a tactic along its scale, clamped."""
    try:
        idx = scale.index(tactic)
    except ValueError:
        idx = len(scale) // 2
    new_idx = max(0, min(len(scale) - 1, idx + steps))
    return scale[new_idx]


def assign_base_identity(team: Any) -> Dict[str, str]:
    """Set a team's base tactical identity from roster strengths.

    Returns the identity dict and stamps it on the team as
    `base_tactics` (so adaptation can revert to it).
    """
    # Evaluate roster: offensive vs defensive talent
    off_talent = 0
    def_talent = 0
    count = 0
    try:
        for p in team.roster[:20]:  # top 20 skaters
            pos = getattr(p, 'primary_position', None)
            pos_name = pos.name if hasattr(pos, 'name') else str(pos)
            if 'GOALIE' in pos_name.upper():
                continue
            # Simple: use overall rating components if available
            off = getattr(p, 'offensive_rating', None) or getattr(p, 'overall', 70)
            dfn = getattr(p, 'defensive_rating', None) or getattr(p, 'overall', 70)
            # Try attributes
            try:
                off = (p.shooting + p.passing + p.puck_handling) / 3
            except Exception:
                pass
            try:
                dfn = (p.defense + p.positioning + p.checking) / 3
            except Exception:
                pass
            off_talent += off
            def_talent += dfn
            count += 1
    except Exception:
        pass

    if count > 0:
        off_avg = off_talent / count
        def_avg = def_talent / count
        diff = off_avg - def_avg
    else:
        diff = 0

    # Map diff to identity
    if diff > 5:
        es = "Offensive"
    elif diff > 2:
        es = "Balanced"  # lean offensive but not extreme
        # Actually use Offensive for clear offensive edge
        es = "Offensive" if diff > 3 else "Balanced"
    elif diff < -5:
        es = "Defensive"
    elif diff < -2:
        es = "Defensive" if diff < -3 else "Balanced"
    else:
        es = "Balanced"

    # PP/PK/matching defaults based on identity
    if es in ("Offensive", "Very Offensive"):
        pp, pk, matching = "Offensive", "Defensive", "Standard"
    elif es in ("Defensive", "Very Defensive"):
        pp, pk, matching = "Balanced", "Defensive", "Aggressive"
    else:
        pp, pk, matching = "Offensive", "Defensive", "Standard"

    identity = {
        "tactic_even_strength": es,
        "tactic_power_play": pp,
        "tactic_penalty_kill": pk,
        "tactic_line_matching": matching,
    }
    # Stamp on team
    try:
        team.base_tactics = dict(identity)
        # Apply as current tactics
        for k, v in identity.items():
            setattr(team, k, v)
    except Exception:
        pass
    return identity


def scout_user_tendencies(user_team: Any, game_results: List[Any],
                          last_n: int = 10) -> Dict[str, float]:
    """Analyze user's last N games for tactical tendencies.

    Returns dict with:
    - goals_for_per_game
    - goals_against_per_game
    - penalties_drawn_per_game (if available)
    - power_play_pct (if available)
    """
    tendencies = {
        "goals_for_per_game": 3.0,
        "goals_against_per_game": 3.0,
        "penalties_drawn_per_game": 3.0,
        "power_play_pct": 0.20,
    }
    try:
        user_name = user_team.team_name
        recent = []
        for gr in reversed(game_results):
            # game_results entries vary; try common formats
            home = getattr(gr, 'home_team', None)
            away = getattr(gr, 'away_team', None)
            if home is None:
                # Try dict format
                if isinstance(gr, dict):
                    home = gr.get('home_team') or gr.get('home')
                    away = gr.get('away_team') or gr.get('away')
                else:
                    continue
            home_name = home.team_name if hasattr(home, 'team_name') else str(home)
            away_name = away.team_name if hasattr(away, 'team_name') else str(away)
            if user_name not in (home_name, away_name):
                continue
            recent.append(gr)
            if len(recent) >= last_n:
                break

        if not recent:
            return tendencies

        gf_total, ga_total = 0, 0
        for gr in recent:
            try:
                if isinstance(gr, dict):
                    hs = gr.get('home_score', 0)
                    aws = gr.get('away_score', 0)
                    hn = gr.get('home_team') or gr.get('home')
                    hn = hn.team_name if hasattr(hn, 'team_name') else str(hn)
                else:
                    hs = getattr(gr, 'home_score', 0)
                    aws = getattr(gr, 'away_score', 0)
                    hn = getattr(gr.home_team, 'team_name', '')
                if hn == user_name:
                    gf_total += hs
                    ga_total += aws
                else:
                    gf_total += aws
                    ga_total += hs
            except Exception:
                continue

        n = len(recent)
        tendencies["goals_for_per_game"] = gf_total / n if n else 3.0
        tendencies["goals_against_per_game"] = ga_total / n if n else 3.0
    except Exception:
        pass
    return tendencies


def adapt_for_opponent(ai_team: Any, user_team: Any,
                      game_results: List[Any]) -> Dict[str, str]:
    """Adjust AI tactics to counter the user's tendencies.

    Returns the adapted tactics dict (also applied to the team).
    Call `revert_to_base(ai_team)` after the game.
    """
    # Ensure base identity exists
    base = getattr(ai_team, 'base_tactics', None)
    if base is None:
        base = assign_base_identity(ai_team)

    tendencies = scout_user_tendencies(user_team, game_results)
    adapted = dict(base)

    gf = tendencies["goals_for_per_game"]
    ga = tendencies["goals_against_per_game"]

    # If user scores a lot, play more defensive (priority: stop the bleeding)
    defensive_shift = False
    if gf > 3.5:
        adapted["tactic_even_strength"] = _shift(
            base["tactic_even_strength"], ES_SCALE, -1)
        defensive_shift = True
    elif gf > 3.2:
        # Slight lean defensive (only if not already defensive)
        cur = base["tactic_even_strength"]
        if cur in ("Offensive", "Very Offensive", "Balanced"):
            adapted["tactic_even_strength"] = _shift(cur, ES_SCALE, -1)
            defensive_shift = True

    # If user defends well (but isn't also torching us), play more offensive
    # to break through. If both are true, the defensive shift takes priority.
    if not defensive_shift:
        if ga < 2.5:
            adapted["tactic_even_strength"] = _shift(
                adapted["tactic_even_strength"], ES_SCALE, +1)
        elif ga < 2.8:
            cur = adapted["tactic_even_strength"]
            if cur in ("Defensive", "Very Defensive", "Balanced"):
                adapted["tactic_even_strength"] = _shift(cur, ES_SCALE, +1)

    # If user has strong PP (inferred from high GF), be more disciplined
    # (less aggressive PK to avoid penalties)
    if gf > 3.5:
        adapted["tactic_penalty_kill"] = _shift(
            base["tactic_penalty_kill"], PK_SCALE, -1)

    # Apply to team
    try:
        for k, v in adapted.items():
            setattr(ai_team, k, v)
    except Exception:
        pass

    return adapted


def revert_to_base(ai_team: Any):
    """Revert AI tactics to base identity after the game."""
    base = getattr(ai_team, 'base_tactics', None)
    if base:
        try:
            for k, v in base.items():
                setattr(ai_team, k, v)
        except Exception:
            pass


