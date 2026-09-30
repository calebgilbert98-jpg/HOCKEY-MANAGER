"""Goalie-pull / 6-on-5 decision logic (additive, no core-sim changes).

The pull decision already existed in simulation.py; this module owns the
*timing* personality:

- Coach styles: each head coach gets a stable pull style (aggressive /
  balanced / conservative) derived from their existing attributes plus a
  deterministic name hash -- no new data, no save-format changes. Styles
  move the pull windows, never the guards: never before 3:00 left, never
  down 3+, never shorthanded, never in OT, never tied or leading.
- Risk appetite: the momentum module's risk reading still shifts timing
  +-15s (a surging team pulls earlier); style and momentum stack.
- Timeouts: one per team per game. A trailing coach may burn it before a
  late offensive- or neutral-zone draw to rest the top unit and steal the
  faceoff, then send the goalie off for the draw. Aggressive coaches will
  do it from the neutral zone; everyone else wants the offensive zone.

Perf: everything here runs at stoppages (a few attribute reads per
faceoff) or once per tick for the on-the-fly check -- negligible.
"""

import hashlib
import random

_STYLES = {
    # down1/down2: pull windows in seconds remaining; nz_draw: pull for a
    # neutral-zone draw after a timeout; timeout_eager: probability of
    # burning the timeout when the spot is right.
    "aggressive": {"down1": 150, "down2": 75, "nz_draw": True,
                   "timeout_eager": 0.85},
    "balanced": {"down1": 120, "down2": 60, "nz_draw": False,
                 "timeout_eager": 0.55},
    "conservative": {"down1": 90, "down2": 45, "nz_draw": False,
                     "timeout_eager": 0.30},
}

_STYLE_ORDER = ["conservative", "balanced", "aggressive"]


def _attrs(coach, *names):
    vals = []
    for n in names:
        try:
            vals.append(float(getattr(coach, n, 50) or 50))
        except Exception:
            vals.append(50.0)
    return sum(vals) / max(1, len(vals))


def pull_style(coach):
    """Stable per-coach pull style. Never raises; None -> balanced."""
    if coach is None:
        return dict(style="balanced", **_STYLES["balanced"])
    try:
        name = f"{getattr(coach, 'first_name', '')} " \
               f"{getattr(coach, 'last_name', '')}"
        seed = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
        base = _STYLE_ORDER[seed % 3]
        # Attribute nudge: motivators/gamblers pull early, disciplinarians
        # and defense-first coaches wait.
        agg = _attrs(coach, "motivating", "adaptability")
        con = _attrs(coach, "level_of_discipline", "defensive_coaching")
        score = (agg - con) / 100.0
        idx = _STYLE_ORDER.index(base)
        if score > 0.25:
            idx += 1
        elif score < -0.25:
            idx -= 1
        idx = max(0, min(2, idx))
        style = _STYLE_ORDER[idx]
        return dict(style=style, **_STYLES[style])
    except Exception:
        return dict(style="balanced", **_STYLES["balanced"])


def coach_for(sim, team):
    """Head-coach staff object for a team (may be None)."""
    try:
        if team is getattr(sim, "home_team", None):
            return getattr(sim, "_home_coach", None)
        return getattr(sim, "_away_coach", None)
    except Exception:
        return None


def pull_windows(sim, team):
    """(down1_secs, down2_secs, style): when this coach pulls, trailing.

    Momentum risk appetite shifts the style window +-15s. Hard rationality
    clamps: never earlier than 3:00 left, never later than 0:30/0:20.
    """
    style = pull_style(coach_for(sim, team))
    try:
        from momentum import risk_appetite as _risk
        extra = int(round(60.0 * (_risk(sim, team) - 1.0)))
        extra = max(-15, min(15, extra))
    except Exception:
        extra = 0
    d1 = max(30, min(180, style["down1"] + extra))
    d2 = max(20, min(90, style["down2"] + extra))
    return d1, d2, style


# ---------------------------------------------------------------------------
# Timeouts: one per team per game, spent setting up the 6-on-5
# ---------------------------------------------------------------------------

def timeout_available(sim, team):
    try:
        return team.team_name not in getattr(sim, "_timeouts_used", set())
    except Exception:
        return False


