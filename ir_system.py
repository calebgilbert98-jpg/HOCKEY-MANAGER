#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""ir_system.py -- Injured Reserve (IR) and Long-Term Injured Reserve (LTIR).

Real NHL rules, EHM-style presentation (Muck 2026-10-02):

IR (Injured Reserve):
  - Player must be injured (is_injured with games remaining).
  - Does NOT count against the 23-man active roster limit
    (see roster_limits.active_roster_count).
  - STILL counts against the salary cap (stays on team.roster, so
    salary_cap_system.roster_cap_charge includes him).
  - Minimum 7 days on IR before eligible to return.

LTIR (Long-Term Injured Reserve):
  - Eligibility: expected to miss >= 10 NHL games (injury_data tables
    seed man-games-lost; the games_remaining_injured counter is the
    source of truth).
  - Cap relief: the team may exceed the salary cap by up to the sum of
    its LTIR players' cap hits (simplified NHL pool -- the real formula
    keys off cap space at placement; the simplified pool preserves the
    key dynamic: losing a star doesn't end your season, but you must
    bank room to activate him).
  - Player still counts against the 50-contract limit (never leaves
    the organization lists).
  - Activation: the team must be compliant under cap + remaining pool
    after the player's relief is removed -- i.e. they need his cap hit
    of breathing room, or they must shed salary first.

All functions never raise. Old saves degrade: ir_status defaults to
"None" via getattr.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

# Minimum days on IR before eligible to return (NHL rule).
IR_MIN_DAYS = 7
# Minimum games remaining for LTIR eligibility (NHL: 10 games + 24 days;
# the engine tracks games, so games is the gate).
LTIR_MIN_GAMES = 10
# Days on LTIR before the player must decide: attempt comeback or retire.
# (Muck 2026-10-02: the Shea Weber / Carey Price moment.)
LTIR_DECISION_DAYS = 1095  # 3 years


def ir_status_of(player: Any) -> str:
    """Player's IR status: 'None' | 'IR' | 'LTIR'. Old-save safe."""
    try:
        return str(getattr(player, "ir_status", "None") or "None")
    except Exception:
        return "None"


def is_on_ir(player: Any) -> bool:
    return ir_status_of(player) == "IR"


def is_on_ltir(player: Any) -> bool:
    return ir_status_of(player) == "LTIR"


def is_on_any_ir(player: Any) -> bool:
    return ir_status_of(player) in ("IR", "LTIR")


def days_on_ir(player: Any, current_date: Any) -> int:
    """Calendar days since placement. 0 when never placed / unparseable."""
    try:
        raw = getattr(player, "ir_placed_date", "") or ""
        if not raw:
            return 0
        placed = date.fromisoformat(str(raw)[:10])
        today = current_date if hasattr(current_date, "year") else date.today()
        return max(0, (today - placed).days)
    except Exception:
        return 0


def eligible_for_ir(player: Any) -> Tuple[bool, str]:
    """Can this player go on IR? (injured, not already stashed)."""
    try:
        if is_on_any_ir(player):
            return False, "Already on IR/LTIR."
        if not bool(getattr(player, "is_injured", False)):
            return False, "Player is not injured."
        remaining = int(getattr(player, "games_remaining_injured", 0) or 0)
        if remaining <= 0:
            return False, "No games remaining on the injury."
        return True, ""
    except Exception:
        return False, "Could not evaluate eligibility."


def eligible_for_ltir(player: Any) -> Tuple[bool, str]:
    """Can this player go on LTIR? (injured, >= LTIR_MIN_GAMES remaining)."""
    try:
        ok, reason = eligible_for_ir(player)
        if not ok:
            return False, reason
        remaining = int(getattr(player, "games_remaining_injured", 0) or 0)
        if remaining < LTIR_MIN_GAMES:
            return False, (
                f"Needs {LTIR_MIN_GAMES}+ games remaining "
                f"(has {remaining}).")
        return True, ""
    except Exception:
        return False, "Could not evaluate eligibility."


def _player_cap_hit(player: Any) -> int:
    try:
        import salary_cap_system as _scs
        return int(_scs._active_roster_hit(player) or 0)
    except Exception:
        try:
            c = getattr(player, "contract", None)
            return int(getattr(c, "salary", 0) or 0)
        except Exception:
            return 0


def _today_iso(current_date: Any) -> str:
    try:
        if hasattr(current_date, "isoformat"):
            return current_date.isoformat()[:10]
        return date.today().isoformat()
    except Exception:
        return ""


def place_on_ir(team: Any, player: Any, current_date: Any = None) -> Tuple[bool, str]:
    """Place an injured player on IR. Never raises."""
    try:
        ok, reason = eligible_for_ir(player)
        if not ok:
            return False, reason
        # Must be on the NHL roster to go on NHL IR.
        roster = getattr(team, "roster", None) or []
        if player not in roster:
            return False, "Player is not on the NHL roster."
        player.ir_status = "IR"
        player.ir_placed_date = _today_iso(current_date)
        return True, ""
    except Exception:
        return False, "Could not place on IR."


