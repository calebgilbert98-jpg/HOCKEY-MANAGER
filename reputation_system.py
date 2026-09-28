# reputation_system.py
# Player & personnel reputation system for Puck Dynasty.
#
# Two independent axes, FM/EHM-style:
#
#   reputation (0-100)  -- career standing / legacy. A RATCHET: it only ever
#       goes up or stays flat. Veterans never lose it. High leadership feeds
#       it directly, so a near-retirement Joe Thornton-type carries a big
#       reputation as a veteran leader even when his on-ice value has faded.
#       Reputation is about *standing*, not trade value.
#
#   controversy (0-100) -- volatility / character risk. Explosive outbursts,
#       visibly not caring, locker-room behaviour, off-ice incidents. High
#       controversy discounts trade value, hurts locker-room chemistry and
#       draws media heat. Unlike reputation it CAN decay: a clean season
#       cools things down toward the player's personality baseline.
#
# The module is headless-safe (no tkinter) so the sim engine can call it.

import random
import re
from datetime import date
from typing import List, Dict, Optional, Any, Tuple

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

VETERAN_AGE = 32            # age at which leadership weighs heaviest
REPUTATION_MAX = 100
CONTROVERSY_MAX = 100

# How much each controversy event type moves the needle (x severity 1-10)
CONTROVERSY_WEIGHTS = {
    "outburst": 2.2,       # explosive outburst at coach / refs / media
    "effort": 1.8,         # visibly not caring, low compete level
    "locker_room": 2.5,    # locker-room behaviour incident
    "off_ice": 2.0,        # off-ice incident
    "holdout": 1.5,        # contract holdout / trade-demand drama
    "suspension": 1.2,      # league suspension (feeds from discipline)
}

# Clean-season cooldown: controversy drifts back toward baseline by this much
CONTROVERSY_DECAY_PER_CLEAN_SEASON = 4

# Reputation tier labels for UI
REPUTATION_TIERS = [
    (90, "Legend"),
    (75, "Star"),
    (60, "Established"),
    (40, "Regular"),
    (20, "Fringe"),
    (0, "Unknown"),
]

CONTROVERSY_TIERS = [
    (75, "Volatile"),
    (50, "Fiery"),
    (25, "Occasional edge"),
    (0, "Model citizen"),
]


# ---------------------------------------------------------------------------
# Field management (save compatibility)
# ---------------------------------------------------------------------------

def ensure_reputation_fields(entity: Any) -> None:
    """Backfill reputation fields on entities loaded from old saves.

    Old pickles predate these fields; without this, attribute access
    raises AttributeError and crashes the load. Safe to call on every load.
    """
    if not hasattr(entity, "reputation"):
        entity.reputation = 0
    if not hasattr(entity, "controversy"):
        entity.controversy = 0
    # Locked identity: dealt once, never re-dealt. No recursion --
    # _deal_base_controversy never calls ensure_reputation_fields.
    if getattr(entity, "base_controversy", None) is None:
        try:
            _deal_base_controversy(entity)
        except Exception:
            entity.base_controversy = 15
    # Coach influence: set at hire (floor 65, icons higher), then earned/burned.
    if _is_staff_entity(entity) and getattr(entity, "influence", None) is None:
        try:
            entity.influence = coach_influence_at_hire(
                accolades=getattr(entity, "career_reputation", 0) or 0)
        except Exception:
            entity.influence = 65
    if not hasattr(entity, "controversy_history"):
        entity.controversy_history = []
    if not hasattr(entity, "reputation_history"):
        entity.reputation_history = []
    # Staff-only: leadership (1-20 EHM scale) and team tenure feed the
    # room-status model. Seeded here for old saves; new Staff get real
    # dataclass defaults (see the game_classes patch).
    if hasattr(entity, "role") and not hasattr(entity, "primary_position"):
        if not hasattr(entity, "leadership"):
            entity.leadership = random.randint(8, 18)
        if not hasattr(entity, "years_with_team"):
            entity.years_with_team = random.randint(0, 4)
        if not hasattr(entity, "gm_trust"):
            entity.gm_trust = 70
        if not hasattr(entity, "ambition"):
            entity.ambition = "climb"
        if not hasattr(entity, "favorite_team"):
            entity.favorite_team = ""
        if not hasattr(entity, "control_need"):
            entity.control_need = 50
        if not hasattr(entity, "first_nhl_chair"):
            entity.first_nhl_chair = False
    # League-level bad blood (rivalries follow people across teams).
    if hasattr(entity, "teams") and hasattr(entity, "standings") and not hasattr(entity, "roster"):
        if not hasattr(entity, "rivalries") or entity.rivalries is None:
            entity.rivalries = []
    # Team-level dynamics state (survives saves once the dataclass lands).
    if hasattr(entity, "roster") and hasattr(entity, "staff"):
        if not hasattr(entity, "dynamics_log") or entity.dynamics_log is None:
            entity.dynamics_log = []
        if not hasattr(entity, "line_control") or entity.line_control is None:
            entity.line_control = "coach"
        if not hasattr(entity, "prev_roster_names") or entity.prev_roster_names is None:
            entity.prev_roster_names = []
        if not hasattr(entity, "roster_churn") or entity.roster_churn is None:
            entity.roster_churn = 0.2
    # Prospect-development fields (prospect_development.py). Old saves predate
    # them; hidden truth defaults to the displayed belief (no phantom gems in
    # old saves -- they must earn it through production).
    if hasattr(entity, "primary_position") and not hasattr(entity, "role"):
        if not getattr(entity, "true_potential_grade", ""):
            entity.true_potential_grade = getattr(entity, "potential_grade", "C") or "C"
        if not hasattr(entity, "farm_league"):
            entity.farm_league = ""
        if not hasattr(entity, "farm_season") or entity.farm_season is None:
            entity.farm_season = {}
        if not hasattr(entity, "farm_history") or entity.farm_history is None:
            entity.farm_history = []
        if not hasattr(entity, "draft_round"):
            entity.draft_round = 0
        # Pedigree floor for old saves: young players get a mild cushion
        # (3 steps below truth); veterans don't need one (evaluation stops
        # at 27 anyway).
        if not getattr(entity, "pedigree_floor", ""):
            try:
                import prospect_development as _pd
                _lad = _pd._ladder()
                _ti = _pd._ladder_index(
                    getattr(entity, "true_potential_grade", "") or
                    getattr(entity, "potential_grade", "C") or "C")
                if (getattr(entity, "age", 99) or 99) < 27:
                    entity.pedigree_floor = _lad[max(0, _ti - 3)]
                else:
                    entity.pedigree_floor = ""
            except Exception:
                entity.pedigree_floor = ""


def seed_player_reputation(player: Any) -> int:
    """Initial reputation from draft pedigree. Called at generation time."""
    ensure_reputation_fields(player)
    base = 5
    try:
        # Early picks arrive with hype; parse "Round X, Pick Y"
        import re
        m = re.search(r"Round\s+(\d+)", getattr(player, "draft_position", "") or "")
        if m:
            rnd = int(m.group(1))
            base += max(0, 18 - rnd * 2)   # 1st round ~+16, 7th round ~+4
    except Exception:
        pass
    # High-leadership prospects already look like future captains
    try:
        base += int(getattr(player, "leadership", 50) / 25)  # +0..+4
    except Exception:
        pass
    player.reputation = max(0, min(REPUTATION_MAX, base))
    return player.reputation


def seed_staff_reputation(staff: Any) -> int:
    """Seed a 0-100 career reputation from staff reputation.

    Handles both legacy 5-15 saves (mapped 5-15 -> 20-70) and post-rescale
    native 1-100 values (clamped)."""
    ensure_reputation_fields(staff)
    legacy = getattr(staff, "reputation", 50) or 50  # legacy 5-15 scale
    if legacy <= 20:
        # Map 5-15 -> 20-70 so existing staff land mid-range, room to grow
        mapped = int(20 + (max(5, min(15, legacy)) - 5) * 5)
    else:
        mapped = max(1, min(100, int(legacy)))
    staff.career_reputation = mapped
    return mapped


# ---------------------------------------------------------------------------
# Reputation updates (RATCHET: never decreases)
# ---------------------------------------------------------------------------

def update_player_reputation(
    player: Any,
    season_points: int = 0,
    games_played: int = 0,
    league_avg_ppg: float = 0.8,
    awards: Optional[List[str]] = None,
    playoff_rounds_won: int = 0,
) -> int:
    """Recompute reputation from this season's body of work.

    The result is ratcheted: ``player.reputation = max(old, new)``.
    Veterans never regress -- a 38-year-old Joe Thornton keeps every bit
    of standing he earned, even in a 20-point season.

    Leadership is a first-class input, weighted heavier for veterans:
    great leaders are remembered as leaders, independent of scoring.

    Captaincy bonus scales with leadership: a 'C' who can't lead the room
    doesn't bank the same standing as a true captain.
    """
    ensure_reputation_fields(player)
    awards = awards or []

    target = 0

    # -- Performance vs league -------------------------------------------
    if games_played > 0:
        ppg = season_points / games_played
        # 1.5x league average pace over a full season ~= star-level year
        perf = (ppg / max(0.01, league_avg_ppg)) * 45
        target += max(0, min(45, perf))

    # -- Awards ------------------------------------------------------------
    award_values = {
        "hart": 12, "norris": 10, "vezina": 10, "art_ross": 10,
        "selke": 6, "calder": 6, "conn_smythe": 12, "stanley_cup": 10,
    }
    for a in awards:
        target += award_values.get(str(a).lower(), 3)

    # -- Playoff success -----------------------------------------------------
    target += min(15, playoff_rounds_won * 4)

    # -- Leadership (the Thornton rule) --------------------------------------
    leadership = getattr(player, "leadership", 50) or 0
    age = getattr(player, "age", 25) or 25
    # Veterans: leadership is worth up to +25. Young players: up to +10.
    # Great leaders bank reputation that outlives their legs.
    if age >= VETERAN_AGE:
        target += (leadership / 100) * 25
    else:
        target += (leadership / 100) * 10

    # -- Captaincy (scaled by leadership) --------------------------------------
    # A figurehead captain banks less than a true leader of men.
    captaincy = getattr(player, "captaincy", None)
    if captaincy == "C":
        target += round(8 * (0.3 + 0.7 * leadership / 100))
    elif captaincy == "A":
        target += round(4 * (0.3 + 0.7 * leadership / 100))

    target = max(0, min(REPUTATION_MAX, int(target)))

    # RATCHET: reputation never goes down.
    if target > player.reputation:
        player.reputation = target
        player.reputation_history.append({
            "date": date.today().isoformat(),
            "reputation": player.reputation,
            "reason": "season_update",
        })
    return player.reputation


def update_staff_reputation(staff: Any, team_win_pct: float = 0.5,
                            championships: int = 0,
                            jack_adams: bool = False) -> int:
    """Move a staff member's 0-100 career_reputation for the season.

    A .500 season holds steady; winning builds slowly, losing erodes
    (coaches, unlike players, CAN lose standing -- that's the hot seat).
    Championships bank +12; a Jack Adams banks +8 (coach of the year is
    the strongest single-season signal after a Cup). Clamped to 0-100.
    """
    ensure_reputation_fields(staff)
    try:
        current = getattr(staff, "career_reputation", 0) or 0
        # Win% swing capped at +/-5 per season; Cups are the big movers.
        swing = max(-5, min(5, int((team_win_pct - 0.5) * 10)))
        target = max(0, min(100, current + swing + championships * 12
                            + (8 if jack_adams else 0)))
        if target != current:
            staff.career_reputation = target
            staff.reputation_history.append({
                "date": date.today().isoformat(),
                "reputation": staff.career_reputation,
                "reason": "season_update",
            })
        return staff.career_reputation
    except Exception:
        return getattr(staff, "career_reputation", 0) or 0


# ---------------------------------------------------------------------------
# Controversy
# ---------------------------------------------------------------------------

def controversy_baseline(entity: Any) -> int:
    """Personality baseline controversy drifts back toward.

    The locked base_controversy IS the baseline. Only entities that were
    never dealt a personality fall back to the discipline/teamwork read.
    """
    try:
        locked = getattr(entity, "base_controversy", None)
        if isinstance(locked, int) and locked >= 0:
            return locked
        discipline = getattr(entity, "discipline", 60) or 60
        teamwork = getattr(entity, "teamwork", 60) or 60
        # discipline 1..100 -> baseline 30..0 ; bad teammates add a little
        base = int((100 - discipline) * 0.3 + (100 - teamwork) * 0.1)
        return max(0, min(40, base))
    except Exception:
        return 10


def record_controversy_event(
    entity: Any,
    event_type: str,
    severity: int = 5,
    description: str = "",
    game_date: Optional[str] = None,
) -> int:
    """Log a controversy incident and raise the entity's controversy score.

    event_type: one of "outburst" | "effort" | "locker_room" | "off_ice"
                | "holdout" | "suspension".
    severity: 1-10.

    This is the hook future systems (media, discipline, morale events)
    will call into -- e.g. a post-game outburst, a healthy scratch over
    effort, a leaked locker-room story.
    """
    ensure_reputation_fields(entity)
    weight = CONTROVERSY_WEIGHTS.get(event_type, 1.5)
    severity = max(1, min(10, severity))
    bump = int(round(weight * severity))

    entity.controversy = max(0, min(CONTROVERSY_MAX, entity.controversy + bump))
    entity.controversy_history.append({
        "date": game_date or date.today().isoformat(),
        "type": event_type,
        "severity": severity,
        "description": description,
        "controversy_after": entity.controversy,
    })
    # Cap history so long careers don't bloat saves
    if len(entity.controversy_history) > 50:
        entity.controversy_history = entity.controversy_history[-50:]
    return entity.controversy


def decay_controversy(entity: Any, incidents_this_season: int = 0,
                      team: Any = None, coach: Any = None,
                      win_pct: Optional[float] = None) -> int:
    """Seasonal volatility development.

    Controversy eases halfway toward its scenario target
    (locked base + scenario offset, clamped to +/-25 of base) -- no
    whiplash, identity preserved. Incidents spike it first; then the
    scenario pulls it back. Called from the end-of-season hook.
    """
    ensure_reputation_fields(entity)
    base = controversy_baseline(entity)
    if _is_staff_entity(entity):
        offset, _ = _coach_volatility_offset(entity, team, coach, win_pct)
    else:
        offset, _ = _player_volatility_offset(entity, team, coach, win_pct)
    target = max(0, min(100, base + offset))
    cur = getattr(entity, "controversy", base) or 0
    if incidents_this_season:
        cur = min(100, cur + incidents_this_season * 3)
    entity.controversy = int(round(max(0, min(100, cur + (target - cur) * 0.5))))
    return entity.controversy


# ---------------------------------------------------------------------------
# Derived values: what reputation & controversy DO
# ---------------------------------------------------------------------------

def locker_room_impact(player: Any, team_context: Optional[Dict[str, Any]] = None) -> float:
    """Net locker-room value of a player. Context decides what edge means.

    Without team_context, returns the base read: respected, high-leadership,
    low-drama players stabilize a room; volatile players drag it down.

    With team_context, BOTH things can be true at once for the same player:
    a hard-nosed, high-edge athlete is fuel on a winning team with a strong
    leadership group and poison on a losing, rudderless one.

    team_context keys:
        win_pct: float 0..1 -- the team's winning atmosphere.
        room_leadership: float 0..100 -- average leadership of the room's core.
            Complimentary structure channels edge; its absence lets edge rot.

    The interaction: volatility * presence * atmosphere. Leaders' edge reads
    as intensity (penalized less, redeemed more); low-leadership volatility
    reads as selfish chaos. Returns roughly -0.8 .. +0.9.
    Feed into team chemistry calculations.
    """
    ensure_reputation_fields(player)
    try:
        leadership = (getattr(player, "leadership", 50) or 50) / 100
        rep = (player.reputation or 0) / 100
        vol = (player.controversy or 0) / 100
        age = getattr(player, "age", 25) or 25
        veteran_bonus = 0.1 if age >= VETERAN_AGE else 0.0

        # Leaders' edge is intensity; everyone else's edge is just noise.
        effective_vol = vol * (1.0 - leadership * 0.4)

        if not team_context:
            return round(
                leadership * 0.45 + rep * 0.25 - effective_vol * 0.6 + veteran_bonus, 3
            )

        win_pct = max(0.0, min(1.0, team_context.get("win_pct", 0.5)))
        room_leadership = max(0.0, min(100.0, team_context.get("room_leadership", 50))) / 100
        atmosphere = (win_pct - 0.5) * 2.0          # -1 (losing) .. +1 (winning)
        structure = 0.5 + room_leadership * 0.5    # structured rooms channel edge
        presence = leadership * 0.7 + rep * 0.3    # how much weight the room gives them

        # Atmosphere also deepens/shallows the base volatility penalty:
        # losing rooms make edge rot faster, winning rooms tolerate it.
        penalty_mult = 1.0 - atmosphere * 0.4 * structure
        base = (leadership * 0.45 + rep * 0.25
                - effective_vol * 0.6 * penalty_mult + veteran_bonus)

        # The swing: same player, opposite signs in opposite rooms.
        # ASYMMETRIC: only a leader's edge becomes fuel in a good room
        # (gated on leadership); anyone's volatility rots a losing room.
        lead_gate = leadership if atmosphere > 0 else 1.0
        swing = vol * presence * atmosphere * 2.8 * structure * lead_gate
        return round(base + swing, 3)
    except Exception:
        return 0.0


def award_championship(entity: Any) -> int:
    """Flat reputation bonus for winning the Stanley Cup. Ratchet-safe by
    construction (pure addition, capped at 100). Call at the offseason
    rollover for every player/staff member on the champion team.
    """
    ensure_reputation_fields(entity)
    try:
        if hasattr(entity, "career_reputation"):
            entity.career_reputation = min(100, entity.career_reputation + 8)
            return entity.career_reputation
        entity.reputation = min(REPUTATION_MAX, (entity.reputation or 0) + 8)
        entity.reputation_history.append({
            "date": date.today().isoformat(),
            "reputation": entity.reputation,
            "reason": "stanley_cup",
        })
        return entity.reputation
    except Exception:
        return 0


def trade_value_modifier(player: Any, buyer_is_contender: bool = False) -> float:
    """Multiplier on a player's trade value from reputation dynamics.

    - Controversy discounts: up to -35% at max volatility. GMs pay less
      for a headache, however talented.
    - Veteran-leader premium: contenders pay +15% for a high-leadership,
      high-reputation veteran at the deadline -- the Thornton effect.
      This is NOT general trade value; it only applies to contenders
      shopping for glue guys.
    """
    ensure_reputation_fields(player)
    mod = 1.0
    try:
        mod -= (player.controversy / CONTROVERSY_MAX) * 0.35
        age = getattr(player, "age", 25) or 25
        leadership = getattr(player, "leadership", 50) or 50
        if (
            buyer_is_contender
            and age >= VETERAN_AGE
            and leadership >= 75
            and player.reputation >= 60
        ):
            mod += 0.15
    except Exception:
        pass
    return round(max(0.4, mod), 3)


def contract_ask_modifier(player: Any) -> float:
    """How reputation/controversy shift a player's salary expectations.

    Stars know their worth (+); volatile players with big reputations
    still get paid, but teams bake in risk (-).
    """
    ensure_reputation_fields(player)
    mod = 1.0
    try:
        mod += (player.reputation / REPUTATION_MAX) * 0.25
        mod -= (player.controversy / CONTROVERSY_MAX) * 0.10
    except Exception:
        pass
    return round(max(0.7, mod), 3)


def media_heat(player_or_staff: Any) -> int:
    """0-100 media attention score. High rep + high controversy = circus."""
    ensure_reputation_fields(player_or_staff)
    try:
        rep = player_or_staff.reputation or 0
        vol = player_or_staff.controversy or 0
        # Controversial stars dominate the cycle; quiet grinders don't
        return max(0, min(100, int(rep * 0.4 + vol * 0.8)))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def describe_reputation(entity: Any) -> str:
    ensure_reputation_fields(entity)
    score = getattr(entity, "reputation", 0) or 0
    for threshold, label in REPUTATION_TIERS:
        if score >= threshold:
            return label
    return "Unknown"


def describe_controversy(entity: Any) -> str:
    ensure_reputation_fields(entity)
    score = getattr(entity, "controversy", 0) or 0
    for threshold, label in CONTROVERSY_TIERS:
        if score >= threshold:
            return label
    return "Model citizen"


def reputation_summary(player: Any) -> Dict[str, Any]:
    """One dict for profile windows: reputation, controversy and derived bits."""
    ensure_reputation_fields(player)
    return {
        "reputation": player.reputation,
        "reputation_tier": describe_reputation(player),
        "controversy": player.controversy,
        "controversy_tier": describe_controversy(player),
        "attitude": describe_attitude(player),   # visible personality label
        "locker_room_impact": locker_room_impact(player),
        "media_heat": media_heat(player),
        "contract_loyalty": contract_loyalty(player),
        "social_group": player_social_group(player),
    }


# ---------------------------------------------------------------------------
# Visible attitude
# ---------------------------------------------------------------------------

# controversy is the VISIBLE attitude/volatility attribute (0-100), shown on
# player profiles like any other attribute. Every system that needs to know
# "what kind of character is this guy" reads it: trade requests, contract
# loyalty, relationships, chemistry. Future scenario hooks (outbursts,
# effort issues, leaks) all feed record_controversy_event().
ATTITUDE_LABELS = [
    (80, "Volatile"),
    (60, "Fiery"),
    (40, "Emotional"),
    (20, "Even-keeled"),
    (0, "Model professional"),
]


def describe_attitude(entity: Any) -> str:
    """Visible personality label for profiles and the Morale tab."""
    ensure_reputation_fields(entity)
    score = getattr(entity, "controversy", 0) or 0
    for threshold, label in ATTITUDE_LABELS:
        if score >= threshold:
            return label
    return "Model professional"


# ---------------------------------------------------------------------------
# Character-driven behaviours
# ---------------------------------------------------------------------------

def trade_request_risk(player: Any, team_context: Optional[Dict[str, Any]] = None) -> float:
    """0..1 likelihood this player agitates for a move.

    Volatile players in bad situations ask out; loyal leaders ride it out.
    Feeds the transfer-request logic: roll against this each month for
    unhappy players.
    """
    ensure_reputation_fields(player)
    try:
        vol = (player.controversy or 0) / 100
        leadership = (getattr(player, "leadership", 50) or 50) / 100
        happiness = getattr(player, "happiness", 70) or 70
        ice_concern = getattr(player, "playing_time_concern", 0) or 0

        risk = vol * 0.35
        risk += max(0.0, (70 - happiness) / 100) * 0.5
        risk += (ice_concern / 100) * 0.25
        if team_context:
            win_pct = max(0.0, min(1.0, team_context.get("win_pct", 0.5)))
            risk += max(0.0, (0.45 - win_pct)) * 0.9   # losing pours fuel
        # Loyal leaders don't quit on the room
        if player.controversy < 40:
            risk -= leadership * 0.15
        if getattr(player, "transfer_requested", False):
            risk = min(1.0, risk + 0.3)  # already agitating: likely to repeat
        return round(max(0.0, min(1.0, risk)), 3)
    except Exception:
        return 0.0


def contract_loyalty(player: Any) -> float:
    """0..1 contract loyalty. High loyalty = re-signs cheaper, doesn't hold out.

    Suggested use in contract talks: demand_mult = 1.05 - loyalty * 0.15.
    """
    ensure_reputation_fields(player)
    try:
        leadership = getattr(player, "leadership", 50) or 50
        happiness = getattr(player, "happiness", 70) or 70
        loyalty = (0.55 + leadership * 0.003 - (player.controversy or 0) * 0.005
                   + (happiness - 70) * 0.003)
        return round(max(0.05, min(0.98, loyalty)), 3)
    except Exception:
        return 0.5


def relationship_chemistry(a: Any, b: Any) -> float:
    """-1..1 how well two players get along. Drives social groups and
    line-combination side effects (future)."""
    for p in (a, b):
        ensure_reputation_fields(p)
    try:
        vol_a = (a.controversy or 0)
        vol_b = (b.controversy or 0)
        lead_a = getattr(a, "leadership", 50) or 50
        lead_b = getattr(b, "leadership", 50) or 50

        score = 0.15  # teammates default mildly positive
        if vol_a < 25 and vol_b < 25:
            score += 0.25                              # quiet pros bond
        if abs(vol_a - vol_b) < 15:
            score += 0.20                              # similar temperaments
        if (vol_a >= 60 and lead_b >= 75) or (vol_b >= 60 and lead_a >= 75):
            score -= 0.45                              # leader vs headcase
        # Veteran mentors the kid
        age_a = getattr(a, "age", 25) or 25
        age_b = getattr(b, "age", 25) or 25
        if lead_a >= 80 and age_b <= 24 and vol_b < 40:
            score += 0.20
        if lead_b >= 80 and age_a <= 24 and vol_a < 40:
            score += 0.20
        if getattr(a, "nationality", "") == getattr(b, "nationality", ""):
            score += 0.10
        return round(max(-1.0, min(1.0, score)), 3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Team hierarchy & social groups (FM-style)
# ---------------------------------------------------------------------------

HIERARCHY_TIERS = ["Team Leaders", "Core Group", "Squad Players", "Fringe"]
HIERARCHY_WEIGHTS = {"Team Leaders": 3.0, "Core Group": 2.0,
                     "Squad Players": 1.0, "Fringe": 0.5}


def _tenure_years(player: Any) -> float:
    tenure = getattr(player, "team_tenure", "") or ""
    if "4+" in tenure:
        return 5.0
    if "3 year" in tenure:
        return 3.0
    if "2 year" in tenure:
        return 2.0
    return 0.5


def hierarchy_score(player: Any) -> float:
    """Influence score: leadership + reputation + tenure. Captains get a bump."""
    ensure_reputation_fields(player)
    try:
        leadership = getattr(player, "leadership", 50) or 50
        score = (leadership * 0.45 + (player.reputation or 0) * 0.35
                 + min(_tenure_years(player), 5) * 3.0)
        if getattr(player, "captaincy", None) == "C":
            score += 8
        elif getattr(player, "captaincy", None) == "A":
            score += 4
        return round(score, 1)
    except Exception:
        return 0.0


def team_hierarchy(roster: List[Any]) -> Dict[str, List[Any]]:
    """FM-style dressing-room hierarchy. Top ~4 by influence lead the room."""
    scored = sorted(((hierarchy_score(p), p) for p in roster),
                    key=lambda t: t[0], reverse=True)
    tiers: Dict[str, List[Any]] = {t: [] for t in HIERARCHY_TIERS}
    for i, (score, p) in enumerate(scored):
        if i < 4 and score >= 55:
            tiers["Team Leaders"].append(p)
        elif score >= 50:
            tiers["Core Group"].append(p)
        elif score >= 30:
            tiers["Squad Players"].append(p)
        else:
            tiers["Fringe"].append(p)
    return tiers


def player_social_group(player: Any) -> str:
    """Primary clique, FM social-groups style. One label per player for v1."""
    ensure_reputation_fields(player)
    try:
        vol = player.controversy or 0
        age = getattr(player, "age", 25) or 25
        if vol >= 55:
            return "Edge group"
        if age >= 32:
            return "Veterans"
        if age <= 23:
            return "Young guns"
        return "Core"
    except Exception:
        return "Core"


def social_groups(roster: List[Any]) -> Dict[str, List[Any]]:
    """Clique breakdown of the room."""
    groups: Dict[str, List[Any]] = {}
    for p in roster:
        groups.setdefault(player_social_group(p), []).append(p)
    return groups


# ---------------------------------------------------------------------------
# Team chemistry: one guy can't ruin a room
# ---------------------------------------------------------------------------

CHEMISTRY_LABELS = [
    (80, "Harmonious"),
    (65, "United"),
    (50, "Functional"),
    (35, "Fractured"),
    (0, "Toxic"),
]


def team_chemistry(roster: List[Any],
                   team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Overall room health, 0-100.

    Impacts are hierarchy-weighted (leaders count 3x, fringe 0.5x), and a
    strong leadership core DAMPENS individual volatility -- one diva cannot
    single-handedly tank a room with a real core. Returns a dict built for
    the Morale tab: score, label, tier breakdown, biggest influences.
    """
    if not roster:
        return {"score": 50, "label": "Functional", "tiers": {}, "influences": []}
    try:
        hierarchy = team_hierarchy(roster)
        leaders = hierarchy["Team Leaders"]
        core_strength = 0.0
        if leaders:
            core_strength = max(0.0, sum(
                locker_room_impact(p, team_context) for p in leaders) / len(leaders))

        weighted_sum = 0.0
        weight_total = 0.0
        influences = []
        for tier, players in hierarchy.items():
            w = HIERARCHY_WEIGHTS[tier]
            for p in players:
                impact = locker_room_impact(p, team_context)
                # Dampening: a strong core absorbs one player's negativity.
                if impact < 0 and tier != "Team Leaders" and core_strength > 0.2:
                    impact = impact / (1.0 + core_strength * 2.5)
                weighted_sum += impact * w
                weight_total += w
                influences.append({
                    "name": getattr(p, "full_name", "Unknown"),
                    "tier": tier,
                    "impact": round(impact, 3),
                    "attitude": describe_attitude(p),
                    "happiness": getattr(p, "happiness", 70),
                })
        overall = weighted_sum / max(0.001, weight_total)
        score = max(0, min(100, int(50 + overall * 55)))
        label = next(lbl for thr, lbl in CHEMISTRY_LABELS if score >= thr)
        influences.sort(key=lambda d: d["impact"])
        return {
            "score": score,
            "label": label,
            "tiers": {t: len(ps) for t, ps in hierarchy.items()},
            "core_strength": round(core_strength, 3),
            "influences": influences,   # sorted worst -> best
        }
    except Exception:
        return {"score": 50, "label": "Functional", "tiers": {}, "influences": []}


# ---------------------------------------------------------------------------
# League perception vs team perception
# ---------------------------------------------------------------------------
# Two different audiences judge every person in hockey:
#   league_perception -- what the other 31 teams, the media and the fans think.
#                      Drives trade interest, hiring appeal, "hot seat" talk.
#   team_perception   -- what his OWN room thinks of him.
#                      Drives chemistry, buy-in, whether he's lost the room.
# They diverge all the time: the box-office diva the league loves but his
# teammates can't stand, or the beloved 4th-liner nobody outside the room
# has heard of. Both are pure functions of stored state (no new fields).

def _staff_100(entity: Any, attr: str, default: int = 50) -> float:
    """Staff 1-100 attribute -> 0-100 scale (native since the full rescale;
    clamp-only for safety)."""
    try:
        v = getattr(entity, attr, default)
        v = default if v is None else v
        return max(1, min(100, int(v)))
    except Exception:
        return default


def _is_staff(entity: Any) -> bool:
    return hasattr(entity, "role") and not hasattr(entity, "primary_position")


def _is_staff_entity(entity: Any) -> bool:
    """Duck-typed staff check for contexts without a real Staff object."""
    return not hasattr(entity, "primary_position")


def _role_name(entity: Any) -> str:
    role = getattr(entity, "role", None)
    return str(getattr(role, "value", role) or "")


def _is_head_coach(entity: Any) -> bool:
    return _is_staff(entity) and "Head Coach" in _role_name(entity)


def _is_gm(entity: Any) -> bool:
    return _is_staff(entity) and "General Manager" in _role_name(entity) \
        and "Assistant" not in _role_name(entity)


def league_perception(entity: Any, season_ppg: float = 0.0,
                      league_avg_ppg: float = 0.8,
                      team_context: Optional[Dict[str, Any]] = None) -> float:
    """0-100: how the league (media, fans, other teams) sees this person."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    try:
        if _is_staff(entity):
            score = (entity.career_reputation or 0) * 0.50
            score += (win_pct - 0.5) * 100 * 0.30          # recent results talk
            score += _staff_100(entity, "media_handling") * 0.10
            score += min(100, (getattr(entity, "experience", 5) or 5) * 4) * 0.10
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 1)) or 0
            if win_pct < 0.45 and ywt >= 2:
                score -= 12                                # hot-seat talk
            if (entity.controversy or 0) >= 60:             # polarizing figure
                score += 5 if win_pct >= 0.5 else -8
            return round(max(0, min(100, score)), 1)
        # -- player --
        form = min(100, (season_ppg / max(0.01, league_avg_ppg)) * 50)
        score = (entity.reputation or 0) * 0.55 + form * 0.20
        score += (win_pct - 0.5) * 30                       # contender halo
        vol = entity.controversy or 0
        if vol >= 50:
            # Box office only sells while he's producing; a cold diva is
            # just a headache and the league prices him like one.
            form_factor = min(1.0, season_ppg / max(0.01, league_avg_ppg))
            if (entity.reputation or 0) >= 60:
                score += vol * 0.08 * (0.3 + 0.7 * form_factor)
            elif (entity.reputation or 0) < 40:
                score -= vol * 0.15                         # headcase discount
        return round(max(0, min(100, score)), 1)
    except Exception:
        return 50.0


