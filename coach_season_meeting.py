# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Pre-season coach expectations meeting: MODEL + WIRING + AI (no UI).

Chris's directive: before training camp / fantasy draft / a new coach hire /
a new save starts, the GM must meet his head coach and outline season
expectations. The meeting produces a stored season MANDATE that must be REAL:
it gates real systems. Applies equally to user and AI GMs.

This module owns the mandate model, the arm/pending API, the trigger entry
points, the advance-blocker dict, the downstream wiring, and the full AI-GM
resolution. It owns NO UI.

SHARED CONTRACT -- the sibling's conversation UI consumes this module:
  * ``SEASON_EXPECTATIONS`` -- the four mandate keys, shared with
    ``ai_gm_identity.EXPECTED_PACE`` (win_cup 0.650 / contend 0.600 /
    playoffs 0.550 / rebuild 0.450).
  * ``normalize_expectation(key)`` -- maps SeasonGoalsView UI keys
    (cup/contender/playoffs/competitive/rebuild, windows.py) onto the
    mandate keys.
  * Mandate dict stored on ``team.season_mandate`` (plain dict, save/load
    safe). Keys: season, expectation, coach_assessment, aligned,
    rookie_stance ("heavy"|"earned"|"sheltered"|"none"),
    tactical_approach (IDENTITY_PRESETS key or None),
    lines_owner ("gm"|"coach"), tactics_owner ("gm"|"coach"),
    deployer_notes (str), meeting_done (bool). Reserved extras written by
    this module: coach_id, coach_name, reason.
  * ``team.season_meeting_pending`` (bool) -- the advance blocker reads it.
    The conversation UI MUST clear it by calling :func:`store_mandate`
    when the meeting completes (store_mandate clears it).
  * ``team.season_meeting_context`` (dict) -- transient context for the UI:
    {"reason", "season", "coach"}.
  * ``arm_season_meeting(team, reason)`` / ``is_meeting_pending(team)`` /
    ``get_head_coach(team)`` / ``coach_season_assessment(team, coach)`` /
    ``resolve_ai_season_meeting(team)``.
  * ``store_mandate(team, fields)`` -- THE completion call. Validates,
    derives ``aligned``, applies the gm_trust effect, applies downstream
    wiring (line_control / tactics_control / identity preset), stores the
    mandate, clears the pending flag. The sibling calls this; the AI path
    calls it too (user/AI parity).
  * ``season_meeting_blocker(app)`` -- the get_continue_state() blocker
    dict (or None). Non-modal: the user can navigate anywhere; only
    day-advance is gated.
  * ``open_season_meeting_window(app)`` -- opens the sibling's surface.
    SIBLING CONTRACT: implement
    ``coach_meeting_window.open_season_meeting(app)`` where ``app`` is the
    HockeyManagerGUI. It MUST be a full-screen surface (Eastside-style
    screen shift, non-modal with preserved state -- per the design rule,
    popups are not the UI paradigm), and it MUST finish via
    ``store_mandate(user_team, {...})``.

Trigger entry points (called from guarded hooks in the game flow):
  * ``on_training_camp(game_manager)`` -- yearly re-arm.
  * ``on_fantasy_draft_complete(game_manager)`` -- rosters known.
  * ``on_new_save(game_manager, user_team)`` -- defers while a fantasy
    draft is pending.
  * ``on_coach_hired(team, game_manager=None)`` -- new voice, new meeting.

