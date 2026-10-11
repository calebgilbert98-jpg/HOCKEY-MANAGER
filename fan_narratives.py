# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Fan-driven narratives — Bucket 5 (Muck 2026-10-02).

Wires fan sentiment into the story ecosystem. When fans are furious, the
media talks about firing the coach. When they're ecstatic, it's Cup parade
talk. Fan mood shapes narratives, media tone, and (subtly) gameplay.

Design principles:
- Additive only: never replaces existing narrative logic, only adds fan-driven stories
- Never raises: all functions try/except guarded
- Subtle effects: fan sentiment nudges, never dictates
- Cross-season memory: Cup wins buy goodwill; losing decades breed cynicism
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

try:
    from fan_sentiment import get_fan_sentiment, sentiment_label
except Exception:
    def get_fan_sentiment(team: Any, current_date: Any = None) -> float:  # type: ignore
        return 60.0

    def sentiment_label(value: float) -> str:  # type: ignore
        return "Content"


# ---------------------------------------------------------------------------
# Sentiment tiers (aligned with fan_sentiment.sentiment_label)
# ---------------------------------------------------------------------------

TIER_ECSTATIC = "ecstatic"      # 85+
TIER_HAPPY = "happy"            # 70-84
TIER_CONTENT = "content"        # 55-69
TIER_RESTLESS = "restless"      # 40-54
TIER_ANGRY = "angry"            # 25-39
TIER_FURIOUS = "furious"        # 0-24


def sentiment_tier(value: float) -> str:
    """Map 0-100 sentiment to a narrative tier."""
    try:
        v = float(value)
    except Exception:
        return TIER_CONTENT
    if v >= 85:
        return TIER_ECSTATIC
    if v >= 70:
        return TIER_HAPPY
    if v >= 55:
        return TIER_CONTENT
    if v >= 40:
        return TIER_RESTLESS
    if v >= 25:
        return TIER_ANGRY
    return TIER_FURIOUS


# ---------------------------------------------------------------------------
# Fan-driven narrative generation
# ---------------------------------------------------------------------------

def _team_name(team: Any) -> str:
    try:
        return str(getattr(team, "name", getattr(team, "city", "the team")))
    except Exception:
        return "the team"


def _coach_name(team: Any) -> str:
    try:
        coach = getattr(team, "head_coach", None)
        if coach:
            return str(getattr(coach, "name", getattr(coach, "full_name", "the coach")))
    except Exception:
        pass
    return "the coach"


def _safe_name(v: Any) -> str:
    """Sanitize a name for use as a .format() substitution value.

    Call-site only: strips "{" / "}" so hostile data can never render as
    leftover template braces in headlines/bodies, and replaces newlines
    with spaces so names can't break single-line output. Never applied
    where names are computed or persisted (news_log etc. keep the
    original values) -- only wrapped around the values at the .format()
    call sites below.
    """
    try:
        _s = str(v)
    except Exception:
        return ""
    return (
        _s.replace("{", "")
        .replace("}", "")
        .replace("\r", " ")
        .replace("\n", " ")
    )


# ---------------------------------------------------------------------------
# Fan narrative text variants (DEV-D: narrative text only).
#
# Each tier gets a list of (headline, body) pairs chosen via random.choice.
# RULES (hard):
#   - Headlines and bodies may use ONLY the {tname} and {cname} slots.
#     These are the only slots generate_fan_narrative computes; adding a
#     slot is a KeyError and a FAIL.
#   - The returned dict shape is exactly
#     {kind, tier, headline, body, weight, audience} with the per-tier
#     kind/weight values unchanged.
#   - Never invent stats, streaks, or events. The tier itself is the only
#     fact the text may lean on.
# ---------------------------------------------------------------------------

