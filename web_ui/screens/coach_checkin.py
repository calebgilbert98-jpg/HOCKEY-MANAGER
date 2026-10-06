"""Coach check-in screen: the quarterly temperature check with the head
coach, web port of the desktop CheckinView (coach_checkin_window.py) over
the real model in coach_checkins.py.

Writes go through bridge._execute_command ("coach_checkin_beat" /
"coach_checkin_finish"); the trust effects are the real situational
deltas from coach_checkins.py, applied live per beat exactly like the
desktop. The voice lines below are ported verbatim from the desktop
window -- flavor over the same mechanics.
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("coach_checkin", __name__)


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Ported verbatim from coach_checkin_window.py (desktop): tone-keyed coach
# replies and the GM framing options per beat.
# ---------------------------------------------------------------------------

_COACH_LINES = {
    "ahead_credit": [
        "Credit where it's due, {name} says. The room bought in early and it's showing.",
        "He nods -- the plan's working, and he's quick to say the players earned it.",
    ],
    "ahead_honest": [
        "He keeps it level: good pace, but he's already thinking about the next stretch.",
        "No victory laps. {name} is pleased, and already onto what's next.",
    ],
    "ahead_demand": [
        "He blinks. \"We're winning and you want answers?\"",
        "{name} doesn't love the tone -- the record, he figures, speaks.",
    ],
    "track_credit": [
        "Right where we said we'd be, he says. Nobody's panicking in here.",
        "Steady. He likes the trajectory even if the highlight reel doesn't.",
    ],
    "track_honest": [
        "On pace. He walks through the underlying numbers -- nothing alarming, nothing to celebrate.",
        "He's honest about it: tracking, but the margins are thin.",
    ],
    "track_demand": [
        "He stiffens a little. \"On pace and I'm getting grilled?\"",
        "{name} thinks the demand is premature -- the mandate's being met.",
    ],
    "behind_credit": [
        "He appreciates the patience. \"We'll get there,\" he says, and he sounds like he believes it.",
        "Your support steadies him. He lays out the fixes he's already working on.",
    ],
    "behind_honest": [
        "He doesn't dodge it. Behind the pace, and he knows which nights cost them.",
        "{name} owns the gap -- no excuses, just the plan to close it.",
    ],
    "behind_demand": [
        "He takes the heat. Not happily, but he takes it.",
        "\"Fair,\" he says tightly. \"We'll answer it on the ice.\"",
    ],
    "behind_deflect": [
        "He points at the personnel, not the plan. The system works, he insists -- the finishers don't.",
        "{name} deflects toward the roster. You note the deflection.",
    ],
    "far_credit": [
        "Even your support can't hide how far off this is. He looks grateful, and worried.",
        "He thanks you for the patience -- and admits the season's slipping.",
    ],
    "far_honest": [
        "The numbers are ugly and he doesn't pretend otherwise.",
        "{name} is blunt: this isn't what either of you signed up for.",
    ],
    "far_demand": [
        "He goes quiet. \"You're right to ask,\" he says finally.",
        "No fight left in the answer -- just a coach who knows the seat is warm.",
    ],
    "far_demand_bristle": [
        "\"You want answers?\" He bristles. \"I've got a system and a room -- what I need is time.\"",
        "The demand lands badly. {name} is a proud man being asked to explain himself.",
    ],
    "room_support": [
        "He exhales. \"That means something, coming from you.\" The room hears it, he promises.",
        "Your backing steadies him. He'll carry it into the room tomorrow.",
    ],
    "room_direct": [
        "He nods, jaw set. \"The standard doesn't move. I'll handle it.\"",
        "Direct, and he respects direct. He takes the message without flinching.",
    ],
    "room_demand": [
        "He hears the demand. Whether he agrees is another conversation.",
        "\"Understood,\" he says -- clipped, professional, unreadable.",
    ],
    "room_defiant": [
        "\"This is MY room.\" The words come out flat and final.",
        "He draws a line: nobody tells him how to run his room. The temperature drops.",
    ],
    "room_praise": [
        "He smiles -- a rare one. \"They've earned that,\" he says of the room.",
        "Credit for the room lands well. He passes it straight to the players.",
    ],
    "rookies_honored": [
        "He's proud of the kids' progress. \"They're earning every shift.\"",
        "\"This is how you build something,\" {name} says.",
    ],
    "rookies_noted": [
        "He nods at the acknowledgement. Nothing more to say -- the ice time speaks.",
        "Noted. He moves on; the development plan is working.",
    ],
    "rookies_accept": [
        "He lays out his read: the kids aren't ready for more, and rushing them costs more than it buys.",
        "{name} defends his usage -- development timeline, not stubbornness.",
    ],
    "rookies_press": [
        "He doesn't like being pressed on his lineup. \"I play who earns it.\"",
        "The pressure lands. He'll think about it -- he won't say he'll change it.",
    ],
    "tactics_stay": [
        "\"The system works. We stay the course.\" He's sure of it.",
        "He appreciates the vote of confidence in the approach.",
    ],
    "tactics_fine": [
        "A brief nod. The tactics conversation stays light.",
        "Nothing to fix, so nothing much to say. He likes it that way.",
    ],
    "tactics_tweak": [
        "He's already got adjustments in mind. \"We'll sharpen the details.\"",
        "Tweaks, not panic. He walks through two or three small changes.",
    ],
    "tactics_overhaul": [
        "He goes very still. Overhauls mid-season are how coaches lose rooms, he says.",
        "\"You hired me for a system,\" {name} says. \"Let me coach it.\"",
    ],
}

# GM framing options per beat: (framing_key, button label, GM line).
_BEAT_FRAMINGS = {
    "expectations": [
        ("credit", "Share the credit",
         "The pace is the story. I wanted you to hear it from me: this is working."),
        ("honest", "Straight accounting",
         "Let's be honest about where we are against what we set out to do."),
        ("demand", "Demand answers",
         "I need answers. The mandate said one thing; the ice says another."),
    ],
    "room_messy": [
        ("support", "I've got your back",
         "The room's struggling. I've got your back -- tell me what you need."),
        ("direct", "The standard isn't moving",
         "The room's a mess and the standard isn't moving. I need it fixed."),
        ("demand", "Fix it, now",
         "Fix the room. Now. Whatever it takes."),
    ],
    "room_healthy": [
        ("praise", "Credit the room",
         "The room's in a good place. That's on you and the leaders -- credit where it's due."),
        ("skip", "Keep it brief",
         "The room looks fine. Let's not spend long here."),
    ],
    "rookies_honored": [
        ("credit", "Credit the development",
         "The kids are playing and producing. That's exactly what we talked about."),
        ("accept", "Just noting it",
         "The rookie plan's on track. Noted."),
    ],
    "rookies_not_honored": [
        ("accept", "Hear him out",
         "Talk me through the rookie usage. I want to understand your read."),
        ("press", "Press him",
         "We agreed on a rookie plan and the ice time doesn't show it."),
    ],
    "tactics_working": [
        ("stay", "Stay the course",
         "The system's delivering. Stay the course."),
        ("tweak", "Keep it light",
         "No need to overthink it -- the approach is fine."),
    ],
    "tactics_not_working": [
        ("tweak", "Tweak it",
         "It's not delivering. What are you adjusting?"),
        ("overhaul", "Overhaul it",
         "This isn't working. I want a real overhaul, not tweaks."),
    ],
}

_BEAT_TITLES = {
    "expectations": "Pace vs the mandate",
    "room": "The room",
    "rookies": "Rookie usage",
    "tactics": "Tactics",
}
_BEAT_ORDER = ["expectations", "room", "rookies", "tactics"]


def _coach_name(coach):
    if coach is None:
        return "your head coach"
    for attr in ("full_name", "name"):
        try:
            v = getattr(coach, attr, "")
            if v:
                return str(v)
        except Exception:
            continue
    try:
        return (f"{getattr(coach, 'first_name', '')} "
                f"{getattr(coach, 'last_name', '')}").strip() \
            or "your head coach"
    except Exception:
        return "your head coach"


def checkin_line(tone, coach, seed=None):
    """Pick the coach's reply for a beat tone (desktop _coach_line)."""
    import random as _r
    pool = _COACH_LINES.get(tone) or _COACH_LINES.get("track_honest")
    rng = _r.Random(seed) if seed is not None else _r
    name = _coach_name(coach).split()[-1]
    return rng.choice(pool).format(name=name)


