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
from datetime import date
from typing import List, Dict, Optional, Any

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
    # Team-level dynamics state (survives saves once the dataclass lands).
    if hasattr(entity, "roster") and hasattr(entity, "staff"):
        if not hasattr(entity, "dynamics_log") or entity.dynamics_log is None:
            entity.dynamics_log = []
        if not hasattr(entity, "line_control") or entity.line_control is None:
            entity.line_control = "coach"


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
    """Seed a 0-100 career reputation from the legacy 5-15 staff reputation."""
    ensure_reputation_fields(staff)
    legacy = getattr(staff, "reputation", 10)  # legacy 5-15 scale
    # Map 5-15 -> 20-70 so existing staff land mid-range, room to grow
    mapped = int(20 + (max(5, min(15, legacy)) - 5) * 5)
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
                            championships: int = 0) -> int:
    """Move a staff member's 0-100 career_reputation for the season.

    A .500 season holds steady; winning builds slowly, losing erodes
    (coaches, unlike players, CAN lose standing -- that's the hot seat).
    Championships bank +12. Clamped to 0-100.
    """
    ensure_reputation_fields(staff)
    try:
        current = getattr(staff, "career_reputation", 0) or 0
        # Win% swing capped at +/-5 per season; Cups are the big movers.
        swing = max(-5, min(5, int((team_win_pct - 0.5) * 10)))
        target = max(0, min(100, current + swing + championships * 12))
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

    Low discipline / low teamwork players live hotter by default.
    """
    try:
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


def decay_controversy(entity: Any, incidents_this_season: int = 0) -> int:
    """Cool controversy down after a clean season.

    Unlike reputation, controversy fades -- but never below the
    personality baseline. Called from the end-of-season hook.
    """
    ensure_reputation_fields(entity)
    if incidents_this_season == 0:
        baseline = controversy_baseline(entity)
        entity.controversy = max(
            baseline, entity.controversy - CONTROVERSY_DECAY_PER_CLEAN_SEASON
        )
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

def _staff_100(entity: Any, attr: str, default: int = 10) -> float:
    """Staff 1-20 attribute -> 0-100 scale."""
    try:
        v = getattr(entity, attr, default)
        v = default if v is None else v
        return max(1, min(20, int(v))) * 5
    except Exception:
        return default * 5


def _is_staff(entity: Any) -> bool:
    return hasattr(entity, "role") and not hasattr(entity, "primary_position")


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
                v = getattr(entity, attr, 12) or 12
                f = max(0.0, (12 - v)) / 20 * w
                factors.append((label, round(f, 3)))
            # 6. Discipline mismatch (two-sided, very NHL) ---------------------
            disc = getattr(entity, "discipline", 10) or 10
            if roster:
                avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / len(roster)
                avg_lead = sum(getattr(p, "leadership", 50) or 50 for p in roster) / len(roster)
                avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / len(roster)
                if disc >= 15 and avg_age >= 28.5 and avg_lead >= 60:
                    factors.append(("Drill sergeant vs veteran room", 0.14))
                if disc <= 8 and (avg_vol >= 38 or avg_age <= 25):
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
        # Deviation from the NHL-average 10: only DISTINCTIVE traits define
        # a style. An all-average coach is balanced, not a weak motivator.
        d = lambda a: (getattr(coach, a, 10) or 10) - 10  # 1-20 scale
        scores = {
            "drill_sergeant": d("discipline") * 2 + d("motivating") * 0.5 - d("man_management") * 0.5,
            "players_coach": d("man_management") * 2 + d("motivating") * 0.5 - d("discipline") * 0.5,
            "tactician": d("tactical_knowledge") * 2 + d("game_preparation") * 0.5,
            "motivator": d("motivating") * 2 + d("leadership") * 1.5,
            "developer": d("working_with_youngsters") * 2 + d("player_development"),
        }
        best = max(scores, key=scores.get)
        # Nothing distinctive -> balanced.
        if scores[best] < 6:
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
        conf = getattr(player, "morale", 10) or 10  # form/confidence, ~1-20
        if age <= 23 and vol >= 45:
            key = "needs_guidance"
        elif flair >= 68 and disc < 50:
            key = "needs_freedom"
        elif disc >= 62 and vol < 35:
            key = "thrives_on_structure"
        elif age >= 32 and lead >= 68:
            key = "veteran_autonomy"
        elif happy < 50 or conf <= 6:
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
        mm = getattr(coach, "man_management", 10) or 10
        fit += (mm - 10) / 10 * 0.25
        # Brash player + weak communicator = oil and water.
        if (player.controversy or 0) >= 60 and mm < 10:
            fit -= 0.2
        return round(max(-1.0, min(1.0, fit)), 3)
    except Exception:
        return 0.0


def player_coach_response(player: Any, coach: Any,
                          team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """How THIS player is responding to the coach: bought in -> quit."""
    try:
        fit = coach_player_fit(coach, player)
        happy = getattr(player, "happiness", 70) or 70
        score = fit * 0.6 + (happy - 65) / 100 * 0.4
        if score >= 0.30:
            label = "Bought in"
        elif score >= -0.05:
            label = "Neutral"
        elif score >= -0.35:
            label = "Tuning out"
        else:
            label = "Quit on coach"
        return {"score": round(score, 3), "label": label,
                "fit": fit, "engagement": engagement_style(player)["label"]}
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
    mot = getattr(coach, "motivating", 10) or 10
    lead = getattr(coach, "leadership", 10) or 10
    if mot >= 14 or lead >= 14:
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
                          roster: List[Any]) -> Dict[str, Any]:
    """Coach mistreats (benches/buries) a player. The target seethes; if he's
    popular, the room notices."""
    ensure_reputation_fields(player)
    name = getattr(player, "full_name", "Unknown")
    player.happiness = max(0, (getattr(player, "happiness", 70) or 70) - 15)
    player.controversy = min(100, (player.controversy or 0) + 5)
    pop = team_perception(player, roster=roster)
    if pop >= 65:
        _shift_happiness(roster, -3, lambda p: p is not player)
        text = (f"{getattr(coach, 'full_name', 'Coach')} buried {name}. "
                f"The room thinks it's unfair -- popular players have long memories.")
        delta = -4
    else:
        text = f"{getattr(coach, 'full_name', 'Coach')} buried {name}. Few complaints."
        delta = -1
    return record_team_event(team, "mistreatment", text, morale_delta=delta, tone="down")


def detect_dynamics_issues(team: Any, team_context: Optional[Dict[str, Any]],
                           roster: List[Any], coach: Any) -> List[Dict[str, Any]]:
    """Watch-list: structural problems the numbers can see right now."""
    issues: List[Dict[str, Any]] = []
    try:
        ctx = team_context or {}
        win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
        disc = getattr(coach, "discipline", 10) or 10
        style = coach_style(coach)
        n = max(1, len(roster))
        avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / n
        avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / n
        avg_flair = sum(getattr(p, "flair", 50) or 50 for p in roster) / n
        tactic = getattr(team, "tactic_even_strength", "Balanced")

        streak = ctx.get("losing_streak", 0)
        if streak >= 3 and disc >= 13:
            issues.append({"key": "too_tense", "severity": "high",
                           "text": f"Players look tense -- {streak}-game skid under a demanding coach. The room is gripping the sticks."})
        if avg_age <= 25.5 and disc <= 8:
            issues.append({"key": "not_hard_enough", "severity": "high",
                           "text": "Young group, soft practices: the coach isn't demanding enough and it shows."})
        if avg_vol >= 40 and disc <= 9:
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
                 roster: Optional[List[Any]] = None) -> Dict[str, Any]:
    """The GM advises the coach. Whether he listens depends on personality:
    adaptable communicators listen; brash, stubborn coaches take it as an
    insult. Trust (gm_trust) evolves with every exchange."""
    ensure_reputation_fields(coach)
    if not hasattr(coach, "gm_trust") or coach.gm_trust is None:
        coach.gm_trust = 70
    label = ADVICE_TYPES.get(advice_key, advice_key)
    brash = (coach.controversy or 0) >= 60
    try:
        adapt = getattr(coach, "adaptability", 10) or 10
        mm = getattr(coach, "man_management", 10) or 10
        p = (0.35 + (adapt * 5) / 100 * 0.30
             + (100 - (coach.controversy or 0)) / 100 * 0.20
             + (mm * 5) / 100 * 0.15
             + (coach.gm_trust - 70) / 100 * 0.50)
        if brash:
            p *= 0.6  # takes advice as an insult
        p = max(0.05, min(0.95, p))
        listened = random.random() < p
        cname = getattr(coach, "full_name", "Coach")
        if listened:
            coach.gm_trust = min(100, coach.gm_trust + 5)
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
