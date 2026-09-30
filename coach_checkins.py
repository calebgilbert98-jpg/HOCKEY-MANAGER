# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Quarterly coach check-ins: MODEL + WIRING + AI (no UI).

Chris's directive: the pre-season expectations conversation continues as the
season develops. After games ~20, ~40 and ~60 the GM sits down with his head
coach for a temperature check: how is the coach meeting the mandate from the
last chat? If the room is a mess the GM brings it up -- not as a
leash-shortening, but as a gauge: "earlier in the season we agreed X, how are
we tracking?"

This module owns the check-in model, the arm/pending/expiry API, the trigger
entry point, the situational trust scale (small bands -- a temperature check,
not the defining conversation), the mandate history, and the full AI-GM
resolution. It owns NO UI.

SHARED CONTRACT -- the sibling's conversation UI consumes this module:
  * ``CHECKIN_QUARTERS = (20, 40, 60)`` -- games-played thresholds.
  * ``is_checkin_pending(team)`` / ``get_pending_quarter(team)`` /
    ``arm_checkin(team, quarter, season)`` / ``expire_checkin(team)``.
  * ``room_state(team)`` -- {"avg_morale", "atmosphere_label",
    "atmosphere_score", "low_count", "messy"} (never raises).
  * ``rookie_minutes_share(team)`` / ``rookie_stance_honored(team)``.
  * ``tactics_working(team)`` -- pace-based read on the installed approach.
  * ``checkin_expectation_delta(team, coach, framing)``,
    ``checkin_room_delta(team, coach, framing)``,
    ``checkin_rookie_delta(team, coach, framing)``,
    ``checkin_tactics_delta(team, coach, framing)`` -- each returns
    (delta, tone, note). The UI applies them live per beat.
  * ``compute_checkin_trust_delta(team, coach, fields)`` -- the full total
    for the AI path (no conversation there). Identical components,
    identical scale (user/AI parity).
  * ``complete_checkin(team, fields, per_beat_applied=False)`` -- THE
    completion call. Validates, applies trust, appends the history entry to
    ``mandate["checkins"]``, clears the pending flag. The sibling calls
    this; the AI path calls it too.
  * ``resolve_ai_checkin(team, quarter, season_year)`` -- full AI
    resolution, no UI, never skipped.
  * ``on_day_advanced(game_manager)`` -- trigger entry point, called from
    a guarded hook in HockeyManagerGUI.simulate_day after the date rolls.

Downstream: check-in effects flow into the EXISTING gm_trust meter only --
no parallel evaluator. The carousel keeps judging the coach against his
mandate (dressing_room._coach_board_expectation); the check-ins are dated
evidence on the trail.

Non-blocking by construction: check-ins are RESUMABLE pending items. They
never appear in get_continue_state(); the day always advances. A pending
check-in expires when the next quarter's threshold is crossed or the
season rolls over.