def place_on_ltir(team: Any, player: Any, current_date: Any = None) -> Tuple[bool, str]:
    """Place an injured player on LTIR. Never raises."""
    try:
        ok, reason = eligible_for_ltir(player)
        if not ok:
            return False, reason
        roster = getattr(team, "roster", None) or []
        if player not in roster:
            return False, "Player is not on the NHL roster."
        player.ir_status = "LTIR"
        player.ir_placed_date = _today_iso(current_date)
        return True, ""
    except Exception:
        return False, "Could not place on LTIR."


def ltir_players(team: Any) -> List[Any]:
    """All players on LTIR (for the relief pool). Never raises."""
    try:
        return [p for p in (getattr(team, "roster", None) or [])
                if is_on_ltir(p)]
    except Exception:
        return []


def ir_players(team: Any) -> List[Any]:
    """All players on regular IR. Never raises."""
    try:
        return [p for p in (getattr(team, "roster", None) or [])
                if is_on_ir(p)]
    except Exception:
        return []


def ltir_relief(team: Any) -> int:
    """Cap relief pool: sum of LTIR players' cap hits. Never raises."""
    try:
        return sum(_player_cap_hit(p) for p in ltir_players(team))
    except Exception:
        return 0


def effective_cap_ceiling(team: Any) -> int:
    """Salary cap + LTIR relief pool. Never raises."""
    try:
        import salary_cap_system as _scs
        cap = int(getattr(team, "salary_cap", _scs.DEFAULT_CAP)
                  or _scs.DEFAULT_CAP)
    except Exception:
        cap = 88_000_000
    try:
        return cap + ltir_relief(team)
    except Exception:
        return cap


def is_compliant_with_ltir(team: Any) -> bool:
    """True when total cap charge fits under cap + LTIR relief."""
    try:
        import salary_cap_system as _scs
        return int(_scs.compliance_charge(team) or 0) <= effective_cap_ceiling(team)
    except Exception:
        return True


def can_activate_from_ltir(team: Any, player: Any) -> Tuple[bool, str]:
    """Check whether activating this LTIR player keeps the team compliant.

    Activation removes the player's relief from the pool, so the team
    needs his cap hit of breathing room under the effective ceiling.
    """
    try:
        if not is_on_ltir(player):
            return False, "Player is not on LTIR."
        import salary_cap_system as _scs
        hit = _player_cap_hit(player)
        pool_after = max(0, ltir_relief(team) - hit)
        try:
            cap = int(getattr(team, "salary_cap", _scs.DEFAULT_CAP)
                      or _scs.DEFAULT_CAP)
        except Exception:
            cap = 88_000_000
        charge = int(_scs.compliance_charge(team) or 0)
        if charge <= cap + pool_after:
            return True, ""
        short = charge - (cap + pool_after)
        return False, (
            f"Need ${short:,} in cap room to activate "
            f"{getattr(player, 'full_name', 'player')} from LTIR.")
    except Exception:
        return False, "Could not evaluate cap compliance."


def can_activate_from_ir(player: Any, current_date: Any) -> Tuple[bool, str]:
    """IR activation: 7-day minimum + healed."""
    try:
        if not is_on_ir(player):
            return False, "Player is not on IR."
        if bool(getattr(player, "is_injured", False)):
            remaining = int(getattr(player, "games_remaining_injured", 0) or 0)
            return False, f"Still injured ({remaining} games remaining)."
        days = days_on_ir(player, current_date)
        if days < IR_MIN_DAYS:
            return False, (
                f"Must spend {IR_MIN_DAYS} days on IR "
                f"({IR_MIN_DAYS - days} remaining).")
        return True, ""
    except Exception:
        return False, "Could not evaluate activation."


def activate_player(team: Any, player: Any,
                    current_date: Any = None) -> Tuple[bool, str]:
    """Activate a player off IR/LTIR. LTIR checks cap compliance. Never raises."""
    try:
        status = ir_status_of(player)
        if status == "IR":
            ok, reason = can_activate_from_ir(player, current_date)
            if not ok:
                return False, reason
        elif status == "LTIR":
            # Healed check first.
            if bool(getattr(player, "is_injured", False)):
                remaining = int(getattr(player, "games_remaining_injured", 0) or 0)
                return False, f"Still injured ({remaining} games remaining)."
            ok, reason = can_activate_from_ltir(team, player)
            if not ok:
                return False, reason
        else:
            return False, "Player is not on IR/LTIR."
        player.ir_status = "None"
        player.ir_placed_date = ""
        return True, ""
    except Exception:
        return False, "Could not activate player."