def _framing_key_for(beat, situation):
    """Which _BEAT_FRAMINGS table a beat uses (desktop CheckinView parity)."""
    if beat == "room":
        return "room_messy" if situation.get("messy") else "room_healthy"
    if beat == "rookies":
        return ("rookies_honored" if situation.get("honored")
                else "rookies_not_honored")
    if beat == "tactics":
        return ("tactics_working" if situation.get("working")
                else "tactics_not_working")
    return "expectations"


def gm_line_for(beat, framing, situation=None):
    """The GM's spoken line for a framing choice on a beat."""
    key = _framing_key_for(beat, situation or {})
    for f, _label, gl in _BEAT_FRAMINGS.get(key, []):
        if f == framing:
            return gl
    return framing


def _framing_options(beat, situation):
    """Options for a beat given the situational read (desktop parity)."""
    key = _framing_key_for(beat, situation)
    return [{"key": f, "label": label, "line": line}
            for f, label, line in _BEAT_FRAMINGS[key]]


def _ckm():
    try:
        import coach_checkins as _m
        return _m
    except Exception:
        return None


def _team(live):
    gm = _resolve_gm(live)
    return _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)


def _checkin_state(live):
    """JSON-safe state for the check-in page. Never raises."""
    team = _team(live)
    m = _ckm()
    state = {"pending": False, "quarter": None, "quarter_label": "Quarterly",
             "coach_name": "your head coach", "coach_trust": 70,
             "game": 0, "mandate": "", "beats": {}, "transcript": [],
             "all_done": False, "message": ""}
    if team is None or m is None:
        state["message"] = "No team loaded." if team is None \
            else "Check-in system unavailable."
        return state
    try:
        state["pending"] = bool(m.is_checkin_pending(team))
    except Exception:
        pass
    if not state["pending"]:
        state["message"] = "No check-in is due right now. The next one is " \
            "armed after games ~20, ~40 and ~60."
        return state
    q = _safe(lambda: m.get_pending_quarter(team))
    state["quarter"] = q
    state["quarter_label"] = _safe(lambda: m.quarter_label(q), "Quarterly")
    coach = _safe(lambda: m.get_head_coach(team))
    if coach is None:
        try:
            coach = (getattr(team, "staff", None) or [None])[0]
        except Exception:
            coach = None
    state["coach_name"] = _coach_name(coach)
    state["coach_trust"] = _safe(
        lambda: round(float(getattr(coach, "gm_trust", 70) or 70)), 70)
    state["game"] = _safe(lambda: m.team_games_played(team), 0)
    mandate = _safe(lambda: m.get_active_mandate(team), {}) or {}
    state["mandate"] = str(mandate.get("expectation", "playoffs"))

    # Situational inputs (desktop CheckinView._load_context, same calls).
    try:
        band, actual, expected, _g = m.pace_band(team)
    except Exception:
        band, actual, expected = "track", 0.5, 0.55
    try:
        room = m.room_state(team) or {}
    except Exception:
        room = {"messy": False, "avg_morale": 70,
                "atmosphere_label": "Steady"}
    try:
        honored, share, stance = m.rookie_stance_honored(team)
    except Exception:
        honored, share, stance = True, 0.0, "none"
    try:
        working, tact_actual, tact_expected = m.tactics_working(team)
    except Exception:
        working, tact_actual, tact_expected = True, 0.5, 0.55

    band_word = {"ahead": "ahead of", "track": "tracking",
                 "behind": "behind", "far": "well behind"}.get(band, band)
    state["beats"]["expectations"] = {
        "title": _BEAT_TITLES["expectations"],
        "intro": (f"we're {band_word} it -- {actual:.3f} against "
                  f"{expected:.3f} expected."),
        "options": _framing_options("expectations", {}),
    }
    messy = bool(room.get("messy"))
    if messy:
        intro = (f"it's a mess in there -- {room.get('atmosphere_label')}, "
                 f"morale {room.get('avg_morale', 0):.0f}. "
                 f"You can't not bring it up.")
    else:
        intro = f"it's in decent shape -- {room.get('atmosphere_label')}."
    state["beats"]["room"] = {
        "title": _BEAT_TITLES["room"],
        "intro": intro,
        "mandatory": messy,
        "options": _framing_options("room", {"messy": messy}),
    }
    stance_word = {"heavy": "heavy rookie minutes", "earned": "earned ice time",
                   "sheltered": "sheltered minutes",
                   "none": "an AHL year for the kids"}.get(stance, stance)
    if honored:
        intro = (f"the plan was {stance_word}, and the kids are getting "
                 f"their share ({share:.0%}).")
    else:
        intro = (f"the plan was {stance_word}, but the kids' share is only "
                 f"{share:.0%}.")
    state["beats"]["rookies"] = {
        "title": _BEAT_TITLES["rookies"],
        "intro": intro,
        "options": _framing_options("rookies", {"honored": honored}),
    }
    if working:
        intro = (f"the approach is delivering -- pace {tact_actual:.3f} "
                 f"against {tact_expected:.3f} expected.")
    else:
        intro = (f"the approach isn't delivering -- pace "
                 f"{tact_actual:.3f} against {tact_expected:.3f} expected.")
    state["beats"]["tactics"] = {
        "title": _BEAT_TITLES["tactics"],
        "intro": intro,
        "options": _framing_options("tactics", {"working": working}),
    }

    # Resumable transcript (desktop replayed the in-progress draft).
    try:
        draft = getattr(team, "checkin_draft", None)
        if isinstance(draft, dict) and draft.get("quarter") == q:
            state["transcript"] = [
                {"beat": r.get("beat"), "gm_line": r.get("gm_line"),
                 "coach_line": r.get("coach_line"),
                 "delta": r.get("delta")}
                for r in draft.get("chosen", [])
            ]
            done_beats = [r.get("beat") for r in draft.get("chosen", [])]
            state["done_beats"] = done_beats
            state["all_done"] = all(
                b in done_beats for b in _BEAT_ORDER)
    except Exception:
        pass
    return state


