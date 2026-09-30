# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Parity engine: competitive compression with cross-game team momentum.

The problem: raw talent/tactics multipliers compound over 82 games into
144-point super-teams and 18-point cellar-dwellers. The real NHL's spread
is roughly 55-125 points -- bad teams still win a third of their games.

The design (deliberately asymmetric):
  * FORM -- team momentum carried across games (-100..+100, mean-reverting
    x0.96 per game). Applies at most +/-4% to chance generation. This is
    the streak flavor: hot teams feel hot, cold teams feel cold.
  * CORRECTIVE FORCES -- stronger than form, applied on top, and they come
    from coaches and players, not a rubber band:
      - Coach adjustment: on a 4+ game winless skid the coach tightens up,
        shuffles lines, changes the goalie routine. Up to +6.4%, scaled by
        the coach's motivating/man-management quality. Coaches play in.
      - New-coach bounce: +5% decaying over 10 games after a hire (the
        carousel has a memory; the room responds to a new voice).
      - Player pride: veteran leaders (leadership 75+) refuse to lose --
        up to +2% on skids. Players play in.
      - Target on your back: non-top-8 teams get +2% against top-5 teams.
        Everyone brings their best against the champs.
      - Trap-game flatness: top-8 teams go -1.5% against bottom-8 teams,
        unless their coach is highly disciplined (70+). Complacency is
        a coaching failure.
  Net: a spiraling bad team facing a hot team gets roughly +10% against
  roughly +0.5%. The corrective layer dominates raw momentum, so streaks
  are felt but the table compresses toward the NHL band.

"One decision, two fidelities": GameSim and AdvancedGameSim both call
pregame_multiplier() (the same decision); each applies it through its own
channel (GameSim: xG factor on shot quality; AdvGS: shot_prob scaling).
record_result() is called once per game from each engine's run().

The engine keeps its own season table (W/L/OTL/points per team name) built
from record_result calls, so target-on-back works in every context --
season driver, playoffs, balance harness -- with zero extra wiring.
new_season() clears it; called from League.generate_schedule().

Kill switch: parity_engine.DISABLED = True (A/B testing, same pattern as
goalie_personality.DISABLED). Every public function never raises.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

DISABLED = False

# ---------------------------------------------------------------------------
# Tuning constants (all effects deliberately small and deterministic)
# ---------------------------------------------------------------------------
FORM_CAP = 100.0
FORM_DECAY = 0.96          # mean reversion per game
FORM_EFFECT = 0.04         # +/-4% max from pure momentum

WIN_FORM = 8.0             # regulation win
OT_WIN_FORM = 6.0          # OT/SO win counts less (coin-flippy)
OTL_FORM = 1.0             # salvaged point steadies the room
LOSS_FORM = -8.0
STREAK_FORM_STEP = 2.0     # extra per streak game beyond 2
STREAK_FORM_CAP = 6.0

SKID_TRIGGER = 4           # winless games before coach adjustment
COACH_ADJ_PER_GAME = 0.008 # up to +6.4% at 8 winless
COACH_ADJ_CAP_GAMES = 8

NEW_COACH_GAMES = 10       # bounce window
NEW_COACH_PEAK = 0.05      # +5% on day one, linear decay

LEADER_ATTR = 75           # leadership rating that counts as "veteran voice"
PRIDE_PER_LEADER = 0.005   # up to +2% with 4 leaders on a skid
PRIDE_SKID_TRIGGER = 3

TARGET_GAMES = 15          # table needs this many GP before tiers are real
TARGET_BOOST = 0.02        # +2% vs a top-5 team
TRAP_FLAT = 0.985          # -1.5% for top-8 vs bottom-8
TRAP_DISCIPLINE_CUT = 70   # demanding coaches suppress complacency

# Module-level season table: {team_name: {'gp','w','l','otl','points'}}.
# Built purely from record_result() calls -- no league object needed.
_records: Dict[str, Dict[str, int]] = {}


# ---------------------------------------------------------------------------
# Season lifecycle
# ---------------------------------------------------------------------------
def new_season() -> None:
    """Clear the season table. Called from League.generate_schedule()."""
    try:
        _records.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-team persistent state (lives on the team object, survives across games)