def team_perception(entity: Any, team_context: Optional[Dict[str, Any]] = None,
                    roster: Optional[List[Any]] = None) -> float:
    """0-100: how his OWN room sees him. The 'lost the room' input."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    try:
        if _is_staff(entity):
            score = (_staff_100(entity, "man_management") * 0.30
                     + _staff_100(entity, "motivating") * 0.25
                     + _staff_100(entity, "leadership") * 0.25
                     + (100 - (entity.controversy or 0)) * 0.20)
            score += (win_pct - 0.5) * 40    # winning covers, losing exposes
            # Track record buys rope: banked Cups and Jack Adams awards in
            # the career record cushion a bad year -- the room gives a
            # proven winner the benefit of the doubt. Capped so the
            # hot-seat mechanic still bites.
            try:
                _accs = getattr(entity, "career_accolades", None) or []
                _titles = sum(
                    1 for _a in _accs
                    if isinstance(_a, dict)
                    and _a.get("award") in ("stanley_cup", "jack_adams"))
                score += min(8, _titles * 2)
            except Exception:
                pass
            return round(max(0, min(100, score)), 1)
        # -- player --
        leadership = getattr(entity, "leadership", 50) or 50
        effort100 = (locker_room_impact(entity, ctx) + 1) * 50
        tenure_score = min(100, 40 + _tenure_years(entity) * 12)
        score = (leadership * 0.30 + (100 - (entity.controversy or 0)) * 0.25
                 + effort100 * 0.20 + tenure_score * 0.15 + win_pct * 100 * 0.10)
        captaincy = getattr(entity, "captaincy", None)
        if captaincy == "C":
            score += 8 * (0.3 + 0.7 * leadership / 100)   # the letter carries weight
        elif captaincy == "A":
            score += 4 * (0.3 + 0.7 * leadership / 100)
        return round(max(0, min(100, score)), 1)
    except Exception:
        return 50.0


# ---------------------------------------------------------------------------
# Losing the room
# ---------------------------------------------------------------------------
# Real-NHL model. Risk factors combine with noisy-OR (the probabilistically
# honest way: each factor is an independent chance to break the room), then
# mitigations (banked goodwill, beloved-vet shield) multiply the remainder
# down. Returns the probability plus every factor's contribution so the UI
# (and the debugger) can show the receipt.

ROOM_LEVELS = [
    (0.75, "Lost"),
    (0.55, "Fracturing"),
    (0.35, "Strain"),
    (0.0, "Secure"),
]


def _noisy_or(factors: List[float], mitigations: List[float]) -> float:
    risk = 1.0
    for f in factors:
        risk *= 1.0 - max(0.0, min(1.0, f))
    risk = 1.0 - risk
    for m in mitigations:
        risk *= 1.0 - max(0.0, min(1.0, m))
    return max(0.0, min(1.0, risk))


def room_status(entity: Any, team_context: Optional[Dict[str, Any]] = None,
                roster: Optional[List[Any]] = None,
                season_ppg: float = 0.0,
                league_avg_ppg: float = 0.8) -> Dict[str, Any]:
    """Probability this person has lost / is losing the room, with the full
    factor breakdown. Works for head coaches, GMs and players."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    roster = roster or []
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    factors: List[tuple] = []
    mitigations: List[tuple] = []
    brash = (entity.controversy or 0) >= 60

    try:
        if _is_staff(entity) and not _is_gm(entity):
            kind = "coach"
            # 1. Losing -- the #1 killer of coaches in real life --------------
            f = min(0.50, max(0.0, 0.55 - win_pct) * 1.5)
            factors.append(("Losing record", round(f, 3)))
            # 2. Shelf life -- the message goes stale (NHL avg ~3 yrs) ---------
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 2)) or 0
            f = min(0.24, max(0.0, ywt - 3) * 0.06)
            factors.append(("Message gone stale", round(f, 3)))
            # 3-5. Can't communicate / motivate / lead -------------------------
            for attr, label, w in (("man_management", "Poor communicator", 0.45),
                                   ("motivating", "Can't motivate", 0.35),
                                   ("leadership", "Not a leader", 0.30)):
                v = getattr(entity, attr, 60) or 60
                f = max(0.0, (60 - v)) / 100 * w
                factors.append((label, round(f, 3)))
            # 6. Discipline mismatch (two-sided, very NHL) ---------------------
            disc = getattr(entity, "discipline", 50) or 50
            if roster:
                avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / len(roster)
                avg_lead = sum(getattr(p, "leadership", 50) or 50 for p in roster) / len(roster)
                avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / len(roster)
                if disc >= 75 and avg_age >= 28.5 and avg_lead >= 60:
                    factors.append(("Drill sergeant vs veteran room", 0.14))
                if disc <= 40 and (avg_vol >= 38 or avg_age <= 25):
                    factors.append(("Lost control (soft coach, wild room)", 0.18))
            # 7. The leaders have quit on him ---------------------------------
            if roster:
                leaders = team_hierarchy(roster).get("Team Leaders", [])
                if leaders:
                    lh = sum(getattr(p, "happiness", 70) or 70 for p in leaders) / len(leaders)
                    if lh < 55:
                        factors.append(("Team leaders tuned out", 0.20))
                    elif lh < 65:
                        factors.append(("Team leaders wavering", 0.10))
            # 8. Brash accelerant -- public fights burn faster ----------------
            if brash:
                factors.append(("Brash personality accelerant", 0.10))
            # Mitigation: banked goodwill -------------------------------------
            if (entity.career_reputation or 0) >= 75:
                mitigations.append(("Championship goodwill", 0.25))
            if not _is_head_coach(entity):
                # Assistants don't get fired for the room; cap their risk.
                cap = 0.60
            else:
                cap = 1.0
        elif _is_gm(entity):
            kind = "gm"
            f = min(0.40, max(0.0, 0.55 - win_pct) * 1.2)
            factors.append(("Losing record", round(f, 3)))
            lp = league_perception(entity, team_context=ctx)
            if lp < 45:
                factors.append(("Fan/media pressure", 0.15))
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 2)) or 0
            if ywt >= 4 and (entity.career_reputation or 0) < 55:
                factors.append(("Tenure without results", 0.18))
            if brash:
                factors.append(("Brash GM accelerant", 0.10))
            cap = 1.0
        else:
            kind = "player"
            rep = entity.reputation or 0
            leadership = getattr(entity, "leadership", 50) or 50
            # 1. Production collapse vs expectation ----------------------------
            if rep >= 50 and league_avg_ppg > 0:
                exp_ppg = league_avg_ppg * (0.4 + rep / 60)
                under = max(0.0, 1 - season_ppg / max(0.01, exp_ppg))
                factors.append(("Production collapse", round(under * 0.30, 3)))
            # 2. Controversy ---------------------------------------------------
            factors.append(("Controversy", round((entity.controversy or 0) / 100 * 0.30, 3)))
            # 3. Effort questioned ----------------------------------------------
            if locker_room_impact(entity, ctx) < -0.05:
                factors.append(("Effort questioned", 0.18))
            # 4. Losing ----------------------------------------------------------
            factors.append(("Losing", round(max(0.0, 0.5 - win_pct) * 0.7, 3)))
            # 5. Captain scrutiny -- the C means you own it ----------------------
            scrutiny = 1.0
            if getattr(entity, "captaincy", None) == "C":
                scrutiny = 1.25
            elif getattr(entity, "captaincy", None) == "A":
                scrutiny = 1.10
            if brash and (entity.controversy or 0) >= 65:
                factors.append(("Brash star finger-pointing", 0.08))
            # Mitigation: beloved vet shield ------------------------------------
            if _tenure_years(entity) >= 4 and leadership >= 70:
                mitigations.append(("Beloved veteran shield", 0.35))
            risk = _noisy_or([f for _, f in factors], [m for _, m in mitigations])
            risk = min(1.0, risk * scrutiny)
            if rep < 45 and getattr(entity, "captaincy", None) is None:
                risk = min(risk, 0.30)   # role players don't lose rooms; they get waived
            cap = 1.0
            factors = [(l, v) for l, v in factors]  # keep order

        if kind != "player":
            risk = _noisy_or([f for _, f in factors], [m for _, m in mitigations])
            risk = min(risk, cap)

        level = next(lbl for thr, lbl in ROOM_LEVELS if risk >= thr)
        return {
            "kind": kind,
            "risk": round(risk, 3),
            "level": level,
            "brash": brash,
            "factors": sorted(factors, key=lambda t: t[1], reverse=True),
            "mitigations": [l for l, _ in mitigations],
            "league_perception": league_perception(entity, season_ppg, league_avg_ppg, ctx),
            "team_perception": team_perception(entity, ctx, roster),
        }
    except Exception:
        return {"kind": "unknown", "risk": 0.0, "level": "Secure", "brash": False,
                "factors": [], "mitigations": [],
                "league_perception": 50.0, "team_perception": 50.0}


# ---------------------------------------------------------------------------
# Implications: what "losing the room" DOES
# ---------------------------------------------------------------------------

def room_implications(status: Dict[str, Any], entity: Any,
                      team_context: Optional[Dict[str, Any]] = None,
                      roster: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Concrete fallout for a room_status result. Areas: media, chemistry,
    trade, personnel, performance. Brash personalities escalate PUBLICLY
    (leaks, circus); quiet ones silently quit (effort drop, no circus)."""
    ensure_reputation_fields(entity)
    level = status.get("level", "Secure")
    kind = status.get("kind", "player")
    brash = status.get("brash", False)
    quiet = (entity.controversy or 0) < 30
    name = getattr(entity, "full_name", "Unknown")
    out: List[Dict[str, Any]] = []
    if level == "Secure":
        return out

    def add(area, text, magnitude):
        out.append({"area": area, "text": text, "magnitude": magnitude})

    # -- shared escalation ladder -------------------------------------------
    if level == "Strain":
        add("media", f"Media starts asking questions about {name}", 5)
        add("chemistry", "Room tension: chemistry drift", -3)
    elif level == "Fracturing":
        add("media", f"'Has {name} lost the room?' becomes the story", 12)
        add("chemistry", "Fracturing room: chemistry hit", -8)
        if kind == "player":
            add("trade", "Unhappy teammates' trade-request risk x1.5", 1.5)
            if getattr(entity, "captaincy", None) == "C":
                add("personnel", "Captaincy under review: strip the C?", 1)
        else:
            add("personnel", "Ownership pressure: win or else", 1)
    else:  # Lost
        add("chemistry", "Lost room: chemistry collapse", -15)
        if kind == "coach":
            add("personnel", f"Recommend termination: {name} should be fired", 1)
            add("media", "Firing watch: every loss is the lead story", 20)
        elif kind == "gm":
            add("personnel", f"Ownership review: {name}'s job in danger", 1)
        else:
            add("trade", f"{name} likely to demand a trade", 1)
            if getattr(entity, "captaincy", None) == "C":
                add("personnel", "Captaincy under review: strip the C?", 1)

    # -- personality split: brash goes public, quiet silently quits ----------
    if level in ("Fracturing", "Lost"):
        if brash:
            add("media", "Brash fallout: leaks to press, media circus", 15)
            add("chemistry", "Distraction penalty: circus drains the room", -5)
        elif quiet:
            add("performance", "Silent quit: effort drops without a sound", -8)

    # -- winning still papers over cracks at the margins ----------------------
    # (risk already prices winning heavily; this only softens Strain noise)
    return out


# ---------------------------------------------------------------------------
# Coaching styles & player engagement styles
# ---------------------------------------------------------------------------
# Every coach has a style derived from his attributes; every player has an
# engagement style derived from his personality. Style x engagement = fit,
# and fit is what the Morale screen shows as "how players respond to coach".

COACHING_STYLES = {
    "drill_sergeant": {
        "label": "Drill Sergeant",
        "description": "Bag skates, accountability, no excuses. Veterans tune it out; kids need it.",
        "restrictiveness": 0.9,
    },
    "players_coach": {
        "label": "Player's Coach",
        "description": "Arm around the shoulder. The room runs itself -- until it doesn't.",
        "restrictiveness": 0.3,
    },
    "tactician": {
        "label": "Tactician",
        "description": "Systems-first, video, structure. Skill gets a leash, not freedom.",
        "restrictiveness": 0.8,
    },
    "motivator": {
        "label": "Motivator",
        "description": "Speeches, emotion, us-against-the-world. Runs hot, burns out.",
        "restrictiveness": 0.4,
    },
    "developer": {
        "label": "Developer",
        "description": "Teacher first. Patience, reps, and a long view -- kids blossom.",
        "restrictiveness": 0.4,
    },
    "balanced": {
        "label": "Balanced",
        "description": "No single gear. Adjusts to the room he has.",
        "restrictiveness": 0.55,
    },
}


def coach_style(coach: Any) -> Dict[str, Any]:
    """Derive the coach's style from his attributes. Returns the style dict
    plus the winning key."""
    ensure_reputation_fields(coach)
    try:
        # Deviation from the NHL-average coach (~65): only DISTINCTIVE traits
        # define a style. An all-average coach is balanced, not a weak motivator.
        d = lambda a: (getattr(coach, a, 65) or 65) - 65  # 1-100 scale
        scores = {
            "drill_sergeant": d("discipline") * 2 + d("motivating") * 0.5 - d("man_management") * 0.5,
            "players_coach": d("man_management") * 2 + d("motivating") * 0.5 - d("discipline") * 0.5,
            "tactician": d("tactical_knowledge") * 2 + d("game_preparation") * 0.5,
            "motivator": d("motivating") * 2 + d("leadership") * 1.5,
            "developer": d("working_with_youngsters") * 2 + d("player_development"),
        }
        best = max(scores, key=scores.get)
        # Nothing distinctive -> balanced.
        if scores[best] < 30:
            best = "balanced"
        style = dict(COACHING_STYLES[best])
        style["key"] = best
        return style
    except Exception:
        style = dict(COACHING_STYLES["balanced"])
        style["key"] = "balanced"
        return style


ENGAGEMENT_STYLES = {
    "needs_guidance": "Young and wild: needs a firm hand and clear structure.",
    "needs_freedom": "Creative skill: thrives with freedom, withers in a trap.",
    "thrives_on_structure": "Detail-driven: loves systems and accountability.",
    "veteran_autonomy": "Been there: wants trust, not micromanagement.",
    "fragile_confidence": "Confidence shot: needs an arm around him.",
    "steady_professional": "Pro's pro: brings it regardless of who's behind the bench.",
}


def engagement_style(player: Any) -> Dict[str, Any]:
    """Derive how this player engages with coaching from his personality."""
    ensure_reputation_fields(player)
    try:
        age = getattr(player, "age", 26) or 26
        vol = player.controversy or 0
        flair = getattr(player, "flair", 50) or 50
        disc = getattr(player, "discipline", 50) or 50
        lead = getattr(player, "leadership", 50) or 50
        happy = getattr(player, "happiness", 70) or 70
        conf = getattr(player, "morale", 50) or 50  # form/confidence, 1-100
        if age <= 23 and vol >= 45:
            key = "needs_guidance"
        elif flair >= 68 and disc < 50:
            key = "needs_freedom"
        elif disc >= 62 and vol < 35:
            key = "thrives_on_structure"
        elif age >= 32 and lead >= 68:
            key = "veteran_autonomy"
        elif happy < 50 or conf <= 30:
            # Happiness is about the room; morale is about his own game.
            # A happy-but-cold player still needs an arm around him.
            key = "fragile_confidence"
        else:
            key = "steady_professional"
        return {"key": key, "label": key.replace("_", " ").title(),
                "description": ENGAGEMENT_STYLES[key]}
    except Exception:
        return {"key": "steady_professional", "label": "Steady Professional",
                "description": ENGAGEMENT_STYLES["steady_professional"]}


# Style x engagement fit matrix. Positive = buys in, negative = friction.
_COACH_FIT = {
    "drill_sergeant": {"needs_guidance": 0.4, "needs_freedom": -0.5,
                       "thrives_on_structure": 0.4, "veteran_autonomy": -0.2,
                       "fragile_confidence": -0.3, "steady_professional": 0.1},
    "players_coach": {"needs_guidance": -0.2, "needs_freedom": 0.3,
                      "thrives_on_structure": 0.1, "veteran_autonomy": 0.3,
                      "fragile_confidence": 0.4, "steady_professional": 0.1},
    "tactician": {"needs_guidance": 0.2, "needs_freedom": -0.4,
                  "thrives_on_structure": 0.4, "veteran_autonomy": 0.0,
                  "fragile_confidence": 0.0, "steady_professional": 0.2},
    "motivator": {"needs_guidance": 0.1, "needs_freedom": 0.2,
                  "thrives_on_structure": 0.0, "veteran_autonomy": 0.1,
                  "fragile_confidence": 0.3, "steady_professional": 0.1},
    "developer": {"needs_guidance": 0.5, "needs_freedom": 0.1,
                  "thrives_on_structure": 0.1, "veteran_autonomy": -0.1,
                  "fragile_confidence": 0.3, "steady_professional": 0.1},
    "balanced": {"needs_guidance": 0.1, "needs_freedom": 0.1,
                 "thrives_on_structure": 0.1, "veteran_autonomy": 0.1,
                 "fragile_confidence": 0.1, "steady_professional": 0.1},
}


def coach_player_fit(coach: Any, player: Any) -> float:
    """-1..1: how well this player's engagement style fits the coach."""
    try:
        style = coach_style(coach)["key"]
        eng = engagement_style(player)["key"]
        fit = _COACH_FIT.get(style, {}).get(eng, 0.0)
        # Good communicators smooth every edge; bad ones sharpen them.
        mm = getattr(coach, "man_management", 50) or 50
        fit += (mm - 50) / 50 * 0.25
        # A developer's touch lives in the attribute, not just the style
        # label: even a motivator with a 90 youth rating reaches kids.
        wwy = getattr(coach, "working_with_youngsters", 50) or 50
        if eng in ("needs_guidance", "fragile_confidence") \
                and (getattr(player, "age", 26) or 26) <= 23:
            fit += (wwy - 50) / 50 * 0.3
        # Brash player + weak communicator = oil and water.
        if (player.controversy or 0) >= 60 and mm < 50:
            fit -= 0.2
        return round(max(-1.0, min(1.0, fit)), 3)
    except Exception:
        return 0.0


# Archetype families: what a coach's system does and doesn't value.
_ARCHETYPE_FAMILY = {
    "Sniper": "skill", "Playmaker": "skill",
    "Offensive Defenseman": "skill", "Puck-Moving Defenseman": "skill",
    "Power Forward": "power",
    "Grinder": "grind", "Two-Way Forward": "grind",
    "Defensive Defenseman": "grind", "Two-Way Defenseman": "grind",
    "Physical Defenseman": "grind", "Enforcer": "grind",
}
_STYLE_VALUES = {
    "drill_sergeant": {"skill": 0.90, "grind": 1.15, "power": 1.05},
    "players_coach": {"skill": 1.15, "grind": 0.85, "power": 1.00},
    "tactician": {"skill": 1.00, "grind": 1.05, "power": 1.00},
    "motivator": {"skill": 1.10, "grind": 0.95, "power": 1.05},
    "developer": {"skill": 1.00, "grind": 1.00, "power": 1.00},
    "balanced": {"skill": 1.00, "grind": 1.00, "power": 1.00},
}


def coach_archetype_valuation(coach: Any, player: Any) -> float:
    """0.5..1.15: how much this coach's system credits this player's
    archetype. A skill-first coach undervalues a generational grinder --
    the player doesn't stop being elite, he just stops being *seen*."""
    try:
        arch = getattr(player, "archetype", "") or ""
        family = _ARCHETYPE_FAMILY.get(str(arch), None)
        if family is None:
            return 1.0
        style = coach_style(coach)["key"]
        val = _STYLE_VALUES.get(style, {}).get(family, 1.0)
        # An unproven young coach leans even harder into his bias.
        rep = getattr(coach, "reputation", 50) or 50
        if rep < 45 and style in ("players_coach", "motivator") and family == "grind":
            val -= 0.05
        # The GM asked for this player to be featured: the coach is playing
        # him now, so the system values him.
        if getattr(player, "usage_featured", False):
            val = min(1.15, val + 0.15)
        return round(max(0.5, min(1.15, val)), 3)
    except Exception:
        return 1.0


def player_coach_response(player: Any, coach: Any,
                          team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """How THIS player is responding to the coach: bought in -> quit."""
    try:
        # A bond forged in fire (Torts/Werenski arc) outlasts any fit model.
        bonds = getattr(player, "coach_bonds", None) or {}
        if getattr(coach, "id", None) in bonds:
            return {"score": 0.85, "label": "Bought in",
                    "fit": coach_player_fit(coach, player),
                    "engagement": engagement_style(player)["label"],
                    "bond": bonds[getattr(coach, "id")]}
        fit = coach_player_fit(coach, player)
        happy = getattr(player, "happiness", 70) or 70
        score = fit * 0.6 + (happy - 65) / 100 * 0.4
        # Influence: an icon's voice carries (+0.10); a lame duck's doesn't.
        score += ((getattr(coach, "influence", 70) or 70) - 70) * 0.004
        # Credit: a coach whose system doesn't value your archetype costs
        # you -- unless you're laid back, in which case it doesn't matter
        # to you at all.
        valuation = coach_archetype_valuation(coach, player)
        base = getattr(player, "base_controversy", 50)
        if base is None:
            base = controversy_baseline(player)
        if valuation < 0.9 and base >= 30:
            score -= 0.08
        if score >= 0.30:
            label = "Bought in"
        elif score >= -0.05:
            label = "Neutral"
        elif score >= -0.35:
            label = "Tuning out"
        else:
            label = "Quit on coach"
        return {"score": round(score, 3), "label": label,
                "fit": fit, "engagement": engagement_style(player)["label"],
                "valuation": coach_archetype_valuation(coach, player)}
    except Exception:
        return {"score": 0.0, "label": "Neutral", "fit": 0.0,
                "engagement": "Steady Professional"}


# ---------------------------------------------------------------------------
# Team dynamics feed
# ---------------------------------------------------------------------------
# The living story of the room: every event that pushes morale up or down,
# stored on the team so it survives saves. The Morale screen renders it
# newest-first with up/down indicators.

def _team_log(team: Any) -> list:
    if not hasattr(team, "dynamics_log") or team.dynamics_log is None:
        team.dynamics_log = []
    return team.dynamics_log


def record_team_event(team: Any, event_type: str, text: str,
                      morale_delta: int = 0, tone: str = "neutral") -> Dict[str, Any]:
    """Append a dynamics event. tone: 'up' | 'down' | 'neutral'."""
    log = _team_log(team)
    event = {"date": date.today().isoformat(), "type": event_type,
             "text": text, "morale_delta": morale_delta, "tone": tone}
    log.append(event)
    del log[:-100]  # keep the story readable
    return event


def get_dynamics_feed(team: Any, limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first dynamics events."""
    return list(reversed(_team_log(team)[-limit:]))


def _shift_happiness(roster: List[Any], delta: int,
                     predicate=None) -> int:
    """Shift happiness for matching players. Returns count affected."""
    n = 0
    for p in roster:
        try:
            if predicate is None or predicate(p):
                p.happiness = max(0, min(100, (getattr(p, "happiness", 70) or 70) + delta))
                n += 1
        except Exception:
            pass
    return n


def apply_bag_skate(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Bag skate after a loss. Discipline message; the room hates it.
    Drill sergeants get a pass -- their rooms expect it."""
    style = coach_style(coach)["key"]
    if style == "drill_sergeant":
        n = _shift_happiness(roster, -1)
        text = (f"{getattr(coach, 'full_name', 'Coach')} bag-skated the team after the loss. "
                f"Business as usual under a drill sergeant ({n} affected).")
        delta = -1
    else:
        n = _shift_happiness(roster, -3)
        # Young wild players take it hardest.
        _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 26) or 26) <= 23)
        text = (f"{getattr(coach, 'full_name', 'Coach')} bag-skated the team after the loss. "
                f"The room is fuming ({n} affected).")
        delta = -3
    return record_team_event(team, "bag_skate", text, morale_delta=delta, tone="down")