@bp.route("/coach-checkin")
def coach_checkin_page():
    return render_template("coach_checkin.html")


@bp.route("/api/coach-checkin")
def api_coach_checkin():
    live = _live()
    if live is None:
        return jsonify({"pending": False, "message": "Game not loaded."})
    return jsonify(_safe(lambda: _checkin_state(live),
                         {"pending": False, "message": "Unavailable."}))


@bp.route("/api/coach-checkin/answer", methods=["POST"])
def api_coach_checkin_answer():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    beat = data.get("beat", "")
    framing = data.get("framing", "")
    valid_beats = {"expectations", "room", "rookies", "tactics"}
    if beat not in valid_beats:
        return jsonify({"ok": False, "error": "bad beat"}), 400
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    nonce = _uuid.uuid4().hex
    ok = enqueue_command("coach_checkin_beat", beat=beat,
                         framing=framing, nonce=nonce)
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/coach-checkin/finish", methods=["POST"])
def api_coach_checkin_finish():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    nonce = _uuid.uuid4().hex
    ok = enqueue_command("coach_checkin_finish", nonce=nonce)
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/coach-checkin/result")
def api_coach_checkin_result():
    live = _live()
    result = _safe(lambda: getattr(live, "_web_dev_result", None)) \
        if live else None
    return jsonify({"result": result})