_FAN_FURIOUS_VARIANTS: List[tuple] = [
    (f"{{tname}} fans demand change: 'Fire {{cname}}' chants ring out",
     f"The fanbase has reached a breaking point. Boos cascade down "
     f"with every mistake, and social media is ablaze with calls for "
     f"{{cname}}'s job. The building feels toxic."),
    (f"Booed off the ice: {{tname}} faithful have seen enough",
     f"The jeers are loud and relentless. {{tname}} fans are "
     f"directing their fury at the bench, and {{cname}} is hearing "
     f"every word of it."),
    (f"'Fire {{cname}}' chants echo through {{tname}}",
     f"It's open revolt in the stands. {{tname}} supporters are done "
     f"waiting for change and they're not being quiet about it anymore."),
    (f"Mutiny in {{tname}}: the fanbase turns on {{cname}}",
     f"Once-loyal supporters are calling for heads. The {{tname}} "
     f"building feels hostile, and the message to the front office "
     f"could not be clearer."),
    (f"{{tname}} fans at the breaking point",
     f"Every mistake draws a chorus of boos. {{tname}} fans have run "
     f"out of patience, and the anger in the building is impossible "
     f"to ignore."),
    (f"Enough is enough in {{tname}}: fans want {{cname}} gone",
     f"The faithful are fuming. In "
     f"{{tname}}, the conversation has moved past frustration to "
     f"outright demands for a coaching change."),
    (f"Toxic atmosphere as {{tname}} fans vent their fury",
     f"The building feels hostile. {{tname}} supporters are letting "
     f"the team hear it, and the loudest boos are reserved "
     f"for the bench."),
    (f"The hot seat is scorching: {{tname}} fans turn on {{cname}}",
     f"There's no more defending it in {{tname}}. The fanbase has "
     f"decided {{cname}} is the problem, and the chants are only "
     f"getting louder."),
    (f"Uprising in the stands: {{tname}} faithful demand answers",
     f"It's not just the mood -- it's the direction. {{tname}} fans "
     f"want to know what the plan is, and they want {{cname}} to "
     f"explain it or leave."),
    (f"{{tname}} building turns on its own team",
     f"When the loudest noise in the barn is aimed at the home bench, "
     f"you know it's bad. {{tname}} fans have turned their anger "
     f"inward, and nobody behind the bench is safe from it."),
]

_FAN_ANGRY_VARIANTS: List[tuple] = [
    (f"Restless in {{tname}}: fans growing impatient",
     f"Grumbling in the stands is getting louder. {{tname}} supporters "
     f"are questioning the direction, and patience is wearing thin."),
    (f"Grumbling in {{tname}}: patience wearing thin",
     f"The grumbles in the stands are getting harder to ignore. "
     f"{{tname}} fans still show up, but the faith is fading."),
    (f"{{tname}} fans starting to question the direction",
     f"The anger is real now -- and it's spreading. {{tname}} supporters are "
     f"asking what the plan is, and nobody seems to have an answer."),
    (f"Discontent brewing among {{tname}} faithful",
     f"The building is quieter than it should be. {{tname}} fans are "
     f"still in their seats, but the belief is leaking out of them."),
    (f"Restlessness sets in for {{tname}}",
     f"The energy in the building is fading. {{tname}} fans are "
     f"running out of reasons to keep the faith."),
    (f"{{tname}} fans want more -- and they're saying so",
     f"The murmur is turning into a message. {{tname}} supporters "
     f"love this team, but love is starting to look a lot like "
     f"frustration."),
    (f"Frustration mounting in {{tname}}",
     f"You can feel it in the building: the groans, the nervous "
     f"energy, the shorter leash. {{tname}} fans are losing their "
     f"patience."),
    (f"The {{tname}} faithful are angry -- and getting louder",
     f"What started as grumbling is becoming a chorus. {{tname}} "
     f"fans want answers, and they want them soon."),
    (f"Questions piling up in {{tname}}",
     f"The fanbase isn't furious yet, but the questions are stacking "
     f"up. {{tname}} supporters want to know where this is headed."),
    (f"{{tname}} fans running out of patience",
     f"The goodwill is gone. {{tname}} fans are still showing up, "
     f"but the leash is getting shorter by the night."),
]

