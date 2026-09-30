"""Last-change line matching: a live tactical lever, not a pregame checkbox.

The shift engine already honors home-team matchup prefs at stoppages
(shift_engine._matching_response reads Team.line_matchups, else auto). This
module adds the three things that make it a *decision* for the player:

  1. live control -- set_shadow() writes prefs mid-game; the next stoppage
     uses them,
  2. visible edge -- line_strength() + edge_label() say who's winning the
     current on-ice matchup and by how much,
  3. chance attribution -- record_chance()/record_goal() tag every dangerous
     chance and goal with the (home_line, away_line) pair on the ice, so the
     report shows WHERE chances came from.

All reads are defensive; without shift state the functions return None and
the UI hides the matchup elements.
"""

from typing import Any, Dict, List, Optional, Tuple

_F_POSITIONS = ("LW", "C", "RW")
_D_POSITIONS = ("L", "R")


def line_players(team: Any, unit: str = "F", num: int = 1) -> List[Any]:
    """Players on a numbered forward line (1-4) or D pair (1-3)."""
    try:
        lineup = getattr(team, "lineup", None) or {}
        if unit == "F":
            keys = [f"F{num}_{p}" for p in _F_POSITIONS]
        else:
            keys = [f"D{num}_{p}" for p in _D_POSITIONS]
        return [lineup[k] for k in keys if lineup.get(k) is not None]
    except Exception:
        return []


def line_strength(players: List[Any]) -> Optional[float]:
    """Mean overall rating. None when the line is unknown/empty."""
    try:
        vals = [float(p.overall_rating()) for p in players
                if hasattr(p, "overall_rating")]
        return sum(vals) / len(vals) if vals else None
    except Exception:
        return None


def edge_label(diff: Optional[float]) -> str:
    """diff = home strength - away strength (overall points)."""
    if diff is None:
        return "even"
    a = abs(diff)
    if a >= 5:
        return "strong edge" if diff > 0 else "strongly outmatched"
    if a >= 2:
        return "edge" if diff > 0 else "outmatched"
    return "even"


def _shift_lines(sim: Any) -> Optional[Tuple[int, int]]:
    """(home_f_line, away_f_line) currently on the ice."""
    try:
        from shift_engine import get_shift_state
        hs = get_shift_state(sim, getattr(sim, "home_team", None))
        aws = get_shift_state(sim, getattr(sim, "away_team", None))
        return (int(hs.f_line), int(aws.f_line))
    except Exception:
        return None


def current_matchup(sim: Any) -> Optional[Dict[str, Any]]:
    """Live on-ice matchup with the strength edge, home perspective."""
    try:
        lines = _shift_lines(sim)
        if not lines:
            return None
        hf, af = lines
        hs = line_strength(line_players(getattr(sim, "home_team", None), "F", hf))
        aws = line_strength(line_players(getattr(sim, "away_team", None), "F", af))
        diff = (hs - aws) if (hs is not None and aws is not None) else None
        return {"home_line": hf, "away_line": af,
                "home_strength": hs, "away_strength": aws,
                "diff": diff, "edge": edge_label(diff)}
    except Exception:
        return None


def _table(sim: Any) -> Dict[Tuple[int, int], Dict[str, int]]:
    t = getattr(sim, "_matchup_chances", None)
    if t is None:
        t = {}
        sim._matchup_chances = t
    return t


def _new_row() -> Dict[str, int]:
    return {"hd": 0, "hd_a": 0, "md": 0, "md_a": 0, "gf": 0, "ga": 0}


def record_chance(sim: Any, attacking_team: Any, danger: str) -> None:
    """Tag a dangerous chance with the on-ice line pair."""
    try:
        if danger not in ("high", "medium"):
            return
        lines = _shift_lines(sim)
        if not lines:
            return
        t = _table(sim)
        row = t.setdefault((lines[0], lines[1]), _new_row())
        home_att = attacking_team is getattr(sim, "home_team", None)
        col = "hd" if danger == "high" else "md"
        # stored home-perspective regardless of who attacked
        row[col if home_att else col + "_a"] += 1
    except Exception:
        pass