def use_timeout(sim, team, reason):
    """Burn the team's timeout. Rests the draw unit, boosts the next
    faceoff, and marks the team to pull for the ensuing draw."""
    try:
        used = sim.__dict__.setdefault("_timeouts_used", set())
        if team.team_name in used:
            return False
        used.add(team.team_name)
        # Rest the skaters about to take the draw.
        try:
            from game_classes import PlayerPosition as _PP
            _goalie = _PP.GOALIE
        except Exception:
            _goalie = None
        try:
            try:
                from condition_system import (
                    TIMEOUT_RECOVERY as _W3_TR,
                    fatigue_recovery_mult as _w3_rec,
                    sync_game_energy as _w3_sync,
                )
            except Exception:
                _W3_TR, _w3_rec, _w3_sync = 8.0, None, None
            for p in sim._get_on_ice(team):
                if _goalie is not None and \
                        getattr(p, "primary_position", None) == _goalie:
                    continue
                pf = getattr(sim, "player_fatigue", None)
                if pf is not None:
                    # W3: timeout breather scales with the stamina blend --
                    # high-stamina players get more out of the rest.
                    _rec = _W3_TR * (_w3_rec(p) if _w3_rec else 1.0)
                    _new = min(100.0, float(pf.get(p.id, 80)) + _rec)
                    pf[p.id] = _new
                    if _w3_sync is not None:
                        try:
                            _w3_sync(p, _new)
                        except Exception:
                            pass
        except Exception:
            pass
        sim.__dict__.setdefault("_timeout_faceoff_boost", {})[team.team_name] = True
        sim.__dict__.setdefault("_timeout_pending_pull", set()).add(team.team_name)
        try:
            sim._log_event(
                f"{team.team_name} use their timeout -- {reason}.", "TIMEOUT")
            sim._emit_pbp("timeout", team=team.team_name, reason=reason,
                          home_score=getattr(sim, "home_score", 0),
                          away_score=getattr(sim, "away_score", 0))
        except Exception:
            pass
        return True
    except Exception:
        return False


def timeout_faceoff_boost(sim, team):
    """One-shot faceoff bonus from a fresh timeout (+8 skill, consumed)."""
    try:
        d = getattr(sim, "_timeout_faceoff_boost", None) or {}
        if d.pop(team.team_name, None):
            return 8.0
    except Exception:
        pass
    return 0.0


def timeout_pending_pull(sim, team):
    """Did this team just burn its timeout to set up the 6-on-5 draw?"""
    try:
        s = getattr(sim, "_timeout_pending_pull", None) or set()
        if team.team_name in s:
            s.discard(team.team_name)
            return True
    except Exception:
        pass
    return False


def maybe_timeout_before_draw(sim, team, fx):
    """Trailing coach's decision at a late stoppage: burn the timeout to
    rest the top unit and steal the draw, then pull for it.

    Only inside the last 2:00, only down 1-2, only for an offensive-zone
    draw (aggressive coaches accept the neutral zone too). The eagerness
    roll is the coach's personality; the spot is the game state.
    """
    try:
        if getattr(sim, "period", 1) != 3:
            return False
        home = team is getattr(sim, "home_team", None)
        diff = ((getattr(sim, "home_score", 0) - getattr(sim, "away_score", 0))
                if home else
                (getattr(sim, "away_score", 0) - getattr(sim, "home_score", 0)))
        deficit = -diff
        if deficit not in (1, 2):
            return False
        if getattr(sim, "clock", 999) > 120:
            return False
        if not timeout_available(sim, team):
            return False
        adir = 1 if home else -1
        in_oz = (adir == 1 and fx > 125) or (adir == -1 and fx < 75)
        in_nz = 75 <= fx <= 125
        style = pull_style(coach_for(sim, team))
        if in_oz:
            spot = "the offensive-zone draw"
        elif in_nz and style["nz_draw"]:
            spot = "the neutral-zone draw"
        else:
            return False
        if random.random() > style["timeout_eager"]:
            return False
        reason = (f"down {deficit}, {int(getattr(sim, 'clock', 0))}s left -- "
                  f"rest the top unit for {spot} and pull for the 6-on-5")
        return use_timeout(sim, team, reason)
    except Exception:
        return False