_FAN_ECSTATIC_VARIANTS: List[tuple] = [
    (f"{{tname}} fever: Cup parade routes being discussed",
     f"The building is electric every night. {{tname}} fans are "
     f"dreaming big, and the buzz around this team is palpable. "
     f"The noise is relentless."),
    (f"Cup dreams in {{tname}}: the bandwagon is full",
     f"The building is shaking every night. {{tname}} fans are "
     f"talking June hockey, and nobody is telling them to calm down."),
    (f"Electric in {{tname}}: the barn is rocking",
     f"Visiting teams are dreading the trip in. {{tname}} fans have "
     f"turned the building into the loudest room in hockey."),
    (f"{{tname}} fever grips the city",
     f"Jerseys everywhere, watch parties packed, the building "
     f"rocking. {{tname}} has the whole town believing."),
    (f"Standing room only: {{tname}} is the hottest ticket in town",
     f"Tickets are gold dust. {{tname}} fans are packing the building "
     f"every night and making it count."),
    (f"Parade talk in {{tname}}",
     f"It's the biggest dream in hockey and nobody's hiding it. "
     f"{{tname}} fans are dreaming big, and the buzz is everywhere."),
    (f"The loudest building in hockey belongs to {{tname}}",
     f"Visiting benches can't hear themselves think. {{tname}} fans "
     f"are bringing playoff-level noise to every single night."),
    (f"{{tname}} fans believing -- and why not?",
     f"The energy is real and it's earned. {{tname}} supporters are "
     f"riding this wave all the way."),
    (f"{{tname}} fever hits new heights",
     f"The pregame roar is deafening. {{tname}} fans have made the "
     f"building a fortress, and they know it."),
    (f"Dream season brewing in {{tname}}",
     f"The whole city is buzzing. {{tname}} fans can feel something "
     f"special happening, and they're savoring every minute of it."),
]

_FAN_HAPPY_VARIANTS: List[tuple] = [
    (f"{{tname}} fans riding high",
     f"Good vibes in {{tname}}. The fanbase is behind this team, "
     f"and the building has real energy."),
    (f"Good vibes in {{tname}}",
     f"The building has a buzz to it. {{tname}} fans are enjoying "
     f"the ride and showing up loud."),
    (f"{{tname}} faithful firmly behind this team",
     f"No grumbling in the stands these days. {{tname}} supporters "
     f"like what they see and they're letting the team know it."),
    (f"Smiles in the stands: {{tname}} fans feeling good",
     f"The mood around {{tname}} is light. Fans are coming to the "
     f"rink happy and leaving happier."),
    (f"The barn is happy in {{tname}}",
     f"There's a real warmth in the building. {{tname}} fans are "
     f"proud of this group and it shows."),
    (f"{{tname}} fans enjoying the ride",
     f"No doom, no gloom. {{tname}} supporters are having fun "
     f"watching this team play."),
    (f"Belief building among {{tname}} faithful",
     f"The optimism feels earned. {{tname}} fans "
     f"genuinely believe in this team, and the energy is growing."),
    (f"{{tname}}: a fanbase in a good place",
     f"The building feels right. {{tname}} fans are engaged, "
     f"optimistic, and making noise for all the right reasons."),
    (f"Warm nights in {{tname}}",
     f"The rink has a glow to it. {{tname}} fans are behind the "
     f"bench, behind the team, and loving it."),
    (f"{{tname}} fans have their team's back",
     f"Through thick and thin, the faithful show up. Right now in "
     f"{{tname}}, it's the good kind of showing up."),
]