def record_goal(sim: Any, scoring_team: Any) -> None:
    try:
        lines = _shift_lines(sim)
        if not lines:
            return
        t = _table(sim)
        row = t.setdefault((lines[0], lines[1]), _new_row())
        if scoring_team is getattr(sim, "home_team", None):
            row["gf"] += 1
        else:
            row["ga"] += 1
    except Exception:
        pass


def _verdict(hf: int, af: int, row: Dict[str, int]) -> str:
    hdc = row.get("hd", 0) - row.get("hd_a", 0)
    gf = row.get("gf", 0) - row.get("ga", 0)
    if hdc >= 3 and gf >= 0:
        return f"your {hf} is owning their {af} ({row['hd']}-{row.get('hd_a', 0)} HD)"
    if hdc <= -3:
        return (f"their {af} is eating your {hf} alive "
                f"({row.get('hd_a', 0)}-{row['hd']} HD) -- change it")
    if gf >= 2:
        return f"your {hf} outscored their {af} {row['gf']}-{row['ga']}"
    if gf <= -2:
        return f"their {af} outscored your {hf} {row['ga']}-{row['gf']}"
    return ""


def report(sim: Any) -> List[Dict[str, Any]]:
    """Per-matchup table, home perspective, most-chances first."""
    out: List[Dict[str, Any]] = []
    try:
        t = _table(sim)
        for (hf, af), row in t.items():
            total = row.get("hd", 0) + row.get("hd_a", 0) + row.get("gf", 0) + row.get("ga", 0)
            if total == 0:
                continue
            out.append({"home_line": hf, "away_line": af,
                        "hd_for": row.get("hd", 0),
                        "hd_against": row.get("hd_a", 0),
                        "goals_for": row.get("gf", 0),
                        "goals_against": row.get("ga", 0),
                        "verdict": _verdict(hf, af, row)})
        out.sort(key=lambda r: -(r["hd_for"] + r["hd_against"]
                                 + r["goals_for"] + r["goals_against"]))
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------
# Live control: the user's lever.
# ----------------------------------------------------------------------

def set_shadow(team: Any, away_line: int, home_line: Optional[int],
               unit: str = "F") -> None:
    """'My `home_line` shadows their `away_line`.' None = coach's auto.

    Writes straight into Team.line_matchups; shift_engine picks it up at
    the next stoppage. No restart, no re-sim.
    """
    try:
        prefs = getattr(team, "line_matchups", None)
        if prefs is None:
            return
        key = "F" if unit == "F" else "D"
        n = 4 if unit == "F" else 3
        if not (1 <= away_line <= 4 and (home_line is None or 1 <= home_line <= n)):
            return
        # prefs are indexed by MY line: F[i] = opp line my line i+1 shadows.
        # Clear any other line currently shadowing the same away line, then
        # set the requested one (one shadow per away line).
        cur = list(prefs.get(key) or [None] * n)
        cur = (cur + [None] * n)[:n]
        for i in range(n):
            if cur[i] == away_line:
                cur[i] = None
        if home_line is not None:
            cur[home_line - 1] = away_line
        prefs[key] = cur
    except Exception:
        pass


def preset_shutdown(team: Any) -> None:
    """Checkers + top pair shadow their stars."""
    set_shadow(team, 1, 3, "F")
    set_shadow(team, 1, 1, "D")


def preset_shelter_scorers(team: Any) -> None:
    """Top line hunts their depth; everyone else on auto."""
    set_shadow(team, 4, 1, "F")


def preset_auto(team: Any) -> None:
    """Coach's automatic responses."""
    try:
        prefs = getattr(team, "line_matchups", None)
        if prefs is None:
            return
        prefs["F"] = [None, None, None, None]
        prefs["D"] = [None, None, None]
    except Exception:
        pass


def describe_prefs(team: Any) -> List[str]:
    """Human-readable current shadow assignments."""
    out: List[str] = []
    try:
        prefs = getattr(team, "line_matchups", None) or {}
        for i, want in enumerate(list(prefs.get("F") or [])[:4]):
            if want:
                out.append(f"your {i + 1} shadows their {want}")
        for i, want in enumerate(list(prefs.get("D") or [])[:3]):
            if want:
                out.append(f"your top-{i + 1} pair shadows their {want}")
    except Exception:
        pass
    return out
