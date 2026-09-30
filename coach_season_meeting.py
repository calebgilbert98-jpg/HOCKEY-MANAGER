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

TUNING CONSTANTS (need Chris's approval -- flagged in the build report):
  TRUST_ALIGNED_BUMP, TRUST_MISALIGNED_DENT, COACH_LOW_MORALE_NOTCH,
  AI_CONTROL_KEEP, AI_CONTROL_DEFER, AI_WWY_HEAVY.
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

# ---------------------------------------------------------------------------
# Tuning constants -- NEED CHRIS'S APPROVAL (see module docstring)
# ---------------------------------------------------------------------------

#: gm_trust delta when GM and coach agree in the meeting. Mirrors the
#: honored-advice bump in reputation_system.advise_coach (+5).
TRUST_ALIGNED_BUMP = 5
#: gm_trust delta when they disagree. A real ding, smaller than the
#: +15 reprieve bump.
TRUST_MISALIGNED_DENT = -8
#: Coach morale (1-100) below which his season assessment drops a notch.
COACH_LOW_MORALE_NOTCH = 40
#: AI authority: control_need >= this -> the coach keeps lines + tactics.
AI_CONTROL_KEEP = 65
#: AI authority: control_need <= this -> the GM takes lines + tactics.
AI_CONTROL_DEFER = 40
#: AI rookie stance: working_with_youngsters >= this nudges the stance one
#: step toward "heavy".
AI_WWY_HEAVY = 75


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
                  apply_trust: bool = True) -> Optional[Dict[str, Any]]:
    """Validate, store, and apply a season mandate -- THE completion call.

    The sibling's conversation UI calls this when the meeting completes;
    the AI path calls it too (user/AI parity). Derives ``aligned`` from
    expectation vs coach_assessment, applies the shared gm_trust effect,
    applies downstream wiring, stores the mandate, clears the pending
    flag. Never raises; returns the stored mandate or None.
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
        if apply_trust and coach is not None:
            try:
                delta = TRUST_ALIGNED_BUMP if aligned else TRUST_MISALIGNED_DENT
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

        return {
            "id": "season_meeting",
            "title": "Meet with your head coach",
            "detail": ("Before the season starts, sit down with %s and agree "
                       "on expectations, the rookie plan, and who owns the "
                       "lines and the whiteboard." % cname),
            "action": ("Open Season Meeting", _open),
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