def generate_fan_narrative(team: Any, current_date: Any = None) -> Optional[Dict[str, Any]]:
    """Generate a fan-driven narrative based on current sentiment.

    Returns a narrative dict (or None) suitable for the narrative ledger /
    media system. Never raises.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)
        tname = _team_name(team)
        cname = _coach_name(team)

        if tier == TIER_FURIOUS:
            _headline, _body = random.choice(_FAN_FURIOUS_VARIANTS)
            return {
                "kind": "fan_unrest",
                "tier": tier,
                "headline": _headline.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "body": _body.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "weight": 75,
                "audience": "fans",
            }
        elif tier == TIER_ANGRY:
            _headline, _body = random.choice(_FAN_ANGRY_VARIANTS)
            return {
                "kind": "fan_unrest",
                "tier": tier,
                "headline": _headline.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "body": _body.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "weight": 50,
                "audience": "fans",
            }
        elif tier == TIER_ECSTATIC:
            _headline, _body = random.choice(_FAN_ECSTATIC_VARIANTS)
            return {
                "kind": "fan_buzz",
                "tier": tier,
                "headline": _headline.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "body": _body.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "weight": 70,
                "audience": "fans",
            }
        elif tier == TIER_HAPPY:
            _headline, _body = random.choice(_FAN_HAPPY_VARIANTS)
            return {
                "kind": "fan_buzz",
                "tier": tier,
                "headline": _headline.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "body": _body.format(tname=_safe_name(tname), cname=_safe_name(cname)),
                "weight": 40,
                "audience": "fans",
            }
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Media tone shifts
# ---------------------------------------------------------------------------

def media_tone_for_sentiment(team: Any, current_date: Any = None) -> str:
    """Return a media tone modifier based on fan sentiment.

    Used by the media system to shift headline tone. Never raises.
    Returns: "hostile" | "critical" | "neutral" | "warm" | "glowing"
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)
        return {
            TIER_FURIOUS: "hostile",
            TIER_ANGRY: "critical",
            TIER_RESTLESS: "neutral",
            TIER_CONTENT: "neutral",
            TIER_HAPPY: "warm",
            TIER_ECSTATIC: "glowing",
        }.get(tier, "neutral")
    except Exception:
        return "neutral"


# ---------------------------------------------------------------------------
# Subtle gameplay effects
# ---------------------------------------------------------------------------

def _memory_sentiment(team: Any, current_date: Any = None) -> float:
    """Fan sentiment with cross-season memory applied.

    A Cup winner's goodwill keeps the building loud longer; a decade of
    losing keeps it quiet. Falls back to the base reading when the
    memory module is unavailable. Never raises.
    """
    try:
        from fan_sentiment import get_fan_sentiment_with_memory as _mem
        return float(_mem(team, current_date))
    except Exception:
        try:
            return float(get_fan_sentiment(team, current_date))
        except Exception:
            return 60.0


def crowd_energy_mult(team: Any, current_date: Any = None) -> float:
    """Home crowd energy multiplier from fan sentiment.

    Subtle: 0.92 (furious) to 1.08 (ecstatic). Never dictates outcomes.
    Memory-aware: a defending champion's crowd stays loud; a long
    suffering fanbase stays quiet. Never raises.
    """
    try:
        sentiment = _memory_sentiment(team, current_date)
        # Map 0-100 to 0.92-1.08
        return 0.92 + (sentiment / 100.0) * 0.16
    except Exception:
        return 1.0


def board_pressure(team: Any, current_date: Any = None) -> float:
    """Board pressure on GM/coach from fan sentiment.

    0.0 (ecstatic fans, no pressure) to 1.0 (furious fans, hot seat).
    Feeds GM job security calculations. Memory-aware: goodwill buys
    patience, sustained losing erodes it faster. Never raises.
    """
    try:
        sentiment = _memory_sentiment(team, current_date)
        # Invert: low sentiment = high pressure
        return max(0.0, min(1.0, (70.0 - sentiment) / 70.0))
    except Exception:
        return 0.0


def fa_appeal_mult(team: Any, current_date: Any = None) -> float:
    """Free agent appeal modifier from fan sentiment.

    Players want to play for happy fanbases. Subtle: 0.95 to 1.05.
    Memory-aware: a franchise with buzz attracts; a toxic market
    repels. Never raises.
    """
    try:
        sentiment = _memory_sentiment(team, current_date)
        return 0.95 + (sentiment / 100.0) * 0.10
    except Exception:
        return 1.0