def apply_inspiring_speech(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Locker-room speech. Lands only if the coach can actually move a room."""
    mot = getattr(coach, "motivating", 50) or 50
    lead = getattr(coach, "leadership", 50) or 50
    if mot >= 70 or lead >= 70:
        _shift_happiness(roster, 5)
        text = (f"{getattr(coach, 'full_name', 'Coach')} gave an inspiring locker-room speech. "
                f"The room is buzzing.")
        return record_team_event(team, "speech", text, morale_delta=5, tone="up")
    _shift_happiness(roster, 1)
    text = (f"{getattr(coach, 'full_name', 'Coach')} tried a speech. It fell flat.")
    return record_team_event(team, "speech", text, morale_delta=1, tone="neutral")


def apply_great_practice(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Sharp practice after a loss. Small, honest bounce."""
    _shift_happiness(roster, 2)
    text = (f"Great practice after the loss -- {getattr(coach, 'full_name', 'Coach')} "
            f"had them sharp and focused.")
    return record_team_event(team, "practice", text, morale_delta=2, tone="up")


def apply_mistreat_player(team: Any, coach: Any, player: Any,
                          roster: List[Any],
                          rivalries: Optional[list] = None) -> Dict[str, Any]:
    """Coach mistreats (benches/buries) a player. The target seethes; if he's
    popular, the room notices."""
    ensure_reputation_fields(player)
    name = getattr(player, "full_name", "Unknown")
    player.happiness = max(0, (getattr(player, "happiness", 70) or 70) - 15)
    player.controversy = min(100, (player.controversy or 0) + 5)
    pop = team_perception(player, roster=roster)
    ff = fan_favourite_score(player, team)
    fav = ff["score"] >= 70
    friends = [p for p in roster
               if p is not player and _ensure_relationships(p).get(player.id, 0) >= 50]
    if pop >= 65:
        _shift_happiness(roster, -3, lambda p: p is not player)
        text = (f"{getattr(coach, 'full_name', 'Coach')} buried {name}. "
                f"The room thinks it's unfair -- popular players have long memories.")
        delta = -4
        if rivalries is not None:
            record_coach_player_beef(rivalries, coach, player,
                                     f"buried him unfairly; the room noticed")
    else:
        text = f"{getattr(coach, 'full_name', 'Coach')} buried {name}. Few complaints."
        delta = -1
    if fav:
        _shift_happiness(roster, -2)
        for p in friends:
            p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
        text += (f" {name} is a {ff['tier'].lower()} -- the fans are letting the "
                 f"organization hear it, and his friends in the room aren't happy.")
        delta -= 2
        leaders_backing = any(
            p in team_hierarchy(roster).get("Team Leaders", []) for p in friends)
        if leaders_backing:
            text += " The leadership group is not happy."
            delta -= 1
    return record_team_event(team, "mistreatment", text, morale_delta=delta, tone="down")


def detect_dynamics_issues(team: Any, team_context: Optional[Dict[str, Any]],
                           roster: List[Any], coach: Any) -> List[Dict[str, Any]]:
    """Watch-list: structural problems the numbers can see right now."""
    issues: List[Dict[str, Any]] = []
    try:
        ctx = team_context or {}
        win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
        disc = getattr(coach, "discipline", 50) or 50
        style = coach_style(coach)
        n = max(1, len(roster))
        avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / n
        avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / n
        avg_flair = sum(getattr(p, "flair", 50) or 50 for p in roster) / n
        tactic = getattr(team, "tactic_even_strength", "Balanced")

        streak = ctx.get("losing_streak", 0)
        if streak >= 3 and disc >= 65:
            issues.append({"key": "too_tense", "severity": "high",
                           "text": f"Players look tense -- {streak}-game skid under a demanding coach. The room is gripping the sticks."})
        if avg_age <= 25.5 and disc <= 40:
            issues.append({"key": "not_hard_enough", "severity": "high",
                           "text": "Young group, soft practices: the coach isn't demanding enough and it shows."})
        if avg_vol >= 40 and disc <= 45:
            issues.append({"key": "lack_discipline", "severity": "medium",
                           "text": "The room lacks discipline -- too many passengers, not enough accountability."})
        if avg_flair >= 62 and tactic == "Defensive" and style["restrictiveness"] >= 0.7:
            if win_pct >= 0.58:
                issues.append({"key": "no_freedom", "severity": "low",
                               "text": "Skilled group playing a suffocating trap with no freedom... and it's working. Nobody's complaining yet."})
            elif win_pct < 0.45:
                issues.append({"key": "no_freedom", "severity": "high",
                               "text": "Skilled group forced into trap hockey with zero freedom -- and it's NOT working. The skill guys are dying on the vine."})
            else:
                issues.append({"key": "no_freedom", "severity": "medium",
                               "text": "Skilled group in a defensive system: the freedom question is simmering."})
        rs_coach = room_status(coach, ctx, roster)
        if rs_coach["level"] in ("Fracturing", "Lost"):
            issues.append({"key": "coach_tuned_out", "severity": "high",
                           "text": f"Coach is {rs_coach['level'].lower()} the room ({rs_coach['risk']:.0%} risk)."})
        if getattr(team, "line_control", "coach") == "gm" and win_pct >= 0.58:
            issues.append({"key": "gm_overstep", "severity": "medium",
                           "text": "GM is picking the lines on a winning team -- strong personalities are bristling."})
        for p in roster:
            try:
                val = coach_archetype_valuation(coach, p)
                ovr = p.overall_rating() if hasattr(p, "overall_rating") else 60
                rep = getattr(p, "reputation", 50) or 50
                pot = (getattr(p, "potential_grade", "") or "").upper()
                elite = ovr >= 70 or rep >= 60 or pot == "A"
                if elite and val < 0.9:
                    base = getattr(p, "base_controversy", 50)
                    if base is None:
                        base = controversy_baseline(p)
                    name = getattr(p, "full_name", "A player")
                    arch = getattr(p, "archetype", "player") or "player"
                    if base < 30:
                        issues.append({
                            "key": "underutilized", "severity": "low",
                            "text": f"{name} ({arch}) isn't credited by this system -- but he's laid back, so it doesn't matter to him. The fans and the league still see the draw; ask the coach to feature him (Advise Coach)."})
                    else:
                        issues.append({
                            "key": "underutilized", "severity": "medium",
                            "text": f"{name} ({arch}) is being undervalued in this system -- and he knows it. The fans and the league still see the draw; ask the coach to feature him (Advise Coach)."})
            except Exception:
                continue
        return issues
    except Exception:
        return issues


# ---------------------------------------------------------------------------
# GM advises coach
# ---------------------------------------------------------------------------

ADVICE_TYPES = {
    "ease_up": "Ease off the players",
    "crack_down": "Demand more in practice",
    "free_the_skill": "Give the skilled players more freedom",
    "more_structure": "Install more structure",
    "play_the_kids": "Play the young players more",
    "shorten_bench": "Lean on the veterans",
    "feature_player": "Feature a player (more ice time)",
}

_ADVICE_FALLOUT = {
    "ease_up": ("Coach eased off at the GM's suggestion -- the room exhales.", 4, None),
    "crack_down": ("Coach cracked down at the GM's suggestion -- practices got sharp, moods didn't.", -2, None),
    "free_the_skill": ("Coach freed up the skill players at the GM's suggestion.", 6, lambda p: (getattr(p, "flair", 50) or 50) >= 68),
    "more_structure": ("Coach installed more structure at the GM's suggestion.", 4, lambda p: engagement_style(p)["key"] == "thrives_on_structure"),
    "play_the_kids": ("Coach is playing the kids at the GM's suggestion.", 5, lambda p: (getattr(p, "age", 26) or 26) <= 23),
    "shorten_bench": ("Coach is leaning on the veterans at the GM's suggestion.", 4, lambda p: (getattr(p, "age", 26) or 26) >= 30),
}


def advise_coach(coach: Any, advice_key: str, team: Any = None,
                 roster: Optional[List[Any]] = None,
                 target_player: Any = None) -> Dict[str, Any]:
    """The GM advises the coach. Whether he listens depends on personality:
    adaptable communicators listen; brash, stubborn coaches take it as an
    insult. Trust (gm_trust) evolves with every exchange.
    advice_key 'feature_player' needs target_player: the GM asks the coach
    to give one specific player more ice time and a bigger role."""
    ensure_reputation_fields(coach)
    if not hasattr(coach, "gm_trust") or coach.gm_trust is None:
        coach.gm_trust = 70
    label = ADVICE_TYPES.get(advice_key, advice_key)
    if advice_key == "feature_player" and target_player is not None:
        label = f"Feature {getattr(target_player, 'full_name', 'player')} (more ice time)"
    brash = (coach.controversy or 0) >= 60
    try:
        adapt = getattr(coach, "adaptability", 50) or 50
        mm = getattr(coach, "man_management", 50) or 50
        p = (0.35 + adapt / 100 * 0.30
             + (100 - (coach.controversy or 0)) / 100 * 0.20
             + mm / 100 * 0.15
             + (coach.gm_trust - 70) / 100 * 0.50)
        if brash:
            p *= 0.6  # takes advice as an insult
        if advice_key == "feature_player":
            # Telling a coach WHO to play is personal. Stings more.
            p *= 0.85
        # If the GM holds the lineup pen, there's nothing to ask for.
        if advice_key == "feature_player" and team is not None and \
                getattr(team, "line_control", "coach") == "gm":
            return {"listened": True, "probability": 1.0,
                    "text": "You hold the lineup pen -- no need to ask. He's already playing.",
                    "gm_trust": coach.gm_trust}
        p = max(0.05, min(0.95, p))
        listened = random.random() < p
        cname = getattr(coach, "full_name", "Coach")
        if listened:
            coach.gm_trust = min(100, coach.gm_trust + 5)
            if advice_key == "feature_player" and target_player is not None:
                pname = getattr(target_player, "full_name", "The player")
                target_player.usage_featured = True
                target_player.happiness = min(100, (getattr(target_player, "happiness", 70) or 70) + 6)
                text = (f"{pname} is getting top-six minutes and a bigger role at the GM's request. "
                        f"He noticed.")
                if team is not None:
                    record_team_event(team, "gm_advice", f"GM advised: {label}. {text}",
                                      morale_delta=3, tone="up")
                return {"listened": True, "probability": round(p, 3),
                        "text": f"{cname} listened. {text}", "gm_trust": coach.gm_trust,
                        "featured": pname}
            text, delta, pred = _ADVICE_FALLOUT.get(advice_key, (f"Coach took the advice: {label}.", 2, None))
            n = _shift_happiness(roster or [], delta, pred)
            if team is not None:
                record_team_event(team, "gm_advice", f"GM advised: {label}. {text} ({n} players lifted).",
                                  morale_delta=delta, tone="up" if delta > 0 else "neutral")
            return {"listened": True, "probability": round(p, 3),
                    "text": f"{cname} listened. {text}", "gm_trust": coach.gm_trust}
        coach.gm_trust = max(0, coach.gm_trust - 8)
        if brash:
            text = f"{cname} bristled at the interference: 'I know my room.' Trust erodes."
        else:
            text = f"{cname} nodded politely... and changed nothing. Trust erodes."
        if team is not None:
            record_team_event(team, "gm_advice", f"GM advised: {label}. {text}",
                              morale_delta=-2, tone="down")
        return {"listened": False, "probability": round(p, 3),
                "text": text, "gm_trust": coach.gm_trust}
    except Exception:
        return {"listened": False, "probability": 0.0, "text": "Advice lost in the noise.",
                "gm_trust": getattr(coach, "gm_trust", 70)}


def unfeature_player(coach: Any, target_player: Any, team: Any = None) -> Dict[str, Any]:
    """The GM rescinds the feature request: back to whatever the coach decides."""
    try:
        target_player.usage_featured = False
        pname = getattr(target_player, "full_name", "The player")
        if team is not None:
            record_team_event(team, "gm_advice",
                              f"GM rescinded the feature request for {pname} -- usage is the coach's call again.",
                              morale_delta=0, tone="neutral")
        return {"ok": True, "text": f"{pname} is no longer a requested feature -- the coach decides his usage again."}
    except Exception:
        return {"ok": False, "text": "Nothing changed."}


# ---------------------------------------------------------------------------
# Line control: coach decides, or the GM takes the pen
# ---------------------------------------------------------------------------

def set_line_control(team: Any, who: str,
                     team_context: Optional[Dict[str, Any]] = None,
                     roster: Optional[List[Any]] = None) -> Dict[str, Any]:
    """who: 'coach' | 'gm'. Taking the lines on a WINNING team for no reason
    enrages strong personalities. Doing it on a loser is understood."""
    if not hasattr(team, "line_control") or team.line_control is None:
        team.line_control = "coach"
    who = "gm" if who == "gm" else "coach"
    if team.line_control == who:
        return {"changed": False, "text": f"Line control already with {who}."}
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    roster = roster or []
    team.line_control = who
    if who == "gm":
        if win_pct >= 0.58:
            # Great record, no reason: strong personalities take it personally.
            def strong(p):
                return (p.controversy or 0) >= 55 and (p.reputation or 0) >= 55
            n_strong = 0
            for p in roster:
                ensure_reputation_fields(p)
                try:
                    if strong(p):
                        p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 12)
                        p.controversy = min(100, (p.controversy or 0) + 5)
                        n_strong += 1
                    else:
                        p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
                except Exception:
                    pass
            text = (f"GM seized the lineup pen on a WINNING team ({win_pct:.0%}). "
                    f"{n_strong} strong personalities are furious -- why fix what isn't broken?")
            record_team_event(team, "line_control", text, morale_delta=-6, tone="down")
            return {"changed": True, "text": text, "strong_affected": n_strong}
        _shift_happiness(roster, 3, lambda p: (getattr(p, "happiness", 70) or 70) < 55)
        _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 27) or 27) >= 32)
        text = (f"GM took over the lines ({win_pct:.0%} record). Struggling players welcome the shake-up; "
                f"veterans are wary.")
        record_team_event(team, "line_control", text, morale_delta=1, tone="neutral")
        return {"changed": True, "text": text, "strong_affected": 0}
    _shift_happiness(roster, 2)
    text = "Coach has the lineup pen back. Clarity restored."
    record_team_event(team, "line_control", text, morale_delta=2, tone="up")
    return {"changed": True, "text": text, "strong_affected": 0}


# ---------------------------------------------------------------------------
# Coach ambitions, control need, and amicable line control
# ---------------------------------------------------------------------------
# Not every coach hears "I'm taking the lines" the same way. Babcock hears a
# threat; Cooper hears a conversation; a rookie promoted from the AHL hears
# the GM who believed in him. control_need (0-100) is the axis.

COACH_AMBITIONS = {
    "stanley_cup": "Win a Cup -- everything else is noise.",
    "climb": "Climb the ladder -- AHL success, then an NHL chair.",
    "developer": "Build the next generation.",
    "hometown": "Coach his boyhood team before he's done.",
    "lifer": "Content where he is; loves the day-to-day.",
}


def control_label(coach: Any) -> str:
    cn = getattr(coach, "control_need", 50) or 50
    if cn >= 70:
        return "Authoritarian"
    if cn >= 45:
        return "Demanding"
    if cn >= 25:
        return "Collaborative"
    return "Player-led"


def _dry_spell(ctx: Dict[str, Any]) -> bool:
    return ctx.get("losing_streak", 0) >= 3 or ctx.get("win_pct", 0.5) < 0.45


def preview_line_control_discussion(coach: Any,
                                    team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The GM sits the coach down: 'we're in a dry spell, let me try something
    with the lines.' Returns the coach's likely response BEFORE it happens,
    so the Morale screen can show it FM-style."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    cn = getattr(coach, "control_need", 50) or 50
    trust = getattr(coach, "gm_trust", 70) or 70
    adapt = getattr(coach, "adaptability", 50) or 50
    dry = _dry_spell(ctx)
    rookie = bool(getattr(coach, "first_nhl_chair", False)) and \
        (getattr(coach, "years_with_team", 0) or 0) <= 2
    cname = getattr(coach, "full_name", "Coach").split()[0]

    if rookie:
        return {"tone": "welcomes", "penalty": 0, "trust_delta": 3,
                "text": f"{cname} welcomes it -- you believed in him when nobody else did. "
                        f"He'll try anything within reason for the team (and his career)."}
    if cn <= 35:
        if dry:
            return {"tone": "accepts", "penalty": 0, "trust_delta": 2,
                    "text": f"{cname} gets it -- dry spell, willing to try anything. No hard feelings."}
        return {"tone": "accepts", "penalty": -2, "trust_delta": 0,
                "text": f"{cname} is a little surprised (things are fine), but he trusts you."}
    if cn < 70:
        if dry:
            return {"tone": "wary", "penalty": -2, "trust_delta": -2,
                    "text": f"{cname} is wary -- it's his room -- but the results force his hand."}
        return {"tone": "wary", "penalty": -5, "trust_delta": -4,
                "text": f"{cname} doesn't love being second-guessed while things are working."}
    # Authoritarian: Babcock hears a threat no matter how nicely it's phrased.
    if dry:
        return {"tone": "bristles", "penalty": -4, "trust_delta": -6,
                "text": f"{cname} bristles. Even asked nicely, he hears: you don't trust him."}
    return {"tone": "furious", "penalty": -8, "trust_delta": -10,
            "text": f"{cname} is furious. Taking his lines is taking his authority -- he'll remember this."}


def set_line_control(team: Any, who: str,
                     team_context: Optional[Dict[str, Any]] = None,
                     roster: Optional[List[Any]] = None,
                     coach: Any = None,
                     approach: str = "seize") -> Dict[str, Any]:
    """who: 'coach' | 'gm'. approach: 'seize' (nuclear) | 'discuss' (amicable:
    'we're in a dry spell, let me try something'). Discuss avoids major
    penalties when the coach's personality allows it."""
    if not hasattr(team, "line_control") or team.line_control is None:
        team.line_control = "coach"
    who = "gm" if who == "gm" else "coach"
    if team.line_control == who:
        return {"changed": False, "text": f"Line control already with {who}."}
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    roster = roster or []
    team.line_control = who

    if who == "coach":
        _shift_happiness(roster, 2)
        text = "Coach has the lineup pen back. Clarity restored."
        record_team_event(team, "line_control", text, morale_delta=2, tone="up")
        return {"changed": True, "text": text, "approach": approach}

    # ---- GM takes the pen ----
    if approach == "discuss" and coach is not None:
        prev = preview_line_control_discussion(coach, ctx)
        coach.gm_trust = max(0, min(100, (getattr(coach, "gm_trust", 70) or 70) + prev["trust_delta"]))
        pen = prev["penalty"]
        if pen:
            _shift_happiness(roster, pen)
        tone = "up" if prev["tone"] in ("welcomes", "accepts") else "down"
        text = f"GM discussed the lines with {getattr(coach, 'full_name', 'Coach')}. {prev['text']}"
        record_team_event(team, "line_control", text,
                          morale_delta=pen, tone=tone)
        return {"changed": True, "text": text, "approach": "discuss",
                "tone": prev["tone"], "strong_affected": 0}

    # ---- seize (nuclear option, unchanged) ----
    if win_pct >= 0.58:
        def strong(p):
            return (p.controversy or 0) >= 55 and (p.reputation or 0) >= 55
        n_strong = 0
        for p in roster:
            ensure_reputation_fields(p)
            try:
                if strong(p):
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 12)
                    p.controversy = min(100, (p.controversy or 0) + 5)
                    n_strong += 1
                else:
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
            except Exception:
                pass
        text = (f"GM seized the lineup pen on a WINNING team ({win_pct:.0%}). "
                f"{n_strong} strong personalities are furious -- why fix what isn't broken?")
        record_team_event(team, "line_control", text, morale_delta=-6, tone="down")
        return {"changed": True, "text": text, "approach": "seize",
                "strong_affected": n_strong}
    _shift_happiness(roster, 3, lambda p: (getattr(p, "happiness", 70) or 70) < 55)
    _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 27) or 27) >= 32)


# ---------------------------------------------------------------------------
# Tactics control: who owns the whiteboard
# ---------------------------------------------------------------------------
# Mirrors the line-control flow: the coach owns tactics by default. The GM
# can SUGGEST (the coach may say no), ENFORCE (overrule -- he won't forget),
# or TAKE OVER the whiteboard outright. Every response runs through the
# same personality factors: control_need, gm_trust, adaptability, form,
# and whether he's a rookie you believed in.

_TACTICS_CAT_LABEL = {"forecheck": "Forecheck",
                      "neutral_zone": "Neutral zone",
                      "dzone": "D-zone coverage", "ozone": "O-zone attack",
                      "breakout": "Breakout",
                      "pp": "Power play", "pk": "Penalty kill"}


def _tactics_coach(team: Any) -> Any:
    try:
        for stf in getattr(team, "staff", []) or []:
            if "Head Coach" in str(getattr(getattr(stf, "role", None), "value", "")):
                return stf
    except Exception:
        pass
    return None


def _changes_summary(changes: Dict[str, str]) -> str:
    bits = [_TACTICS_CAT_LABEL.get(c, c) for c in changes]
    if len(bits) == 1:
        return bits[0]
    return ", ".join(bits[:-1]) + " and " + bits[-1]


