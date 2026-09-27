"""Assistant coaches: the Paul Coffey effect, generalized.

Head coaches own the systems (tactics.py). Assistants bring more (or less)
out of the players -- and it shows up in results, not just on paper:

- Any great coach can have the effect, scaled on prowess (attributes,
  reputation, experience -- NHL or AHL pedigree). Not just franchise icons.
- It only lands when the pieces fit: a working system the room has learned,
  a group he meshes with, and results to back it up.
- It can run out: losing, a fractured room, and shelf life erode it.
- Icons are the exception: a franchise icon's legacy is cemented. His aura
  doesn't decay no matter what happens on the ice.

Design notes (Chris's constraints):
- No development aspect: assistants don't grow attributes. They get more
  out of the players who are already there, through morale and buy-in.
- Assistants never touch per-game xG/pace directly. The morale channel
  (which the sim already reads) and faster system buy-in carry the effect,
  so league scoring stays neutral by construction.
- Personality on likelihood: prowess, man-management and mesh gate
  everything; duds actively drag.
- Old saves: every read is getattr-defensive.
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


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def assistant_prowess(staff: Any) -> float:
    """0-100: how good a coach this is, from attributes and pedigree.

    Specialty coaching matters most, then tactical knowledge, the ability
    to manage men, reputation (an NHL/AHL track record opens ears), and
    sheer years behind a bench.
    """
    try:
        spec = assistant_specialty(staff)
        attr = {"defense": "defensive_coaching",
                "offense": "attacking_coaching",
                "goalie": "coaching_goalies"}.get(spec)
        specialty = float(getattr(staff, attr, 50) or 50) if attr else 60.0
        tactical = float(getattr(staff, "tactical_knowledge", 50) or 50)
        man = float(getattr(staff, "man_management", 50) or 50)
        rep = float(getattr(staff, "reputation", 50) or 50)
        exp = _clamp(float(getattr(staff, "experience", 5) or 5), 0.0, 30.0)
        score = (specialty * 0.40 + tactical * 0.20 + man * 0.15
                 + rep * 0.15 + (exp / 30.0 * 100.0) * 0.10)
        return _clamp(score, 20.0, 99.0)
    except Exception:
        return 50.0


def assistant_effect(staff: Any) -> float:
    """Current effectiveness 0-100. First read seeds it from prowess;
    the monthly tick then moves it with results, mesh and shelf life."""
    try:
        eff = getattr(staff, "assistant_effect", None)
        if eff is None:
            eff = assistant_prowess(staff)
            staff.assistant_effect = eff
        return float(eff)
    except Exception:
        return 50.0


def _team_win_pct(team: Any) -> Optional[float]:
    try:
        w = float(getattr(team, "wins", 0) or 0)
        l = float(getattr(team, "losses", 0) or 0)
        otl = float(getattr(team, "otl", 0) or 0)
        g = w + l + otl
        return (w + 0.5 * otl) / g if g > 0 else None
    except Exception:
        return None


def assistants_monthly_tick(team: Any, win_pct: Optional[float] = None) -> List[str]:
    """Monthly engine: effectiveness drifts, the room feels it.

    Drift (non-icons only):
      results   win% >= .600: +3 | <= .400: -4   (reflective with results)
      mesh      chemistry >= 70: +1.5 | < 45: -2.5
      system    familiarity >= 80: +1 | < 60: -1.5 (part of a working system)
      shelf     3+ years with the team: -1/month (the message gets stale)
    Icons skip drift entirely: legacy cemented, regardless of results.

    Morale push (everyone, icons included): the roster's morale moves
    (effect - 55) * 0.05 per assistant per month, scaled by mesh. Great
    assistants lift rooms; duds drag them. The sim already reads morale,
    so this is the "brings more out of players" channel.
    Returns news-worthy lines (a voice going stale, a great hire paying off).
    """
    lines: List[str] = []
    try:
        assistants = _assistants_of(team)
        if not assistants:
            return lines
        if win_pct is None:
            win_pct = _team_win_pct(team)
        try:
            import reputation_system as _rs
            chem = float((_rs.team_chemistry(
                getattr(team, "roster", []) or []) or {}).get("score", 50))
        except Exception:
            chem = 50.0
        fam = float(getattr(team, "tactics_familiarity", 85) or 85)
        mesh = 0.4 + 0.6 * _clamp(chem / 100.0, 0.0, 1.0)
        tname = getattr(team, "team_name", "the club") or "the club"

        for ac in assistants:
            name = (f"{getattr(ac, 'first_name', '')} "
                    f"{getattr(ac, 'last_name', '')}").strip() or "The assistant"
            eff = assistant_effect(ac)
            if is_franchise_icon(ac, team):
                # Cemented: re-anchor to prowess every month. Losing seasons,
                # stale messages, fractured rooms -- none of it touches him.
                ac.assistant_effect = assistant_prowess(ac)
                eff = float(ac.assistant_effect)
            else:
                d = 0.0
                if win_pct is not None:
                    d += 3.0 if win_pct >= 0.600 else (-4.0 if win_pct <= 0.400 else 0.0)
                d += 1.5 if chem >= 70 else (-2.5 if chem < 45 else 0.0)
                d += 1.0 if fam >= 80 else (-1.5 if fam < 60 else 0.0)
                if (getattr(ac, "years_with_team", 0) or 0) >= 3:
                    d -= 1.0
                new_eff = _clamp(eff + d, 20.0, 99.0)
                ac.assistant_effect = new_eff
                if eff >= 55 and new_eff < 55:
                    lines.append(f"{name}'s message is going stale in {tname}.")
                elif eff < 55 and new_eff >= 65:
                    lines.append(f"{name} has the {tname} room buzzing.")
                eff = new_eff
            # The room feels him, for better or worse.
            push = (eff - 55.0) * 0.05 * mesh
            if abs(push) >= 0.2:
                for p in getattr(team, "roster", []) or []:
                    try:
                        m = getattr(p, "morale", None)
                        if isinstance(m, (int, float)):
                            p.morale = _clamp(m + push, 1.0, 100.0)
                    except Exception:
                        continue
    except Exception:
        pass
    return lines


def assistant_familiarity_bonus(team: Any) -> float:
    """Buy-in: the room learns systems faster under a voice it trusts.

    Elite (effect >= 80): +2 | solid (>= 65): +1 | dud (< 40): -1.
    Icons always count as elite -- the room hangs on a legend.
    """
    try:
        bonus = 0.0
        for ac in _assistants_of(team):
            eff = assistant_effect(ac)
            if is_franchise_icon(ac, team):
                eff = max(eff, 80.0)
            if eff >= 80:
                bonus += 2.0
            elif eff >= 65:
                bonus += 1.0
            elif eff < 40:
                bonus -= 1.0
        return _clamp(bonus, -2.0, 4.0)
    except Exception:
        return 0.0


def on_assistant_hired(team: Any, staff: Any, app: Any = None) -> Optional[str]:
    """Hire news. Icons are events; elite-prowess hires are stories too."""
    try:
        role = str(getattr(getattr(staff, "role", None), "value", ""))
        if not any(r in role for r in _ASSISTANT_ROLES):
            return None
        name = (f"{getattr(staff, 'first_name', '')} "
                f"{getattr(staff, 'last_name', '')}").strip()
        tname = getattr(team, "team_name", "the club") or "the club"
        spec = assistant_specialty(staff)
        if is_franchise_icon(staff, team):
            line = (f"{tname} bring {name} home behind the bench -- "
                    f"a franchise icon to run the {spec}. The room is buzzing.")
        elif assistant_prowess(staff) >= 80:
            line = (f"{tname} land highly-regarded {spec} coach {name or 'assistant'} "
                    f"behind the bench.")
        else:
            line = (f"{tname} add {name or 'a new assistant'} "
                    f"({spec}) to the coaching staff.")
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
            name = (f"{getattr(ac, 'first_name', '')} "
                    f"{getattr(ac, 'last_name', '')}").strip()
            spec = assistant_specialty(ac)
            eff = assistant_effect(ac)
            tag = " -- FRANCHISE ICON" if is_franchise_icon(ac, team) else ""
            lines.append(f"{name} ({spec}, effect {eff:.0f}){tag}")
    except Exception:
        pass
    return lines