def fanbase_crowd_layer(home_mult: float, home_team: Any,
                        current_date: Any = None) -> float:
    """Persistent fanbase engagement layer for the home crowd multiplier.

    One decision, two fidelities: both sims call this on the home
    crowd mult from crowd_effects(). Tonight's crowd (energy/mood from
    pregame_crowd) is the weather; this is the climate -- the slow
    stock of how the fanbase feels about its team, with cross-season
    memory. Bounded [0.90, 1.10] on the combined value; never dictates.
    Never raises.
    """
    try:
        _m = crowd_energy_mult(home_team, current_date)
        return max(0.90, min(1.10, float(home_mult) * _m))
    except Exception:
        try:
            return float(home_mult)
        except Exception:
            return 1.0


# ---------------------------------------------------------------------------
# Cross-season memory
# ---------------------------------------------------------------------------

def apply_season_memory(team: Any, won_cup: bool = False,
                       made_playoffs: bool = False) -> None:
    """Apply cross-season fanbase memory. Called at season end.

    - Cup win: sets a goodwill buffer that decays slowly over ~3 seasons
    - Missing playoffs: adds a cynicism marker
    - Decade of losing (tracked via consecutive losing seasons): deep cynicism

    Never raises.
    """
    try:
        # Goodwill from Cup wins (decays over seasons)
        if won_cup:
            team.fan_goodwill_seasons = 3
        else:
            gw = int(getattr(team, "fan_goodwill_seasons", 0) or 0)
            team.fan_goodwill_seasons = max(0, gw - 1)

        # Track consecutive losing seasons for deep cynicism
        if not made_playoffs:
            losing = int(getattr(team, "fan_losing_streak", 0) or 0)
            team.fan_losing_streak = losing + 1
        else:
            team.fan_losing_streak = 0
    except Exception:
        pass


def goodwill_sentiment_floor(team: Any) -> float:
    """Minimum sentiment floor from Cup goodwill.

    A recent Cup win prevents sentiment from fully collapsing —
    fans remember. Never raises.
    """
    try:
        gw = int(getattr(team, "fan_goodwill_seasons", 0) or 0)
        if gw >= 3:
            return 45.0  # Fresh champs: fans stay patient
        elif gw >= 2:
            return 38.0
        elif gw >= 1:
            return 32.0
    except Exception:
        pass
    return 0.0


def cynicism_sentiment_ceiling(team: Any) -> float:
    """Maximum sentiment ceiling from sustained losing.

    A decade of futility breeds cynicism — even winning streaks don't
    fully electrify a beaten-down fanbase. Never raises.
    """
    try:
        losing = int(getattr(team, "fan_losing_streak", 0) or 0)
        if losing >= 8:
            return 70.0  # Deep cynicism: can't reach ecstatic
        elif losing >= 5:
            return 78.0
        elif losing >= 3:
            return 85.0
    except Exception:
        pass
    return 100.0


# ---------------------------------------------------------------------------
# Daily/weekly integration
# ---------------------------------------------------------------------------

# Cooldown: don't spam fan narratives (days between stories per team)
_NARRATIVE_COOLDOWN_DAYS = 14