def ai_manage_ir(team: Any, current_date: Any = None) -> Dict[str, int]:
    """AI GM IR/LTIR management. Never raises.

    - Long-term injuries (>= LTIR_MIN_GAMES) -> LTIR automatically.
    - Shorter injuries (>= 3 games) -> IR automatically.
    - Healed players on IR past the 7-day minimum -> activate.
    - Healed players on LTIR -> activate when cap-compliant.
    Returns counts of actions taken.
    """
    done = {"ltir_placed": 0, "ir_placed": 0, "activated": 0, "ltir_decisions": 0}
    try:
        roster = list(getattr(team, "roster", None) or [])
    except Exception:
        return done
    for p in roster:
        try:
            status = ir_status_of(p)
            # 3-year LTIR decision: comeback or retire (AI decides by age)
            if status == "LTIR" and needs_ltir_decision(p, current_date):
                try:
                    _age = int(getattr(p, "age", 35) or 35)
                    # Young players try to come back; veterans retire with dignity
                    _comeback = _age < 34
                    ok, _ = resolve_ltir_decision(team, p, _comeback, current_date)
                    if ok:
                        done["ltir_decisions"] += 1
                except Exception:
                    pass
                continue
            if status == "None" and bool(getattr(p, "is_injured", False)):
                remaining = int(getattr(p, "games_remaining_injured", 0) or 0)
                if remaining >= LTIR_MIN_GAMES:
                    ok, _ = place_on_ltir(team, p, current_date)
                    if ok:
                        done["ltir_placed"] += 1
                elif remaining >= 3:
                    ok, _ = place_on_ir(team, p, current_date)
                    if ok:
                        done["ir_placed"] += 1
            elif status in ("IR", "LTIR") and not bool(getattr(p, "is_injured", False)):
                ok, _ = activate_player(team, p, current_date)
                if ok:
                    done["activated"] += 1
        except Exception:
            continue
    return done


def needs_ltir_decision(player: Any, current_date: Any = None) -> bool:
    """Has this player been on LTIR long enough to face the decision?

    3+ years on LTIR: attempt a comeback or retire. The Shea Weber moment.
    Never raises.
    """
    try:
        if ir_status_of(player) != "LTIR":
            return False
        # Don't re-trigger if already decided
        if bool(getattr(player, "_ltir_decision_made", False)):
            return False
        return days_on_ir(player, current_date) >= LTIR_DECISION_DAYS
    except Exception:
        return False


def resolve_ltir_decision(team: Any, player: Any, attempt_comeback: bool,
                          current_date: Any = None) -> Tuple[bool, str]:
    """Resolve the 3-year LTIR decision. Never raises.

    attempt_comeback=True: player tries to return. Attributes decline from
    the long layoff (age + rust), injury risk elevated. May still fail
    physically and be forced to retire.
    attempt_comeback=False: player retires with dignity. Media story,
    fan farewell, Hall of Fame consideration begins.
    """
    try:
        pname = getattr(player, "full_name", getattr(player, "last_name", "The player"))
        player._ltir_decision_made = True

        if not attempt_comeback:
            # Retire with dignity
            try:
                player.is_retired = True
                player.ir_status = "None"
                player.ir_placed_date = ""
            except Exception:
                pass
            # Media story: the farewell
            try:
                from headlines import deliver_spec as _deliver
                # Find app via team -> league -> game_manager -> app chain
                _app = None
                try:
                    _lg = getattr(team, "league", None)
                    _gm = getattr(_lg, "game_manager", None) if _lg else None
                    _app = getattr(_gm, "app", None) if _gm else None
                except Exception:
                    pass
                if _app is not None:
                    _deliver(_app, {
                        "kind": "retirement",
                        "player": pname,
                        "team": getattr(team, "team_name", ""),
                        "text": f"After three years on long-term injured reserve, {pname} has announced his retirement.",
                    })
            except Exception:
                pass
            return True, f"{pname} retires after 3 years on LTIR."

        # Attempt comeback: the hard road
        try:
            # Rust: attributes decline from the layoff
            import random
            _rust = random.uniform(0.85, 0.95)  # 5-15% decline
            for attr in ("overall", "skating", "shooting", "passing",
                         "defense", "physical"):
                try:
                    _v = getattr(player, attr, None)
                    if isinstance(_v, (int, float)) and _v > 0:
                        setattr(player, attr, max(1, int(_v * _rust)))
                except Exception:
                    continue
            # Elevated re-injury risk
            try:
                player.injury_prone = min(99, int(getattr(player, "injury_prone", 50) or 50) + 20)
            except Exception:
                pass
            # Back to IR (not LTIR) for the comeback attempt — shorter leash
            player.ir_status = "IR"
            player.ir_placed_date = _today_iso(current_date)
            # Clear the injury so they can attempt to play
            player.is_injured = False
            player.games_remaining_injured = 0
        except Exception:
            pass
        return True, f"{pname} attempts a comeback after 3 years on LTIR."
    except Exception:
        return False, "Decision failed."


def ir_summary_line(team: Any) -> str:
    """One-line IR/LTIR summary for UI. Never raises."""
    try:
        n_ir = len(ir_players(team))
        n_ltir = len(ltir_players(team))
        if not n_ir and not n_ltir:
            return ""
        parts = []
        if n_ir:
            parts.append(f"IR: {n_ir}")
        if n_ltir:
            relief = ltir_relief(team)
            parts.append(f"LTIR: {n_ltir} (relief ${relief:,})")
        return " | ".join(parts)
    except Exception:
        return ""