Downstream wiring (the mandate is REAL):
  * Expectations -> carousel: ``dressing_room._coach_board_expectation``
    prefers the mandate's EXPECTED_PACE when a mandate exists (the coach
    is judged against what was AGREED). The board's judgment of the GM
    (``ai_gm_identity.update_job_security``) is untouched -- the gap
    between board demand and mandate is the intended tension.
  * Lines owner -> ``team.line_control`` (the real gate read by
    quick_sim's lineup pen and reputation_system.advise_coach). A
    preseason agreement is not a seizure: written directly, no morale
    fallout (the mid-season set_line_control power-grab path keeps its
    own consequences).
  * Tactics owner -> ``tactics.set_tactics_control`` (the real whiteboard
    gate read by tactics_window and the install backstop).
  * Tactical approach -> ``tactics.apply_identity_preset`` (real path,
    familiarity dip included).
  * Rookie stance -> ``deployment_policy._honored_advice`` reads the
    stored stance as standing GM instruction: "heavy" -> play_the_kids,
    "sheltered" -> shorten_bench, "earned"/"none" -> no nudge. Reuses the
    existing multipliers -- no new tuning.

TUNING CONSTANTS -- the situational trust scale (rebalanced 2026-09-30,
needs Chris's approval -- flagged in the build report):
  Every trust delta is a function of (GM choice, coach personality,
  situational fit). Bounds: the worst realistic single meeting moves
  trust 70 -> low 50s; the best realistic meeting tops out in the mid
  80s. Trust is hard to build and hard to destroy in one conversation.
  TRUST_ALIGN_GROUNDED / TRUST_ALIGN_SHARED / TRUST_SEAL_ALIGNED /
  TRUST_SEAL_MISALIGNED / TRUST_TANK_REFUSAL / TRUST_KEEP_DOMAIN /
  TRUST_TAKE_FIRST_CHAIR (below), plus the documented per-beat rules:
  expectation beat in [-5, +3], rookie beat in [-3, +3], tactics beat
  in [-2, +2], each ownership beat in [-3, +2], deployer beat in
  [-2, +3]. See the trust_*_delta functions for the full rules.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Contract: expectation keys
# ---------------------------------------------------------------------------

#: The four mandate keys -- the ai_gm_identity keys. EXPECTED_PACE lives in
#: ai_gm_identity (win_cup 0.650, contend 0.600, playoffs 0.550,
#: rebuild 0.450); imported lazily so this module never hard-depends.
SEASON_EXPECTATIONS = ["win_cup", "contend", "playoffs", "rebuild"]

_NOTCH_ORDER = ["rebuild", "playoffs", "contend", "win_cup"]

#: SeasonGoalsView UI keys (windows.py) -> mandate keys. Five UI levels
#: into four AI buckets: "competitive" (Winning Record) lands on
#: "playoffs" -- the nearest bucket (documented slight inflation).
_UI_TO_AI = {
    "cup": "win_cup",
    "contender": "contend",
    "playoffs": "playoffs",
    "competitive": "playoffs",
    "rebuild": "rebuild",
    "win_cup": "win_cup",
    "contend": "contend",
}

ROOKIE_STANCES = ("heavy", "earned", "sheltered", "none")

#: Tactical style buckets for the tactics-beat fit check: a system that
#: clashes with the coach's philosophy costs more than an adjacent one.
_PRESET_STYLE = {
    "chaos_pressure": "attack",
    "stranglehold": "defense",
    "hybrid_transition": "balanced",
}

# ---------------------------------------------------------------------------
# Tuning constants -- NEED CHRIS'S APPROVAL (see module docstring)
# ---------------------------------------------------------------------------

#: gm_trust delta when GM and coach agree AND the agreed rung matches what
#: the roster earns: an honest, grounded conversation builds trust.
TRUST_ALIGN_GROUNDED = 3
#: gm_trust delta when they agree but both misread the roster: agreement
#: still feels good, even if reality will teach them otherwise.
TRUST_ALIGN_SHARED = 2
#: Closing handshake at seal when expectation == coach_assessment.
TRUST_SEAL_ALIGNED = 2
#: Closing handshake at seal when they carried a disagreement into camp.
TRUST_SEAL_MISALIGNED = -2
#: gm_trust delta when a coach refuses a tank mandate the roster doesn't
#: warrant (ambitious/authoritarian coach, roster earns contend+). The
#: refusal stays possible -- the cost is survivable, not fatal.
TRUST_TANK_REFUSAL = -4
#: gm_trust delta when the coach keeps a domain (lines or tactics).
TRUST_KEEP_DOMAIN = 2
#: gm_trust delta when a first-nhl-chair rookie cedes a domain: he defers
#: gratefully to the GM who believed in him.
TRUST_TAKE_FIRST_CHAIR = 1
#: Coach morale (1-100) below which his season assessment drops a notch.
COACH_LOW_MORALE_NOTCH = 40
#: AI authority: control_need >= this -> the coach keeps lines + tactics.
AI_CONTROL_KEEP = 65
#: AI authority: control_need <= this -> the GM takes lines + tactics.
AI_CONTROL_DEFER = 40
#: AI rookie stance: working_with_youngsters >= this nudges the stance one
#: step toward "heavy".
AI_WWY_HEAVY = 75
#: Roster age profile bands (average roster age): a young core takes to
#: heavy rookie minutes naturally; a veteran room resents them.
ROSTER_YOUNG_MAX_AGE = 26.0
ROSTER_VETERAN_MIN_AGE = 28.5


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _calendar_year() -> int:
    try:
        return date.today().year
    except Exception:
        return 2026


def _shift(key: str, delta: int) -> str:
    try:
        i = _NOTCH_ORDER.index(key)
    except ValueError:
        i = 1
    return _NOTCH_ORDER[max(0, min(len(_NOTCH_ORDER) - 1, i + delta))]


def normalize_expectation(key: Any) -> Optional[str]:
    """Map a SeasonGoalsView UI key (or an AI key) onto a mandate key.

    Returns None for unknown/empty input.
    """
    if key is None:
        return None
    k = str(key).strip().lower()
    if k in SEASON_EXPECTATIONS:
        return k
    return _UI_TO_AI.get(k)


def _coach_display_name(coach: Any) -> str:
    if coach is None:
        return ""
    for attr in ("full_name", "name"):
        try:
            v = getattr(coach, attr, "")
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            continue
    try:
        fn = getattr(coach, "first_name", "")
        ln = getattr(coach, "last_name", "")
        full = f"{fn} {ln}".strip()
        if full:
            return full
    except Exception:
        pass
    return ""


def _roster_avg_overall(team: Any) -> float:
    ovrs: List[float] = []
    try:
        for p in getattr(team, "roster", None) or []:
            try:
                fn = getattr(p, "overall_rating", None)
                v = fn() if callable(fn) else fn
                ovrs.append(float(v))
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return sum(ovrs) / len(ovrs) if ovrs else 60.0


def _league_season_year(game_manager: Any) -> int:
    try:
        league = getattr(game_manager, "league", None)
        y = getattr(league, "season_year", None)
        if y:
            return int(y)
    except Exception:
        pass
    return _calendar_year()


def _is_user_team(team: Any, game_manager: Any = None) -> bool:
    try:
        if bool(getattr(team, "is_user_team", False)):
            return True
    except Exception:
        pass
    try:
        if game_manager is not None and getattr(game_manager, "user_team", None) is team:
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def get_head_coach(team: Any) -> Optional[Any]:
    """The club's NHL head coach (Staff) or None.

    Primary path is ``team.get_staff_by_role(StaffRole.HEAD_COACH)``;
    falls back to scanning team.staff and then the team.head_coach
    attribute (older shapes / test doubles). Never raises.
    """
    if team is None:
        return None
    try:
        from game_classes import StaffRole
        try:
            found = team.get_staff_by_role(StaffRole.HEAD_COACH)
        except Exception:
            found = None
        if found:
            return found[0]
    except Exception:
        pass
    try:
        for s in getattr(team, "staff", None) or []:
            try:
                role = getattr(s, "role", None)
                rv = getattr(role, "value", role)
                if isinstance(rv, str) and rv.strip().lower() == "head coach":
                    return s
            except Exception:
                continue
    except Exception:
        pass
    try:
        return getattr(team, "head_coach", None)
    except Exception:
        return None


def is_meeting_pending(team: Any) -> bool:
    """True when the club's season meeting still has to happen."""
    try:
        return bool(getattr(team, "season_meeting_pending", False))
    except Exception:
        return False


def get_active_mandate(team: Any) -> Optional[Dict[str, Any]]:
    """The stored season mandate (a copy), or None. Never raises."""
    try:
        m = getattr(team, "season_mandate", None)
        if isinstance(m, dict) and m:
            return dict(m)
    except Exception:
        pass
    return None


def _mandate_season(mandate: Optional[Dict[str, Any]]) -> Optional[int]:
    try:
        s = (mandate or {}).get("season")
        return int(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _context_reason(team: Any) -> str:
    try:
        ctx = getattr(team, "season_meeting_context", None) or {}
        r = ctx.get("reason")
        if r:
            return str(r)
    except Exception:
        pass
    return ""


def arm_season_meeting(team: Any, reason: str = "training_camp",
                       season_year: Optional[int] = None,
                       coach: Any = None) -> bool:
    """Arm the pre-season meeting for a club (sets the pending flag).

    Idempotent per season: a completed meeting for ``season_year`` is not
    re-armed, except for reason="new_coach" (a new voice means a new
    meeting even mid-season). Refreshing context on an already-pending
    meeting is harmless. Never raises; returns True when the flag is set.
    """
    try:
        if team is None:
            return False
        if season_year is None:
            season_year = _mandate_season(get_active_mandate(team))
        if season_year is None:
            season_year = _calendar_year()
        if reason != "new_coach" and not is_meeting_pending(team):
            m = get_active_mandate(team)
            if m and m.get("meeting_done") and _mandate_season(m) == int(season_year):
                return True  # already held this season's meeting
        if coach is None:
            coach = get_head_coach(team)
        team.season_meeting_pending = True
        try:
            team.season_meeting_context = {
                "reason": str(reason or "training_camp"),
                "season": int(season_year),
                "coach": _coach_display_name(coach),
            }
        except Exception:
            pass
        return True
    except Exception:
        return False


def coach_season_assessment(team: Any, coach: Any) -> str:
    """The head coach's own read on the season, from roster + personality.

    Roster strength via ``ai_gm_identity.expectation_from_strength``,
    shaded by ambition (stanley_cup +1 notch, developer -1 notch,
    clamped) and low morale (-1 notch below COACH_LOW_MORALE_NOTCH).
    """
    try:
        from ai_gm_identity import expectation_from_strength
        read = expectation_from_strength(_roster_avg_overall(team))
    except Exception:
        read = "playoffs"
    try:
        if coach is not None:
            amb = str(getattr(coach, "ambition", "") or "").strip().lower()
            if amb == "stanley_cup":
                read = _shift(read, 1)
            elif amb == "developer":
                read = _shift(read, -1)
            if _num(getattr(coach, "morale", 70), 70) < COACH_LOW_MORALE_NOTCH:
                read = _shift(read, -1)
    except Exception:
        pass
    return read if read in SEASON_EXPECTATIONS else "playoffs"


# ---------------------------------------------------------------------------
# Situational inputs for the trust scale
# ---------------------------------------------------------------------------

def _coach_ambition(coach: Any) -> str:
    try:
        return str(getattr(coach, "ambition", "") or "climb").strip().lower()
    except Exception:
        return "climb"


def _coach_control(coach: Any) -> float:
    return _num(getattr(coach, "control_need", 50), 50)


def _coach_youth_trust(coach: Any) -> float:
    return _num(getattr(coach, "working_with_youngsters", 50), 50)


def _is_authoritarian(coach: Any) -> bool:
    return _coach_control(coach) >= 75


def _is_collaborative(coach: Any) -> bool:
    return _coach_control(coach) <= 40


def _is_first_chair(coach: Any) -> bool:
    try:
        return bool(getattr(coach, "first_nhl_chair", False))
    except Exception:
        return False


def _is_developer(coach: Any) -> bool:
    return _coach_ambition(coach) == "developer" or _coach_youth_trust(coach) >= 75


def _is_loyal(coach: Any) -> bool:
    return _coach_ambition(coach) in ("lifer", "hometown")


def _ambition_drive() -> Dict[str, float]:
    try:
        from ai_gm_identity import AMBITION_DRIVE
        return dict(AMBITION_DRIVE)
    except Exception:
        return {"stanley_cup": 1.00, "climb": 0.70, "hometown": 0.50,
                "lifer": 0.35, "developer": 0.25}


def _is_win_now_ambitious(coach: Any) -> bool:
    amb = _coach_ambition(coach)
    if amb == "stanley_cup":
        return True
    try:
        return amb == "climb" and float(_ambition_drive().get("climb", 0.7)) >= 0.7
    except Exception:
        return False


def _coach_tactical_style(coach: Any) -> str:
    """attack | defense | balanced, from the coach's coaching attributes."""
    try:
        atk = _num(getattr(coach, "attacking_coaching", 50), 50.0)
        dfn = _num(getattr(coach, "defensive_coaching", 50), 50.0)
        if atk >= dfn + 12:
            return "attack"
        if dfn >= atk + 12:
            return "defense"
    except Exception:
        pass
    return "balanced"


def roster_earned_expectation(team: Any) -> str:
    """The rung the roster actually earns (strength -> expectation).

    The reality anchor for the expectations beat: the GM's ask and the
    coach's read are both measured against this. Never raises.
    """
    try:
        from ai_gm_identity import expectation_from_strength
        read = expectation_from_strength(_roster_avg_overall(team))
        if read in SEASON_EXPECTATIONS:
            return read
    except Exception:
        pass
    return "playoffs"


def roster_age_profile(team: Any) -> str:
    """young | prime | veteran | unknown, from average roster age.

    Cheap derivation (no new data pipelines): players carry ``age``.
    "unknown" (no age data, e.g. old saves / test doubles) behaves as
    "prime" in the trust math -- neutral, never punitive. Never raises.
    """
    try:
        ages: List[float] = []
        for p in getattr(team, "roster", None) or []:
            try:
                a = getattr(p, "age", None)
                if a is not None:
                    ages.append(float(a))
            except (TypeError, ValueError):
                continue
        if not ages:
            return "unknown"
        avg = sum(ages) / len(ages)
        if avg < ROSTER_YOUNG_MAX_AGE:
            return "young"
        if avg > ROSTER_VETERAN_MIN_AGE:
            return "veteran"
        return "prime"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Situational trust scale -- one component per conversation beat.
#
# Every component returns (delta, tone, note[, misaligned]). The tone is the
# situational classification the conversation UI keys its voice lines on;
# the note is the plain-language reason recorded in the meeting notes.
# The user's meeting applies each beat live (visible consequence); the AI
# path applies compute_meeting_trust_delta() at seal -- identical math,
# identical scale (user/AI parity).
# ---------------------------------------------------------------------------

def trust_expectation_delta(team: Any, coach: Any, chosen: Any,
                            assessed: Any):
    """Expectations beat: the ask measured against reality AND the coach.

    Rules: agreement on the earned rung builds (+3); agreement off it is
    still agreement (+2). Ambition the roster can cash is welcomed or
    cheap; ambition above reality costs -2 per notch (extra -1 for
    overruling a coach who read it right; ambitious coaches forgive 1).
    Honest patience costs little (-2..+1 by personality); patience far
    below what the roster warrants costs more; a tank demand on a
    contend+ roster can draw an outright refusal (-4, survivable).
    Range [-5, +3].
    """
    chosen = normalize_expectation(chosen) or "playoffs"
    assessed = normalize_expectation(assessed) or chosen
    earned = roster_earned_expectation(team)
    ci = _NOTCH_ORDER.index(chosen)
    ai = _NOTCH_ORDER.index(assessed)
    ei = _NOTCH_ORDER.index(earned)
    coach_off = ai - ei  # +: the coach overrates the roster

    if ci == ai:
        if ci == ei:
            return (TRUST_ALIGN_GROUNDED, "aligned_grounded",
                    "GM and coach agreed on what the roster earns.", False)
        return (TRUST_ALIGN_SHARED, "aligned_shared",
                "GM and coach aligned (both off the roster's true rung).",
                False)

    if ci > ai:
        # The GM is more ambitious than the coach's read.
        if _is_first_chair(coach):
            return (1, "above_defer",
                    "Rookie coach deferred to the GM's ambition.", False)
        if ci <= ei:
            # The ambition is real -- the coach was pessimistic.
            if _is_win_now_ambitious(coach):
                return (2, "above_welcomed",
                        "Coach welcomed the bigger, realistic target.", False)
            if _is_developer(coach):
                return (-1, "above_developer_worry",
                        "Developer coach worries win-now impatience hurts the kids.",
                        False)
            return (1, "above_pragmatic",
                    "Coach bought the bigger target, with caveats.", False)
        # Asking above what the roster supports.
        over = ci - ei
        delta = -2 * over
        note = "The target outruns the roster."
        if coach_off == 0:
            delta -= 1
            note = ("The target outruns the roster -- and overrules a coach "
                    "who read it right.")
        if _is_win_now_ambitious(coach):
            delta += 1
            note += " He likes the ambition anyway."
        delta = max(-5, min(1, delta))
        return (delta, "above_delusional", note, delta <= -3)

    # The GM is more patient than the coach's read.
    if coach_off >= 2:
        # The coach wildly overrates the roster; the GM brings him down
        # toward reality. Correcting a delusional read is cheap.
        if _is_authoritarian(coach) or _is_win_now_ambitious(coach):
            return (-2, "correcting_delusion",
                    "Coach bristled, but the roster doesn't support his read.",
                    False)
        return (-1, "correcting_delusion",
                "GM corrected an inflated read; the roster backs him.", False)
    if _is_first_chair(coach):
        return (1, "honest_defer",
                "Rookie coach deferred to the GM's patience.", False)
    if ci == ei:
        # Honest patience: the roster IS this. Small dent, or respect.
        if _is_developer(coach):
            return (1, "honest_developer",
                    "Developer coach respected the honest build.", False)
        if _is_win_now_ambitious(coach):
            return (-2, "honest_pushback",
                    "Ambitious coach pushed back on a patient mandate.", False)
        if _is_loyal(coach):
            return (-1, "honest_loyal",
                    "Loyal coach bought the honest mandate.", False)
        return (-1, "honest_reluctant",
                "Coach accepted a patient mandate reluctantly.", False)
    # Patience beyond what the roster warrants.
    under = ei - ci
    if (chosen == "rebuild" and ei >= _NOTCH_ORDER.index("contend")
            and (_is_authoritarian(coach) or _is_win_now_ambitious(coach))):
        return (TRUST_TANK_REFUSAL, "tank_refusal",
                "Coach refused a tank mandate outright.", True)
    if _is_developer(coach):
        return (-1, "patient_developer",
                "Developer coach accepted the patient mandate.", False)
    if _is_loyal(coach):
        return (-1, "patient_loyal",
                "Loyal coach bought into the patient mandate.", False)
    if _is_win_now_ambitious(coach):
        return (-(1 + under), "patient_pushback",
                "Ambitious coach pushed back on excessive patience.", False)
    return (-(under + 1), "patient_reluctant",
            "Coach accepted excessive patience reluctantly.", False)


def trust_rookie_delta(team: Any, coach: Any, stance: Any, expectation: Any):
    """Rookie-stance beat: the ask measured against the roster's age.

    Heavy minutes for a young core is natural; the same demand on a
    veteran win-now roster is real conflict. "Earned" is universally
    liked; "sheltered" is safe; "none" wastes a young core and itches a
    developer. Range [-3, +3].
    """
    stance = stance if stance in ROOKIE_STANCES else "none"
    expectation = normalize_expectation(expectation) or "playoffs"
    profile = roster_age_profile(team)
    if profile == "unknown":
        profile = "prime"  # neutral when age data is absent
    y = _coach_youth_trust(coach)
    vet_first = y <= 40
    developer = _is_developer(coach)
    win_now = expectation in ("win_cup", "contend")

    if stance == "heavy":
        if profile == "young":
            delta = 3 if (developer or y >= 70) else 2
            return (delta, "heavy_natural",
                    "Heavy minutes for a young core: natural.")
        if profile == "veteran":
            delta = -2
            if vet_first:
                delta -= 1
            if win_now:
                delta -= 1
            return (max(-3, delta), "heavy_conflict",
                    "Heavy rookie minutes on a veteran win-now roster: real conflict.")
        delta = 0
        if developer:
            delta += 1
        if vet_first:
            delta -= 1
        if win_now and y < 55:
            delta -= 1
        return (max(-3, min(2, delta)), "heavy_mixed",
                "Coach weighed heavy rookie minutes against the roster.")
    if stance == "earned":
        return ((2 if y >= 60 else 1), "earned",
                "Coach bought into earned-not-given ice time.")
    if stance == "sheltered":
        return ((2 if profile == "young" else 1), "sheltered",
                "Coach accepted sheltered rookie deployment.")
    if developer:
        return (-2, "none_developer",
                "Developer coach uneasy about a full AHL year for the kids.")
    if profile == "young":
        return (-1, "none_waste",
                "A young core kept down: mild waste.")
    if vet_first:
        return (1, "none_patient",
                "Veterans-first coach approved the patient path.")
    return (0, "none_neutral", "Coach accepted no rookie minutes this year.")


def trust_tactics_delta(team: Any, coach: Any, preset_key: Any):
    """Tactical-approach beat: the system measured against his philosophy.

    A system that fits how he coaches builds trust; an adjacent one is
    fine; a clash costs -- more from an authoritarian, nothing from a
    collaborative coach who adapts. Range [-2, +2].
    """
    cstyle = _coach_tactical_style(coach)
    pstyle = _PRESET_STYLE.get(preset_key)
    if not preset_key or pstyle is None:
        return (0, "tactics_none", "No system installed.")
    if cstyle == pstyle:
        return (2, "tactics_fit", "The system fits how he coaches.")
    if "balanced" in (cstyle, pstyle):
        if _is_authoritarian(coach):
            return (0, "tactics_adjacent",
                    "Authoritarian coach grudgingly accepted an adjacent system.")
        return (1, "tactics_adjacent", "Coach accepted an adjacent system.")
    if _is_authoritarian(coach):
        return (-2, "tactics_clash",
                "Authoritarian coach bristled at a clashing system.")
    if _is_collaborative(coach):
        return (0, "tactics_clash_soft",
                "Collaborative coach will adapt to the clash.")
    return (-1, "tactics_clash",
            "Coach accepted a clashing system with reservations.")


def trust_ownership_delta(coach: Any, owner: Any, domain: str = "lines"):
    """Lines/tactics ownership beat: scaled by the coach's control_need.

    Keeping a domain is +2 for everyone. Taking one stings on a sliding
    scale: -(1 + round(control_need / 50)) -> -1 (collaborative), -2
    (balanced), -3 (authoritarian). A first-chair rookie defers
    gratefully (+1). Range [-3, +2].
    """
    label = "lineup" if domain == "lines" else "tactics"
    if owner != "gm":
        return (TRUST_KEEP_DOMAIN, "keep", "Coach keeps the %s." % label)
    if _is_first_chair(coach):
        return (TRUST_TAKE_FIRST_CHAIR, "take_defer",
                "Rookie coach deferred to the GM who believed in him.")
    delta = -(1 + round(_coach_control(coach) / 50.0))
    return (delta, "take",
            "GM took the %s (control_need %d)." % (label, int(_coach_control(coach))))


def trust_deployer_delta(coach: Any, choice: Any):
    """Deployer beat (GM took both pens): how the arrangement is framed.

    Reassurance lands warmly (grudgingly with an authoritarian); cold
    expectation-setting chills an authoritarian; demanding buy-in bristles
    a proud coach (misaligned) but rallies a loyal or rookie one.
    A falsy choice means the beat never ran -- no delta. Range [-2, +3].
    """
    ch = str(choice or "").strip().lower()
    if not ch:
        return (0, "deployer_none", "", False)
    if ch == "reassure":
        if _is_authoritarian(coach):
            return (1, "deployer_reassure_grudging",
                    "Authoritarian coach grudgingly accepted the deployer role.",
                    False)
        if _is_collaborative(coach):
            return (3, "deployer_reassure_warm",
                    "Collaborative coach embraced the deployer role.", False)
        return (2, "deployer_reassure",
                "Coach accepted the deployer role after reassurance.", False)
    if ch == "expectations":
        if _is_authoritarian(coach):
            return (-2, "deployer_expect_cold",
                    "Authoritarian coach went cold on the deployer role.", False)
        return (0, "deployer_expect",
                "Coach accepted the deployer role as the job.", False)
    if _is_authoritarian(coach) or _is_win_now_ambitious(coach):
        return (-2, "deployer_demand_bristle",
                "Proud coach bristled at the buy-in demand.", True)
    if _is_loyal(coach) or _is_first_chair(coach):
        return (1, "deployer_demand_loyal",
                "Loyal coach gave full buy-in.", False)
    return (0, "deployer_demand_flat", "Coach gave buy-in without warmth.", False)


def trust_seal_delta(aligned: bool) -> int:
    """Closing handshake at seal. The beats carried the substance; this is
    the handshake on the way out of the room."""
    return TRUST_SEAL_ALIGNED if aligned else TRUST_SEAL_MISALIGNED


def compute_meeting_trust_delta(team: Any, coach: Any,
                                fields: Dict[str, Any]) -> int:
    """The full situational trust delta for a completed meeting.

    Sum of every beat component plus the seal handshake. Used by the AI
    resolution path (no conversation beats run there); the user's path
    applies the same components live and only the handshake at seal --
    identical math, identical scale. ``fields`` is the normalized mandate
    dict; ``deployer_choice`` is honored when present (AI never has one).
    Never raises.
    """
    try:
        fields = dict(fields or {})
        total = 0
        d, _, _, _ = trust_expectation_delta(
            team, coach, fields.get("expectation"), fields.get("coach_assessment"))
        total += d
        d, _, _ = trust_rookie_delta(
            team, coach, fields.get("rookie_stance"), fields.get("expectation"))
        total += d
        d, _, _ = trust_tactics_delta(team, coach, fields.get("tactical_approach"))
        total += d
        d, _, _ = trust_ownership_delta(coach, fields.get("lines_owner"), "lines")
        total += d
        d, _, _ = trust_ownership_delta(coach, fields.get("tactics_owner"), "tactics")
        total += d
        if fields.get("deployer_choice"):
            d, _, _, _ = trust_deployer_delta(coach, fields.get("deployer_choice"))
            total += d
        total += trust_seal_delta(bool(fields.get("aligned")))
        return int(total)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Downstream wiring
# ---------------------------------------------------------------------------

def mandate_expected_pace(team: Any) -> Optional[float]:
    """EXPECTED_PACE for the active mandate's expectation, else None.

    Used by dressing_room._coach_board_expectation: the coach is judged
    against what was AGREED in the meeting.
    """
    try:
        from ai_gm_identity import EXPECTED_PACE
        m = get_active_mandate(team)
        if m:
            return float(EXPECTED_PACE.get(m.get("expectation"), 0.0) or 0.0) or None
    except Exception:
        pass
    return None


def apply_mandate_downstream(team: Any, mandate: Dict[str, Any]) -> None:
    """Apply a mandate to the real gates. Never raises.

    * lines_owner -> team.line_control (the gate quick_sim's lineup pen
      and advise_coach read). Direct write: a preseason agreement is not
      a mid-season seizure, so no morale fallout.
    * tactics_owner -> tactics.set_tactics_control (the whiteboard gate).
    * tactical_approach -> tactics.apply_identity_preset (real path).
    """
    try:
        team.line_control = "gm" if mandate.get("lines_owner") == "gm" else "coach"
    except Exception:
        pass
    try:
        import tactics as _tx
        _tx.set_tactics_control(team, mandate.get("tactics_owner", "coach"))
    except Exception:
        pass
    try:
        import tactics as _tx
        approach = mandate.get("tactical_approach")
        if approach:
            _tx.apply_identity_preset(team, approach)
    except Exception:
        pass


def store_mandate(team: Any, fields: Dict[str, Any],
                  apply_trust: bool = True,
                  per_beat_applied: bool = False) -> Optional[Dict[str, Any]]:
    """Validate, store, and apply a season mandate -- THE completion call.

    The sibling's conversation UI calls this when the meeting completes;
    the AI path calls it too (user/AI parity). Derives ``aligned`` from
    expectation vs coach_assessment, applies the situational gm_trust
    effect, applies downstream wiring, stores the mandate, clears the
    pending flag. Never raises; returns the stored mandate or None.

    Trust: the conversation UI applies each beat's situational delta live
    (visible consequence), so it passes ``per_beat_applied=True`` and only
    the seal handshake lands here. The AI path (no conversation) gets the
    full meeting delta from ``compute_meeting_trust_delta`` -- identical
    components, identical scale.
    """
    try:
        if team is None:
            return None
        fields = dict(fields or {})
        season = fields.get("season")
        try:
            season = int(season) if season is not None else _calendar_year()
        except (TypeError, ValueError):
            season = _calendar_year()
        expectation = normalize_expectation(fields.get("expectation")) or "playoffs"
        coach_assessment = (normalize_expectation(fields.get("coach_assessment"))
                            or expectation)
        aligned = (expectation == coach_assessment)
        rookie_stance = fields.get("rookie_stance")
        if rookie_stance not in ROOKIE_STANCES:
            rookie_stance = "none"
        lines_owner = "gm" if fields.get("lines_owner") == "gm" else "coach"
        tactics_owner = "gm" if fields.get("tactics_owner") == "gm" else "coach"
        tactical_approach = fields.get("tactical_approach")
        try:
            import tactics as _tx
            if tactical_approach not in _tx.IDENTITY_PRESETS:
                tactical_approach = None
        except Exception:
            pass
        coach = get_head_coach(team)
        mandate = {
            "season": season,
            "expectation": expectation,
            "coach_assessment": coach_assessment,
            "aligned": aligned,
            "rookie_stance": rookie_stance,
            "tactical_approach": tactical_approach,
            "lines_owner": lines_owner,
            "tactics_owner": tactics_owner,
            "deployer_notes": str(fields.get("deployer_notes") or ""),
            "meeting_done": True,
            # Reserved extras (not part of the sibling's form, but stored):
            "coach_id": getattr(coach, "id", None),
            "coach_name": _coach_display_name(coach),
            "reason": str(fields.get("reason") or _context_reason(team) or ""),
        }
        # One trust scale for the user's meeting and AI resolution alike.
        # per_beat_applied=True (conversation UI): the beats already moved
        # trust live -- only the closing handshake lands at seal.
        # per_beat_applied=False (AI path): the full situational meeting
        # delta, computed from the same beat components.
        if apply_trust and coach is not None:
            try:
                if per_beat_applied:
                    delta = trust_seal_delta(aligned)
                else:
                    delta = compute_meeting_trust_delta(team, coach, mandate)
                cur = _num(getattr(coach, "gm_trust", 70), 70)
                coach.gm_trust = max(0.0, min(100.0, cur + delta))
            except Exception:
                pass
        apply_mandate_downstream(team, mandate)
        team.season_mandate = mandate
        team.season_meeting_pending = False
        try:
            team.season_meeting_context = {}
        except Exception:
            pass
        return dict(mandate)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Advance blocker (Eastside-style, non-modal)
# ---------------------------------------------------------------------------

def season_meeting_blocker(app: Any) -> Optional[Dict[str, Any]]:
    """The get_continue_state() blocker dict when the user club's meeting
    is pending, else None. Called from HockeyManagerGUI.get_continue_state;
    _show_continue_blockers presents it automatically. Non-modal: the user
    can navigate anywhere; only day-advance is gated. Never raises.
    """
    try:
        gm = getattr(app, "game_manager", None)
        ut = getattr(gm, "user_team", None)
        if ut is None or not is_meeting_pending(ut):
            return None
        cname = _coach_display_name(get_head_coach(ut)) or "your head coach"

        def _open():
            try:
                open_season_meeting_window(app)
            except Exception as e:
                try:
                    from popup_system import messagebox
                    messagebox.showwarning(
                        "Season Meeting",
                        "The season-meeting screen failed to open:\n%s\n\n"
                        "Your meeting is still pending -- day advance stays "
                        "gated until it is held." % (e,))
                except Exception:
                    pass

        def _auto():
            """Headless/bulk auto-resolution: run the same AI meeting
            resolution the AI clubs get (user/AI parity). Never raises,
            and never silently fails: if the full AI resolution cannot
            produce a mandate, fall back to a default mandate store so
            the pending flag is always cleared and the day can advance."""
            try:
                _gm = getattr(app, "game_manager", None) or app
                _ut = getattr(_gm, "user_team", None)
                if _ut is None:
                    return False
                _league = getattr(_gm, "league", None)
                try:
                    _season = int(getattr(_league, "season_year", 0) or 0) or None
                except Exception:
                    _season = None
                _mandate = resolve_ai_season_meeting(_ut, _league, _season)
                if not _mandate:
                    # Fallback: store a default mandate directly. The full
                    # AI resolution failed somewhere internally; a default
                    # mandate still clears the pending flag so the sim
                    # cannot soft-lock here.
                    try:
                        _mandate = store_mandate(
                            _ut,
                            {"season": _season,
                             "reason": "ai_resolution_fallback"})
                    except Exception:
                        _mandate = None
                return bool(_mandate)
            except Exception:
                return False

        return {
            "id": "season_meeting",
            "title": "Meet with your head coach",
            "detail": ("Before the season starts, sit down with %s and agree "
                       "on expectations, the rookie plan, and who owns the "
                       "lines and the whiteboard." % cname),
            "action": ("Open Season Meeting", _open),
            "auto_action": ("Hold meeting (AI resolution)", _auto),
        }
    except Exception:
        return None


def open_season_meeting_window(app: Any) -> Any:
    """Open the season-meeting conversation surface (sibling's UI).

    SIBLING CONTRACT: implement
    ``coach_meeting_window.open_season_meeting(app)`` (``app`` is the
    HockeyManagerGUI). It MUST be a full-screen surface (Eastside-style
    screen shift, non-modal with preserved state -- popups are not the UI
    paradigm) and it MUST finish via
    ``store_mandate(game_manager.user_team, {...})`` with the keys
    documented in this module's docstring.
    """
    from coach_meeting_window import open_season_meeting
    return open_season_meeting(app)


# ---------------------------------------------------------------------------
# Trigger entry points (called from guarded hooks in the game flow)
# ---------------------------------------------------------------------------

def on_training_camp(game_manager: Any) -> None:
    """Yearly training-camp trigger: arm the user club, resolve AI clubs."""
    try:
        league = getattr(game_manager, "league", None)
        teams = list(getattr(league, "teams", None) or [])
        season = _league_season_year(game_manager)
        for t in teams:
            try:
                if _is_user_team(t, game_manager):
                    arm_season_meeting(t, reason="training_camp",
                                       season_year=season)
                else:
                    _maybe_resolve_ai(t, season)
            except Exception:
                continue
    except Exception:
        pass


def on_fantasy_draft_complete(game_manager: Any) -> None:
    """Fantasy-draft trigger: rosters are known, before the first advance."""
    try:
        league = getattr(game_manager, "league", None)
        teams = list(getattr(league, "teams", None) or [])
        season = _league_season_year(game_manager)
        for t in teams:
            try:
                if _is_user_team(t, game_manager):
                    arm_season_meeting(t, reason="fantasy_draft",
                                       season_year=season)
                else:
                    _maybe_resolve_ai(t, season)
            except Exception:
                continue
    except Exception:
        pass


def on_new_save(game_manager: Any, user_team: Any = None) -> None:
    """New-save trigger (after gm.set_user_team): arm the user club,
    resolve every AI club immediately. Defers entirely while a fantasy
    draft is pending -- the draft completion re-arms with real rosters."""
    try:
        if getattr(game_manager, "pending_fantasy_draft", False):
            return
        try:
            if (getattr(game_manager, "startup_settings", None) or {}).get(
                    "fantasy_draft"):
                return
        except Exception:
            pass
        league = getattr(game_manager, "league", None)
        teams = list(getattr(league, "teams", None) or [])
        season = _league_season_year(game_manager)
        if user_team is None:
            user_team = getattr(game_manager, "user_team", None)
        for t in teams:
            try:
                if t is user_team or _is_user_team(t, game_manager):
                    arm_season_meeting(t, reason="new_save",
                                       season_year=season)
                else:
                    _maybe_resolve_ai(t, season)
            except Exception:
                continue
    except Exception:
        pass


def on_coach_hired(team: Any, game_manager: Any = None) -> None:
    """New-coach trigger: a new voice means a new meeting. User club arms;
    AI clubs resolve immediately (no UI, never skipped)."""
    try:
        if team is None:
            return
        season = _league_season_year(game_manager)
        if _is_user_team(team, game_manager):
            arm_season_meeting(team, reason="new_coach",
                               season_year=season)
        else:
            resolve_ai_season_meeting(team, season_year=season)
    except Exception:
        pass


def _maybe_resolve_ai(team: Any, season_year: int) -> Optional[Dict[str, Any]]:
    """Resolve the AI meeting unless this season's mandate (with the
    current coach) is already stored."""
    try:
        m = get_active_mandate(team)
        if m and m.get("meeting_done") and _mandate_season(m) == int(season_year):
            coach = get_head_coach(team)
            mid = m.get("coach_id")
            cid = getattr(coach, "id", None) if coach is not None else None
            if (coach is None and not mid) or (mid is not None and mid == cid):
                return m
        return resolve_ai_season_meeting(team, season_year=season_year)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# AI GM resolution (no UI, never skipped for AI clubs)
# ---------------------------------------------------------------------------

def _ai_gm_ambition(team: Any) -> str:
    """The AI GM's ambition tag (from his GM staffer), for AMBITION_DRIVE."""
    try:
        from game_classes import StaffRole
        from ai_gm_identity import AMBITION_DRIVE
        gms = team.get_staff_by_role(StaffRole.GENERAL_MANAGER)
        if gms:
            a = str(getattr(gms[0], "ambition", "") or "").strip().lower()
            if a in AMBITION_DRIVE:
                return a
    except Exception:
        pass
    return "climb"


def _ai_authority(coach: Any) -> tuple:
    """(lines_owner, tactics_owner) from the coach's profile.

    first_nhl_chair defers to the GM who believed in him; high
    control_need keeps both pens; low control_need cedes them.
    """
    try:
        if coach is not None and bool(getattr(coach, "first_nhl_chair", False)):
            return "gm", "gm"
        cn = _num(getattr(coach, "control_need", 50), 50)
        if cn >= AI_CONTROL_KEEP:
            return "coach", "coach"
        if cn <= AI_CONTROL_DEFER:
            return "gm", "gm"
    except Exception:
        pass
    return "coach", "coach"


def _ai_rookie_stance(coach: Any) -> str:
    """Rookie stance from the coach's ambition (+ working_with_youngsters)."""
    try:
        amb = str(getattr(coach, "ambition", "") or "").strip().lower()
    except Exception:
        amb = ""
    stance = {"developer": "heavy", "stanley_cup": "sheltered"}.get(amb, "earned")
    try:
        wwy = _num(getattr(coach, "working_with_youngsters", 50), 50)
        if wwy >= AI_WWY_HEAVY:
            if stance == "earned":
                stance = "heavy"
            elif stance == "sheltered":
                stance = "earned"
    except Exception:
        pass
    return stance


def coach_preset_key(coach: Any) -> str:
    """Best-overlap IDENTITY_PRESETS key for the coach's style prefs.

    Data-driven (counts module matches between the coach's seeded prefs
    and each preset); ties fall to hybrid_transition. Never raises.
    """
    try:
        import tactics as _tx
        prefs = _tx.ensure_coach_tactics(coach)
        best, best_n = "hybrid_transition", -1
        for key, preset in _tx.IDENTITY_PRESETS.items():
            mods = (preset or {}).get("modules", {}) or {}
            n = sum(1 for c, v in mods.items() if prefs.get(c) == v)
            if n > best_n:
                best, best_n = key, n
        return best
    except Exception:
        return "hybrid_transition"


def _ai_deployer_notes(team, coach, expectation, assessment,
                       lines_owner, tactics_owner, stance) -> str:
    try:
        cname = _coach_display_name(coach) or "the coach"
        tname = getattr(team, "team_name", "the club")
        amb = str(getattr(coach, "ambition", "") or "").strip().lower() or "climb"
        agree = "aligned" if expectation == assessment else "disagreed"
        return (f"{tname}: {cname} ({amb}) {agree} with the front office "
                f"(office: {expectation}, coach: {assessment}). Lines: "
                f"{lines_owner}. Whiteboard: {tactics_owner}. Rookies: "
                f"{stance}.")
    except Exception:
        return ""


def resolve_ai_season_meeting(team: Any, league: Any = None,
                             season_year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Full AI resolution of the season meeting -- no UI, never skipped.

    Expectation: roster strength, nudged by the AI GM's ambition drive
    (stanley_cup +1 notch, developer -1 notch), then bent at most one
    notch UP toward a far-above board demand (small gaps hold, and a
    patient board never lowers the mandate: the board-vs-mandate tension
    is the point). The coach's own assessment
    comes from his ambition/personality; agreement/disagreement moves
    gm_trust on the same scale as the user's meeting. Same mandate
    structure and same downstream wiring as the user path.
    """
    try:
        if team is None:
            return None
        if season_year is None:
            season_year = _calendar_year()
        from ai_gm_identity import expectation_from_strength, AMBITION_DRIVE
        coach = get_head_coach(team)
        avg = _roster_avg_overall(team)
        base = expectation_from_strength(avg)
        drive = AMBITION_DRIVE.get(_ai_gm_ambition(team), 0.5)
        nudge = 1 if drive >= 1.0 else (-1 if drive <= 0.25 else 0)
        expectation = _shift(base, nudge)
        board = normalize_expectation(getattr(team, "board_expectation", None))
        if board:
            try:
                gap = _NOTCH_ORDER.index(board) - _NOTCH_ORDER.index(expectation)
                # Board pressure bends the mandate UP one notch when the
                # board is far above the GM's read -- never all the way
                # (the gap is the intended tension). A board demanding LESS
                # never lowers the mandate: patience isn't a ceiling.
                if gap > 1:
                    expectation = _shift(expectation, 1)
            except ValueError:
                pass
        assessment = coach_season_assessment(team, coach)
        lines_owner, tactics_owner = _ai_authority(coach)
        stance = _ai_rookie_stance(coach)
        approach = coach_preset_key(coach)
        notes = _ai_deployer_notes(team, coach, expectation, assessment,
                                   lines_owner, tactics_owner, stance)
        return store_mandate(team, {
            "season": int(season_year),
            "expectation": expectation,
            "coach_assessment": assessment,
            "rookie_stance": stance,
            "tactical_approach": approach,
            "lines_owner": lines_owner,
            "tactics_owner": tactics_owner,
            "deployer_notes": notes,
            "reason": "ai_resolution",
        }, apply_trust=True)
    except Exception:
        return None