def maybe_fire_fan_narrative(team: Any, game_manager: Any = None,
                              current_date: Any = None) -> bool:
    """Check if a fan narrative should fire for this team. Returns True if fired.

    Only fires on tier changes (e.g., content -> angry) or extreme tiers,
    with a cooldown to prevent spam. Never raises.
    """
    try:
        from fan_sentiment import get_fan_sentiment

        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)

        # Only fire for extreme tiers (furious, ecstatic) or tier changes
        last_tier = getattr(team, "_fan_narrative_last_tier", None)

        should_fire = False
        if tier in (TIER_FURIOUS, TIER_ECSTATIC):
            # Extreme tiers: fire (with cooldown)
            should_fire = True
        elif last_tier and last_tier != tier:
            # Tier changed: fire (e.g., content -> angry is newsworthy)
            # But only if moving to a more extreme tier
            tier_order = [TIER_ECSTATIC, TIER_HAPPY, TIER_CONTENT,
                         TIER_RESTLESS, TIER_ANGRY, TIER_FURIOUS]
            try:
                old_idx = tier_order.index(last_tier)
                new_idx = tier_order.index(tier)
                # Fire if moved 2+ steps, or into angry/furious/ecstatic
                if abs(new_idx - old_idx) >= 2 or tier in (TIER_ANGRY, TIER_FURIOUS, TIER_ECSTATIC):
                    should_fire = True
            except Exception:
                pass

        if not should_fire:
            team._fan_narrative_last_tier = tier
            return False

        # Check cooldown
        try:
            from datetime import date
            last_fired = getattr(team, "_fan_narrative_last_date", None)
            if last_fired and current_date:
                if isinstance(current_date, date) and isinstance(last_fired, date):
                    days = (current_date - last_fired).days
                    if days < _NARRATIVE_COOLDOWN_DAYS:
                        return False
                elif isinstance(current_date, str) and isinstance(last_fired, str):
                    d_now = date.fromisoformat(current_date[:10])
                    d_then = date.fromisoformat(last_fired[:10])
                    if (d_now - d_then).days < _NARRATIVE_COOLDOWN_DAYS:
                        return False
        except Exception:
            pass

        # Generate and deliver the narrative
        narrative = generate_fan_narrative(team, current_date)
        if not narrative:
            team._fan_narrative_last_tier = tier
            return False

        # Deliver via headlines system
        try:
            from headlines import make_headline
            msg = make_headline(
                "fan_narrative",
                game_date=current_date,
                headline=narrative["headline"],
                body=narrative["body"],
                tier=narrative["tier"],
                team_name=_team_name(team),
            )
            if msg and game_manager:
                # Add to inbox
                inbox = getattr(game_manager, "inbox", None)
                if inbox is not None:
                    if hasattr(inbox, "add_message"):
                        inbox.add_message(msg)
                    elif hasattr(inbox, "append"):
                        inbox.append(msg)
        except Exception:
            pass

        # Update tracking
        team._fan_narrative_last_tier = tier
        try:
            team._fan_narrative_last_date = current_date
        except Exception:
            pass

        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Boardroom narratives (L4 wire, Muck 2026-10-02)
# ---------------------------------------------------------------------------
# Board pressure isn't just a number in the job-security math -- it's a
# story the world tells: ownership losing patience, the hot seat warming,
# the vote of confidence that means the opposite. These fire on the same
# weekly cadence as fan narratives, with their own cooldown, so the
# pressure the GM feels has a visible reason in the world.

_BOARD_NARRATIVE_COOLDOWN_DAYS = 21


def _gm_name(team: Any) -> str:
    try:
        for _s in (getattr(team, "staff", None) or []):
            try:
                _role = str(getattr(_s, "role", ""))
            except Exception:
                _role = ""
            if "General Manager" in _role and "Assistant" not in _role:
                _fn = str(getattr(_s, "first_name", "") or "")
                _ln = str(getattr(_s, "last_name", "") or "")
                _full = f"{_fn} {_ln}".strip()
                if _full:
                    return _full
    except Exception:
        pass
    return "the GM"


# ---------------------------------------------------------------------------
# Board narrative text variants (DEV-D: narrative text only).
#
# Three branches (seat-warming / escalation / relief), each with a list of
# (headline, body) pairs chosen via random.choice.
# RULES (hard):
#   - Headlines and bodies may use ONLY the {tname} and {gm} slots. These
#     are the only slots generate_board_narrative computes.
#   - The returned dict shape is exactly
#     {kind, headline, body, weight, audience, hot} with the per-branch
#     kind/weight/hot values unchanged.
#   - Never invent stats, streaks, or events. The pressure state is the
#     only fact the text may lean on.
# ---------------------------------------------------------------------------