def preview_tactics_discussion(coach: Any, changes: Dict[str, str],
                               team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The GM floats tactical changes past the coach BEFORE committing.

    Returns his likely response: tone, text, trust_delta, accept_p.
    Same factors as the line-control discussion, plus how drastic the
    overhaul is -- ripping up the whole whiteboard scares any coach.
    """
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    cn = getattr(coach, "control_need", 50) or 50
    trust = getattr(coach, "gm_trust", 70) or 70
    adapt = getattr(coach, "adaptability", 50) or 50
    dry = _dry_spell(ctx)
    rookie = bool(getattr(coach, "first_nhl_chair", False)) and \
        (getattr(coach, "years_with_team", 0) or 0) <= 2
    cname = getattr(coach, "full_name", "Coach").split()[0]
    n = max(1, len(changes))
    ident = len(changes) >= 3  # ripping up 3+ modules is an identity change
    summ = _changes_summary(changes)

    # Likelihood he says yes -- personality is the major factor.
    p = 0.55
    p -= 0.006 * max(0, cn - 50)      # control freaks hate interference
    p += 0.006 * max(0, 50 - cn)      # collaborators welcome input
    p += 0.005 * max(0, trust - 70)   # trust buys latitude
    p -= 0.005 * max(0, 70 - trust)
    p += 0.004 * max(0, adapt - 50)   # flexible minds bend
    if dry:
        p += 0.15                      # losing forces hands
    if rookie:
        p += 0.20                      # he owes you
    p -= 0.07 * (n - 1)                # wholesale overhauls scare coaches
    if ident:
        p -= 0.10                      # identity overhauls scare coaches
    p = max(0.05, min(0.95, p))

    if rookie:
        return {"tone": "welcomes", "trust_delta": 3, "accept_p": p,
                "text": f"{cname} welcomes it -- you gave him his first chair. "
                        f"He'll run the {summ} changes tonight."}
    if cn <= 35:
        if dry:
            return {"tone": "accepts", "trust_delta": 2, "accept_p": p,
                    "text": f"{cname} gets it -- dry spell, and the {summ} tweak "
                            f"is worth a look. No hard feelings."}
        return {"tone": "accepts", "trust_delta": 0, "accept_p": p,
                "text": f"{cname} is a little surprised, but he trusts you. "
                        f"He'll try the {summ} change."}
    if cn < 70:
        if dry:
            return {"tone": "wary", "trust_delta": -2, "accept_p": p,
                    "text": f"{cname} is wary -- it's his system -- but the "
                            f"results force his hand on the {summ}."}
        return {"tone": "wary", "trust_delta": -4, "accept_p": p,
                "text": f"{cname} doesn't love being second-guessed on the "
                        f"{summ} while things are working."}
    if dry:
        return {"tone": "bristles", "trust_delta": -6, "accept_p": p,
                "text": f"{cname} bristles. Even asked nicely, he hears: "
                        f"you don't trust his {summ}."}
    return {"tone": "furious", "trust_delta": -10, "accept_p": p,
            "text": f"{cname} is furious. His {summ} is his authority -- "
                    f"question it and he'll remember."}


def _apply_tactic_changes(team: Any, changes: Dict[str, str],
                          mid_game: bool = False) -> int:
    n = 0
    try:
        import tactics as _tx
        for cat, key in changes.items():
            if _tx.set_team_system(team, cat, key, mid_game=mid_game):
                n += 1
    except Exception:
        pass
    return n


def _bump_trust(coach: Any, delta: int) -> None:
    try:
        coach.gm_trust = max(0, min(100, (getattr(coach, "gm_trust", 70) or 70) + delta))
    except Exception:
        pass


def suggest_tactics_to_coach(team: Any, changes: Dict[str, str],
                             team_context: Optional[Dict[str, Any]] = None,
                             mid_game: bool = False) -> Dict[str, Any]:
    """Float changes past the coach. He may accept (applies them) or refuse.

    Personality drives the likelihood -- see preview_tactics_discussion.
    """
    coach = _tactics_coach(team)
    if coach is None:
        n = _apply_tactic_changes(team, changes, mid_game=mid_game)
        return {"applied": True, "accepted": True, "n": n,
                "text": "No head coach in place -- changes applied directly."}
    prev = preview_tactics_discussion(coach, changes, team_context)
    accepted = random.random() < prev["accept_p"]
    summ = _changes_summary(changes)
    cname = getattr(coach, "full_name", "Coach").split()[0]
    if accepted:
        n = _apply_tactic_changes(team, changes, mid_game=mid_game)
        _bump_trust(coach, 3)
        text = (f"{cname} bought in -- the {summ} change is in. "
                f"He appreciates being asked first.")
        record_team_event(team, "tactics", text, morale_delta=1, tone="up")
        return {"applied": True, "accepted": True, "n": n, "tone": prev["tone"],
                "text": text}
    _bump_trust(coach, -2)
    text = (f"{cname} said no to the {summ} change. {prev['text']} "
            f"The whiteboard stays as it was.")
    record_team_event(team, "tactics", text, morale_delta=-1, tone="down")
    return {"applied": False, "accepted": False, "n": 0, "tone": prev["tone"],
            "text": text}


def enforce_tactics(team: Any, changes: Dict[str, str],
                    team_context: Optional[Dict[str, Any]] = None,
                    mid_game: bool = False) -> Dict[str, Any]:
    """The GM overrules the coach. It works -- and he won't forget it."""
    coach = _tactics_coach(team)
    n = _apply_tactic_changes(team, changes, mid_game=mid_game)
    summ = _changes_summary(changes)
    if coach is None:
        return {"applied": True, "n": n,
                "text": "Changes enforced -- no head coach in place."}
    ensure_reputation_fields(coach)
    cn = getattr(coach, "control_need", 50) or 50
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    cname = getattr(coach, "full_name", "Coach").split()[0]
    hit = int(round(4 + cn / 25.0))  # ~5 collaborators, ~8 authoritarians
    extra = ""
    if win_pct >= 0.58 and cn >= 70:
        hit += 2
        extra = " On a winning team, no less -- he'll remember this."
    _bump_trust(coach, -hit)
    text = (f"GM enforced the {summ} change over {cname}'s objections.{extra}")
    record_team_event(team, "tactics", text, morale_delta=-3, tone="down")
    return {"applied": True, "n": n, "trust_delta": -hit, "text": text}


def take_over_tactics(team: Any, team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The GM takes the whiteboard. The coach reacts as his makeup dictates."""
    coach = _tactics_coach(team)
    try:
        import tactics as _tx
        _tx.set_tactics_control(team, "gm")
    except Exception:
        pass
    if coach is None:
        return {"changed": True, "text": "You own the whiteboard -- no head coach in place."}
    ensure_reputation_fields(coach)
    cn = getattr(coach, "control_need", 50) or 50
    ctx = team_context or {}
    dry = _dry_spell(ctx)
    rookie = bool(getattr(coach, "first_nhl_chair", False)) and \
        (getattr(coach, "years_with_team", 0) or 0) <= 2
    cname = getattr(coach, "full_name", "Coach").split()[0]
    if rookie:
        _bump_trust(coach, 3)
        text = (f"{cname} hands over the whiteboard -- you believed in him, "
                f"and he'll learn watching you work it.")
        record_team_event(team, "tactics", text, morale_delta=1, tone="neutral")
        return {"changed": True, "trust_delta": 3, "text": text}
    if cn <= 35:
        _bump_trust(coach, 1 if dry else 0)
        text = (f"{cname} shrugs -- collaboration is his game. "
                f"The whiteboard is yours{' while the slump lasts' if dry else ''}.")
        record_team_event(team, "tactics", text, morale_delta=0, tone="neutral")
        return {"changed": True, "trust_delta": 1 if dry else 0, "text": text}
    if cn < 70:
        _bump_trust(coach, -6)
        text = (f"{cname} is stung. He'll coach your systems, but being "
                f"handed the whiteboard like an assistant smarts.")
        record_team_event(team, "tactics", text, morale_delta=-3, tone="down")
        return {"changed": True, "trust_delta": -6, "text": text}
    _bump_trust(coach, -10)
    text = (f"{cname} is livid. Taking his whiteboard is taking his job "
            f"in slow motion -- don't expect warmth at practice.")
    record_team_event(team, "tactics", text, morale_delta=-5, tone="down")
    return {"changed": True, "trust_delta": -10, "text": text}


def hand_back_tactics(team: Any) -> Dict[str, Any]:
    """Return the whiteboard to the coach. Systems stay; trust is repaired."""
    coach = _tactics_coach(team)
    try:
        import tactics as _tx
        _tx.set_tactics_control(team, "coach")
    except Exception:
        pass
    if coach is None:
        return {"changed": True, "text": "Whiteboard returned -- no head coach in place."}
    _bump_trust(coach, 4)
    cname = getattr(coach, "full_name", "Coach").split()[0]
    text = (f"{cname} has the whiteboard back. The systems stay as you left "
            f"them -- he's grateful for the trust.")
    record_team_event(team, "tactics", text, morale_delta=2, tone="up")
    return {"changed": True, "trust_delta": 4, "text": text}
    text = (f"GM took over the lines ({win_pct:.0%} record). Struggling players welcome the shake-up; "
            f"veterans are wary.")
    record_team_event(team, "line_control", text, morale_delta=1, tone="neutral")
    return {"changed": True, "text": text, "approach": "seize", "strong_affected": 0}


def coach_job_appeal(coach: Any, team: Any,
                     team_context: Optional[Dict[str, Any]] = None,
                     is_promotion: bool = False) -> Dict[str, Any]:
    """0-100: how badly does this coach want THIS job? Drives hiring logic."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    score = 50
    reasons: List[str] = []
    tname = getattr(team, "team_name", "")
    ambition = getattr(coach, "ambition", "climb") or "climb"

    if (getattr(coach, "favorite_team", "") or "") == tname:
        score += 30
        reasons.append("Boyhood team -- he'd run through a wall for this crest.")
        if ambition == "hometown":
            score += 10
            reasons.append("It's his stated life's ambition.")
    if ambition == "stanley_cup":
        if ctx.get("win_pct", 0.5) >= 0.58:
            score += 15
            reasons.append("Contender -- a Cup is within reach.")
        else:
            score -= 10
            reasons.append("Rebuild -- wastes his window.")
    elif ambition == "climb" and is_promotion:
        score += 12
        reasons.append("A step up the ladder.")
    elif ambition == "developer":
        score += 8
        reasons.append("Likes building -- roster age fits." if ctx.get("avg_age", 27) <= 26
                       else "Wants young players to mold.")
    elif ambition == "lifer":
        score -= 8
        reasons.append("Content where he is.")
    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons, "ambition": ambition,
            "ambition_label": COACH_AMBITIONS.get(ambition, ambition)}


def staffer_from_retired_player(player: Any, teams: List[Any]) -> Dict[str, Any]:
    """A player hangs them up and wants to coach. Carry what matters: his
    leadership, his boyhood team, and the logic that a Suzuki wants the Habs."""
    ensure_reputation_fields(player)
    attrs: Dict[str, Any] = {}
    attrs["leadership"] = max(35, min(95, int(getattr(player, "leadership", 50) or 50)))
    # Favorite team: 40% the sweater he retires in, else a random boyhood team.
    import random as _r
    tnames = [getattr(t, "team_name", "") for t in (teams or []) if getattr(t, "team_name", "")]
    fav = ""
    if tnames:
        last_team = getattr(player, "last_team_name", "") or ""
        if last_team in tnames and _r.random() < 0.40:
            fav = last_team
        else:
            fav = _r.choice(tnames)
    attrs["favorite_team"] = fav
    attrs["ambition"] = "hometown" if fav and _r.random() < 0.5 else "climb"
    attrs["control_need"] = max(10, min(90, int((getattr(player, "controversy", 30) or 30) * 0.8 + 20)))
    attrs["controversy"] = getattr(player, "controversy", 0) or 0
    # The man's nature follows him behind the bench: a hothead player
    # becomes a stubborn coach. And he keeps his pipeline -- the last
    # sweater he wore is where his guys are.
    generate_personality(player)
    attrs["base_controversy"] = getattr(player, "base_controversy", 20)
    attrs["influence"] = coach_influence_at_hire(
        name_value=getattr(player, "career_reputation", 0) or 0)
    last = getattr(player, "last_team_name", "") or getattr(player, "team_name", "")
    attrs["connections"] = [last] if last else []
    # Franchise icon: a star retiring in your sweater is YOUR legend.
    # (Coffey in Edmonton.) Only real stars qualify -- icons are earned.
    try:
        _rep = float(getattr(player, "career_reputation", 0) or 0)
        _gp = float(getattr(player, "career_games", 0) or 0)
        if last and _rep >= 65 and _gp >= 400:
            attrs["icon_team"] = last
            attrs["icon_level"] = "icon" if (_rep >= 80 and _gp >= 600) else "star"
    except Exception:
        pass
    return attrs


# ---------------------------------------------------------------------------
# Rivalries & bad blood
# ---------------------------------------------------------------------------
# FM24-style favourite/rival staff logic, extended: coach-coach, coach-player,
# GM-coach, GM-agent, player-player, and team-team (regional, playoff, brawl).
# Stored on the league (league.rivalries) so bad blood follows people when
# they change teams. Decay is personality-dependent: grudge-holders never
# really let go; career-cost (a lost Cup, a firing) keeps it hot.

RIVALRY_KINDS = ("coach_coach", "coach_player", "gm_coach", "gm_agent",
                 "gm_gm", "player_player", "team_team")

RIVALRY_ORIGINS = ("brawl_game", "playoff_series", "major_injury", "firing",
                   "heavy_hits", "award_race", "regional", "mistreatment",
                   "gm_power_struggle", "contract_dispute", "offer_sheet",
                   "declared")

# The classics. Regional hate never fully dies.
REGIONAL_RIVALRIES = frozenset([
    ("Calgary Flames", "Edmonton Oilers"),
    ("Toronto Maple Leafs", "Ottawa Senators"),
    ("Toronto Maple Leafs", "Montreal Canadiens"),
    ("Boston Bruins", "Montreal Canadiens"),
    ("New York Rangers", "New York Islanders"),
    ("New York Rangers", "New Jersey Devils"),
    ("Philadelphia Flyers", "Pittsburgh Penguins"),
    ("Pittsburgh Penguins", "Washington Capitals"),
    ("Chicago Blackhawks", "St. Louis Blues"),
    ("Los Angeles Kings", "Anaheim Ducks"),
    ("Florida Panthers", "Tampa Bay Lightning"),
    ("Vancouver Canucks", "Edmonton Oilers"),
    ("Colorado Avalanche", "Vegas Golden Knights"),
    ("Dallas Stars", "St. Louis Blues"),
])


def _ekey(entity: Any) -> tuple:
    """Stable identity key: ('player', id) | ('staff', id) | ('team', name) | ('gm', team) | ('agent', name)."""
    try:
        if isinstance(entity, str):
            return ("agent", entity)
        if hasattr(entity, "primary_position"):
            return ("player", getattr(entity, "id", getattr(entity, "full_name", "?")))
        if hasattr(entity, "role"):
            return ("staff", getattr(entity, "id", getattr(entity, "full_name", "?")))
        if hasattr(entity, "roster") and hasattr(entity, "team_name"):
            return ("team", getattr(entity, "team_name", "?"))
        if hasattr(entity, "gm_name"):
            return ("gm", getattr(entity, "team_name", "?"))
    except Exception:
        pass
    return ("unknown", str(entity))


def _ename(entity: Any) -> str:
    try:
        if isinstance(entity, str):
            return entity
        if hasattr(entity, "full_name"):
            return getattr(entity, "full_name", "?")
        if hasattr(entity, "team_name"):
            return getattr(entity, "team_name", "?")
    except Exception:
        pass
    return "?"


def _rivalry_store(league: Any) -> list:
    if not hasattr(league, "rivalries") or league.rivalries is None:
        league.rivalries = []
    return league.rivalries


def add_rivalry(rivalries: list, a: Any, b: Any, kind: str, intensity: int,
                origin: str, story: str, grudge: int = 50,
                career_cost: int = 0) -> Dict[str, Any]:
    """Add (or heat up) a rivalry. Merges with an existing one between the
    same pair: intensity takes the max, stories accumulate."""
    ka, kb = _ekey(a), _ekey(b)
    if ka == kb:
        return {}
    # Canonical ordering so (a,b) == (b,a).
    if ka > kb:
        ka, kb, a, b = kb, ka, b, a
    for r in rivalries:
        if r["a"] == ka and r["b"] == kb and r["kind"] == kind:
            r["intensity"] = max(r["intensity"], max(0, min(100, intensity)))
            r["grudge"] = max(r["grudge"], grudge)
            r["career_cost"] = max(r["career_cost"], career_cost)
            if story and story not in r["story"]:
                r["story"] = r["story"] + " " + story
            return r
    rec = {"a": ka, "b": kb, "a_name": _ename(a), "b_name": _ename(b),
           "kind": kind, "intensity": max(0, min(100, intensity)),
           "origin": origin, "story": story, "date": date.today().isoformat(),
           "grudge": max(0, min(100, grudge)),
           "career_cost": max(0, min(100, career_cost))}
    rivalries.append(rec)
    return rec


def get_rivalries_for(rivalries: list, entity: Any,
                      min_intensity: int = 1) -> List[Dict[str, Any]]:
    k = _ekey(entity)
    return sorted(
        [r for r in rivalries
         if (r["a"] == k or r["b"] == k) and r["intensity"] >= min_intensity],
        key=lambda r: -r["intensity"])


def rivalry_between(rivalries: list, a: Any, b: Any,
                    kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ka, kb = _ekey(a), _ekey(b)
    if ka > kb:
        ka, kb = kb, ka
    for r in rivalries:
        if r["a"] == ka and r["b"] == kb and (kind is None or r["kind"] == kind):
            return r
    return None


def decay_rivalries(rivalries: list, years: int = 1) -> int:
    """Offseason decay. Grudge-holders (high controversy/grudge) and people it
    cost something real (career_cost) barely cool off. Returns count removed."""
    removed = 0
    for r in list(rivalries):
        try:
            # Declared hate has a floor while the declaration stands;
            # regional hate never fully dies either.
            floor = int(r.get("declared_floor") or 0) if r.get("user_declared") \
                else (30 if r["origin"] == "regional" else 0)
            base = 8 * years
            slow = (1 - r["grudge"] / 150.0) * (1 - r["career_cost"] / 200.0)
            r["intensity"] = max(floor, r["intensity"] - base * max(0.15, slow))
            if r["intensity"] <= 5 and floor == 0:
                rivalries.remove(r)
                removed += 1
        except Exception:
            pass
    return removed


def bury_hatchet(rivalries: list, a: Any, b: Any, reason: str = "") -> bool:
    """Explicitly end it (won together, shook hands, time healed)."""
    r = rivalry_between(rivalries, a, b)
    if r:
        rivalries.remove(r)
        return True
    return False


def gm_persona(team: Any) -> Any:
    """The human GM as a rivalry entity. _ekey() reads this as
    ('gm', team_name), distinct from the team itself."""
    from types import SimpleNamespace
    gm = getattr(team, "gm_name", "General Manager") or "General Manager"
    tn = getattr(team, "team_name", "?") or "?"
    return SimpleNamespace(gm_name=gm, team_name=tn,
                           full_name=f"{gm} ({tn})")


def declare_rivalry(league: Any, a: Any, b: Any, kind: str = "team_team",
                    declared_by: str = "user") -> Dict[str, Any]:
    """The human GM publicly declares a rival: another team (team_team) or a
    person -- an opposing head coach (gm_coach).

    A declaration sets heat to at least 70 and, while it stands, the rivalry
    never cools below 40 and can never be buried by time. Only an explicit
    renounce ends it. Merges with any existing record between the pair.
    """
    if kind not in RIVALRY_KINDS:
        raise ValueError(f"unknown rivalry kind: {kind!r}")
    rivalries = _rivalry_store(league)
    an, bn = _ename(a), _ename(b)
    if kind == "team_team":
        story = (f"{an} publicly declared {bn} the enemy. Circle those "
                 f"dates on the calendar.")
    else:
        story = (f"{an} publicly declared {bn} a personal rival. "
                 f"This one is personal.")
    r = add_rivalry(rivalries, a, b, kind, 70, "declared", story, grudge=80)
    r["user_declared"] = True
    r["declared_floor"] = 40
    r["declared_by"] = declared_by
    return r


def renounce_rivalry(league: Any, a: Any, b: Any,
                     kind: Optional[str] = None) -> bool:
    """Take a declaration back. The record keeps its history but loses its
    floor and starts decaying like any other bad blood."""
    r = rivalry_between(_rivalry_store(league), a, b, kind)
    if not r or not r.get("user_declared"):
        return False
    r["user_declared"] = False
    r.pop("declared_floor", None)
    r["story"] = (r.get("story", "")
                  + " The declaration was renounced; the hate cools.").strip()
    return True


def _head_coach_of(team: Any) -> Optional[Any]:
    try:
        for stf in getattr(team, "staff", []) or []:
            if "Head Coach" in str(getattr(getattr(stf, "role", None), "value", "")):
                return stf
    except Exception:
        pass
    return None


def declare_rivalry_for_gm(league: Any, team: Any, target_team: Any,
                           target_kind: str = "team") -> tuple:
    """Resolve a GM's rivalry declaration and record it.

    target_kind 'team' -> team_team vs target_team; 'coach' -> gm_coach vs
    the target team's head coach. Returns (record, target_label).
    Raises ValueError on bad input.
    """
    tname = getattr(team, "team_name", None)
    if target_team is None or getattr(target_team, "team_name", None) in (None, tname):
        raise ValueError("pick another team as your rival")
    if target_kind == "team":
        rec = declare_rivalry(league, team, target_team, kind="team_team")
        return rec, getattr(target_team, "team_name", "?")
    if target_kind == "coach":
        coach = _head_coach_of(target_team)
        if coach is None:
            raise ValueError("they have no head coach to feud with")
        rec = declare_rivalry(league, gm_persona(team), coach, kind="gm_coach")
        return rec, getattr(coach, "full_name", "?")
    raise ValueError("target_kind must be 'team' or 'coach'")


def renounce_rivalry_for_gm(league: Any, team: Any, target_team: Any,
                            target_kind: str = "team") -> bool:
    """Renounce a live declaration. Returns True if one was renounced."""
    tname = getattr(team, "team_name", None)
    if target_team is None or getattr(target_team, "team_name", None) in (None, tname):
        return False
    if target_kind == "team":
        return renounce_rivalry(league, team, target_team, kind="team_team")
    if target_kind == "coach":
        coach = _head_coach_of(target_team)
        if coach is None:
            return False
        return renounce_rivalry(league, gm_persona(team), coach, kind="gm_coach")
    return False


def declared_rivalries_for(rivalries: list, team: Any) -> List[Dict[str, Any]]:
    """Live user-declared rivalries involving this team or its GM persona."""
    keys = {("team", getattr(team, "team_name", "?")),
            ("gm", getattr(team, "team_name", "?"))}
    return sorted(
        [r for r in (rivalries or [])
         if r.get("user_declared") and (r["a"] in keys or r["b"] in keys)],
        key=lambda r: -r.get("intensity", 0))


def seed_regional_rivalries(rivalries: list, teams: List[Any]) -> int:
    """Battle of Alberta etc. Intensity 55, high grudge: regional hate endures."""
    names = {getattr(t, "team_name", ""): t for t in (teams or [])}
    n = 0
    for n1, n2 in REGIONAL_RIVALRIES:
        if n1 in names and n2 in names:
            add_rivalry(rivalries, names[n1], names[n2], "team_team", 55,
                        "regional",
                        f"{n1} vs {n2}: regional hate. The building shakes for these games.",
                        grudge=75)
            n += 1
    return n


def record_brawl_game(rivalries: list, team_a: Any, team_b: Any,
                      coach_a: Any, coach_b: Any,
                      aggressor: str = "a", fights: int = 3) -> List[Dict[str, Any]]:
    """A coach sends his team out to punish the other: heavy hits, fights.
    The coaches carry it with them even if they change teams."""
    out = []
    agg_coach = coach_a if aggressor == "a" else coach_b
    vic_coach = coach_b if aggressor == "a" else coach_a
    out.append(add_rivalry(
        rivalries, agg_coach, vic_coach, "coach_coach", 45, "brawl_game",
        f"{_ename(agg_coach)} sent his team to punish {_ename(vic_coach)}'s: "
        f"{fights} fights, bad blood everywhere.",
        grudge=65))
    out.append(add_rivalry(
        rivalries, team_a, team_b, "team_team",
        30, "brawl_game",
        f"Brawl game: {fights} fights. These teams don't like each other.",
        grudge=55))
    return out


def record_playoff_series(rivalries: list, winner: Any, loser: Any,
                          games: int = 7, upset: bool = False) -> List[Dict[str, Any]]:
    out = []
    heat = 20 + (10 if games >= 7 else 0) + (10 if upset else 0)
    story = (f"Playoff series: {_ename(winner)} over {_ename(loser)} in {games}."
             + (" Seven games. Nobody forgot." if games >= 7 else "")
             + (" The upset stung." if upset else ""))
    out.append(add_rivalry(rivalries, winner, loser, "team_team", heat,
                           "playoff_series", story, grudge=60,
                           career_cost=40 if games >= 7 else 20))
    return out


def record_major_injury(rivalries: list, injured: Any, hitter: Any,
                        season_ending: bool = False) -> Dict[str, Any]:
    return add_rivalry(
        rivalries, injured, hitter, "player_player", 50, "major_injury",
        f"{_ename(hitter)} ended {_ename(injured)}'s "
        f"{'season' if season_ending else 'night'}. The room wants payback.",
        grudge=70, career_cost=60 if season_ending else 25)


def record_firing(rivalries: list, coach: Any, team: Any) -> Dict[str, Any]:
    """The firing: coach blames the GM. Follows the coach to his next job."""
    gm_name = f"{getattr(team, 'gm_name', 'GM')} ({getattr(team, 'team_name', '')})"
    grudge = min(90, 40 + (getattr(coach, "controversy", 0) or 0) // 2)
    return add_rivalry(
        rivalries, coach, gm_name, "gm_coach", 55, "firing",
        f"{_ename(coach)} was fired by {gm_name}. He blames the front office, not the room.",
        grudge=grudge, career_cost=50)


def record_award_race(rivalries: list, pa: Any, pb: Any, award: str) -> Dict[str, Any]:
    """An award race got personal -- but only for players with the
    personality to take it that way. A photo finish between two
    even-keeled pros is just a good race; it takes a hothead (or a
    fiery goalie) to carry it as a grudge. Gated on the LOCKED
    personality baseline (controversy_baseline: base_controversy dealt
    at generation from discipline/composure/aggressiveness), not the
    incident ratchet -- a saint who had one bad week doesn't suddenly
    take Hart snubs personally, and a quiet hothead still has the
    nature. Either man qualifying is enough: he's the one who bristles.
    Returns the record, or {} when neither man has the attitude."""
    def _takes_it_personally(p: Any) -> bool:
        try:
            if str(getattr(p, "goalie_temperament", "") or "").lower() == "fiery":
                return True
            return int(controversy_baseline(p)) >= 40
        except Exception:
            return False
    if not (_takes_it_personally(pa) or _takes_it_personally(pb)):
        return {}
    return add_rivalry(
        rivalries, pa, pb, "player_player", 25, "award_race",
        f"{_ename(pa)} vs {_ename(pb)}: {award} race got personal.",
        grudge=35)


def record_coach_player_beef(rivalries: list, coach: Any, player: Any,
                             reason: str) -> Dict[str, Any]:
    return add_rivalry(
        rivalries, coach, player, "coach_player", 40, "mistreatment",
        f"{_ename(coach)} vs {_ename(player)}: {reason}",
        grudge=55)


def record_agent_dispute(rivalries: list, agent_name: str, team: Any,
                         player: Any, issue: str) -> Dict[str, Any]:
    """GM-agent-player triangle: holdouts, lowball offers, tampering whispers."""
    gm_name = f"{getattr(team, 'gm_name', 'GM')} ({getattr(team, 'team_name', '')})"
    return add_rivalry(
        rivalries, agent_name,
        f"{gm_name} // {_ename(player)}", "gm_agent", 35, "contract_dispute",
        f"{agent_name} vs {gm_name} over {_ename(player)}: {issue}",
        grudge=45)


def get_rivalry_heat(rivalries: list, team_a: Any, team_b: Any,
                     coach_a: Any = None, coach_b: Any = None) -> Dict[str, Any]:
    """0-100 bad blood between two teams right now. Engine hook: high heat
    means more hits, more fights, tighter games."""
    heat = 0
    parts = []
    r = rivalry_between(rivalries, team_a, team_b, "team_team")
    if r:
        heat = max(heat, r["intensity"])
        parts.append(f"{r['a_name']} vs {r['b_name']}: {r['intensity']}")
    if coach_a is not None and coach_b is not None:
        rc = rivalry_between(rivalries, coach_a, coach_b, "coach_coach")
        if rc:
            heat = max(heat, rc["intensity"])
            parts.append(f"coaches: {rc['intensity']} ({rc['origin']})")
    heat = max(0, min(100, heat))
    return {"heat": heat,
            "label": "Simmering" if heat < 35 else "Heated" if heat < 65 else "Bad blood",
            "details": parts}


# ---------------------------------------------------------------------------
# Fan favourites
# ---------------------------------------------------------------------------
# Realistic parameters, in rough order of importance:
#   1. What they do on the ice (production) -- matters most.
#   2. Tenure -- the longer the sweater, the deeper the love.
#   3. Reputation + leadership -- stars and warriors.
#   4. Captaincy -- the C carries weight with fans.
#   5. Character -- box-office divas sell tickets while producing; fans turn
#      on expensive headaches fast.
#   6. Youth hype -- the 20-year-old phenom gets a bonus.

FAN_TIERS = [
    (85, "Beloved icon"),
    (70, "Fan favourite"),
    (55, "Popular"),
    (40, "Known quantity"),
    (0, "Anonymous"),
]


def _tenure_years(player: Any) -> int:
    t = str(getattr(player, "team_tenure", "") or "")
    try:
        if "This season" in t:
            return 0
        if "4+" in t:
            return 5
        import re as _re
        m = _re.search(r"(\d+)", t)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def fan_tier_label(score: float) -> str:
    for cutoff, label in FAN_TIERS:
        if score >= cutoff:
            return label
    return "Anonymous"


def fan_favourite_score(player: Any, team: Any = None) -> Dict[str, Any]:
    """0-100 how much the fans adore this player, and why."""
    ensure_reputation_fields(player)
    score = 15.0
    reasons: List[str] = []
    try:
        gp = max(1, getattr(player, "games_played", 1) or 1)
        pts = getattr(player, "points", 0) or 0
        ppg = pts / gp
        prod = min(30.0, ppg * 25)
        score += prod
        if ppg >= 1.0:
            reasons.append(f"Point-per-game star ({ppg:.2f} PPG)")
        elif ppg >= 0.6:
            reasons.append(f"Steady producer ({ppg:.2f} PPG)")

        yrs = _tenure_years(player)
        ten = min(15.0, yrs * 3)
        score += ten
        if yrs >= 4:
            reasons.append(f"{yrs}+ years in the sweater")

        rep = getattr(player, "reputation", 0) or 0
        score += rep * 0.15
        lead = getattr(player, "leadership", 50) or 50
        score += lead * 0.10
        if lead >= 80:
            reasons.append("Warrior -- leaves it all out there")

        role = str(getattr(player, "captaincy", "") or "").upper()
        if role == "C":
            score += 8
            reasons.append("Wears the C")
        elif role == "A":
            score += 4

        vol = getattr(player, "controversy", 0) or 0
        if vol >= 70:
            if ppg >= 0.8:
                score += 8
                reasons.append("Box-office -- fans love the theatre")
            else:
                score -= 12
                reasons.append("Expensive headache -- fans have turned")
        elif vol <= 20 and lead >= 60:
            score += 4
            reasons.append("Model pro")

        age = getattr(player, "age", 27) or 27
        if age <= 22 and ppg >= 0.7:
            score += 5
            reasons.append("Phenom hype")
    except Exception:
        pass
    score = max(0, min(100, round(score)))
    return {"score": score, "tier": fan_tier_label(score), "reasons": reasons}


def is_fan_favourite(player: Any, team: Any = None) -> bool:
    try:
        return fan_favourite_score(player, team)["score"] >= 70
    except Exception:
        return False


def coach_fan_appeal(coach: Any,
                     team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """0-100: how much the fans like the coach. Winning cures everything;
    player's coaches are loved, drill sergeants are respected (not loved)."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    score = 40.0
    reasons: List[str] = []
    try:
        wp = ctx.get("win_pct", 0.5)
        score += max(0.0, min(1.0, wp)) * 35
        if wp >= 0.6:
            reasons.append("Winning -- fans love a winner")
        yrs = getattr(coach, "years_with_team", 0) or 0
        score += min(10.0, yrs * 2)
        style = coach_style(coach)["label"]
        if style == "Player's Coach":
            score += 10
            reasons.append("Player's coach -- easy to love")
        elif style == "Drill Sergeant":
            score -= 5
            reasons.append("Demanding -- respected more than loved")
        vol = getattr(coach, "controversy", 0) or 0
        score -= vol * 0.1
        if (getattr(coach, "favorite_team", "") or "") == ctx.get("team_name", ""):
            score += 8
            reasons.append("One of our own")
    except Exception:
        pass
    score = max(0, min(100, round(score)))
    return {"score": score, "tier": fan_tier_label(score), "reasons": reasons}


# ---------------------------------------------------------------------------
# Friend / rival formation
# ---------------------------------------------------------------------------
# Whether two players become friends or rivals depends on character
# (controversy/leadership similarity), attributes (age, position group,
# nationality), and where each sits in the room hierarchy (same tier bonds;
# distant tiers grate). Stored on player.relationships: {other_id: -100..100}.

def _pos_group(p: Any) -> str:
    try:
        pos = str(getattr(p, "primary_position", "") or "").upper()
        if "GOAL" in pos or pos == "G":
            return "G"
        if "DEFEN" in pos or pos in ("LD", "RD", "D"):
            return "D"
        return "F"
    except Exception:
        return "F"


def bond_likelihood(a: Any, b: Any,
                    tier_of: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """0-100 friendship likelihood and 0-100 rivalry likelihood for a pair."""
    ensure_reputation_fields(a)
    ensure_reputation_fields(b)
    friendship = 30.0
    rivalry = 8.0
    reasons: List[str] = []
    try:
        if tier_of:
            ta, tb = tier_of.get(id(a)), tier_of.get(id(b))
            if ta and tb:
                if ta == tb:
                    friendship += 20
                    reasons.append(f"Same standing ({ta})")
                else:
                    order = ["Team Leaders", "Core Group", "Squad Players", "Fringe"]
                    gap = abs(order.index(ta) - order.index(tb))
                    if gap >= 2:
                        rivalry += 12
                        reasons.append("Different worlds in the room")
        ca, cb = (a.controversy or 0), (b.controversy or 0)
        if abs(ca - cb) <= 15:
            friendship += 12
            reasons.append("Similar temperaments")
        elif max(ca, cb) >= 65 and abs(ca - cb) >= 40:
            rivalry += 25
            reasons.append("Oil and water")
        la, lb = (getattr(a, "leadership", 50) or 50), (getattr(b, "leadership", 50) or 50)
        if la >= 70 and lb >= 70:
            friendship += 10
            reasons.append("Mutual respect of leaders")
        age_gap = abs((getattr(a, "age", 27) or 27) - (getattr(b, "age", 27) or 27))
        if age_gap <= 3:
            friendship += 8
        elif age_gap >= 9:
            rivalry += 6
            reasons.append("Generation gap")
        if _pos_group(a) == _pos_group(b):
            friendship += 6
        na, nb = str(getattr(a, "nationality", "") or ""), str(getattr(b, "nationality", "") or "")
        if na and na == nb:
            friendship += 4
    except Exception:
        pass
    return {"friendship": max(0, min(100, round(friendship))),
            "rivalry": max(0, min(100, round(rivalry))),
            "reasons": reasons}


def _ensure_relationships(p: Any) -> dict:
    ensure_reputation_fields(p)
    if not hasattr(p, "relationships") or not isinstance(getattr(p, "relationships", None), dict):
        p.relationships = {}
    if not hasattr(p, "coach_bonds") or not isinstance(getattr(p, "coach_bonds", None), dict):
        p.coach_bonds = {}
    return p.relationships


def nudge_relationship(a: Any, b: Any, delta: int,
                       reason: str = "") -> None:
    """Directly move one pair (events: brawl together, betrayal, ...)."""
    try:
        ra, rb = _ensure_relationships(a), _ensure_relationships(b)
        v = max(-100, min(100, ra.get(b.id, 0) + delta))
        ra[b.id] = v
        rb[a.id] = v
    except Exception:
        pass


def evolve_relationships(roster: List[Any], league: Any = None,
                         months: int = 1, seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Monthly roll: friendships and rivalries form and deepen on their own.
    Returns notable new developments for the dynamics feed."""
    import random as _r
    rng = _r.Random(seed)
    for p in roster:
        _ensure_relationships(p)
    tiers = team_hierarchy(roster)
    tier_of = {id(p): t for t, ps in tiers.items() for p in ps}
    league_rivs = list(getattr(league, "rivalries", []) or []) if league else []
    notable: List[Dict[str, Any]] = []
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            try:
                bl = bond_likelihood(a, b, tier_of)
                cur = a.relationships.get(b.id, 0)
                target = bl["friendship"] - bl["rivalry"]
                lr = rivalry_between(league_rivs, a, b) if league_rivs else None
                if lr:
                    target = min(target, -lr["intensity"])
                rate = 0.12 * months * (1.6 if lr else 1.0)  # bad blood festers fast
                step = (target - cur) * rate + rng.uniform(-3, 3)
                new = max(-100, min(100, round(cur + step)))
                a.relationships[b.id] = new
                b.relationships[a.id] = new
                if cur < 40 <= new:
                    notable.append({"kind": "friendship", "a": a, "b": b, "value": new})
                elif cur > -40 >= new:
                    notable.append({"kind": "rift", "a": a, "b": b, "value": new})
            except Exception:
                pass
    return notable


def get_friends(player: Any, roster: List[Any], n: int = 3) -> List[Dict[str, Any]]:
    rels = _ensure_relationships(player)
    scored = [(rels.get(p.id, 0), p) for p in roster if p is not player]
    scored.sort(key=lambda t: -t[0])
    return [{"player": p, "score": s} for s, p in scored[:n] if s >= 30]


def get_rivals(player: Any, roster: List[Any], league: Any = None,
               n: int = 3) -> List[Dict[str, Any]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    rels = _ensure_relationships(player)
    scored = [(rels.get(p.id, 0), p) for p in roster if p is not player]
    scored.sort(key=lambda t: t[0])
    for s, p in scored:
        if s <= -30:
            by_name[getattr(p, "full_name", "?")] = {
                "name": getattr(p, "full_name", "?"), "score": s,
                "origin": "locker room"}
    if league is not None:
        for r in get_rivalries_for(getattr(league, "rivalries", []) or [], player):
            other = r["b_name"] if r["a"] == _ekey(player) else r["a_name"]
            origin = r["origin"].replace("_", " ") + (" (entrenched)" if r.get("solidified") else "")
            entry = {"name": other, "score": -r["intensity"], "origin": origin}
            if other in by_name:
                by_name[other]["score"] = min(by_name[other]["score"], entry["score"])
                by_name[other]["origin"] = entry["origin"]
            else:
                by_name[other] = entry
    out = sorted(by_name.values(), key=lambda d: d["score"])
    return out[:n]


# ---------------------------------------------------------------------------
# Reactions to developments: fan favourites change how news lands
# ---------------------------------------------------------------------------
# The room and the fanbase react to what happens to a player or coach.
# Fan favourites amplify everything: burying one is a scandal, extending one
# is a parade.

def _apply_room_shift(roster: List[Any], delta: int,
                      only: Optional[Any] = None) -> None:
    for p in roster:
        try:
            if only is None or only(p):
                p.happiness = max(0, min(100, (getattr(p, "happiness", 70) or 70) + delta))
        except Exception:
            pass


def player_news_reaction(team: Any, player: Any, kind: str,
                         roster: List[Any],
                         league: Any = None) -> Dict[str, Any]:
    """kind: trade_rumor | benched | injured | milestone | award |
    retirement | extension_signed. Returns what happened."""
    ensure_reputation_fields(player)
    ff = fan_favourite_score(player, team)
    fav = ff["score"] >= 70
    name = getattr(player, "full_name", "Player").split()
    name = name[0] if name else "Player"
    friends = [p for p in roster
               if p is not player and _ensure_relationships(p).get(player.id, 0) >= 50]
    room = 0
    fan = 0
    texts: List[str] = []
    if kind == "trade_rumor":
        room -= 2
        fan -= 15 if fav else 4
        texts.append(f"Trade winds around {name} are a distraction.")
        if fav:
            texts.append(f"The fans are furious -- {name} is a {ff['tier'].lower()}.")
        _apply_room_shift(friends, -2)
    elif kind == "benched":
        room -= 3 if fav else 1
        fan -= 12 if fav else 3
        texts.append(f"{name} benched." + (" The building boos." if fav else ""))
        _apply_room_shift(friends, -3)
    elif kind == "injured":
        tiers = team_hierarchy(roster)
        leader = player in tiers.get("Team Leaders", [])
        room -= 3 if leader else 1
        fan -= 8 if fav else 2
        texts.append(f"{name} hurt." + (" The room feels it." if leader else ""))
        _apply_room_shift(friends, -2)
    elif kind in ("milestone", "award"):
        room += 2
        fan += 10 if fav else 4
        texts.append(f"{name} honoured -- the room loves it."
                     + (" The city is buzzing." if fav else ""))
        _apply_room_shift(friends, 2)
        _apply_room_shift(roster, 1)
    elif kind == "retirement":
        room -= 2 if fav else 1
        fan -= 10 if fav else 3
        texts.append(f"{name} hangs them up."
                     + (" End of an era." if fav else ""))
    elif kind == "extension_signed":
        room += 2 if fav else 1
        fan += 12 if fav else 3
        texts.append(f"{name} extended."
                     + (" The fans are delighted." if fav else ""))
    else:
        texts.append(f"{name}: {kind}.")
    if room:
        _apply_room_shift(roster, room)
    tone = "up" if room > 0 else "down" if room < 0 else "neutral"
    record_team_event(team, "player_news",
                      " ".join(texts) + (f" (Fan impact: {fan:+d}.)" if fan else ""),
                      morale_delta=room, tone=tone)
    return {"room_delta": room, "fan_delta": fan, "fan_favourite": fav,
            "fan_score": ff["score"], "friends_affected": len(friends),
            "text": " ".join(texts)}


def coach_news_reaction(team: Any, coach: Any, kind: str,
                        roster: List[Any],
                        team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """kind: fired | hired | line_seize | extension | milestone_win."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    appeal = coach_fan_appeal(coach, ctx)
    loved = appeal["score"] >= 70
    cname = getattr(coach, "full_name", "Coach").split()[0]
    room = 0
    fan = 0
    texts: List[str] = []
    if kind == "fired":
        wp = ctx.get("win_pct", 0.5)
        if wp < 0.45 and (getattr(coach, "controversy", 0) or 0) >= 60:
            fan += 5
            texts.append(f"{cname} fired. Sections of the fanbase say good riddance.")
        else:
            room -= 4
            fan -= 20 if loved else 8
            texts.append(f"{cname} fired."
                         + (" The fans are livid -- he was beloved." if loved else ""))
        try:
            for p in roster:
                if player_coach_response(p, coach, ctx)["label"] == "Bought in":
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
        except Exception:
            pass
    elif kind == "hired":
        fav_team = (getattr(coach, "favorite_team", "") or "") == getattr(team, "team_name", "")
        room += 2
        fan += 10 if fav_team else 4
        texts.append(f"{cname} hired as head coach."
                     + (" A hometown hero -- the city is thrilled." if fav_team else ""))
    elif kind == "line_seize":
        room -= 2
        fan -= 6 if loved else 2
        texts.append(f"GM took {cname}'s lines."
                     + (" Talk radio is ablaze." if loved else ""))
    elif kind == "extension":
        room += 2
        fan += 8 if loved else 3
        texts.append(f"{cname} extended." + (" The fans approve." if loved else ""))
    elif kind == "milestone_win":
        room += 2
        fan += 8 if loved else 4
        texts.append(f"Milestone win for {cname}.")
    if room:
        _apply_room_shift(roster, room)
    tone = "up" if room > 0 else "down" if room < 0 else "neutral"
    record_team_event(team, "coach_news", " ".join(texts),
                      morale_delta=room, tone=tone)
    return {"room_delta": room, "fan_delta": fan, "fan_appeal": appeal["score"],
            "text": " ".join(texts)}


# Fan favourites take discounts to stay: loyalty nudge inside contract_loyalty.
_orig_contract_loyalty = contract_loyalty


def contract_loyalty(player: Any) -> float:  # noqa: F811
    base = _orig_contract_loyalty(player)
    try:
        if is_fan_favourite(player):
            base = min(0.98, base + 0.08)
    except Exception:
        pass
    return base


# ---------------------------------------------------------------------------
# Rivalry reviews: solidification every few years
# ---------------------------------------------------------------------------
# Every few years each rivalry gets a verdict: does it fade, simmer on, or
# SOLIDIFY into permanent bad blood? Stronger implications dominate the
# verdict -- a season-ending injury calcifies; just chirping along with a
# regional rivalry fades when the context changes.

RIVALRY_ORIGIN_WEIGHT = {
    "declared": 70,          # a public declaration carries real weight
    "major_injury": 90,      # personal, career-affecting -- never really dies
    "brawl_game": 75,        # personal escalation
    "mistreatment": 70,
    "firing": 70,
    "playoff_series": 60,    # 7-game wars can calcify
    "heavy_hits": 55,
    "gm_power_struggle": 50,
    "contract_dispute": 45,
    "award_race": 35,
    "regional": 25,          # just encouraged the rivalry -- ambient
}

# Origins personal enough that the bad blood belongs to the MAN, not the sweater.
PERSONAL_ORIGINS = {"major_injury", "brawl_game", "mistreatment", "heavy_hits"}


def review_rivalries(rivalries: list, years: int = 3) -> List[Dict[str, Any]]:
    """Every few years: solidify, simmer, fade, or bury each rivalry.
    Returns the verdicts (useful for an offseason news feed)."""
    verdicts: List[Dict[str, Any]] = []
    for r in list(rivalries):
        try:
            # Old wounds eventually stop mattering for the nightly tension.
            if isinstance(r.get("incidents"), list):
                r["incidents"] = [i for i in r["incidents"]
                                  if _incident_games_ago(i) <= 164]
            if r.get("user_declared"):
                # A live declaration doesn't fade or get buried by time --
                # only an explicit renounce ends it.
                floor = int(r.get("declared_floor") or 40)
                r["intensity"] = max(floor, r["intensity"] - 1 * years)
                verdicts.append({"rivalry": r, "outcome": "declared",
                                 "text": f"{r['a_name']} vs {r['b_name']}: declared "
                                         f"rivalry, still burning ({r['intensity']:.0f})."})
                continue
            if r.get("solidified"):
                # Entrenched: barely cools, never dies on its own.
                r["intensity"] = max(60, r["intensity"] - 1 * years)
                verdicts.append({"rivalry": r, "outcome": "entrenched",
                                 "text": f"{r['a_name']} vs {r['b_name']}: entrenched. "
                                         f"This one isn't going away."})
                continue
            strength = RIVALRY_ORIGIN_WEIGHT.get(r["origin"], 40)
            # Stronger implications play the biggest factor.
            score = (strength * 0.45 + r["grudge"] * 0.25
                     + r["career_cost"] * 0.15 + r["intensity"] * 0.15)
            if score >= 68:
                r["solidified"] = True
                r["intensity"] = max(r["intensity"], 65)
                verdicts.append({"rivalry": r, "outcome": "solidified",
                                 "text": f"{r['a_name']} vs {r['b_name']}: SOLIDIFIED. "
                                         f"{r['story'][:80]}"})
            elif score >= 42:
                r["intensity"] = max(20, r["intensity"] - 4 * years)
                verdicts.append({"rivalry": r, "outcome": "simmering",
                                 "text": f"{r['a_name']} vs {r['b_name']}: still simmering "
                                         f"({r['intensity']:.0f})."})
            else:
                # Regional hate has a floor: it never fully dies.
                floor = 30 if r["origin"] == "regional" else 0
                r["intensity"] = max(floor, r["intensity"] - 10 * years)
                if r["intensity"] <= 5 and floor == 0:
                    rivalries.remove(r)
                    verdicts.append({"rivalry": r, "outcome": "buried",
                                     "text": f"{r['a_name']} vs {r['b_name']}: buried. "
                                             f"Time healed it."})
                elif floor and r["intensity"] <= floor:
                    verdicts.append({"rivalry": r, "outcome": "enduring",
                                     "text": f"{r['a_name']} vs {r['b_name']}: enduring "
                                             f"({r['intensity']:.0f}) -- some hate never dies."})
                else:
                    verdicts.append({"rivalry": r, "outcome": "fading",
                                     "text": f"{r['a_name']} vs {r['b_name']}: fading "
                                             f"({r['intensity']:.0f})."})
        except Exception:
            pass
    return verdicts


def on_player_transfer(rivalries: list, player: Any,
                       from_team: Any = None,
                       to_team: Any = None) -> Dict[str, Any]:
    """A player changes sweaters. Personal bad blood (injuries, personal
    escalation) follows the MAN -- it's his, not the team's. Ambient stuff he
    merely 'encouraged' (regional chirping, mild award races) is left behind
    or cools to almost nothing."""
    try:
        player.usage_featured = False  # new room, new coach, no standing request
    except Exception:
        pass
    carried: List[Dict[str, Any]] = []
    left: List[Dict[str, Any]] = []
    try:
        for r in list(get_rivalries_for(rivalries, player)):
            if r["kind"] not in ("player_player", "coach_player", "gm_coach"):
                continue
            if r["origin"] in PERSONAL_ORIGINS or r.get("solidified") or r["intensity"] >= 50:
                carried.append(r)
            elif r["intensity"] < 35:
                rivalries.remove(r)
                left.append(r)
            else:
                r["intensity"] = max(10, r["intensity"] - 25)
                left.append(r)
    except Exception:
        pass
    return {"carried": carried, "left_behind": left,
            "text": (f"{_ename(player)} moved. "
                     f"{len(carried)} personal beef(s) follow him; "
                     f"{len(left)} ambient one(s) left behind.")}


# ---------------------------------------------------------------------------
# National teammates
# ---------------------------------------------------------------------------
# International tournaments cut across NHL bad blood. Winning together --
# especially for leaders -- forges bonds; even real NHL enemies can bury it
# after a gold-medal run. A disaster can scar instead.

def apply_international_tournament(rivalries: list, players: List[Any],
                                   nation: str, result: str) -> Dict[str, Any]:
    """result: gold | silver | bronze | early_exit. players: same-nation
    participants. Returns what changed."""
    result = (result or "").lower()
    bond = {"gold": 12, "silver": 8, "bronze": 6}.get(result, 4)
    soften = {"gold": 25, "silver": 15, "bronze": 8}.get(result, 0)
    buried: List[Dict[str, Any]] = []
    bonded = 0
    try:
        for i, a in enumerate(players):
            ensure_reputation_fields(a)
            for b in players[i + 1:]:
                ensure_reputation_fields(b)
                # Shared triumph bonds; leaders bond hardest.
                la = getattr(a, "leadership", 50) or 50
                lb = getattr(b, "leadership", 50) or 50
                extra = 6 if (la >= 70 and lb >= 70) else 0
                nudge_relationship(a, b, bond + extra,
                                   f"{nation} {result} together")
                bonded += 1
                # NHL bad blood can be overcome by winning together.
                r = rivalry_between(rivalries, a, b)
                if r and soften:
                    r["intensity"] -= soften
                    if r["intensity"] <= 10 and not r.get("solidified"):
                        rivalries.remove(r)
                        buried.append(r)
                    elif r.get("solidified") and r["intensity"] < 60:
                        # Even entrenched hate thaws a little.
                        r["intensity"] = 60
        if result == "gold":
            for p in players:
                try:
                    p.reputation = min(100, (getattr(p, "reputation", 0) or 0) + 2)
                except Exception:
                    pass
    except Exception:
        pass
    medal = {"gold": "GOLD", "silver": "silver", "bronze": "bronze"}.get(result, "early exit")
    return {"bonded_pairs": bonded, "buried": buried,
            "text": (f"{nation} {medal}: {bonded} pair(s) bonded. "
                     + (f"{len(buried)} NHL beef(s) buried." if buried else ""))}


# ---------------------------------------------------------------------------
# In-game punishment: coaches sending guys out, and who answers
# ---------------------------------------------------------------------------
# The Maurice scenario: getting blown out in a Cup Final game, he sends his
# guys to wear the other team down for tomorrow. The Knoblauch archetype
# would never -- character forbids it. Tortorella would be livid and answer
# in kind. Personality first, situation second.

def game_tension(home_team: Any, away_team: Any, rivalries: list,
                 is_playoff: bool = False, series_game: int = 0) -> float:
    """0-100: how much bad blood is in the building tonight."""
    try:
        t = 0.0
        for r in rivalries:
            if r["kind"] == "team_team":
                names = {r["a_name"], r["b_name"]}
                hn = getattr(home_team, "team_name", "")
                an = getattr(away_team, "team_name", "")
                if hn in names and an in names:
                    t += r["intensity"] * 0.6
        if is_playoff:
            t += 15 + max(0, series_game) * 2
        return round(min(100.0, t), 1)
    except Exception:
        return 0.0


def coach_reprisal_tendency(coach: Any) -> float:
    """0 = would never send guys out (Knoblauch). 1 = always will (Tortorella)."""
    try:
        style = coach_style(coach)["label"]
        t = 0.30
        if style == "Drill Sergeant":
            t += 0.35
        elif style == "Motivator":
            t += 0.15
        elif style == "Player's Coach":
            t -= 0.25
        t += (getattr(coach, "controversy", 20) or 20) / 100 * 0.30
        t += (getattr(coach, "discipline", 50) or 50) / 100 * 0.10
        return round(max(0.0, min(1.0, t)), 3)
    except Exception:
        return 0.3


def order_punishment(coach: Any, team: Any, game_state: Dict[str, Any],
                     rivalries: Optional[list] = None) -> Dict[str, Any]:
    """Does the coach send his guys out to punish the other team?
    game_state: score_diff (team's perspective), period, is_playoff,
    opponent, tension.
    The ORDERED team gets the bigger modifier -- the order carries weight
    the mere retaliation doesn't."""
    try:
        tendency = coach_reprisal_tendency(coach)
        sd = game_state.get("score_diff", 0)
        period = game_state.get("period", 1)
        is_playoff = game_state.get("is_playoff", False)
        tension = game_state.get("tension", 0)
        # Personality alone can never order it: even the hottest coach maxes at
        # 0.55 on a calm night. It takes a situation -- a blowout, bad blood,
        # running it up -- to push anyone over the line. (Torts doesn't send
        # the boys out on a quiet Tuesday either.)
        score = tendency * 0.55
        reasons: List[str] = []
        if sd <= -3 and is_playoff:
            score += 0.35
            reasons.append("blown out in a playoff game -- wear them down for tomorrow")
        elif sd <= -3:
            score += 0.15
            reasons.append("getting run out of the building")
        elif sd <= -2 and period >= 3:
            score += 0.10
            reasons.append("game slipping away late")
        if tension >= 60:
            score += 0.15
            reasons.append("bad blood already boiling over")
        if game_state.get("running_it_up"):
            score += 0.10
            reasons.append("they're running it up")
        ordered = score >= 0.75
        cname = getattr(coach, "full_name", "Coach")
        if not ordered:
            story = f"{cname} keeps it clean. No order sent."
            if tension >= 60:
                story += " The room remembers, but this isn't who they are."
            return {"ordered": False, "tendency": tendency, "score": round(score, 3),
                    "reasons": reasons, "tension": tension, "story": story}
        # It happened: the building knows, and so does the league.
        if rivalries is not None:
            try:
                opp = game_state.get("opponent")
                if opp is not None:
                    opp_coach = getattr(opp, "head_coach", None)
                    if opp_coach is None:
                        opp_coach = opp_head_coach_of(rivalries, opp)
                    record_brawl_game(rivalries, team, opp, coach, opp_coach,
                                      aggressor="a", fights=4)
            except Exception:
                pass
        return {"ordered": True, "tendency": tendency, "score": round(score, 3),
                "reasons": reasons,
                "instigator_mod": 1.25,    # the ordered team: +25% physical impact
                "retaliation_mod": 1.10,   # the answer: smaller, reactive
                "story": f"{cname} sent them out: {'; '.join(reasons)}."}
    except Exception:
        return {"ordered": False, "tendency": 0.3, "score": 0.0,
                "reasons": [], "story": "No order."}


def opp_head_coach_of(rivalries: list, team: Any) -> Any:
    """Best-effort lookup of a team's head coach for rivalry records."""
    try:
        hc = getattr(team, "head_coach", None)
        if hc is not None:
            return hc
    except Exception:
        pass
    # Fallback: a lightweight stand-in keyed by team so the record still lands.
    class _StandIn:
        pass
    s = _StandIn()
    s.id = f"hc_{getattr(team, 'team_name', 'unknown')}"
    s.full_name = f"{getattr(team, 'team_name', 'Opponent')} head coach"
    return s


def respond_to_punishment(coach: Any, game_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """They're running your guys. Do you answer?
    Tortorella: livid, retaliates, tension +20. Knoblauch: composed, never."""
    try:
        tendency = coach_reprisal_tendency(coach)
        cname = getattr(coach, "full_name", "Coach")
        if tendency >= 0.65:
            return {"responds": True, "tone": "livid",
                    "retaliation_mod": 1.15, "tension_delta": 20,
                    "story": f"{cname} is LIVID on the bench -- the response is coming, "
                             f"and it's coming hard."}
        if tendency >= 0.35:
            return {"responds": True, "tone": "measured",
                    "retaliation_mod": 1.05, "tension_delta": 10,
                    "story": f"{cname} answers it -- measured, but they won't be pushed around."}
        tension = (game_state or {}).get("tension", 0)
        story = f"{cname} keeps the bench calm. 'We play hockey. We don't do that.'"
        simmer = False
        if tension >= 60:
            # We won't forget -- but this group isn't the type to answer.
            simmer = True
            story += (" The room is seething, though. They won't forget this one.")
        return {"responds": False, "tone": "composed",
                "retaliation_mod": 1.0, "tension_delta": 0,
                "simmer": simmer, "carried_tension": tension if simmer else 0,
                "story": story}
    except Exception:
        return {"responds": False, "tone": "composed", "retaliation_mod": 1.0,
                "tension_delta": 0, "story": "No response."}


# ---------------------------------------------------------------------------
# NHL-grounded violence rates: fights, tussles, and line brawls
# ---------------------------------------------------------------------------
# Grounded in the modern game (2021-22 through 2024-25):
# - Fights: ~0.26 per game (hockeyfights.com). ~80% of games are fight-free,
#   ~17-18% see exactly one fight; only ~2-3% see more than one.
# - Line brawls (3+ combatants fighting at once): ~2 per 1312-game season.
#   Recent ones, all following the same script -- blowout + 3rd period +
#   a flashpoint, punished with 10-minute misconducts, never suspensions:
#     2022-23: TBL-VGK Mar 9 '23, FLA-OTT Apr 6 '23 (166 PIM)
#     2023-24: FLA-OTT Nov 27 '23 (167 PIM, all 10 skaters misconducted),
#              NYR-NJD Apr 3 '24 (brawl 2 seconds in, 8 ejected),
#              TOR-BUF Mar 31 '24 (all 10 misconducted after a post-whistle scrum)
#     2024-25: WSH-SEA Mar 9 '25 (all 10 in the box, mostly roughing minors),
#              FLA-EDM Jun 10 '25 (SCF Game 3, all 10 on the ice in a 6-1 blowout)
# - Tussles (post-whistle scrums): common -- most heated games have a few --
#   but they almost never escalate. Refs and players keep them at shoving.
# - True bench-clearing brawls are extinct; the model doesn't produce them.
NHL_FIGHTS_PER_GAME = 0.26
# True line brawls (3+ simultaneous fighting pairs) are far rarer than the
# word "brawl" in headlines suggests. Five-season census, 2021-22 through
# 2025-26, regular season + playoffs (~6,990 games):
#   21-22: none found
#   22-23: TBL-VGK Mar'23, FLA-OTT Apr'23 (166 PIM)
#   23-24: FLA-OTT Nov'23 (167 PIM, all 10 misconducted),
#           NYR-NJD Apr'24 (five simultaneous fights off the opening draw)
#   24-25: FLA-EDM Jun'25 SCF G3 (6-1 blowout, all 10 involved)
#   25-26: FLA-TBL (3 simultaneous fights, 3rd period of a 4-0 game)
# 6 confirmed in ~6,990 games ~= 0.00086. Near-misses (TOR-BUF Mar'24,
# BUF-TBL Mar'26 multi-fight games; WSH-SEA Mar'25 scrum) don't clear the
# 3-pair bar. Round to 0.0009: ~1.2 line brawls per 1312-game NHL season.
NHL_BRAWLS_PER_GAME = 0.0009


def fight_probability(tension: float, is_playoff: bool = False,
                      ordered: bool = False,
                      retaliation_mod: float = 1.0) -> float:
    """Per-game probability of at least one fight.

    Scales with the tension meter: a calm night (~10) sits well below the
    league average, a boiling rivalry (~80+) fights at multiples of it.
    Playoff teams are more disciplined about sitting five; an ordered team
    (coach sent them out) is much more likely to go."""
    try:
        # League average (~0.26) lands around tension 20; a calm night sits
        # below it, a boiling rivalry fights at multiples of it.
        p = NHL_FIGHTS_PER_GAME * (0.45 + 2.6 * (max(0.0, tension) / 100.0))
        if is_playoff:
            p *= 0.75
        if ordered:
            p *= 2.2
        return round(min(0.85, p * max(0.0, retaliation_mod)), 4)
    except Exception:
        return NHL_FIGHTS_PER_GAME


def brawl_probability(tension: float, is_playoff: bool = False,
                      ordered: bool = False, blowout: bool = False,
                      period: int = 1) -> float:
    """Per-game probability of a LINE BRAWL: 3+ combatants fighting at once.

    Exceedingly rare by design (~0.2% of games league-wide). Needs real heat
    AND the classic script: a blowout, the third period, a flashpoint. An
    ordered team in a boiling blowout is the only scenario that moves the
    needle much -- and even then it's a long shot, like the real thing."""
    try:
        heat = max(0.0, tension - 35.0) / 65.0
        p = NHL_BRAWLS_PER_GAME * (heat ** 2) * 6.0
        if blowout:
            p *= 4.0
        if period >= 3:
            p *= 2.0
        if ordered:
            p *= 5.0
        if is_playoff:
            p *= 0.8
        return round(min(0.06, p), 5)
    except Exception:
        return 0.0


def after_whistle_penalty_mult(is_playoff: bool, series_game: int = 1) -> float:
    """How the whistle treats post-whistle stuff (roughing, unsportsmanlike).

    The myth is that refs swallow the whistle in the playoffs; the data is
    subtler -- overall power plays tick UP early (desperation penalties in
    mismatched round-1 series). But RETALIATORY penalties fall off a cliff:
    coaches bench anyone who takes a dumb one, and officials let scrums go,
    especially late in a series. So: after-the-whistle minors get rarer in
    the playoffs, more so the deeper the series goes. Fights still draw
    fighting majors -- nobody ignores a fight."""
    try:
        if not is_playoff:
            return 1.0
        g = max(1, min(7, int(series_game)))
        return round(max(0.25, 0.62 - 0.05 * g), 3)
    except Exception:
        return 1.0


def playoff_penalty_mult(is_playoff: bool, series_game: int = 1) -> float:
    """Desperation-penalty rate in the playoffs (hooking, holding, tripping,
    slashing -- the ordinary stuff, not retaliation and not fights).

    theScore (Mar 2025): overall power plays tick UP in the postseason,
    especially in early rounds -- desperation penalties rise in mismatched
    round-1 series, then the rate eases as the series deepens and the whistle
    tightens. So Games 1-2 run a touch hotter than a regular-season game and
    Game 7 runs a touch cooler. Modest by design: ~+15% / -5%."""
    try:
        if not is_playoff:
            return 1.0
        g = max(1, min(7, int(series_game)))
        return {1: 1.15, 2: 1.12, 3: 1.08, 4: 1.04,
                5: 1.00, 6: 0.97, 7: 0.95}[g]
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Performance as a beef rectifier: the Torts/Werenski arc
# ---------------------------------------------------------------------------
# A hard coach who drags a career year out of a player forges a bond out of
# the beef. The friction becomes the foundation -- "he made me the player
# I am." Once forged, the player is bought in for good.

def rectify_coach_player_beef(rivalries: list, player: Any, coach: Any,
                              career_best: bool = False,
                              form: float = 50.0) -> Dict[str, Any]:
    """Performance heals coach-player bad blood. A career year under a hard
    coach turns the beef into a bond."""
    try:
        r = rivalry_between(rivalries, player, coach)
        if not r or r["kind"] != "coach_player":
            return {"rectified": False, "reason": "no coach-player beef to rectify"}
        style = coach_style(coach)["label"]
        hard = style == "Drill Sergeant" or (getattr(coach, "discipline", 50) or 50) >= 70
        score = 0.0
        if career_best:
            score += 60
        score += max(0.0, form - 60) * 1.0
        if hard:
            score += 15  # the hard-driving coach gets credit for the career year
        score -= r["grudge"] * 0.3  # deep grudges are harder to melt
        cname = getattr(coach, "full_name", "Coach")
        pname = getattr(player, "full_name", "Player")
        if score >= 55:
            bury_hatchet(rivalries, player, coach)
            ensure_reputation_fields(player)
            bonds = getattr(player, "coach_bonds", None)
            if bonds is None:
                player.coach_bonds = {}
                bonds = player.coach_bonds
            bonds[getattr(coach, "id", id(coach))] = (
                f"Career year under {cname} -- the beef became a bond")
            try:
                player.happiness = min(100, (getattr(player, "happiness", 70) or 70) + 8)
                player.morale = min(100, (getattr(player, "morale", 70) or 70) + 8)
            except Exception:
                pass
            return {"rectified": True, "score": round(score, 1),
                    "story": f"{cname} was hard on {pname} -- and dragged a career year "
                             f"out of him. The beef is gone; what's left is a bond. "
                             f"'He made me the player I am.'"}
        return {"rectified": False, "score": round(score, 1),
                "reason": "not enough on-ice proof yet -- the beef survives"}
    except Exception:
        return {"rectified": False, "reason": "error"}


# ---------------------------------------------------------------------------
# Game tension drivers: fights, penalties, history, and recent wounds
# ---------------------------------------------------------------------------
# Tension is the room's MEMORY -- it can be sky-high even when the coach
# would never order retaliation. You hurt our star last game? We won't
# forget. But whether we ANSWER is a separate, personality-gated question.

INCIDENT_WEIGHTS = {
    "star_injured": 25,      # you hurt our best player -- we remember
    "player_injured": 12,
    "controversial_hit": 10,
    "bad_call": 8,            # a missed call / uncalled infraction -- we remember
    "coach_comments": 8,     # he ran his mouth in the media
    "brawl": 15,
}


def fresh_violent_incident(rivalries: list, team_a: Any, team_b: Any,
                           within_games: int = 10) -> bool:
    """True if these two teams have a brawl / injury / controversial-hit
    incident in their rivalry log within the last `within_games` games.

    Drives the rarest script in hockey: the premeditated opening-faceoff
    line brawl. NYR-NJD, Apr 3 2024: five simultaneous fights two seconds
    in, answering Rempe's suspendable elbow on Siegenthaler the last time
    they met. Observed rate: ~1 in 5 NHL seasons -- keep any roll built on
    this tiny."""
    try:
        violent = {"brawl", "star_injured", "player_injured",
                   "controversial_hit"}
        names = {getattr(team_a, "team_name", ""),
                 getattr(team_b, "team_name", "")}
        for r in rivalries or []:
            if r.get("kind") != "team_team":
                continue
            rnames = {r.get("a_name"), r.get("b_name")}
            if names != rnames:
                continue
            for inc in r.get("incidents") or []:
                if inc.get("kind") in violent and \
                        _incident_games_ago(inc) <= within_games:
                    return True
        return False
    except Exception:
        return False


def record_game_incident(rivalries: list, team_a: Any, team_b: Any,
                         kind: str, detail: str = "") -> Dict[str, Any]:
    """Log something these two teams won't forget. Stored on the team_team
    rivalry record so it survives saves and follows the feud."""
    try:
        if kind not in INCIDENT_WEIGHTS:
            return {"recorded": False, "reason": f"unknown kind {kind}"}
        # Find or create the team_team record.
        r = None
        for cand in rivalries:
            if cand["kind"] == "team_team":
                names = {cand["a_name"], cand["b_name"]}
                if ({getattr(team_a, "team_name", ""), getattr(team_b, "team_name", "")} <= names
                        and len(names) == 2):
                    r = cand
                    break
        if not r:
            if _ekey(team_a) == _ekey(team_b):
                return {"recorded": False, "reason": "a team cannot feud with itself"}
            r = add_rivalry(rivalries, team_a, team_b, "team_team", 15,
                            "regional",
                            f"{_ename(team_a)} vs {_ename(team_b)}: bad blood started here.")
        log = r.get("incidents")
        if not isinstance(log, list):
            r["incidents"] = log = []
        log.append({"kind": kind, "detail": detail,
                    "date": date.today().isoformat()})
        # Narrative-ledger bridge: the normalized record keeps the same
        # facts so rivalry, media, fans, history and inbox all read one
        # source. The rivalry store above stays the system of record.
        try:
            from narrative_ledger import active_ledger as _active_ledger
            _led = _active_ledger()
            if _led is not None:
                _led.record(
                    "incident",
                    teams=[getattr(team_a, "team_name", ""),
                           getattr(team_b, "team_name", "")],
                    facts={"incident_kind": kind, "detail": detail,
                           "date": date.today().isoformat()},
                    weight=int(INCIDENT_WEIGHTS.get(kind, 30) or 30),
                    text=detail or kind,
                )
        except Exception:
            pass
        return {"recorded": True, "kind": kind, "detail": detail}
    except Exception:
        return {"recorded": False, "reason": "error"}


def _incident_games_ago(inc: Dict[str, Any]) -> float:
    try:
        d = date.fromisoformat(inc.get("date", date.today().isoformat()))
        days = (date.today() - d).days
        return max(0.0, days / 3.0)  # roughly a game every 3 days
    except Exception:
        return 0.0


def _rivalry_age_years(r: Dict[str, Any]) -> float:
    try:
        d = date.fromisoformat(r.get("date", date.today().isoformat()))
        return max(0.0, (date.today() - d).days / 365.0)
    except Exception:
        return 0.0


INCIDENT_LABELS = {
    "star_injured": "Star injured",
    "player_injured": "Player injured",
    "controversial_hit": "Controversial hit",
    "coach_comments": "Coach ran his mouth",
    "brawl": "Brawl",
}


def _roster_chippiness(roster: Any) -> float:
    """Mean locked personality of a roster -- chippy rooms run hotter."""
    try:
        vals = []
        for p in (roster or []):
            v = getattr(p, "base_controversy", None)
            if v is None:
                v = getattr(p, "controversy", 30)
            vals.append(v or 30)
        return sum(vals) / len(vals) if vals else 30.0
    except Exception:
        return 30.0


def game_tension_breakdown(home_team: Any, away_team: Any, rivalries: list,
                           is_playoff: bool = False, series_game: int = 0,
                           recent_fights: int = 0, recent_pim: int = 0,
                           extra_incidents: Optional[List[Dict[str, Any]]] = None,
                           crowd_hype: float = 0.0) -> Dict[str, Any]:
    """0-100 tension plus the signed drivers behind it.

    Returns {"tension": float, "drivers": [{"label": str, "points": float}]}.
    + heats the game up, - cools it down. Two strangers still get a little
    heat (pride on the line); rivalries, wounds, fights, and chippy
    personnel pile on, while clean professional matchups cool it off.

    crowd_hype (0-100, from arena_atmosphere.crowd_hype_for_tension): a loud
    building raises everyone's pulse. 0 = not provided, no adjustment.
    """
    drivers: List[Dict[str, Any]] = []
    try:
        t = 0.0
        hn = getattr(home_team, "team_name", "")
        an = getattr(away_team, "team_name", "")
        incidents: List[Dict[str, Any]] = list(extra_incidents or [])
        rivalry_pts = 0.0
        for r in (rivalries or []):
            if r.get("kind") != "team_team":
                continue
            names = {r.get("a_name"), r.get("b_name")}
            if not ({hn, an} <= names and len(names) == 2):
                continue
            inten = r.get("intensity", 0) or 0
            # Historic feuds weigh more than fresh ones at the same heat.
            if r.get("solidified") or _rivalry_age_years(r) >= 5:
                contrib = inten * 0.75 + 5
                tag = " (entrenched)"
            else:
                contrib = inten * 0.6
                tag = ""
            rname = r.get("name") or f"{r.get('a_name')} vs {r.get('b_name')}"
            drivers.append({"label": f"Rivalry: {rname}{tag}",
                            "points": round(contrib, 1)})
            rivalry_pts += contrib
            for inc in (r.get("incidents") or []):
                incidents.append(inc)
        t += rivalry_pts
        # Fights and penalty minutes: chippiness is measurable.
        if recent_fights:
            pts = min(24.0, recent_fights * 6.0)
            drivers.append({"label": f"Fights recently ({recent_fights})",
                            "points": round(pts, 1)})
            t += pts
        if recent_pim:
            pts = min(15.0, recent_pim * 0.3)
            drivers.append({"label": f"Penalty minutes recently ({recent_pim})",
                            "points": round(pts, 1)})
            t += pts
        # Recent wounds decay -- last game matters, two months ago barely does.
        for inc in incidents:
            w = INCIDENT_WEIGHTS.get(inc.get("kind"), 0)
            if not w:
                continue
            ago = inc.get("games_ago", _incident_games_ago(inc))
            pts = w * (0.75 ** max(0.0, ago))
            if pts >= 0.5:
                ilabel = INCIDENT_LABELS.get(inc.get("kind"), inc.get("kind"))
                drivers.append({"label": f"{ilabel} ({int(ago)} games ago)",
                                "points": round(pts, 1)})
            t += pts
        if is_playoff:
            pts = 15 + max(0, series_game) * 2
            drivers.append({"label": f"Playoff stakes (game {series_game or 1})",
                            "points": round(pts, 1)})
            t += pts
        # Baseline: two NHL teams, pride on the line -- always some heat.
        drivers.append({"label": "Pride on the line", "points": 8.0})
        t += 8.0
        # Personnel: chippy rooms run hotter; clean rooms cool it down.
        chip = (_roster_chippiness(getattr(home_team, "roster", []))
                + _roster_chippiness(getattr(away_team, "roster", []))) / 2.0
        if chip >= 55:
            pts = round(min(10.0, (chip - 50) * 0.4), 1)
            drivers.append({"label": "Chippy personnel", "points": pts})
            t += pts
        elif chip >= 40:
            pts = round((chip - 35) * 0.25, 1)
            drivers.append({"label": "Edgy personnel", "points": pts})
            t += pts
        elif chip <= 30:
            drivers.append({"label": "Clean, professional matchup", "points": -2.0})
            t -= 2.0
        if not incidents and rivalry_pts == 0:
            drivers.append({"label": "No recent bad blood", "points": -1.0})
            t -= 1.0
        # Crowd hype: a loud building raises everyone's pulse -- even a
        # nervous barn is intense. 0 = not provided.
        try:
            ch = float(crowd_hype or 0.0)
        except Exception:
            ch = 0.0
        if ch > 0.0:
            pts = round((ch - 55.0) * 0.15, 1)
            if pts >= 1.0:
                drivers.append({"label": "Electric crowd", "points": pts})
                t += pts
            elif pts <= -1.0:
                drivers.append({"label": "Flat crowd", "points": pts})
                t += pts
        tension = round(min(100.0, max(0.0, t)), 1)
        drivers.sort(key=lambda d: -abs(d["points"]))
        return {"tension": tension, "drivers": drivers}
    except Exception:
        return {"tension": 0.0, "drivers": []}


def game_tension(home_team: Any, away_team: Any, rivalries: list,
                 is_playoff: bool = False, series_game: int = 0,
                 recent_fights: int = 0, recent_pim: int = 0,
                 extra_incidents: Optional[List[Dict[str, Any]]] = None) -> float:
    """0-100: how much bad blood is in the building tonight."""
    return game_tension_breakdown(
        home_team, away_team, rivalries, is_playoff=is_playoff,
        series_game=series_game, recent_fights=recent_fights,
        recent_pim=recent_pim,
        extra_incidents=extra_incidents)["tension"]


# ---------------------------------------------------------------------------
# Personality: locked identity, living volatility
# ---------------------------------------------------------------------------
# base_controversy is dealt ONCE at generation and never changes -- it's who
# the man IS. controversy is how much he's ACTING OUT right now, and it
# drifts with scenario: mentors, coaching fit, adversity, happiness, money.
# A base-80 hothead can learn to live at 55. He will never be a 10.
# Identity is preserved; behavior is earned.

def _deal_base_controversy(entity: Any, hothead_chance: float = 0.08) -> int:
    """The actual deal. Never calls ensure_reputation_fields (no recursion).

    Personality is READ from the other devs' attribute model, not rolled
    independently: discipline / composure / aggressiveness / teamwork are
    already generated per prospect type (tier + archetype + age), so an
    enforcer archetype with 82 aggressiveness deals hotter than a two-way
    center with 72 discipline -- exactly what their system already says.
    A small individual nudge plus rare true outliers keep it human.
    Staff on the EHM 1-20 scale are normalized first.
    """
    disc = getattr(entity, "discipline", 60) or 60
    comp = getattr(entity, "composure", 60) or 60
    aggr = getattr(entity, "aggressiveness", 50) or 50
    team = getattr(entity, "teamwork", 60) or 60
    if max(disc, comp, aggr, team) <= 20:
        disc, comp, aggr, team = disc * 5, comp * 5, aggr * 5, team * 5
    base = ((100 - disc) * 0.35 + (100 - comp) * 0.25
            + max(0, aggr - 50) * 0.6 + (100 - team) * 0.1)
    base += random.randint(-8, 8)  # individuality within the type
    roll = random.random()
    if roll < hothead_chance * 0.4:
        base = random.randint(55, 85)   # hothead despite the numbers
    elif roll < hothead_chance * 0.4 + 0.03:
        base = random.randint(0, 8)     # saint despite the numbers
    base = max(0, min(100, int(round(base))))
    entity.base_controversy = base
    entity.controversy = base
    return base


def generate_personality(entity: Any, hothead_chance: float = 0.08) -> int:
    """Deal a locked personality. Idempotent -- never re-deals a locked one."""
    try:
        ensure_reputation_fields(entity)
        if isinstance(getattr(entity, "base_controversy", None), int):
            return entity.base_controversy
        return _deal_base_controversy(entity, hothead_chance)
    except Exception:
        return 20


# ---------------------------------------------------------------------------
# Generation blends: every batch of new players gets a real mix.
#
# The room model reads three separate axes off a player -- public drama
# (base_controversy), temper (aggressiveness + low composure), and quiet
# difficulty (selfishness + low teamwork) -- so generation deals them as a
# BLEND, not one label. A saint can have a hot head; a tough sell can avoid
# every camera; a showman can be all spotlight and no temper. Archetype
# leans the odds, never locks them; a per-class tilt gives each draft class
# its own character, so the league's personality shifts as the seasons turn.
# Identity is dealt once, here, at generation -- never re-dealt.
# ---------------------------------------------------------------------------

_GENERATION_BLENDS = (
    "professional",   # low drama, even temper, team-first
    "quiet",          # very low drama, keeps to himself
    "showman",        # high drama, low temper -- loves the spotlight
    "saint_hothead",  # low drama, high temper -- saint with a hot head
    "tough_sell",     # low drama, high difficulty -- quiet, hard to please
    "volatile",       # high drama + high temper
)

_BLEND_WEIGHTS = {
    "professional": 52.0,
    "quiet": 12.0,
    "showman": 10.0,
    "saint_hothead": 9.0,
    "tough_sell": 9.0,
    "volatile": 8.0,
}

# tilt -> {blend: weight multiplier}
_CLASS_TILTS = {
    "fiery": {"saint_hothead": 1.8, "volatile": 1.8},
    "circus": {"showman": 1.8, "volatile": 1.8},
    "sulky": {"tough_sell": 2.0},
    "professional": {"professional": 1.5, "quiet": 1.5},
}


# A little room for the unexpected: a small share of prospects get a
# WILDCARD -- one axis twisted away from their blend. The kid stays a
# coherent person, just not the one the scouts expected: the quiet
# professional with a hidden hot head, the showman with a real bite.
# The blend fingerprint records what everyone expected; personality_twist
# records the surprise. Nothing here can break the game -- every downstream
# effect is one-time and bounded -- but every class gets a few stories
# nobody saw coming.
_WILDCARD_CHANCE = 0.04
_WILDCARD_TWISTS = {
    "professional": ("hidden_temper", "quiet_edge"),
    "quiet": ("quiet_edge", "hidden_temper"),
    "showman": ("spotlight_bite",),
    "saint_hothead": ("public_edge",),
    "tough_sell": ("thin_skin",),
    "volatile": ("soft_center",),
}
# twist -> axis it flips
_TWIST_AXES = {
    "hidden_temper": "temper_high",
    "spotlight_bite": "temper_high",
    "thin_skin": "temper_high",
    "public_edge": "drama_high",
    "quiet_edge": "difficult_high",
    "soft_center": "temper_low",
}


def _blend_archetype_lean(archetype_name: Any) -> Dict[str, float]:
    """Archetype leans the blend odds -- a lean, never a lock."""
    name = str(archetype_name or "").lower()
    if any(k in name for k in ("enforc", "tough guy", "grind", "pest",
                               "agitat")):
        return {"saint_hothead": 2.2, "volatile": 2.0, "professional": 0.8}
    if any(k in name for k in ("sniper", "playmaker", "finesse", "snipe",
                               "dangler", "offensive")):
        return {"showman": 1.8, "volatile": 1.4}
    if any(k in name for k in ("two-way", "twoway", "defensive", "shutdown",
                               "checker", "stay-at-home", "stay at home")):
        return {"professional": 1.4, "quiet": 1.3, "volatile": 0.6}
    if any(k in name for k in ("goalie", "goaltender", "netminder")):
        return {"quiet": 1.3, "professional": 1.2}
    return {}


def _set_trait(player: Any, attr: str, lo: int, hi: int) -> None:
    try:
        setattr(player, attr, max(1, min(99, random.randint(lo, hi))))
    except Exception:
        pass


def _apply_blend(player: Any, blend: str, twist: str = "") -> None:
    """Reshape the raw traits so the whole game reads one coherent person.

    Drama shapes discipline/composure/aggressiveness (which the locked
    base_controversy is then dealt from); temper overrides aggressiveness
    and composure; difficulty sets selfishness (dealt here -- real players
    never had one) and teamwork. A wildcard twist flips exactly one axis,
    so the surprise is still a legible person. Tendencies follow
    temperament.
    """
    drama_high = blend in ("showman", "volatile")
    temper_high = blend in ("saint_hothead", "volatile")
    difficult_high = blend == "tough_sell"
    _axis = _TWIST_AXES.get(twist, "")
    if _axis == "drama_high":
        drama_high = True
    elif _axis == "temper_high":
        temper_high = True
    elif _axis == "temper_low":
        temper_high = False
    elif _axis == "difficult_high":
        difficult_high = True

    if drama_high:
        _set_trait(player, "discipline", 30, 45)
        _set_trait(player, "composure", 35, 50)
        _set_trait(player, "aggressiveness", 55, 75)
    else:
        _set_trait(player, "discipline", 60, 80)
        _set_trait(player, "composure", 60, 80)
        _set_trait(player, "aggressiveness", 35, 55)
    if temper_high:
        _set_trait(player, "aggressiveness", 72, 90)
        _set_trait(player, "composure", 25, 42)
    else:
        _set_trait(player, "composure", 55, 75)
        _set_trait(player, "aggressiveness", 30, 52)
    if difficult_high:
        _set_trait(player, "selfishness", 68, 90)
        _set_trait(player, "teamwork", 25, 42)
    else:
        _set_trait(player, "selfishness", 30, 52)
        _set_trait(player, "teamwork", 55, 78)

    # Tendencies follow temperament: hot heads hit, showmen shoot.
    try:
        if temper_high:
            _ht = int(getattr(player, "hitting_tendency", 50) or 50)
            player.hitting_tendency = max(_ht, random.randint(55, 85))
        if blend == "showman":
            _st = int(getattr(player, "shooting_tendency", 50) or 50)
            player.shooting_tendency = max(_st, random.randint(55, 85))
    except Exception:
        pass
    # A visible fingerprint of the deal (for QA and draft stories):
    # what everyone expected, plus the surprise if there was one.
    try:
        player.personality_blend = blend
        player.personality_twist = twist
    except Exception:
        pass


def roll_class_tilt() -> Optional[str]:
    """Roll one draft class's character. Most classes are neutral; some
    come in with a temperament of their own."""
    try:
        if random.random() < 0.55:
            return None
        return random.choice(["fiery", "circus", "sulky", "professional"])
    except Exception:
        return None


def deal_generation_blend(player: Any,
                          tilt: Optional[str] = None) -> int:
    """Deal one generated player's personality blend. Idempotent: a player
    who already has a locked base_controversy keeps it -- identity is
    dealt once, at generation, never re-dealt."""
    try:
        if isinstance(getattr(player, "base_controversy", None), int):
            return player.base_controversy
        weights = dict(_BLEND_WEIGHTS)
        for _b, _m in _blend_archetype_lean(
                getattr(player, "archetype", "")).items():
            weights[_b] = weights.get(_b, 0.0) * _m
        for _b, _m in _CLASS_TILTS.get(tilt or "", {}).items():
            weights[_b] = weights.get(_b, 0.0) * _m
        _total = sum(weights.values()) or 1.0
        _roll = random.random() * _total
        _blend = "professional"
        for _name in _GENERATION_BLENDS:
            _roll -= weights.get(_name, 0.0)
            if _roll <= 0:
                _blend = _name
                break
        # The unexpected: one twisted axis, rarely. Still a coherent
        # person -- just not the one the scouts expected.
        _twist = ""
        try:
            if random.random() < _WILDCARD_CHANCE:
                _options = _WILDCARD_TWISTS.get(_blend, ())
                if _options:
                    _twist = random.choice(_options)
        except Exception:
            _twist = ""
        _apply_blend(player, _blend, twist=_twist)
        # Deal the locked drama from the reshaped traits -- with no outlier
        # roll. The blend already deals rare combos deliberately; an extra
        # dice roll here would break the combo's coherence (a saint with a
        # 70 controversy isn't a saint). The blend's declared drama (after
        # any wildcard twist) gets the final word over the estimator --
        # "saint despite the numbers".
        _drama_high = _blend in ("showman", "volatile") \
            or _TWIST_AXES.get(_twist, "") == "drama_high"
        try:
            if getattr(player, "base_controversy", None) is None:
                _deal_base_controversy(player, 0.0)
                if _drama_high:
                    player.base_controversy = max(
                        40, player.base_controversy)
                    player.controversy = max(40, player.controversy)
                else:
                    player.base_controversy = min(
                        39, player.base_controversy)
                    player.controversy = min(39, player.controversy)
            ensure_reputation_fields(player)
            return player.base_controversy
        except Exception:
            return 20
    except Exception:
        return getattr(player, "base_controversy", 20) or 20



def _draft_overall(p: Any) -> Optional[int]:
    try:
        s = getattr(p, "draft_position", "") or ""
        if "Round 1" in s:
            m = re.search(r"Pick (\d+)", s)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


def _golden_prospect(p: Any) -> bool:
    """Won everything before the NHL: top-10 pick, or 'A' potential as a teen."""
    ov = _draft_overall(p)
    if ov is not None:
        return ov <= 10
    try:
        return ((getattr(p, "potential_grade", "") or "").upper() == "A"
                and (getattr(p, "age", 99) or 99) <= 21)
    except Exception:
        return False


def _player_tier(p: Any, team: Any) -> str:
    try:
        if team is None:
            return ""
        tiers = team_hierarchy(getattr(team, "roster", []) or [])
        pid = getattr(p, "id", None)
        for name, members in tiers.items():
            if any(getattr(m, "id", None) == pid for m in members):
                return name
    except Exception:
        pass
    return ""


def _player_volatility_offset(p: Any, team: Any = None, coach: Any = None,
                              win_pct: Optional[float] = None) -> tuple:
    """Scenario offset for a player: negative calms, positive escalates."""
    off = 0
    reasons: List[str] = []
    base = controversy_baseline(p)
    age = getattr(p, "age", 27) or 27
    happy = getattr(p, "happiness", 65) or 65

    # Veteran mentorship: the room raises him right -- or nobody checks him.
    mentors = 0
    if team is not None:
        for mate in getattr(team, "roster", []) or []:
            if mate is p:
                continue
            if (getattr(mate, "leadership", 0) or 0) >= 75 \
                    and (getattr(mate, "age", 0) or 0) >= 30:
                mentors += 1
    if mentors:
        d = -min(8, 3 * mentors)
        off += d
        reasons.append(f"{mentors} veteran mentor(s) steadying him ({d})")
    elif base >= 50:
        off += 2
        reasons.append("no veteran presence to check him (+2)")

    # The right coaching -- or the wrong one.
    if coach is not None:
        try:
            label = player_coach_response(p, coach).get("label", "")
            if label == "Bought in":
                off -= 4
                reasons.append("right coach for him (-4)")
            elif label == "Tuning out":
                off += 3
                reasons.append("tuning the coach out (+3)")
            elif label == "Quit on coach":
                off += 6
                reasons.append("quit on the coach (+6)")
        except Exception:
            pass

    # Working with youngsters: a developer calms young volatility; a coach
    # who can't reach kids makes a young hothead worse.
    if age <= 23 and coach is not None and base >= 45:
        wwy = getattr(coach, "working_with_youngsters", 50) or 50
        if wwy >= 75:
            off -= 3
            reasons.append("a developer who reaches young players (-3)")
        elif wwy <= 40:
            off += 2
            reasons.append("coach can't reach young players (+2)")

    # Golden-prospect adversity shock: won everything, never faced it until now.
    # McDavid prevails. Not every prospect is built like that.
    if _golden_prospect(p) and (getattr(p, "nhl_games_played", 999) or 999) < 100:
        adversity = (win_pct is not None and win_pct < 0.45) or happy < 45 \
            or _player_tier(p, team) in ("Fringe", "Squad Players")
        if adversity:
            character = (getattr(p, "leadership", 50) or 50) + (100 - base)
            if character >= 140:
                off -= 4
                reasons.append("golden prospect met real adversity and prevailed (-4)")
            else:
                wwy = 50
                if coach is not None:
                    wwy = getattr(coach, "working_with_youngsters", 50) or 50
                if wwy >= 75:
                    off += 4
                    reasons.append("entitlement meets reality, but the coach reaches him (+4)")
                else:
                    off += 7
                    reasons.append("entitlement meets reality: first real adversity (+7)")

    # Tough early years humble a young hothead who wasn't handed everything.
    if age <= 23 and base >= 50 and not _golden_prospect(p):
        if (win_pct is not None and win_pct < 0.50) or happy < 55:
            off -= 4
            reasons.append("tough rookie years humbled him (-4)")

    # Knows his place: happy and winning vs miserable on a loser.
    if happy >= 65 and win_pct is not None and win_pct >= 0.55:
        off -= 3
        reasons.append("happy and winning (-3)")
    if happy < 45 and win_pct is not None and win_pct < 0.45:
        off += 6
        reasons.append("miserable on a loser (+6)")

    # Just got paid -- security calms. Underpaid and knows it -- doesn't.
    try:
        ovr = p.overall_rating() if hasattr(p, "overall_rating") else 40
        salary = getattr(p, "salary", 0) or 0
        expected = max(750_000, (ovr - 38) * 750_000)
        if salary >= expected * 1.2:
            off -= 2
            reasons.append("paid and secure (-2)")
        elif salary < expected * 0.7 and ovr >= 42:
            off += 3
            reasons.append("underpaid and knows it (+3)")
    except Exception:
        pass

    # Age mellows everyone, even hotheads.
    if age >= 30:
        off -= 3
        reasons.append("veteran perspective (-3)")
    elif age >= 24:
        off -= 2
        reasons.append("maturing (-2)")

    return max(-25, min(25, off)), reasons


def _coach_volatility_offset(c: Any, team: Any = None, coach: Any = None,
                             win_pct: Optional[float] = None) -> tuple:
    """Scenario offset for a coach."""
    off = 0
    reasons: List[str] = []
    base = controversy_baseline(c)
    ywt = getattr(c, "years_with_team", 0) or 0
    if win_pct is not None and win_pct < 0.450:
        off -= 5
        reasons.append("losing humbled him (-5)")
    if ywt <= 1 and base >= 50:
        off -= 6
        reasons.append("new organization, changing his ways (-6)")
    if win_pct is not None and win_pct >= 0.600 \
            and (getattr(c, "controversy", 0) or 0) >= 50:
        off += 4
        reasons.append("winning lets him get away with it (+4)")
    return max(-25, min(25, off)), reasons


def volatility_drivers(entity: Any, team: Any = None, coach: Any = None,
                       win_pct: Optional[float] = None) -> List[str]:
    """Human-readable reasons behind this year's volatility drift."""
    try:
        ensure_reputation_fields(entity)
        if _is_staff_entity(entity):
            return _coach_volatility_offset(entity, team, coach, win_pct)[1]
        return _player_volatility_offset(entity, team, coach, win_pct)[1]
    except Exception:
        return []


def coach_market_appeal(coach: Any, hiring_org: tuple = ()) -> Dict[str, Any]:
    """How badly does the league want this coach? Record talks, controversy
    costs -- unless someone in the hiring org vouches for him. A stubborn,
    controversial coach who isn't winning needs friends to pipeline him."""
    try:
        ensure_reputation_fields(coach)
        rep = getattr(coach, "reputation", 50) or 50
        cont = getattr(coach, "controversy", 20) or 20
        tax = cont * 0.4
        vouched = any(v in (getattr(coach, "connections", None) or [])
                      for v in (hiring_org or ()))
        if vouched:
            tax *= 0.5
        influence = getattr(coach, "influence", 70) or 70
        score = max(0, min(100, rep * 0.65 - tax + 15 + influence * 0.1))
        return {"appeal": round(score, 1), "reputation": rep,
                "controversy_tax": round(tax, 1), "vouched": vouched,
                "story": (f"{_ename(coach)}: appeal {score:.0f} "
                          f"(rep {rep}, controversy tax {tax:.0f}"
                          f"{', vouched by a friend in the org' if vouched else ''}).")}
    except Exception:
        return {"appeal": 50.0, "reputation": 50, "controversy_tax": 0,
                "vouched": False, "story": "Appeal unavailable."}


def volatility_trade_discount(player: Any) -> float:
    """Talent-personality-volatility balance for trade value: hotheads cost
    less, but a superstar is worth the headache."""
    try:
        c = getattr(player, "controversy", 0) or 0
        ovr = player.overall_rating() if hasattr(player, "overall_rating") else 40
        star = max(0.0, min(1.0, (ovr - 40) / 24.0))
        discount = (c / 100.0) * 0.25 * (1.15 - star)
        return round(max(0.70, 1 - discount), 3)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Coach influence: accolades, recent success, name value, respect
# ---------------------------------------------------------------------------
# influence (0-100) is how much weight a coach's voice carries. It's set at
# hire -- floor 65, icons higher -- then earned or burned every season.

def coach_influence_at_hire(accolades: float = 0, name_value: float = 0) -> int:
    """Influence a coach walks in the door with.

    accolades: career_reputation (Cups and winning are already baked in).
    name_value: for the NHL legend turned coach -- his playing career
                opens doors his coaching resume hasn't earned yet.
    No new hire starts below 65. Icons start near 95.
    """
    score = 65 + min(20, (accolades or 0) * 0.25) + min(20, (name_value or 0) * 0.22)
    return max(65, min(95, int(round(score))))


def develop_coach_influence(coach: Any, win_pct: Optional[float] = None,
                            is_champ: bool = False,
                            roster: Optional[List[Any]] = None) -> int:
    """Yearly influence drift: recent success builds it, losing burns it,
    and respect in the room is the final judge."""
    ensure_reputation_fields(coach)
    inf = getattr(coach, "influence", None)
    if inf is None:
        inf = coach_influence_at_hire(
            accolades=getattr(coach, "career_reputation", 0) or 0)
    if win_pct is not None:
        if is_champ:
            inf += 6
        elif win_pct >= 0.600:
            inf += 3
        elif win_pct >= 0.500:
            inf += 1
        elif win_pct < 0.400:
            inf -= 9
        elif win_pct < 0.450:
            inf -= 6
    if roster is not None:
        try:
            level = room_status(coach, {"win_pct": win_pct or 0.5},
                                roster=roster)["level"]
            inf += {"Lost": -8, "Fracturing": -5, "Strain": -2,
                    "Secure": 1}.get(level, 0)
        except Exception:
            pass
    coach.influence = max(0, min(100, int(round(inf))))
    return coach.influence


# ---------------------------------------------------------------------------
# Coach influence on development: talent - personality - coaching
# ---------------------------------------------------------------------------

def coach_development_factor(player: Any, coach: Any) -> float:
    """0.6..1.4: how much this coach accelerates (or stalls) this player's
    growth. The voice's weight (influence), the youth touch, the player's
    coachability and current buy-in -- but generational talent transcends
    coaching: a McDavid develops under anyone, the right coach just
    squeezes the last drops out."""
    try:
        if coach is None:
            return 1.0
        age = getattr(player, "age", 25) or 25
        factor = 1.0
        # 1. The voice's weight.
        influence = getattr(coach, "influence", 70) or 70
        factor *= 0.70 + (influence / 100.0) * 0.60
        # 2. The youth touch, for young players.
        if age <= 23:
            wwy = getattr(coach, "working_with_youngsters", 50) or 50
            factor *= 1.0 + (wwy - 50) / 50 * 0.25
        # 3. Personality: raw coachability, then the current relationship.
        cont = getattr(player, "controversy", 0) or 0
        factor *= 1.0 - (cont / 100.0) * 0.25
        try:
            label = player_coach_response(player, coach).get("label", "")
            factor *= {"Bought in": 1.15, "Neutral": 1.0,
                       "Tuning out": 0.90, "Quit on coach": 0.75}.get(label, 1.0)
        except Exception:
            pass
        # 4. Generational talent develops regardless -- damp toward 1.0.
        pot = (getattr(player, "potential_grade", "") or "").upper()
        if pot == "A" and age <= 23:
            factor = 0.65 + 0.35 * factor
        return round(max(0.6, min(1.4, factor)), 3)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Situations factor: the room, the bench, and the kids, compounded into one
# pre-game edge. Morale + coaching + development all land here, and the sim
# reads it as its own channel (like the controversy momentum channel) rather
# than as part of any capped budget.
# ---------------------------------------------------------------------------

SITUATION_XG_PER_POINT = 0.008  # +/-8% finishing at the extremes; the room
                                 # matters, but talent still decides most nights

def snapshot_roster_churn(team: Any) -> float:
    """Offseason roster-turnover snapshot for the situations factor.

    Compares the current NHL roster (by name -- survives saves) against last
    offseason's snapshot and stores the churn fraction (0-1) on
    team.roster_churn. High churn = "new faces still gelling" penalty;
    a kept core = "battle-tested" bonus. First run (old saves): league-
    average 0.2. Call once per offseason for every team. Never raises.
    """
    try:
        names = []
        for p in getattr(team, "roster", None) or []:
            fn = getattr(p, "first_name", "") or ""
            ln = getattr(p, "last_name", "") or ""
            full = f"{fn} {ln}".strip() or str(getattr(p, "full_name", "?"))
            names.append(full)
        prev = list(getattr(team, "prev_roster_names", None) or [])
        if prev and names:
            overlap = len(set(prev) & set(names))
            churn = 1.0 - overlap / len(names)
        else:
            churn = 0.2
        team.roster_churn = round(max(0.0, min(1.0, churn)), 3)
        team.prev_roster_names = names
        return team.roster_churn
    except Exception:
        return 0.2


_ROOM_SCORE = {"Secure": 1.5, "Strain": -1.0, "Fracturing": -2.5, "Lost": -4.0}
_BUYIN_SCORE = {"Bought in": 1.0, "Neutral": 0.0, "Tuning out": -1.0,
                "Quit on coach": -1.5}


def situations_factor(team: Any, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """How much tonight's situation lifts or drags this team.

    Compounds three legs that used to live in separate systems:
      ROOM  -- chemistry, whether the coach still has the room, recent
               dynamics (rallies lift, bag-skate fallout drags)
      BENCH -- coach influence, buy-in across the roster, GM trust,
               line-control power struggles
      HUNGER -- young legs with high morale (energy) vs a roster full of
               unhappy players (drag). Morale-based, so it works even
               before the attribute engine weighs in.

    Returns {"team", "score" (-10..10), "xg_mult", "drivers", "story"}.
    Pure function of stored state; never raises.
    """
    ctx = ctx or {}
    drivers: List[tuple] = []

    def add(label: str, value: float) -> None:
        if value:
            drivers.append((label, round(value, 2)))

    roster = list(getattr(team, "roster", None) or [])
    coach = None
    try:
        from game_classes import StaffRole
        staff = team.get_staff_by_role(StaffRole.HEAD_COACH)
        coach = staff[0] if staff else None
    except Exception:
        coach = getattr(team, "head_coach", None)

    # ---- ROOM -----------------------------------------------------------
    try:
        if coach is not None:
            rs = room_status(coach, {"win_pct": ctx.get("win_pct", 0.5)},
                             roster=roster)
            lvl = rs.get("level", "Secure")
            add(f"Room: {lvl.lower()}", _ROOM_SCORE.get(lvl, 0.0))
    except Exception:
        pass
    try:
        if roster:
            chem = team_chemistry(roster)
            add("Room chemistry", max(-2.0, min(2.0, (chem.get("score", 50) - 55) / 22.5)))
    except Exception:
        pass
    # ---- CONTINUITY: years pass, players and staff change -----------------
    # Summer turnover takes time to gel; a kept core becomes an identity.
    # This is what makes each team's situation evolve year to year -- and
    # differently in every playthrough, driven by actual roster decisions.
    try:
        churn = getattr(team, "roster_churn", None)
        churn = 0.2 if churn is None else max(0.0, min(1.0, float(churn)))
        if churn >= 0.35:
            add("New faces still gelling", round(-churn * 3.0, 2))
        elif churn <= 0.12:
            add("Gelled, battle-tested core", 1.0)
    except Exception:
        pass
    try:
        if coach is not None:
            ywt = getattr(coach, "years_with_team", 0) or 0
            if ywt <= 1:
                add("New voice behind the bench", 0.75)
    except Exception:
        pass
    try:
        log = list(getattr(team, "dynamics_log", None) or [])[-6:]
        blob = " ".join(str(e).lower() for e in log)
        if any(k in blob for k in ("rally", "inspiring speech", "great practice",
                                   "bought in", "standing ovation")):
            add("Room rallying", 1.0)
        if any(k in blob for k in ("bag skate", "mistreat", "quit on",
                                   "tuning out", "fallout")):
            add("Room fallout", -1.0)
    except Exception:
        pass

    # ---- BENCH ----------------------------------------------------------
    try:
        if coach is not None:
            inf = getattr(coach, "influence", 70) or 70
            add("Coach influence", max(-2.5, min(2.5, (inf - 70) / 20.0)))
            trust = getattr(coach, "gm_trust", 70) or 70
            if trust < 45:
                add("GM doesn't trust the coach", -1.0)
    except Exception:
        pass
    try:
        if coach is not None and roster:
            scores = []
            for p in roster:
                try:
                    r = player_coach_response(p, coach)
                    scores.append(_BUYIN_SCORE.get(r.get("label", "Neutral"), 0.0))
                except Exception:
                    continue
            if scores:
                add("Locker-room buy-in", round(sum(scores) / len(scores) * 1.5, 2))
    except Exception:
        pass
    try:
        if getattr(team, "line_control", "coach") == "gm":
            add("GM holding the lineup pen", -0.5)
    except Exception:
        pass

    # ---- HUNGER ---------------------------------------------------------
    try:
        if roster:
            kids = [p for p in roster if (getattr(p, "age", 27) or 27) <= 23]
            if kids:
                hungry = sum(1 for p in kids if (getattr(p, "morale", 70) or 70) >= 70)
                add("Hungry young legs", round(hungry / len(kids) * 2.0, 2))
            sour = sum(1 for p in roster if (getattr(p, "happiness", 70) or 70) <= 35)
            if sour:
                add("Unhappy room", round(-sour / len(roster) * 4.0, 2))
    except Exception:
        pass

    score = max(-10.0, min(10.0, sum(v for _, v in drivers)))
    score = round(score, 2)
    xg_mult = round(1.0 + score * SITUATION_XG_PER_POINT, 4)

    drivers.sort(key=lambda t: -abs(t[1]))
    tname = getattr(team, "team_name", "The team")
    if drivers:
        top_label, top_val = drivers[0]
        mood = "lifting them" if top_val > 0 else "weighing them down"
        story = (f"{tname}: situation {'+' if score >= 0 else ''}{score} -- "
                 f"{top_label} {mood}.")
    else:
        story = f"{tname}: no situational edge tonight."

    return {
        "team": getattr(team, "team_name", "unknown"),
        "score": score,
        "xg_mult": xg_mult,
        "drivers": [{"label": l, "value": v} for l, v in drivers],
        "story": story,
    }


# ---------------------------------------------------------------------------
# Contract decisions: overpays, market-setting deals, offer sheets
# ---------------------------------------------------------------------------
# Sits ON TOP of SalaryCapSystem (salary_cap_system.py): that engine owns the
# math (demand, market comps, market setters). This layer owns the human
# fallout -- fan beefs with overpaid players, GM reputation swings, and
# GM-GM bad blood when someone resets the market or fires off an offer sheet.

def contract_verdict(aav: float, expected_aav: float) -> Dict[str, Any]:
    """Classify a contract against its expected (market/demand) value.

    Returns verdict + overpay ratio. Thresholds mirror real front-office
    language: within 15% is just business; 15-40% over is an overpay the
    fanbase will grumble about; beyond that is albatross territory.
    """
    try:
        ratio = float(aav) / max(float(expected_aav), 1.0)
    except (TypeError, ValueError):
        ratio = 1.0
    if ratio < 0.85:
        verdict = "steal"
    elif ratio < 1.15:
        verdict = "fair"
    elif ratio < 1.40:
        verdict = "overpay"
    else:
        verdict = "megadeal"
    return {"verdict": verdict, "overpay_ratio": round(ratio, 3)}


def _team_gm_staff(team: Any) -> Optional[Any]:
    """The Staff entity holding the GM chair, if the team has one."""
    try:
        for s in getattr(team, "staff", None) or []:
            if getattr(getattr(s, "role", None), "name", "") == "GENERAL_MANAGER":
                return s
    except Exception:
        pass
    return None


def _nudge_gm_rep(team: Any, delta: int, reason: str) -> None:
    gm = _team_gm_staff(team)
    if gm is None:
        return
    try:
        ensure_reputation_fields(gm)
        cur = int(getattr(gm, "career_reputation", 0) or 0)
        gm.career_reputation = max(0, min(100, cur + delta))
        gm.reputation_history.append({"date": date.today().isoformat(),
                                     "reputation": gm.career_reputation,
                                     "reason": reason})
    except Exception:
        pass


def record_offer_sheet(rivalries: list, offering_team: Any, target_team: Any,
                       player: Any, aav: float,
                       matched: bool = False) -> Dict[str, Any]:
    """A shameless offer sheet poaches an RFA: instant bad blood.

    GM-GM heat (this is personal -- you went into his kitchen), team-team
    heat, the jilted fanbase turns on the player, and the league's GMs take
    notice. Call this from the offer-sheet transaction path when it lands.
    """
    pname = _ename(player)
    oname = getattr(offering_team, "team_name", "?")
    tname = getattr(target_team, "team_name", "?")
    story = (f"{oname} offer-sheeted {pname} (${aav:,.0f} AAV) away from "
             f"{tname}" + (" -- matched! The GM stood his ground."
                           if matched else " -- and got their man."))
    out: Dict[str, Any] = {"story": story, "rivalries": []}
    ogm, tgm = gm_persona(offering_team), gm_persona(target_team)
    r = add_rivalry(rivalries, ogm, tgm, "gm_gm", 80, "offer_sheet",
                    f"{_ename(ogm)} poached {pname} from {_ename(tgm)} "
                    f"with a ${aav:,.0f} AAV offer sheet.",
                    grudge=70, career_cost=25)
    if r:
        out["rivalries"].append(r)
    r = add_rivalry(rivalries, offering_team, target_team, "team_team", 40,
                    "offer_sheet",
                    f"{oname} raided {tname}'s RFA {pname}.",
                    grudge=55)
    if r:
        out["rivalries"].append(r)
    # Professional regard craters too -- you don't respect a GM who
    # offer-sheets you, and he knows it.
    try:
        _bump_gm_respect(rivalries, offering_team, target_team, -10)
    except Exception:
        pass
    # The jilted fanbase never forgets -- even if the player stays.
    try:
        player.fan_backlash = max(int(getattr(player, "fan_backlash", 0) or 0),
                                  55 if matched else 70)
    except Exception:
        pass
    try:
        record_team_event(target_team, "offer_sheet",
                          f"{pname} signed an offer sheet with {oname}. "
                          f"The building is furious.",
                          morale_delta=-3, tone="down")
    except Exception:
        pass
    return out


def evaluate_contract_decision(player: Any, aav: float, expected_aav: float,
                               team: Any = None, league: Any = None,
                               market_setter: bool = False,
                               is_offer_sheet: bool = False,
                               from_team: Any = None) -> Dict[str, Any]:
    """Score the human fallout of a contract: overpay verdict, fan beef with
    the player, GM reputation swing, and GM-GM heat when the deal resets the
    market (market_setter=True comes straight from
    SalaryCapSystem.register_signing -- Caleb's market engine is untouched).

    Pure-ish: never raises; applies effects to player/team/league in place.
    """
    cv = contract_verdict(aav, expected_aav)
    verdict, ratio = cv["verdict"], cv["overpay_ratio"]
    pname = _ename(player)
    tname = getattr(team, "team_name", "the club") if team is not None else "the club"
    effects: List[str] = []
    texts: List[str] = []

    # Contract pressure: the bigger the overpay, the hotter the seat. The
    # fans will turn a grumble into a full beef if production doesn't match.
    try:
        pressure = max(0, min(100, int(round((ratio - 1.0) * 120)))) if ratio > 1 else 0
        player.contract_pressure = pressure
    except Exception:
        pressure = 0

    fav = False
    try:
        fav = fan_favourite_score(player, team)["score"] >= 70
    except Exception:
        pass

    if verdict == "steal":
        texts.append(f"{pname} signed well below market (${aav:,.0f} AAV) -- "
                     f"a steal for {tname}.")
        effects.append("gm_rep+4 (shrewd deal)")
        _nudge_gm_rep(team, 4, "team_friendly_signing")
        try:
            record_team_event(team, "contract",
                              f"{pname} took a team-friendly deal. The room "
                              f"notices who buys in.", morale_delta=2, tone="up")
        except Exception:
            pass
    elif verdict == "fair":
        texts.append(f"{pname} signed at market value (${aav:,.0f} AAV).")
    else:
        # Overpay / megadeal: fans do the math instantly.
        slack = 0.6 if fav else 1.0  # beloved players get the benefit of the doubt
        backlash = max(0, min(100, int(round((ratio - 1.15) * 220 * slack)) + (10 if verdict == "megadeal" else 0)))
        try:
            player.fan_backlash = max(int(getattr(player, "fan_backlash", 0) or 0), backlash)
        except Exception:
            pass
        if verdict == "overpay":
            texts.append(f"{pname} got ${aav:,.0f} AAV -- about "
                         f"{int(round((ratio - 1) * 100))}% over market. "
                         f"The fanbase is grumbling.")
            effects.append(f"fan_backlash={backlash} on player")
            _nudge_gm_rep(team, -2, "overpay_signing")
            effects.append("gm_rep-2 (overpay)")
        else:
            texts.append(f"{pname}'s ${aav:,.0f} AAV deal is an albatross -- "
                         f"{int(round((ratio - 1) * 100))}% over market. "
                         f"Talk radio is on fire.")
            effects.append(f"fan_backlash={backlash} on player")
            _nudge_gm_rep(team, -5, "albatross_contract")
            effects.append("gm_rep-5 (albatross)")
        try:
            record_team_event(team, "contract", " ".join(texts),
                              morale_delta=-1 if verdict == "overpay" else -2,
                              tone="down")
        except Exception:
            pass

    rivalries = _rivalry_store(league) if league is not None else []
    if market_setter and league is not None and team is not None:
        # Caleb's engine just moved the market: comparable stars league-wide
        # will demand 10-15% more. Every other GM knows exactly who to
        # blame -- the beef is pairwise and personal, not a vague grumble.
        story = (f"{_ename(gm_persona(team))} reset the market with {pname}'s "
                 f"${aav:,.0f} AAV deal -- every agent with a comparable "
                 f"client just raised their ask.")
        heated = 0
        for other in _league_teams(league):
            if other is team:
                continue
            try:
                r = add_rivalry(rivalries, gm_persona(team),
                                gm_persona(other), "gm_gm", 25,
                                "market_reset", story, grudge=55)
                if r:
                    heated += 1
                _bump_gm_respect(rivalries, team, other, -3)
            except Exception:
                pass
        if heated:
            effects.append(f"gm_gm heat 25 x{heated} (market reset)")
        texts.append("Around the league, rival GMs are furious -- this deal "
                     "just made all of their extensions more expensive.")
        _nudge_gm_rep(team, -1, "reset_market_against_peers")
        effects.append("gm_rep-1 (peer resentment)")

    if is_offer_sheet and league is not None and team is not None and from_team is not None:
        os_out = record_offer_sheet(rivalries, team, from_team, player, aav)
        texts.append(os_out["story"])
        effects.append("offer_sheet: gm_gm 80, team_team 40")

    return {"verdict": verdict, "overpay_ratio": ratio,
            "contract_pressure": pressure,
            "market_setter": bool(market_setter),
            "story": " ".join(texts), "effects": effects}


# ====================================================================# GM STATURE EFFECTS — the league judges YOU
#
# Three axes, all whispers:
#   stature  — league-wide: dealings (shrewd <-> reckless) + accolades
#              (Cups banked) + tenure (a point a year, cap 5). Moves trade
#              greed, FA/staff appeal, and the board's leash.
#   heat     — personal grudge per GM pair: offer sheets, market resets,
#              trade fleecings. A GM you burned taxes you or won't deal.
#   respect  — personal regard per GM pair (seeds 50): fair dealing builds
#              it, fleeces and offer sheets erode it. High mutual respect
#              deals easy; none at all drives harder bargains.
# Trades never move stature — other GMs don't grade your deals. The fallout
# lands on the fans/room (dynamics feed) and the owners (board events).
# ---------------------------------------------------------------------------
# career_reputation (0-100, tracked on the GM staff entity) was half-built:
# nudged by signings/offer sheets but read by nothing. This section gives it
# teeth. Stature is the "shrewd <-> incompetent" axis; gm_gm rivalry heat is
# the "ruthless <-> honorable" axis. Both feed the same decision points:
#
#   trades      -> AI greed (stature) + refusal pressure (personal heat)
#   free agency -> star acceptance + dysfunction premium on the ask
#   staff       -> top coaches' willingness to sign
#   board       -> monthly confidence drift toward stature
#
# Guardrails (Muck's rules): additive only, never overrides agreed logic;
# every consumer clamps its effect ("whisper, never shout"); nothing raises.
# ===========================================================================

GM_STATURE_NEUTRAL = 50


def gm_stature(team: Any) -> int:
    """The GM's league-wide stature, 0-100. Never raises.

    A brand-new GM (no history, rep still 0) seeds to neutral 50 through the
    existing seed_staff_reputation -- unknown, not a mark.

    The resume behind the number:
    - history of dealings: the career_reputation base (shrewd signings up,
      overpays/albatrosses/market resets down),
    - accolades: Cups bank +8 each through the existing banking,
    - tenure: +1 per season in the chair, capped at +5. Time served earns
      the benefit of the doubt.
    """
    try:
        gm = _team_gm_staff(team)
        if gm is None:
            return GM_STATURE_NEUTRAL
        ensure_reputation_fields(gm)
        rep = int(getattr(gm, "career_reputation", 0) or 0)
        if rep == 0 and not getattr(gm, "reputation_history", None):
            try:
                rep = int(seed_staff_reputation(gm))
            except Exception:
                rep = GM_STATURE_NEUTRAL
        rep += min(gm_tenure_years(team), 5)
        return max(0, min(100, rep))
    except Exception:
        return GM_STATURE_NEUTRAL


def gm_tenure_years(team: Any) -> int:
    """Distinct calendar years with any reputation history: seasons in the
    GM's chair. Never raises."""
    try:
        gm = _team_gm_staff(team)
        years = set()
        for e in (getattr(gm, "reputation_history", None) or []):
            d = (e or {}).get("date", "") or ""
            if len(d) >= 4 and d[:4].isdigit():
                years.add(d[:4])
        return len(years)
    except Exception:
        return 0


def gm_gm_heat(league: Any, team_a: Any, team_b: Any) -> int:
    """Personal heat (0-100) between two GMs. Never raises.

    Reads the gm_gm rivalry records -- offer sheets, market resets, trade
    fleecings. Distinct from team_team heat: this is personal.
    """
    try:
        store = _rivalry_store(league) if league is not None else []
        r = rivalry_between(store, gm_persona(team_a), gm_persona(team_b),
                            kind="gm_gm")
        return int(r.get("intensity", 0)) if r else 0
    except Exception:
        return 0


GM_RESPECT_NEUTRAL = 50


def _respect_store(league_or_list: Any) -> list:
    """Accept a league or a raw rivalry list; return the list. Never raises."""
    try:
        if isinstance(league_or_list, list):
            return league_or_list
        if league_or_list is None:
            return []
        return _rivalry_store(league_or_list)
    except Exception:
        return []


def gm_gm_respect(league: Any, team_a: Any, team_b: Any) -> int:
    """Mutual professional respect (0-100) between two GMs. Never raises.

    The third axis next to league-wide stature and personal heat: every pair
    of GMs carries its own level of regard. Seeds neutral 50 -- unknown, not
    disrespected. Fair dealing builds it; fleeces and offer sheets erode it.
    """
    try:
        store = _respect_store(league)
        r = rivalry_between(store, gm_persona(team_a), gm_persona(team_b),
                            kind="gm_respect")
        return int(r.get("intensity", GM_RESPECT_NEUTRAL)) if r else GM_RESPECT_NEUTRAL
    except Exception:
        return GM_RESPECT_NEUTRAL


def _league_teams(league: Any) -> list:
    """All team objects in a league (list or dict). Never raises."""
    try:
        teams = getattr(league, "teams", None) or []
        return list(teams.values()) if isinstance(teams, dict) else list(teams)
    except Exception:
        return []


def _bump_gm_respect(league: Any, team_a: Any, team_b: Any, delta: int) -> int:
    """Nudge mutual respect between two GMs, clamped 0-100. Creates the
    record at neutral 50 on first touch. Returns the new value. Never
    raises. (add_rivalry max-merges, which is wrong for respect -- this
    accumulates instead.)"""
    try:
        store = _respect_store(league)
        if league is None:
            return GM_RESPECT_NEUTRAL
        pa, pb = gm_persona(team_a), gm_persona(team_b)
        r = rivalry_between(store, pa, pb, kind="gm_respect")
        if r is None:
            ka, kb = _ekey(pa), _ekey(pb)
            if ka == kb:
                return GM_RESPECT_NEUTRAL
            if ka > kb:
                ka, kb = kb, ka
                pa, pb = pb, pa
            r = {"a": ka, "b": kb, "a_name": _ename(pa), "b_name": _ename(pb),
                 "kind": "gm_respect",
                 "intensity": max(0, min(100, GM_RESPECT_NEUTRAL + int(delta))),
                 "origin": "dealings",
                 "story": "Professional regard between two GMs.",
                 "date": date.today().isoformat(), "grudge": 0, "career_cost": 0}
            store.append(r)
            return int(r["intensity"])
        r["intensity"] = max(0, min(100, int(r.get("intensity", GM_RESPECT_NEUTRAL)) + int(delta)))
        return int(r["intensity"])
    except Exception:
        return GM_RESPECT_NEUTRAL


def gm_trade_greed_mult(league: Any, user_team: Any,
                        partner_team: Any) -> Tuple[float, List[str]]:
    """Greed multiplier for an AI GM facing YOUR offer. Never raises.

    Three axes, all whispers:
    - league-wide stature (dealings + Cups + tenure): respect earns a token
      discount, a clown reputation gets you quietly squeezed;
    - personal heat: a GM you burned taxes you harder than any team rivalry;
    - mutual respect: GMs who've done fair business deal easy; GMs with no
      regard for each other drive harder bargains.
    Team-vs-team rivalry is priced separately in trade_storylines (bitter
    rivals demand a premium there) -- this is the GM-relationship layer.
    """
    mult, notes = 1.0, []
    try:
        rep = gm_stature(user_team)
        # Flat through the middle: only the extremes move the needle.
        # A respected GM gets a token of goodwill; a GM running a muck
        # gets quietly squeezed. Everyone is still here to win.
        if rep >= 75:
            mult *= 0.97
            notes.append("respected around the league")
        elif rep < 25:
            mult *= 1.05
            notes.append("word gets around")
        heat = gm_gm_heat(league, user_team, partner_team)
        if heat >= 70:
            mult *= 1.15
            notes.append("won't do business with you")
        elif heat >= 40:
            mult *= 1.06
            notes.append("bad blood with this GM")
        resp = gm_gm_respect(league, user_team, partner_team)
        if resp >= 70:
            mult *= 0.98
            notes.append("mutual respect -- easy dealing")
        elif resp <= 30:
            mult *= 1.06
            notes.append("no respect between these GMs")
        mult = max(0.90, min(1.20, mult))
    except Exception:
        pass
    return round(mult, 3), notes


def gm_fa_accept_delta(team: Any, player: Any) -> float:
    """Acceptance-chance delta for a free agent offer. Never raises.

    Stars can afford to be picky about who they play for; depth players just
    want a contract. A whisper either way -- bounded to +/-0.05.
    """
    try:
        rep = gm_stature(team)
        try:
            star = player.overall_rating() >= 85
        except Exception:
            star = False
        scale = 1.0 if star else 0.4
        if rep >= 75:
            return round(0.05 * scale, 3)
        if rep <= 25:
            return round(-0.05 * scale, 3)
    except Exception:
        pass
    return 0.0


def gm_ask_premium(team: Any) -> float:
    """Dysfunction premium on a player's salary ask. Never raises.

    Only bites when you're genuinely running a muck (rep under 30): up to
    6% over market to get a signature. Everyone else pays sticker.
    """
    try:
        rep = gm_stature(team)
        return round(1.0 + max(0.0, (30 - rep) / 30.0) * 0.06, 3)
    except Exception:
        return 1.0


def gm_staff_accept_delta(team: Any) -> float:
    """Acceptance-chance delta for a staff/coach offer. Never raises.

    Top coaches mildly prefer a GM the league respects. Bounded to
    +/-0.05 -- money and prestige still decide.
    """
    try:
        rep = gm_stature(team)
        if rep >= 70:
            return 0.05
        if rep <= 30:
            return -0.05
    except Exception:
        pass
    return 0.0


def record_trade_outcome(league: Any, team_a: Any, team_b: Any, ratio_a: float,
                         board_a: Any = None) -> Dict[str, Any]:
    """Score a completed trade's fallout. Never raises.

    ratio_a = value team A receives / value team A gives (>=1 means A won).
    Muck's rule: a trade never moves league-wide stature -- other GMs don't
    grade your deals. The fallout lands where it belongs: the fans/room
    cheer a fleece and fume when you get worked for a key piece (dynamics
    feed), the owners react through the board, and the counterparty holds
    a personal grudge (pairwise gm_gm heat, not league opinion).
    """
    out: Dict[str, Any] = {"heat": 0, "notes": []}
    try:
        ratio = float(ratio_a)
    except Exception:
        return out
    try:
        aname = _ename(gm_persona(team_a))
        if ratio >= 1.30:
            # The building loves a fleece; the owners too. The GM on the
            # other end remembers -- personally.
            try:
                record_team_event(
                    team_a, "trade_fleece",
                    f"{aname} worked the phones and won the deal. "
                    f"The fans are buzzing.",
                    morale_delta=2, tone="up")
            except Exception:
                pass
            try:
                store = _rivalry_store(league) if league is not None else []
                r = add_rivalry(
                    store, gm_persona(team_b), gm_persona(team_a), "gm_gm",
                    40, "trade_fleece",
                    f"{_ename(gm_persona(team_b))} got worked by {aname} "
                    f"in a lopsided deal.",
                    grudge=50)
                if r:
                    out["heat"] = 40
            except Exception:
                pass
            out["notes"].append("fans cheer the fleece")
            try:
                _bump_gm_respect(league, team_a, team_b, -8)
            except Exception:
                pass
            if board_a is not None:
                try:
                    board_a.record_big_event("good_trade")
                except Exception:
                    pass
        elif ratio <= 0.75:
            # Took too little for a key piece: the room and the fans groan,
            # the owners notice. The league's opinion of you doesn't move.
            try:
                record_team_event(
                    team_a, "trade_fleeced",
                    f"{aname} sold low and the fans know it. The building "
                    f"is restless.",
                    morale_delta=-2, tone="down")
            except Exception:
                pass
            out["notes"].append("fans fume at the sell-low")
            if board_a is not None:
                try:
                    board_a.record_big_event("bad_trade")
                except Exception:
                    pass
        elif 0.90 <= ratio <= 1.10:
            # Fair dealing builds the personal ledger: mutual respect up,
            # no stature swing either way.
            try:
                _bump_gm_respect(league, team_a, team_b, 4)
            except Exception:
                pass
            out["notes"].append("a fair deal -- respect grows")
    except Exception:
        pass
    return out


def gm_board_drift(board: Any, team: Any) -> int:
    """Monthly board-confidence drift toward GM stature. Never raises.

    A respected GM gets a slightly longer leash; a GM running a muck gets
    a slightly shorter one. +/-1 per month max -- results dominate, as
    they should. Respects the can_be_sacked toggle (drift applies, the sack
    check itself honors the toggle as before).
    """
    try:
        rep = gm_stature(team)
        delta = int(round((rep - 50) / 50.0))
        if delta:
            board.confidence = max(0, min(100, board.confidence + delta))
            try:
                board._check_sack()
            except Exception:
                pass
        return delta
    except Exception:
        return 0
# ---------------------------------------------------------------------------
# Fresh start: the "you both win" payoff for analytics finds
# ---------------------------------------------------------------------------

def apply_fresh_start(player: Any, old_team: Any, new_team: Any,
                      teams: List[Any] = None) -> Dict[str, Any]:
    """A player rescued from a bad situation gets a new lease on hockey.

    When the analytics department finds the right guy in the wrong
    situation and the GM brings him home, both sides win: the player gets
    a real room, real linemates, real stakes -- and the team gets his
    real game. This is the mechanical payoff for the Moneyball loop.

    Effects scale with the size of the upgrade:
    - Lottery team -> contender: big morale/happiness lift, "reborn" narrative
    - Bad -> middling or middling -> good: moderate lift
    - Lateral or downward: no bonus (and a small grumble if it's a clear
      step down -- nobody celebrates a downgrade)

    Also records the move in the dynamics feed so the room notices the
    new guy arriving with something to prove.
    """
    ensure_reputation_fields(player)
    result: Dict[str, Any] = {"morale_delta": 0, "happiness_delta": 0,
                              "story": "", "rescue": False}

    def _pct(t) -> float:
        if t is None:
            return 0.5
        gp = getattr(t, "games_played", 0) or 0
        pts = getattr(t, "points", 0) or 0
        return (pts / (2 * gp)) if gp > 0 else 0.5

    old_pct = _pct(old_team)
    new_pct = _pct(new_team)
    upgrade = new_pct - old_pct

    pname = getattr(player, "full_name", getattr(player, "name", "The newcomer"))
    old_name = getattr(old_team, "team_name", "his old club") if old_team else "his old club"
    new_name = getattr(new_team, "team_name", "his new club") if new_team else "his new club"

    happiness = getattr(player, "happiness", 70) or 70
    morale = getattr(player, "morale", 70) or 70

    if upgrade >= 0.150:
        # Lottery -> contender: the full rebirth.
        dh, dm = 12, 10
        result["rescue"] = True
        result["story"] = (
            f"{pname} looks reborn after escaping {old_name} for {new_name}. "
            f"Going from a {old_pct:.3f} club to a {new_pct:.3f} contender has "
            f"him playing like the guy the analytics department said he was.")
    elif upgrade >= 0.070:
        dh, dm = 7, 6
        result["rescue"] = True
        result["story"] = (
            f"{pname} is settling in nicely at {new_name} after leaving "
            f"{old_name}. Better linemates, better stakes -- the underlying "
            f"numbers said this was coming.")
    elif upgrade >= 0.020:
        dh, dm = 3, 3
        result["story"] = (f"{pname} welcomes the change of scenery from "
                           f"{old_name} to {new_name}.")
    elif upgrade <= -0.100:
        # Clear step down: the guy knows it.
        dh, dm = -6, -4
        result["story"] = (
            f"{pname} isn't hiding his disappointment at going from "
            f"{old_name} to {new_name}. Somebody's agent is already "
            f"working the phones.")
    else:
        # Lateral move: small novelty bump, nothing more.
        dh, dm = 2, 1
        result["story"] = ""

    try:
        player.happiness = max(0, min(100, happiness + dh))
    except Exception:
        pass
    try:
        player.morale = max(0, min(100, morale + dm))
    except Exception:
        pass
    result["morale_delta"] = dm
    result["happiness_delta"] = dh

    # The room notices: log to the new team's dynamics feed.
    if result["story"] and new_team is not None:
        try:
            record_team_event(new_team, "fresh_start", result["story"],
                              morale_delta=dm,
                              tone="up" if dm >= 0 else "down")
        except Exception:
            pass
    return result


def watch_steal_candidate(player: Any, team: Any, tip: dict,
                          date_str: str = "") -> None:
    """Open a steal watch when a scout-tipped player is acquired via trade.

    A tip is not success; the player's later performance is. This
    snapshots his pre-trade pace so check_steal_watch() can validate
    the scout's call against what actually happens in the new uniform.
    Idempotent: re-watching the same player refreshes the snapshot.
    date_str is the simulation trade date (never wall clock).
    """
    try:
        from game_classes import PlayerPosition
        is_goalie = (getattr(player, "primary_position", None)
                     == PlayerPosition.GOALIE)
    except Exception:
        is_goalie = False
    try:
        pid = getattr(player, "id", id(player))
        watch = getattr(team, "steal_watch", None)
        if watch is None:
            team.steal_watch = watch = {}
        entry = {
            "date": str(date_str or __import__("datetime").date.today().isoformat()),
            "scout": tip.get("scout", "?"),
            "scout_id": tip.get("scout_id", ""),
            "selling_team": tip.get("selling_team", ""),
            "jpa": tip.get("jpa", 10),
            "value_score": tip.get("value_score", 0.0),
            "signals": list(tip.get("signals", []) or []),
            "is_goalie": bool(is_goalie),
            "pre_gp": int(getattr(player, "games_played", 0) or 0),
        }
        if is_goalie:
            entry["pre_saves"] = int(getattr(player, "saves", 0) or 0)
            entry["pre_sa"] = int(getattr(player, "shots_against", 0) or 0)
        else:
            entry["pre_points"] = int((getattr(player, "goals", 0) or 0)
                                      + (getattr(player, "assists", 0) or 0))
        watch[pid] = entry
    except Exception:
        pass


def watch_sell_candidate(player: Any, selling_team: Any, buying_team: Any,
                         tip: dict, date_str: str = "") -> None:
    """Open a sell watch when a sell-tipped player is traded away.

    The mirror of watch_steal_candidate: the scout said this player's
    surface production was a mirage. If he regresses in the new uniform,
    the selling scout and GM called the peak; if he thrives, the read
    failed and the doubt lands on them. Snapshots pre-trade pace.
    Idempotent per player. date_str is the simulation trade date.
    """
    try:
        from game_classes import PlayerPosition
        is_goalie = (getattr(player, "primary_position", None)
                     == PlayerPosition.GOALIE)
    except Exception:
        is_goalie = False
    try:
        pid = getattr(player, "id", id(player))
        watch = getattr(selling_team, "sell_watch", None)
        if watch is None:
            selling_team.sell_watch = watch = {}
        entry = {
            "date": str(date_str or __import__("datetime").date.today().isoformat()),
            "scout": tip.get("scout", "?"),
            "scout_id": tip.get("scout_id", ""),
            "buying_team": getattr(buying_team, "team_name", ""),
            "jpa": tip.get("jpa", 10),
            "signals": list(tip.get("signals", []) or []),
            "is_goalie": bool(is_goalie),
            "pre_gp": int(getattr(player, "games_played", 0) or 0),
        }
        if is_goalie:
            entry["pre_saves"] = int(getattr(player, "saves", 0) or 0)
            entry["pre_sa"] = int(getattr(player, "shots_against", 0) or 0)
        else:
            entry["pre_points"] = int((getattr(player, "goals", 0) or 0)
                                      + (getattr(player, "assists", 0) or 0))
        watch[pid] = entry
    except Exception:
        pass


def _grade_watch_scout(team: Any, scout_id: str, result: str,
                       player_name: str, kind: str, date_str: str) -> None:
    """Grade the scout behind a watch. Lazy import: no cycle."""
    try:
        import analytics_scouting as _as
        scout = _as.find_scout_by_id(team, scout_id)
        if scout is not None:
            _as.grade_scout_call(scout, result, player_name, kind,
                                 date_str)
    except Exception:
        pass


def _nudge_philosophy(team: Any, delta: float) -> None:
    try:
        import analytics_scouting as _as
        _as.nudge_philosophy(team, delta)
    except Exception:
        pass


def check_steal_watch(team: Any, league: Any = None,
                      date_str: str = "") -> List[Dict[str, Any]]:
    """Validate pending steal watches against post-trade production.

    Called monthly. For each watched player with 15+ games since the
    trade (10+ for goalies):
    - Skaters: VALIDATED if post-trade P/GP beats pre-trade pace by
      0.30+ or reaches star pace (0.85+). The scout saw it coming.
    - Goalies: VALIDATED if post-trade SV% beats pre-trade by .015+.
    Watches expire after 50 games without validation -- the scout was
    wrong. Expiry is NOT silent: it grades a miss on the scout's record
    and plants doubt in the room. The tip alone never triggers the
    payoff; only the performance window does.

    date_str is the simulation date used for grading stamps.
    Returns event dicts; each may carry "news" (str) for the feed and
    "kind" in {"steal_validated", "steal_failed"}.
    """
    from datetime import date as _date
    events: List[Dict[str, Any]] = []
    try:
        watch = getattr(team, "steal_watch", None) or {}
        if not watch:
            return events
        today = str(date_str or _date.today().isoformat())
        tname = getattr(team, "team_name", "?")
        roster = list(getattr(team, "roster", []) or [])
        by_id = {getattr(p, "id", id(p)): p for p in roster}
        for pid in list(watch.keys()):
            entry = watch[pid]
            player = by_id.get(pid)
            pname = getattr(player, "full_name",
                            getattr(player, "name", "?")) \
                if player is not None else "?"
            if player is None:
                # Player moved on; watch dies with the tenure.
                del watch[pid]
                continue
            gp_now = int(getattr(player, "games_played", 0) or 0)
            post_gp = gp_now - int(entry.get("pre_gp", 0) or 0)
            if post_gp < 0:
                # Season rollover wiped totals; re-baseline the watch.
                entry["pre_gp"] = gp_now
                if entry.get("is_goalie"):
                    entry["pre_saves"] = int(getattr(player, "saves", 0) or 0)
                    entry["pre_sa"] = int(getattr(player, "shots_against", 0) or 0)
                else:
                    entry["pre_points"] = int((getattr(player, "goals", 0) or 0)
                                              + (getattr(player, "assists", 0) or 0))
                continue
            hit = False
            if entry.get("is_goalie"):
                if post_gp >= 10:
                    sa = int(getattr(player, "shots_against", 0) or 0) - int(entry.get("pre_sa", 0) or 0)
                    sv = int(getattr(player, "saves", 0) or 0) - int(entry.get("pre_saves", 0) or 0)
                    if sa > 0:
                        post_sv = sv / sa
                        pre_sa = int(entry.get("pre_sa", 0) or 0)
                        pre_sv_n = int(entry.get("pre_saves", 0) or 0)
                        pre_sv = (pre_sv_n / pre_sa) if pre_sa > 0 else 0.900
                        hit = (post_sv - pre_sv) >= 0.015
            else:
                if post_gp >= 15:
                    pts_now = int((getattr(player, "goals", 0) or 0)
                                  + (getattr(player, "assists", 0) or 0))
                    post_pts = pts_now - int(entry.get("pre_points", 0) or 0)
                    post_ppg = post_pts / post_gp
                    pre_gp = int(entry.get("pre_gp", 0) or 0)
                    pre_ppg = (int(entry.get("pre_points", 0) or 0) / pre_gp) if pre_gp > 0 else 0.0
                    hit = (post_ppg - pre_ppg) >= 0.30 or post_ppg >= 0.85
            scout_name = entry.get("scout", "?")
            if hit:
                _grade_watch_scout(team, entry.get("scout_id", ""),
                                   "hit", pname, "buy", today)
                _nudge_philosophy(team, +4.0)
                # Resolve the selling club to its team object so the
                # payoff can criticize the actual counterparty.
                _cp_team = None
                _cp_name = str(entry.get("selling_team", "") or "")
                if _cp_name:
                    for _t in _league_teams(league):
                        if getattr(_t, "team_name", "") == _cp_name:
                            _cp_team = _t
                            break
                note_tip_payoff(
                    "buy_validated", player, team,
                    counterparty_name=_cp_name,
                    counterparty_team=_cp_team,
                    scout_name=scout_name, league=league,
                    signals=list(entry.get("signals", []) or []))
                events.append({"kind": "steal_validated",
                               "player": player, "team": team,
                               "scout": scout_name, "post_gp": post_gp,
                               "news": (
                                   f"VALIDATED READ -- {scout_name}'s call on "
                                   f"{pname} paid off: producing since the "
                                   f"move to {tname}. The pro scouts earned "
                                   f"their paychecks.")})
                del watch[pid]
            elif post_gp >= 50:
                # Failed bet: doubt, not silence. The scout's record takes
                # the miss; the room notices the read didn't pan out.
                _grade_watch_scout(team, entry.get("scout_id", ""),
                                   "miss", pname, "buy", today)
                _nudge_philosophy(team, -3.0)
                try:
                    record_team_event(
                        team, "analytics_flop",
                        f"{scout_name}'s read on {pname} hasn't panned out "
                        f"({post_gp} games since the move). The room is "
                        f"wondering about that pro-scouting department.",
                        morale_delta=-1, tone="down")
                except Exception:
                    pass
                try:
                    _bump_gm_respect(league, team, team, -2)
                except Exception:
                    pass
                events.append({"kind": "steal_failed",
                               "player": player, "team": team,
                               "scout": scout_name, "post_gp": post_gp})
                del watch[pid]
    except Exception:
        pass
    return events


def check_sell_watch(team: Any, teams: List[Any],
                     league: Any = None,
                     date_str: str = "") -> List[Dict[str, Any]]:
    """Validate pending sell watches against post-trade regression.

    Called monthly on the SELLING team. The watched player now skates
    elsewhere, so he is resolved across all rosters.
    - VALIDATED (15+ post-trade GP, P/GP <= 70% of pre-trade pace):
      the scout called the peak. Selling GM banks credit; the buyer
      takes market criticism.
    - EXPIRED (50+ GP without regression): the read failed -- doubt,
      not silence.
    Returns event dicts with kinds "sell_validated" / "sell_failed".
    date_str is the simulation date used for grading stamps.
    """
    from datetime import date as _date
    events: List[Dict[str, Any]] = []
    try:
        watch = getattr(team, "sell_watch", None) or {}
        if not watch:
            return events
        today = str(date_str or _date.today().isoformat())
        tname = getattr(team, "team_name", "?")
        # Authoritative roster map: player id -> player AND the team
        # object currently rostering him. No name-matching.
        by_id: Dict[Any, Any] = {}
        team_of: Dict[Any, Any] = {}
        for t in teams or []:
            for p in list(getattr(t, "roster", []) or []):
                _pid = getattr(p, "id", id(p))
                by_id[_pid] = p
                team_of[_pid] = t
        buying_team = None
        for pid in list(watch.keys()):
            entry = watch[pid]
            player = by_id.get(pid)
            pname = getattr(player, "full_name",
                            getattr(player, "name", "?")) \
                if player is not None else "?"
            if player is None:
                del watch[pid]
                continue
            buying_team = team_of.get(pid)
            gp_now = int(getattr(player, "games_played", 0) or 0)
            post_gp = gp_now - int(entry.get("pre_gp", 0) or 0)
            if post_gp < 0:
                entry["pre_gp"] = gp_now
                if entry.get("is_goalie"):
                    entry["pre_saves"] = int(getattr(player, "saves", 0) or 0)
                    entry["pre_sa"] = int(getattr(player, "shots_against", 0) or 0)
                else:
                    entry["pre_points"] = int((getattr(player, "goals", 0) or 0)
                                              + (getattr(player, "assists", 0) or 0))
                continue
            hit = False
            if entry.get("is_goalie"):
                if post_gp >= 10:
                    sa = int(getattr(player, "shots_against", 0) or 0) - int(entry.get("pre_sa", 0) or 0)
                    sv = int(getattr(player, "saves", 0) or 0) - int(entry.get("pre_saves", 0) or 0)
                    if sa > 0:
                        post_sv = sv / sa
                        pre_sa = int(entry.get("pre_sa", 0) or 0)
                        pre_sv_n = int(entry.get("pre_saves", 0) or 0)
                        pre_sv = (pre_sv_n / pre_sa) if pre_sa > 0 else 0.900
                        hit = (pre_sv - post_sv) >= 0.015
            else:
                if post_gp >= 15:
                    pts_now = int((getattr(player, "goals", 0) or 0)
                                  + (getattr(player, "assists", 0) or 0))
                    post_pts = pts_now - int(entry.get("pre_points", 0) or 0)
                    post_ppg = post_pts / post_gp
                    pre_gp = int(entry.get("pre_gp", 0) or 0)
                    pre_ppg = (int(entry.get("pre_points", 0) or 0) / pre_gp) if pre_gp > 0 else 0.0
                    hit = (pre_ppg > 0.15) and (post_ppg <= pre_ppg * 0.70)
            scout_name = entry.get("scout", "?")
            bname = (getattr(buying_team, "team_name", "?")
                     if buying_team is not None
                     else entry.get("buying_team", "?"))
            if hit:
                _grade_watch_scout(team, entry.get("scout_id", ""),
                                   "hit", pname, "sell", today)
                _nudge_philosophy(team, +3.0)
                note_tip_payoff(
                    "sell_validated", player, team,
                    counterparty_name=bname, scout_name=scout_name,
                    league=league,
                    signals=list(entry.get("signals", []) or []),
                    counterparty_team=buying_team)
                events.append({"kind": "sell_validated",
                               "player": player, "team": team,
                               "scout": scout_name, "post_gp": post_gp,
                               "news": (
                                   f"CALLED THE PEAK -- {scout_name} flagged "
                                   f"{pname}'s decline before {tname} moved "
                                   f"him, and the numbers have collapsed "
                                   f"since. {bname} bought high.")})
                del watch[pid]
            elif post_gp >= 50:
                _grade_watch_scout(team, entry.get("scout_id", ""),
                                   "miss", pname, "sell", today)
                try:
                    record_team_event(
                        team, "sell_flop",
                        f"{scout_name} said {pname}'s best hockey was behind "
                        f"him -- {post_gp} games later he's thriving "
                        f"elsewhere. That one stings in the front office.",
                        morale_delta=-1, tone="down")
                except Exception:
                    pass
                events.append({"kind": "sell_failed",
                               "player": player, "team": team,
                               "scout": scout_name, "post_gp": post_gp})
                del watch[pid]
    except Exception:
        pass
    return events


def note_tip_payoff(kind: str, player: Any, team: Any,
                    counterparty_name: str = "", scout_name: str = "?",
                    league: Any = None, signals: List[str] = None,
                    counterparty_team: Any = None) -> None:
    """One event feeds several systems (regression payoff narratives).

    kind "buy_validated": the tipped player genuinely broke out after
    the acquiring team bet on the scout's read. The payoff lands in
    every system the roadmap names:
      - the acquiring scout's record (graded by the caller),
      - the acquiring GM's reputation (eye for talent),
      - player confidence (vindicated: morale/happiness lift),
      - fan-favourite acceleration (standing bump + buzz),
      - media framing (dynamics event naming the scout + department),
      - the seller's market criticism (respect nick + "sold low" note).
    kind "sell_validated": the sold player's production collapsed as the
    scout predicted. The selling GM banks "called the peak" credit; the
    BUYER takes the market criticism for buying high.
    """
    signals = signals or []
    try:
        ensure_reputation_fields(player)
        pname = getattr(player, "full_name", getattr(player, "name", "?"))
        tname = getattr(team, "team_name", "?") if team is not None else "?"
        sig = f" ({'; '.join(signals[:2])})" if signals else ""

        if kind == "buy_validated":
            story = (f"The analytics department called it: {pname} is "
                     f"producing like a star at {tname}{sig}. "
                     f"{scout_name} saw it first -- the pro scouts earned "
                     f"their paychecks, and the fans are buzzing.")
            try:
                record_team_event(team, "analytics_steal", story,
                                  morale_delta=2, tone="up")
            except Exception:
                pass
            # Player confidence: vindicated.
            try:
                player.morale = min(100, int(getattr(player, "morale", 50) or 50) + 4)
                player.happiness = min(100, int(getattr(player, "happiness", 50) or 50) + 4)
            except Exception:
                pass
            # Fan-favourite acceleration: validated breakouts bank standing.
            try:
                player.reputation = min(
                    100, (getattr(player, "reputation", 0) or 0) + 4)
            except Exception:
                pass
            # Acquiring GM: eye for talent. Seller: market criticism.
            if league is not None and counterparty_team is not None:
                try:
                    _bump_gm_respect(league, team, counterparty_team, +6)
                    _bump_gm_respect(league, counterparty_team, team, -6)
                except Exception:
                    pass
            if counterparty_name:
                try:
                    record_team_event(
                        counterparty_team, "sold_low",
                        f"Sold low on {pname} -- he's breaking out at "
                        f"{tname}{sig}. The market noticed.",
                        morale_delta=-1, tone="down")
                except Exception:
                    pass
        elif kind == "sell_validated":
            story = (f"{scout_name} called the peak: {pname}'s production "
                     f"has collapsed since {tname} moved him{sig}. Selling "
                     f"before the decline -- that's pro scouting.")
            try:
                record_team_event(team, "called_the_peak", story,
                                  morale_delta=2, tone="up")
            except Exception:
                pass
            try:
                player.reputation = max(
                    0, (getattr(player, "reputation", 0) or 0) - 3)
            except Exception:
                pass
            if league is not None and counterparty_team is not None:
                try:
                    _bump_gm_respect(league, team, counterparty_team, +6)
                    _bump_gm_respect(league, counterparty_team, team, -6)
                except Exception:
                    pass
                try:
                    record_team_event(
                        counterparty_team, "bought_high",
                        f"Bought high on {pname} -- his production has "
                        f"fallen off since the move{sig}. The market "
                        f"noticed.",
                        morale_delta=-1, tone="down")
                except Exception:
                    pass
            elif counterparty_name:
                pass  # buyer unknown; credit stands without criticism
    except Exception:
        pass


def note_analytics_steal(player: Any, team: Any, value_score: float,
                         signals: List[str]) -> None:
    """Legacy entry point -- kept for save/call compatibility.

    Routes into the full payoff chain as a buy-side validation without
    counterparty attribution.
    """
    try:
        note_tip_payoff("buy_validated", player, team,
                        counterparty_name="", scout_name="The pro scouts",
                        league=None, signals=signals or [])
    except Exception:
        pass