# ---------------------------------------------------------------------------
def _state(team: Any) -> Dict[str, Any]:
    try:
        st = getattr(team, "_parity_state", None)
        if not isinstance(st, dict):
            st = {}
            team._parity_state = st
        st.setdefault("form", 0.0)
        st.setdefault("streak", 0)        # signed: +N wins / -N losses
        st.setdefault("winless", 0)       # games since last win (OTL counts)
        st.setdefault("coach_key", None)
        st.setdefault("new_coach_games", 0)
        return st
    except Exception:
        return {"form": 0.0, "streak": 0, "winless": 0,
                "coach_key": None, "new_coach_games": 0}


def _coach_key(team: Any) -> Optional[str]:
    try:
        c = getattr(team, "head_coach", None)
        if c is None:
            return None
        return str(getattr(c, "id", None) or getattr(c, "name", None)
                   or getattr(c, "full_name", None) or id(c))
    except Exception:
        return None


def _coach_quality(team: Any) -> float:
    """0..1 from motivating + man_management (1-100 scale)."""
    try:
        c = getattr(team, "head_coach", None)
        if c is None:
            return 0.5
        mot = float(getattr(c, "motivating", 50) or 50)
        man = float(getattr(c, "man_management", 50) or 50)
        return max(0.0, min(1.0, (mot + man) / 200.0))
    except Exception:
        return 0.5


def _coach_discipline(team: Any) -> float:
    try:
        c = getattr(team, "head_coach", None)
        if c is None:
            return 50.0
        d = getattr(c, "discipline", None)
        if d is None:
            d = getattr(c, "level_of_discipline", 50)
        return float(d or 50)
    except Exception:
        return 50.0