_BOARD_WARMING_VARIANTS: List[tuple] = [
    (f"Ownership losing patience in {{tname}}",
     f"Whispers out of the {{tname}} boardroom suggest ownership "
     f"is losing patience. {{gm}} is feeling the heat as the "
     f"fanbase turns -- if results don't turn, the seat gets "
     f"genuinely hot."),
    (f"Seat warming: {{gm}} feeling the heat in {{tname}}",
     f"The {{tname}} boardroom is asking harder questions. {{gm}} "
     f"isn't in immediate danger, but the margin for error is gone."),
    (f"Whispers from the {{tname}} boardroom",
     f"Ownership is watching closely. {{gm}} still has the job, but "
     f"the patience that came with it is running out."),
    (f"{{tname}} ownership's patience wearing thin",
     f"The message from upstairs is getting harder to read as "
     f"supportive. {{gm}} needs results before the whispers turn "
     f"into meetings."),
    (f"Pressure mounting on {{gm}} in {{tname}}",
     f"It's not a hot seat yet -- but the {{tname}} front office "
     f"can feel it warming. Ownership expects better, and soon."),
    (f"{{tname}} brass growing restless",
     f"The boardroom mood has shifted. {{gm}} is under no illusions: "
     f"the honeymoon with ownership is over."),
    (f"The {{tname}} hot seat: not yet, but close",
     f"{{gm}} keeps the job today. But ownership's tone has changed "
     f"in {{tname}}, and everyone around the league can hear it."),
    (f"Ownership watching closely in {{tname}}",
     f"Every move is under a microscope now. {{gm}} has the full "
     f"attention of the {{tname}} boardroom -- and not the good kind."),
]

_BOARD_ESCALATION_VARIANTS: List[tuple] = [
    (f"Hot seat watch: {{gm}} under fire in {{tname}}",
     f"The {{tname}} boardroom is no longer whispering. Ownership "
     f"is openly questioning the direction, and {{gm}}'s job "
     f"security is the talk of the league's insider circuit."),
    (f"{{gm}} on the brink in {{tname}}",
     f"The {{tname}} boardroom has stopped pretending. Ownership is "
     f"openly discussing the future, and {{gm}}'s name is at the "
     f"center of it."),
    (f"No more whispers: {{tname}} ownership openly questioning {{gm}}",
     f"The patience is gone. The {{tname}} board wants answers, and "
     f"{{gm}} is running out of them."),
    (f"Hot seat scorching for {{gm}} in {{tname}}",
     f"Around the league, it's treated as a matter of when, not if. "
     f"The {{tname}} boardroom is bracing for a change at the top."),
    (f"{{tname}} boardroom in crisis mode",
     f"The pressure is mounting and the speculation is getting "
     f"louder. {{gm}}'s grip on the {{tname}} job is slipping by "
     f"the day."),
    (f"Countdown on in {{tname}}: {{gm}} under siege",
     f"Ownership has made its frustration public. {{gm}} is fighting "
     f"for the job now, and everyone in the building knows it."),
    (f"Ownership turns up the heat on {{gm}}",
     f"The {{tname}} board is done waiting. Public comments, private "
     f"ultimatums -- {{gm}} is officially on the clock."),
    (f"{{tname}}: the seat is officially hot",
     f"There's no spinning it anymore. Ownership in {{tname}} has "
     f"lost faith in the direction, and {{gm}} is the one answering "
     f"for it."),
]

_BOARD_RELIEF_VARIANTS: List[tuple] = [
    (f"{{tname}} ownership backs {{gm}}",
     f"{{tname}} ownership has publicly backed {{gm}}. The pressure on "
     f"the front office has lifted, and the board is aligned behind "
     f"the plan. {{gm}} has the {{tname}} front office's full "
     f"support."),
    (f"Storm passes in {{tname}}: {{gm}} safe",
     f"The boardroom has calmed. {{gm}} earned some breathing room, "
     f"and ownership is letting the hockey do the talking."),
    (f"Vote of confidence -- the real kind -- for {{gm}}",
     f"This time it wasn't the dreaded kind. {{tname}} ownership "
     f"genuinely backed {{gm}}, and the hot seat talk has gone quiet."),
    (f"{{tname}} boardroom breathes easier",
     f"The crisis meetings are over. Ownership is pleased, {{gm}} "
     f"is secure, and the {{tname}} front office can get back to work."),
    (f"Heat off: {{gm}} earns ownership's trust back",
     f"Whatever was said behind closed doors worked. {{gm}} has the "
     f"{{tname}} boardroom's confidence again -- the seat is cool."),
    (f"{{tname}} ownership all in on {{gm}}",
     f"No hedging, no qualifiers. The {{tname}} board is publicly "
     f"behind {{gm}}, and the rumor mill has moved on."),
    (f"Calm returns to the {{tname}} boardroom",
     f"The storm has passed. {{gm}} weathered it, ownership has "
     f"moved on, and the focus is back on hockey."),
    (f"{{gm}} off the hot seat in {{tname}}",
     f"The pressure valve released. {{tname}} ownership is satisfied "
     f"and {{gm}} can plan beyond tomorrow."),
]


