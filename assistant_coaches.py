"""Assistant coaches: the Paul Coffey effect.

Head coaches own the systems (tactics.py). Assistants own the *teaching*:
a great defensive assistant accelerates young defensemen, and a franchise
icon behind the bench changes the room -- players buy into systems faster
and kids hang on every word. Hiring YOUR icon is the Coffey hire: prowess
*and* status.

Design notes (Chris's constraints):
- Assistants never touch per-game xG/pace directly. Head coach + systems
  own the sim math, so league scoring stays neutral by construction.
  Assistants work through development, familiarity (buy-in), and morale.
- Personality on likelihood: icon_level gates the multipliers.
- Old saves: every read is getattr-defensive; Staff.icon_team defaults "".
"""

from typing import Any, Dict, List, Optional, Tuple

_ASSISTANT_ROLES = ("Assistant Coach", "Associate Coach")


def _assistants_of(team: Any) -> List[Any]:
    """All assistant/associate coaches on a team's staff list."""
    try:
        out = []
        for stf in getattr(team, "staff", []) or []:
            role = str(getattr(getattr(stf, "role", None), "value", ""))
            if any(r in role for r in _ASSISTANT_ROLES):
                out.append(stf)
        return out
    except Exception:
        return []


def assistant_specialty(staff: Any) -> str:
    """Offense / defense / goalie / general from coaching attributes."""
    try:
        atk = float(getattr(staff, "attacking_coaching", 50) or 50)
        dfn = float(getattr(staff, "defensive_coaching", 50) or 50)
        gls = float(getattr(staff, "coaching_goalies", 50) or 50)
        best = max(atk, dfn, gls)
        if best < 60:
            return "general"
        if dfn >= atk and dfn >= gls:
            return "defense"
        if atk >= gls:
            return "offense"
        return "goalie"
    except Exception:
        return "general"


def icon_level(staff: Any) -> str:
    """'' | 'star' | 'icon' -- how big a legend this staffer was as a player."""
    try:
        return str(getattr(staff, "icon_level", "") or "")
    except Exception:
        return ""


def is_franchise_icon(staff: Any, team: Any) -> bool:
    """True when this staffer is a franchise icon OF THIS TEAM.

    The Coffey check: a legend's status is team-specific. Coffey coaching
    in Edmonton hits different than Coffey coaching anywhere else.
    """
    try:
        it = getattr(staff, "icon_team", "") or ""
        tn = getattr(team, "team_name", "") or ""
        return bool(it and tn and it == tn)
    except Exception:
        return False


def _position_group(player: Any) -> str:
    try:
        pos = str(getattr(player, "primary_position", "")).upper()
        if "GOALIE" in pos:
            return "goalie"
        if "DEFENSE" in pos or pos in ("D", "LD", "RD"):
            return "defense"
        return "offense"
    except Exception:
        return "offense"


def assistant_development_deltas(player: Any, team: Any) -> List[Tuple[str, float]]:
    """Development-engine terms: assistants develop the kids at their position.

    A defensive assistant with 90 defensive_coaching moves young defensemen;
    a franchise icon multiplies it -- kids hang on every word from a legend
    in their franchise's sweater. Returns [(label, points)] for the deltas
    list, same shape as the head-coach fit term.
    """
    deltas: List[Tuple[str, float]] = []
    try:
        age = getattr(player, "age", 99) or 99
        if age > 26:
            return deltas
        pgroup = _position_group(player)
        tname = getattr(team, "team_name", "?") or "?"
        for ac in _assistants_of(team):
            spec = assistant_specialty(ac)
            if spec == "general" or spec != pgroup:
                continue
            attr = {"defense": "defensive_coaching",
                    "offense": "attacking_coaching",
                    "goalie": "coaching_goalies"}[spec]
            skill = float(getattr(ac, attr, 50) or 50)
            pts = (skill - 50.0) / 100.0 * 8.0          # -4..+4
            young = float(getattr(ac, "working_with_youngsters", 50) or 50)
            pts *= 0.7 + (young / 100.0) * 0.6           # 0.7..1.3
            name = f"{getattr(ac, 'first_name', '')} {getattr(ac, 'last_name', '')}".strip()
            if is_franchise_icon(ac, team):
                lvl = icon_level(ac)
                mult = 1.5 if lvl == "icon" else 1.25
                pts *= mult
                label = (f"Learning from {name} ({tname} icon)")
            else:
                label = f"{spec.title()} assistant: {name or 'coach'}"
            if abs(pts) >= 0.5:
                deltas.append((label, round(pts, 1)))
    except Exception:
        pass
    return deltas


def assistant_familiarity_bonus(team: Any) -> float:
    """Extra familiarity points per tick: the room buys in faster when a
    legend teaches the system. Called by tactics.tick_tactics_familiarity."""
    try:
        bonus = 0.0
        for ac in _assistants_of(team):
            if is_franchise_icon(ac, team):
                bonus += 2.0 if icon_level(ac) == "icon" else 1.0
            elif float(getattr(ac, "tactical_knowledge", 0) or 0) >= 80:
                bonus += 1.0  # great teachers teach fast, icon or not
        return min(bonus, 4.0)
    except Exception:
        return 0.0


def on_assistant_hired(team: Any, staff: Any, app: Any = None) -> Optional[str]:
    """Hire effects: the room reacts, the news notices.

    Hiring a franchise icon lifts the kids at his position (small happiness
    bump -- the dream is real) and always makes the news feed; icons make
    bigger news. Returns the news line (or None).
    """
    try:
        role = str(getattr(getattr(staff, "role", None), "value", ""))
        if not any(r in role for r in _ASSISTANT_ROLES):
            return None
        name = f"{getattr(staff, 'first_name', '')} {getattr(staff, 'last_name', '')}".strip()
        tname = getattr(team, "team_name", "the club") or "the club"
        line = None
        if is_franchise_icon(staff, team):
            spec = assistant_specialty(staff)
            line = (f"{tname} bring {name} home behind the bench -- "
                    f"a franchise icon to run the {spec}. The room is buzzing.")
            # The kids at his position feel it immediately.
            try:
                pgroup = {"defense": "defense", "offense": "offense",
                          "goalie": "goalie"}.get(spec)
                for p in getattr(team, "roster", []) or []:
                    if _position_group(p) != pgroup:
                        continue
                    if (getattr(p, "age", 99) or 99) > 24:
                        continue
                    hap = getattr(p, "happiness", None)
                    if isinstance(hap, (int, float)):
                        p.happiness = max(0, min(100, hap + 4))
            except Exception:
                pass
        else:
            line = (f"{tname} add {name or 'a new assistant'} "
                    f"({assistant_specialty(staff)}) to the coaching staff.")
        if app is not None and line:
            try:
                app.add_news(line)
            except Exception:
                pass
        return line
    except Exception:
        return None


def describe_assistants(team: Any) -> List[str]:
    """Human-readable staff lines for the staff screen."""
    lines: List[str] = []
    try:
        for ac in _assistants_of(team):
            name = f"{getattr(ac, 'first_name', '')} {getattr(ac, 'last_name', '')}".strip()
            spec = assistant_specialty(ac)
            tag = " -- FRANCHISE ICON" if is_franchise_icon(ac, team) else ""
            lines.append(f"{name} ({spec}){tag}")
    except Exception:
        pass
    return lines