def _count_leaders(team: Any) -> int:
    """Veteran voices: leadership 75+ on the roster."""
    try:
        n = 0
        for p in getattr(team, "roster", []) or []:
            try:
                if float(getattr(p, "leadership", 0) or 0) >= LEADER_ATTR:
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def _team_name(team: Any) -> str:
    try:
        return str(getattr(team, "team_name", "") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Post-game: record the result, move form, maintain the season table
# ---------------------------------------------------------------------------
def record_result(home: Any, away: Any, home_won: bool,
                  went_ot: bool = False) -> None:
    """Update form/streaks/records for both teams. Never raises.

    Called once per finished game from each engine's run(). OTL counts as
    "not a loss" for the room's psychology (the bleeding stopped) but does
    not reset the winless counter (the win still hasn't come).
    """
    if DISABLED:
        return
    try:
        hn, an = _team_name(home), _team_name(away)
        for t, name, won in ((home, hn, home_won), (away, an, not home_won)):
            st = _state(t)
            # Mean reversion first: memory fades.
            st["form"] = st["form"] * FORM_DECAY
            if won:
                step = WIN_FORM if not went_ot else OT_WIN_FORM
                if st["streak"] >= 2:
                    step += min(st["streak"] - 1, 3) * STREAK_FORM_STEP
                    step = min(step, WIN_FORM + STREAK_FORM_CAP)
                st["form"] += step
                st["streak"] = st["streak"] + 1 if st["streak"] > 0 else 1
                st["winless"] = 0
            elif went_ot:
                # OTL: a point salvaged. Streak of losses snaps, but the
                # winless run continues.
                st["form"] += OTL_FORM
                st["streak"] = 0
                st["winless"] += 1
            else:
                step = LOSS_FORM
                if st["streak"] <= -2:
                    step -= min(-st["streak"] - 1, 3) * STREAK_FORM_STEP
                    step = max(step, LOSS_FORM - STREAK_FORM_CAP)
                st["form"] += step
                st["streak"] = st["streak"] - 1 if st["streak"] < 0 else -1
                st["winless"] += 1
            st["form"] = max(-FORM_CAP, min(FORM_CAP, st["form"]))
            # New-coach bounce decays with games coached.
            if st["new_coach_games"] > 0:
                st["new_coach_games"] -= 1
            # Season table.
            rec = _records.get(name)
            if rec is None:
                rec = _records[name] = {"gp": 0, "w": 0, "l": 0,
                                        "otl": 0, "points": 0}
            rec["gp"] += 1
            if won:
                rec["w"] += 1
                rec["points"] += 2
            elif went_ot:
                rec["otl"] += 1
                rec["points"] += 1
            else:
                rec["l"] += 1
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Standings tiers (from the engine's own table)
# ---------------------------------------------------------------------------
def _points_pct(name: str) -> Optional[float]:
    rec = _records.get(name)
    if not rec or rec["gp"] < TARGET_GAMES:
        return None
    return rec["points"] / (2.0 * rec["gp"])


def _tier(name: str) -> Optional[str]:
    """'top5' / 'top8' / 'bottom8' / 'mid' / None (table too young)."""
    pct = _points_pct(name)
    if pct is None:
        return None
    ranked = sorted(
        ((n, r["points"] / (2.0 * r["gp"]))
         for n, r in _records.items() if r["gp"] >= TARGET_GAMES),
        key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return None
    order = [n for n, _ in ranked]
    try:
        idx = order.index(name)
    except ValueError:
        return None
    n = len(order)
    if idx < 5:
        return "top5"
    if idx < 8:
        return "top8"
    if idx >= n - 8:
        return "bottom8"
    return "mid"


# ---------------------------------------------------------------------------
# Pre-game: the single shared decision both engines call
# ---------------------------------------------------------------------------
def pregame_multiplier(team: Any, opponent: Any,
                       playoffs: bool = False) -> float:
    """Total parity multiplier for `team` against `opponent`. Never raises.

    Small, deterministic, and asymmetric by design: the corrective forces
    (coaches, players, target-on-back) outweigh raw form momentum, so
    streaks are felt but the standings compress.
    """
    if DISABLED:
        return 1.0
    try:
        st = _state(team)
        # New voice behind the bench? The room responds immediately.
        ck = _coach_key(team)
        if ck != st["coach_key"]:
            st["coach_key"] = ck
            if ck is not None:
                st["new_coach_games"] = NEW_COACH_GAMES

        mult = 1.0

        # 1. Form momentum: streaks carried across games. +/-4% max.
        mult *= 1.0 + (st["form"] / FORM_CAP) * FORM_EFFECT

        # 2. Coach adjustment on a skid: tighten up, shuffle lines, change
        #    the goalie routine. Better motivators get more out of it.
        if st["winless"] >= SKID_TRIGGER:
            q = _coach_quality(team)
            adj = (min(st["winless"], COACH_ADJ_CAP_GAMES)
                   * COACH_ADJ_PER_GAME * (0.6 + 0.8 * q))
            mult *= 1.0 + adj

        # 3. New-coach bounce: linear decay over the window.
        if st["new_coach_games"] > 0:
            mult *= 1.0 + NEW_COACH_PEAK * (st["new_coach_games"]
                                            / NEW_COACH_GAMES)

        # 4. Player pride: veteran leaders refuse to lose.
        if st["winless"] >= PRIDE_SKID_TRIGGER:
            leaders = _count_leaders(team)
            if leaders:
                pride = (min(leaders, 4) * PRIDE_PER_LEADER
                         * min(st["winless"], 6) / 6.0)
                mult *= 1.0 + pride

        # 5/6. Table-context forces need a mature table and a regular
        # season (playoff series are their own psychology).
        if not playoffs:
            my_tier = _tier(_team_name(team))
            opp_tier = _tier(_team_name(opponent))
            # Target on your back: everyone brings their best vs the elite.
            if opp_tier == "top5" and my_tier not in ("top5", "top8", None):
                mult *= 1.0 + TARGET_BOOST
            # Trap-game flatness -- unless the coach demands standards.
            if my_tier in ("top5", "top8") and opp_tier == "bottom8":
                if _coach_discipline(team) < TRAP_DISCIPLINE_CUT:
                    mult *= TRAP_FLAT

        # Sanity clamp: the parity layer never decides a game by itself.
        return max(0.90, min(1.12, mult))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Introspection (UI / debug / QA)
# ---------------------------------------------------------------------------
def form_state(team: Any) -> Dict[str, Any]:
    """Readable snapshot of a team's parity state. Never raises."""
    try:
        st = _state(team)
        name = _team_name(team)
        rec = _records.get(name, {"gp": 0, "w": 0, "l": 0,
                                  "otl": 0, "points": 0})
        return {
            "form": round(st["form"], 1),
            "streak": st["streak"],
            "winless": st["winless"],
            "new_coach_games": st["new_coach_games"],
            "tier": _tier(name),
            "record": dict(rec),
        }
    except Exception:
        return {}


def season_table() -> Dict[str, Dict[str, int]]:
    """Copy of the engine's own season table. Never raises."""
    try:
        return {k: dict(v) for k, v in _records.items()}
    except Exception:
        return {}