def generate_board_narrative(team: Any,
                             current_date: Any = None) -> Optional[Dict[str, Any]]:
    """Generate a boardroom narrative from current board pressure.

    Returns a narrative dict (or None). Fires when pressure is high
    (ownership losing patience) or when it breaks (relief / vote of
    confidence). Never raises.
    """
    try:
        pressure = board_pressure(team, current_date)
        tname = _team_name(team)
        gm = _gm_name(team)
        was_hot = bool(getattr(team, "_board_narrative_hot", False))

        if pressure >= 0.70 and not was_hot:
            # The seat is warming -- first time crossing the line.
            _headline, _body = random.choice(_BOARD_WARMING_VARIANTS)
            return {
                "kind": "board_pressure",
                "headline": _headline.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "body": _body.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "weight": 60,
                "audience": "board",
                "hot": True,
            }
        elif pressure >= 0.85 and was_hot:
            # Escalation: it got worse.
            _headline, _body = random.choice(_BOARD_ESCALATION_VARIANTS)
            return {
                "kind": "board_pressure",
                "headline": _headline.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "body": _body.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "weight": 80,
                "audience": "board",
                "hot": True,
            }
        elif pressure < 0.35 and was_hot:
            # Relief: the storm passed.
            _headline, _body = random.choice(_BOARD_RELIEF_VARIANTS)
            return {
                "kind": "board_relief",
                "headline": _headline.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "body": _body.format(tname=_safe_name(tname), gm=_safe_name(gm)),
                "weight": 40,
                "audience": "board",
                "hot": False,
            }
        return None
    except Exception:
        return None


def maybe_fire_board_narrative(team: Any, game_manager: Any = None,
                               current_date: Any = None) -> bool:
    """Check if a boardroom narrative should fire for this team.

    Fires when board pressure crosses into hot-seat territory, escalates,
    or breaks -- with a cooldown so the boardroom doesn't spam the inbox.
    Never raises.
    """
    try:
        narrative = generate_board_narrative(team, current_date)
        if not narrative:
            return False

        # Cooldown
        try:
            from datetime import date
            last_fired = getattr(team, "_board_narrative_last_date", None)
            if last_fired and current_date:
                if isinstance(current_date, date) and isinstance(last_fired, date):
                    days = (current_date - last_fired).days
                    if days < _BOARD_NARRATIVE_COOLDOWN_DAYS:
                        return False
                elif isinstance(current_date, str) and isinstance(last_fired, str):
                    d_now = date.fromisoformat(current_date[:10])
                    d_then = date.fromisoformat(last_fired[:10])
                    if (d_now - d_then).days < _BOARD_NARRATIVE_COOLDOWN_DAYS:
                        return False
        except Exception:
            pass

        # Deliver via headlines system
        try:
            from headlines import make_headline
            msg = make_headline(
                "board_narrative",
                game_date=current_date,
                headline=narrative["headline"],
                body=narrative["body"],
                team_name=_team_name(team),
                gm_name=_gm_name(team),
            )
            if msg and game_manager:
                inbox = getattr(game_manager, "inbox", None)
                if inbox is not None:
                    if hasattr(inbox, "add_message"):
                        inbox.add_message(msg)
                    elif hasattr(inbox, "append"):
                        inbox.append(msg)
        except Exception:
            pass

        # Update tracking
        try:
            team._board_narrative_hot = bool(narrative.get("hot", False))
            team._board_narrative_last_date = current_date
        except Exception:
            pass

        return True
    except Exception:
        return False