TUNING CONSTANTS -- the check-in trust scale (NEEDS CHRIS'S APPROVAL):
  Small bands by design: per beat in [-3, +2], a full check-in in
  [-8, +6]. CHK_* below, plus ROOM_MESS_MORALE / ROOM_MESS_ATMOSPHERE
  (the "room is a mess" thresholds) and CHK_ROOKIE_SHARE (the
  stance-vs-reality bands).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Contract: quarters
# ---------------------------------------------------------------------------

#: Games-played thresholds that arm the three in-season check-ins.
CHECKIN_QUARTERS: Tuple[int, int, int] = (20, 40, 60)

#: Framings the GM can choose per beat (the conversation UI offers these).
EXPECTATION_FRAMINGS = ("credit", "honest", "demand")
ROOM_FRAMINGS = ("support", "direct", "demand", "praise", "skip")
ROOKIE_FRAMINGS = ("credit", "accept", "press")
TACTICS_FRAMINGS = ("stay", "tweak", "overhaul")

# ---------------------------------------------------------------------------
# Tuning constants -- NEED CHRIS'S APPROVAL (see module docstring)
# ---------------------------------------------------------------------------

#: Expectation-vs-reality beat: |actual - expected| pace gap bands.
CHK_AHEAD_GAP = 0.050
CHK_BEHIND_GAP = 0.050
CHK_FAR_BEHIND_GAP = 0.120

#: Room-state beat: below either of these, the room "is a mess" and the
#: beat becomes mandatory (the GM must bring it up).
ROOM_MESS_MORALE = 55          # average player morale (1-100)
ROOM_MESS_ATMOSPHERE = 45      # room_atmosphere score (0-100)

#: Rookie beat: U23 skater games-share of team GP that counts as the
#: stance being honored. "none" (AHL year) is honored when the kids are
#: genuinely kept down (share below the band).
CHK_ROOKIE_SHARE = {
    "heavy": 0.55,
    "earned": 0.40,
    "sheltered": 0.25,
    "none": 0.25,
}

#: Trust scale -- expectation beat matrix [band][framing].
CHK_EXPECT_MATRIX = {
    "ahead": {"credit": 2, "honest": 1, "demand": 0},
    "track": {"credit": 1, "honest": 1, "demand": -1},
    "behind": {"credit": 0, "honest": -1, "demand": -2},
    "far": {"credit": -1, "honest": -2, "demand": -3},
}
#: Room beat: (framing, messy) -> delta. Authoritarian coaches take an
#: extra -1 on "demand" (nobody tells them how to run their room).
CHK_ROOM_SUPPORT = 1
CHK_ROOM_DIRECT = -1
CHK_ROOM_DEMAND = -2
CHK_ROOM_AUTH_DEMAND_EXTRA = -1
CHK_ROOM_PRAISE = 1
#: Rookie beat.
CHK_ROOKIE_HONORED = 1
CHK_ROOKIE_PRESS = -1
#: Tactics beat.
CHK_TACTICS_STAY = 1
CHK_TACTICS_OVERHAUL = -2


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _today_str() -> str:
    try:
        return date.today().isoformat()
    except Exception:
        return ""


def _sibling():
    """Lazy import of the season-meeting contract module."""
    try:
        import coach_season_meeting as _m
        return _m
    except Exception:
        return None


def _expected_pace():
    try:
        from ai_gm_identity import EXPECTED_PACE
        return dict(EXPECTED_PACE)
    except Exception:
        return {"win_cup": 0.650, "contend": 0.600,
                "playoffs": 0.550, "rebuild": 0.450}


def _mandate(team: Any) -> Optional[Dict[str, Any]]:
    m = _sibling()
    if m is not None:
        fn = getattr(m, "get_active_mandate", None)
        if callable(fn):
            try:
                return fn(team)
            except Exception:
                pass
    try:
        d = getattr(team, "season_mandate", None)
        if isinstance(d, dict) and d:
            return dict(d)
    except Exception:
        pass
    return None


def _mandate_done(team: Any) -> bool:
    m = _mandate(team)
    return bool(m and m.get("meeting_done"))


def get_active_mandate(team: Any) -> Dict[str, Any]:
    """Public alias: the team's active season mandate (plain dict).
    Never raises."""
    try:
        return dict(_mandate(team) or {})
    except Exception:
        return {}


def _mandate_season(team: Any) -> Optional[int]:
    try:
        s = (_mandate(team) or {}).get("season")
        return int(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _coach(team: Any) -> Optional[Any]:
    m = _sibling()
    if m is not None:
        fn = getattr(m, "get_head_coach", None)
        if callable(fn):
            try:
                return fn(team)
            except Exception:
                pass
    return None


def get_head_coach(team: Any) -> Optional[Any]:
    """Public alias: the team's head coach, or None. Never raises."""
    return _coach(team)


def _is_authoritarian(coach: Any) -> bool:
    try:
        return _num(getattr(coach, "control_need", 50), 50) >= 75
    except Exception:
        return False


def _coach_ambition(coach: Any) -> str:
    try:
        return str(getattr(coach, "ambition", "") or "climb").strip().lower()
    except Exception:
        return "climb"


def team_games_played(team: Any) -> int:
    """Regular-season games played, from the record. Never raises."""
    try:
        w = int(getattr(team, "wins", 0) or 0)
        l = int(getattr(team, "losses", 0) or 0)
        otl = int(getattr(team, "ot_losses", 0) or 0)
        return max(0, w + l + otl)
    except Exception:
        return 0


def team_points_pace(team: Any) -> Tuple[float, int]:
    """(points-pace 0..1, games played). dressing_room's helper first."""
    try:
        import dressing_room as _dr
        fn = getattr(_dr, "_team_points_pace", None)
        if callable(fn):
            return fn(team, None)
    except Exception:
        pass
    try:
        gp = team_games_played(team)
        if gp > 0:
            w = int(getattr(team, "wins", 0) or 0)
            otl = int(getattr(team, "ot_losses", 0) or 0)
            return (2.0 * w + otl) / (2.0 * gp), gp
    except Exception:
        pass
    return 0.5, 0


# ---------------------------------------------------------------------------
# Pending API
# ---------------------------------------------------------------------------

def is_checkin_pending(team: Any) -> bool:
    try:
        return bool(getattr(team, "checkin_pending", False))
    except Exception:
        return False


def get_pending_quarter(team: Any) -> Optional[int]:
    try:
        q = getattr(team, "checkin_quarter", None)
        return int(q) if q is not None else None
    except (TypeError, ValueError):
        return None


def current_quarter(team: Any) -> Optional[int]:
    """The highest armed quarter the team's GP has reached, else None."""
    gp = team_games_played(team)
    hit = None
    for q in CHECKIN_QUARTERS:
        if gp >= q:
            hit = q
    return hit


def quarter_label(quarter: Optional[int]) -> str:
    return {20: "First-quarter", 40: "Second-quarter",
            60: "Third-quarter"}.get(quarter or 0, "Quarterly")


def arm_checkin(team: Any, quarter: int, season: Optional[int] = None,
                reason: str = "quarter") -> bool:
    """Arm a quarterly check-in (sets the pending flag). Idempotent per
    (season, quarter): a completed check-in for that quarter is not
    re-armed. Never raises."""
    try:
        if team is None or quarter not in CHECKIN_QUARTERS:
            return False
        if season is None:
            season = _mandate_season(team)
        if season is None:
            try:
                season = date.today().year
            except Exception:
                season = 2026
        if not is_checkin_pending(team):
            for h in ((_mandate(team) or {}).get("checkins") or []):
                try:
                    if (int(h.get("season") or 0) == int(season)
                            and int(h.get("quarter") or 0) == int(quarter)
                            and not h.get("skipped")):
                        return True  # already held this quarter
                except (TypeError, ValueError):
                    continue
        team.checkin_pending = True
        team.checkin_quarter = int(quarter)
        try:
            coach = _coach(team)
            cname = ""
            try:
                cname = str(getattr(coach, "full_name", "")
                            or getattr(coach, "name", "") or "")
            except Exception:
                pass
            team.checkin_context = {
                "reason": str(reason or "quarter"),
                "season": int(season),
                "quarter": int(quarter),
                "coach": cname.strip(),
            }
        except Exception:
            pass
        return True
    except Exception:
        return False


def expire_checkin(team: Any, reason: str = "expired") -> bool:
    """Expire a pending check-in without recording it. Never raises."""
    try:
        if team is None:
            return False
        team.checkin_pending = False
        team.checkin_quarter = None
        try:
            team.checkin_context = {}
        except Exception:
            pass
        try:
            if hasattr(team, "checkin_draft"):
                delattr(team, "checkin_draft")
        except Exception:
            pass
        return True
    except Exception:
        return False


def _postseason_underway(league: Any) -> bool:
    """True once the regular season is complete and the playoff bracket
    holds series. Check-ins are a regular-season conversation ("before
    playoffs"); a pending one expires when the season ends. Never raises.
    """
    try:
        bracket = getattr(league, "playoff_bracket", None)
        if bracket is None:
            return False
        rounds = getattr(bracket, "ROUND_ORDER", None) or ()
        series = getattr(bracket, "playoff_series", None) or {}
        return any(series.get(r) for r in rounds)
    except Exception:
        return False


def maybe_arm_checkins(game_manager: Any) -> None:
    """Per-day maintenance: arm crossed quarters, expire stale pendings.

    The user club arms (RESUMABLE pending item, never a blocker); every AI
    club resolves immediately -- no UI, never skipped. A pending check-in
    whose quarter has passed expires silently. A pending check-in with GP
    below the first quarter means the season rolled over: expire. Once the
    postseason is underway the regular-season conversation is over:
    pending check-ins expire and nothing new arms. Clubs with no completed
    preseason mandate get nothing. Never raises.
    """
    try:
        league = getattr(game_manager, "league", None)
        teams = list(getattr(league, "teams", None) or [])
        if _postseason_underway(league):
            for t in teams:
                try:
                    if is_checkin_pending(t):
                        expire_checkin(t, "season_ended")
                except Exception:
                    continue
            return
        ut = getattr(game_manager, "user_team", None)
        for t in teams:
            try:
                _maintain_team(t, t is ut, game_manager)
            except Exception:
                continue
    except Exception:
        pass


def _maintain_team(team: Any, is_user: bool, game_manager: Any) -> None:
    if not _mandate_done(team):
        if is_checkin_pending(team):
            expire_checkin(team, "no_mandate")
        return
    season = _mandate_season(team)
    gp = team_games_played(team)
    done_q = set()
    for h in ((_mandate(team) or {}).get("checkins") or []):
        try:
            if (int(h.get("season") or 0) == int(season or 0)
                    and not h.get("skipped")):
                done_q.add(int(h.get("quarter") or 0))
        except (TypeError, ValueError):
            continue
    pending_q = get_pending_quarter(team) if is_checkin_pending(team) else None
    if is_checkin_pending(team) and gp < CHECKIN_QUARTERS[0]:
        expire_checkin(team, "season_rollover")
        pending_q = None
    # Every crossed quarter with no completed check-in needs one. The
    # user's club arms the LATEST (one pending conversation at a time;
    # the older one expires by supersession). AI clubs resolve each in
    # order -- no UI, never skipped.
    todo = [q for q in CHECKIN_QUARTERS
            if gp >= q and q not in done_q and q != pending_q]
    if not todo:
        return
    if is_user:
        arm_checkin(team, max(todo), season)
    else:
        for q in sorted(todo):
            try:
                resolve_ai_checkin(team, q, season_year=season)
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Situational inputs
# ---------------------------------------------------------------------------

def room_state(team: Any) -> Dict[str, Any]:
    """The room's health: avg morale, atmosphere, and the messy verdict.

    "Messy" (the GM MUST bring it up): average morale below
    ROOM_MESS_MORALE or the atmosphere score below ROOM_MESS_ATMOSPHERE
    (label Strained/Fractured). Never raises.
    """
    out = {"avg_morale": 70.0, "atmosphere_label": "Steady",
           "atmosphere_score": 60.0, "low_count": 0, "messy": False}
    try:
        mor = []
        low = 0
        for p in getattr(team, "roster", None) or []:
            try:
                v = float(getattr(p, "morale", 70))
                mor.append(v)
                if v < 45:
                    low += 1
            except (TypeError, ValueError):
                continue
        if mor:
            out["avg_morale"] = sum(mor) / len(mor)
        out["low_count"] = low
    except Exception:
        pass
    try:
        import dressing_room as _dr
        atm = _dr.room_atmosphere(team) or {}
        out["atmosphere_label"] = str(atm.get("label") or out["atmosphere_label"])
        out["atmosphere_score"] = float(atm.get("score") or 0.0)
    except Exception:
        pass
    try:
        out["messy"] = (out["avg_morale"] < ROOM_MESS_MORALE
                        or out["atmosphere_score"] < ROOM_MESS_ATMOSPHERE)
    except Exception:
        out["messy"] = False
    return out


def rookie_minutes_share(team: Any) -> float:
    """Share of team GP skated by U23 skaters (0..1). Never raises."""
    try:
        gp = team_games_played(team)
        if gp <= 0:
            return 0.0
        shares = []
        for p in getattr(team, "roster", None) or []:
            try:
                if str(getattr(p, "primary_position", "")
                       or getattr(p, "position", "")).upper() == "G":
                    continue
                if float(getattr(p, "age", 30)) >= 23:
                    continue
                pgp = int(getattr(getattr(p, "stats", None),
                                 "games_played", 0) or 0)
                shares.append(min(1.0, pgp / gp))
            except (TypeError, ValueError):
                continue
        if not shares:
            return 0.0
        return sum(shares) / len(shares)
    except Exception:
        return 0.0


def rookie_stance_honored(team: Any) -> Tuple[bool, float, str]:
    """(honored, share, stance): is the mandate's rookie stance actually
    being lived? Never raises."""
    try:
        stance = (_mandate(team) or {}).get("rookie_stance", "none")
        if stance not in ("heavy", "earned", "sheltered", "none"):
            stance = "none"
        share = rookie_minutes_share(team)
        band = CHK_ROOKIE_SHARE[stance]
        honored = share >= band if stance != "none" else share < band
        return honored, share, stance
    except Exception:
        return True, 0.0, "none"


def tactics_working(team: Any) -> Tuple[bool, float, float]:
    """(working, actual_pace, expected_pace): pace-based read on whether
    the installed approach is delivering. Never raises."""
    try:
        actual, _gp = team_points_pace(team)
        expected = float(_expected_pace().get(
            (_mandate(team) or {}).get("expectation", "playoffs"), 0.55))
        return actual >= expected - 0.03, actual, expected
    except Exception:
        return True, 0.5, 0.55


def pace_band(team: Any) -> Tuple[str, float, float, float]:
    """(band, actual, expected, gap): ahead | track | behind | far."""
    try:
        actual, _gp = team_points_pace(team)
        expected = float(_expected_pace().get(
            (_mandate(team) or {}).get("expectation", "playoffs"), 0.55))
        gap = actual - expected
        if gap >= CHK_AHEAD_GAP:
            return "ahead", actual, expected, gap
        if gap <= -CHK_FAR_BEHIND_GAP:
            return "far", actual, expected, gap
        if gap <= -CHK_BEHIND_GAP:
            return "behind", actual, expected, gap
        return "track", actual, expected, gap
    except Exception:
        return "track", 0.5, 0.55, 0.0


# ---------------------------------------------------------------------------
# Situational trust scale -- one component per check-in beat.
#
# Each returns (delta, tone, note). The tone is the situational
# classification the conversation UI keys its voice lines on; the note is
# the plain-language reason recorded in the check-in history. Bands are
# deliberately small: a temperature check, not the defining conversation.
# The user's path applies each beat live; the AI path applies
# compute_checkin_trust_delta() at completion -- identical math.
# ---------------------------------------------------------------------------

def checkin_expectation_delta(team: Any, coach: Any, framing: Any):
    """Expectation-vs-reality beat: the pace gap, and how the GM frames it.

    "credit" shares the upside and softens the downside; "honest" is a
    straight accounting; "demand" asks for answers -- an authoritarian
    coach takes an extra -1 when demands land on his desk.
    Range [-3, +2].
    """
    framing = str(framing or "honest").strip().lower()
    if framing not in EXPECTATION_FRAMINGS:
        framing = "honest"
    band, actual, expected, gap = pace_band(team)
    try:
        delta = int(CHK_EXPECT_MATRIX[band][framing])
    except KeyError:
        delta = 0
    tone = f"{band}_{framing}"
    note = (f"Pace {actual:.3f} vs mandate {expected:.3f} "
            f"({band}, framed '{framing}').")
    if framing == "demand" and _is_authoritarian(coach):
        delta -= 1
        tone = f"{band}_demand_bristle"
        note += " Authoritarian coach bristled at the demand."
    if band == "behind" and framing == "honest" and _is_authoritarian(coach):
        tone = "behind_deflect"
        note += " Coach deflected toward personnel."
    delta = max(-3, min(2, delta))
    return delta, tone, note


def checkin_room_delta(team: Any, coach: Any, framing: Any):
    """Room-state beat. When the room is a mess this beat is mandatory --
    the GM must bring it up. Support steadies (+1); going direct costs
    (-1); demanding fixes from an authoritarian about HIS room costs
    (-3). A healthy room praised is (+1); skipped is 0. Range [-3, +1].
    """
    framing = str(framing or "support").strip().lower()
    if framing not in ROOM_FRAMINGS:
        framing = "support"
    st = room_state(team)
    messy = bool(st.get("messy"))
    if not messy:
        if framing == "praise":
            return (CHK_ROOM_PRAISE, "room_praise",
                    f"Room healthy ({st['atmosphere_label']}); GM praised it.")
        return (0, "room_skip", "Room healthy; the beat was skipped.")
    if framing == "support":
        return (CHK_ROOM_SUPPORT, "room_support",
                f"Messy room ({st['atmosphere_label']}, morale "
                f"{st['avg_morale']:.0f}); GM offered support.")
    if framing == "direct":
        return (CHK_ROOM_DIRECT, "room_direct",
                f"Messy room; GM was direct about the standard.")
    # demand
    delta = CHK_ROOM_DEMAND
    tone = "room_demand"
    note = f"Messy room; GM demanded fixes."
    if _is_authoritarian(coach):
        delta += CHK_ROOM_AUTH_DEMAND_EXTRA
        tone = "room_defiant"
        note += " Authoritarian coach: nobody tells him how to run his room."
    return max(-3, delta), tone, note


def checkin_rookie_delta(team: Any, coach: Any, framing: Any):
    """Rookie-stance-vs-reality beat. Honored -> credit (+1). Not honored:
    the GM accepts the coach's read (0) or presses (-1). Range [-1, +1].
    """
    framing = str(framing or "credit").strip().lower()
    if framing not in ROOKIE_FRAMINGS:
        framing = "credit"
    honored, share, stance = rookie_stance_honored(team)
    if honored:
        if framing == "credit":
            return (CHK_ROOKIE_HONORED, "rookies_honored",
                    f"Stance '{stance}' honored (kids' share {share:.0%}).")
        return (0, "rookies_noted",
                f"Stance '{stance}' honored; GM noted it flatly.")
    if framing == "press":
        return (CHK_ROOKIE_PRESS, "rookies_press",
                f"Stance '{stance}' NOT honored (share {share:.0%}); "
                "GM pressed.")
    return (0, "rookies_accept",
            f"Stance '{stance}' not honored (share {share:.0%}); "
            "GM accepted the coach's read.")


def checkin_tactics_delta(team: Any, coach: Any, framing: Any):
    """Tactics beat: pace-based read on the installed approach. Working ->
    stay the course (+1). Not working: tweak (0) or overhaul (-2).
    Range [-2, +1].
    """
    framing = str(framing or "stay").strip().lower()
    if framing not in TACTICS_FRAMINGS:
        framing = "stay"
    working, actual, expected = tactics_working(team)
    if working:
        if framing == "stay":
            return (CHK_TACTICS_STAY, "tactics_stay",
                    f"Approach delivering (pace {actual:.3f} vs "
                    f"{expected:.3f}); staying the course.")
        return (0, "tactics_fine",
                "Approach delivering; the beat was light.")
    if framing == "overhaul":
        return (CHK_TACTICS_OVERHAUL, "tactics_overhaul",
                f"Approach not delivering (pace {actual:.3f} vs "
                f"{expected:.3f}); GM wants an overhaul.")
    return (0, "tactics_tweak",
            f"Approach not delivering; GM asked for tweaks.")


def compute_checkin_trust_delta(team: Any, coach: Any,
                                fields: Dict[str, Any]) -> int:
    """The full situational trust delta for a completed check-in.

    Sum of every beat component. Used by the AI resolution path (no
    conversation beats run there); the user's path applies the same
    components live -- identical math, identical scale. Never raises.
    """
    try:
        fields = dict(fields or {})
        total = 0
        d, _, _ = checkin_expectation_delta(
            team, coach, fields.get("expectation_framing"))
        total += d
        d, _, _ = checkin_room_delta(team, coach, fields.get("room_framing"))
        total += d
        d, _, _ = checkin_rookie_delta(team, coach, fields.get("rookie_framing"))
        total += d
        d, _, _ = checkin_tactics_delta(team, coach, fields.get("tactics_framing"))
        total += d
        return int(total)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

def complete_checkin(team: Any, fields: Dict[str, Any],
                     apply_trust: bool = True,
                     per_beat_applied: bool = False) -> Optional[Dict[str, Any]]:
    """Validate, record, and apply a quarterly check-in -- THE completion.

    The sibling's conversation UI calls this when the check-in wraps;
    the AI path calls it too (user/AI parity). Appends the history entry
    to ``mandate["checkins"]`` (so the next check-in references the
    last), clears the pending flag. Never raises; returns the entry.

    Trust: the conversation UI applies each beat's delta live, so it
    passes per_beat_applied=True and nothing further lands here (no seal
    delta -- the beats carried the substance). The AI path gets the full
    situational total from compute_checkin_trust_delta.
    """
    try:
        if team is None:
            return None
        fields = dict(fields or {})
        mandate = _mandate(team)
        if not mandate or not mandate.get("meeting_done"):
            return None
        season = fields.get("season")
        try:
            season = int(season) if season is not None else _mandate_season(team)
        except (TypeError, ValueError):
            season = _mandate_season(team)
        quarter = fields.get("quarter")
        try:
            quarter = int(quarter) if quarter is not None else get_pending_quarter(team)
        except (TypeError, ValueError):
            quarter = get_pending_quarter(team)
        if quarter not in CHECKIN_QUARTERS:
            return None
        coach = _coach(team)
        if apply_trust and coach is not None:
            try:
                if per_beat_applied:
                    delta = 0
                else:
                    delta = compute_checkin_trust_delta(team, coach, fields)
                cur = _num(getattr(coach, "gm_trust", 70), 70)
                coach.gm_trust = max(0.0, min(100.0, cur + delta))
            except Exception:
                pass
        gp = team_games_played(team)
        entry = {
            "date": str(fields.get("date") or _today_str()),
            "season": int(season) if season is not None else None,
            "quarter": int(quarter),
            "game": int(gp),
            "topics": list(fields.get("topics") or []),
            "deltas": dict(fields.get("deltas") or {}),
            "notes": list(fields.get("notes") or []),
        }
        try:
            hist = mandate.get("checkins")
            if not isinstance(hist, list):
                hist = []
            hist.append(entry)
            mandate["checkins"] = hist
            team.season_mandate = mandate
        except Exception:
            pass
        expire_checkin(team, "completed")
        return dict(entry)
    except Exception:
        return None


def last_checkin(team: Any) -> Optional[Dict[str, Any]]:
    """The most recent completed check-in entry, or None. Never raises."""
    try:
        hist = (_mandate(team) or {}).get("checkins") or []
        done = [h for h in hist if isinstance(h, dict) and not h.get("skipped")]
        return dict(done[-1]) if done else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# AI GM resolution (no UI, never skipped)
# ---------------------------------------------------------------------------

def _ai_framings(team: Any, coach: Any) -> Dict[str, str]:
    """The AI GM's beat framings: honest accounting, supportive in a messy
    room, accepts the coach's read on rookies, tweaks (not overhauls) a
    struggling system. A Cup-or-bust GM far behind the pace demands
    answers. Deterministic and documented."""
    band, _a, _e, _g = pace_band(team)
    messy = bool(room_state(team).get("messy"))
    honored, _s, _st = rookie_stance_honored(team)
    working, _a2, _e2 = tactics_working(team)
    exp = "honest"
    if band == "far" and _coach_ambition(coach) == "stanley_cup":
        exp = "demand"
    elif band == "ahead":
        exp = "credit"
    return {
        "expectation_framing": exp,
        "room_framing": "support" if messy else "praise",
        "rookie_framing": "credit" if honored else "accept",
        "tactics_framing": "stay" if working else "tweak",
    }


def resolve_ai_checkin(team: Any, quarter: int,
                       season_year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Full AI resolution of a quarterly check-in -- no UI, never skipped.

    Same beats, same trust math, same history shape as the user path.
    Never raises.
    """
    try:
        if team is None or quarter not in CHECKIN_QUARTERS:
            return None
        if season_year is None:
            season_year = _mandate_season(team)
        coach = _coach(team)
        framings = _ai_framings(team, coach)
        notes = []
        try:
            band, actual, expected, _g = pace_band(team)
            notes.append(
                f"Q{quarter}: pace {actual:.3f} vs mandate {expected:.3f} ({band}).")
            st = room_state(team)
            notes.append(
                f"Room {st['atmosphere_label']} (morale {st['avg_morale']:.0f}).")
        except Exception:
            pass
        return complete_checkin(team, {
            "season": season_year,
            "quarter": quarter,
            "topics": ["expectations", "room", "rookies", "tactics"],
            "deltas": {},
            "notes": notes,
            **framings,
        }, apply_trust=True, per_beat_applied=False)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Trigger entry point (called from a guarded hook in simulate_day)
# ---------------------------------------------------------------------------

def on_day_advanced(game_manager: Any) -> None:
    """Daily trigger: arm crossed quarters, expire stale pendings.

    Guarded: a check-in failure must never break day advancement.
    """
    try:
        maybe_arm_checkins(game_manager)
    except Exception:
        pass
