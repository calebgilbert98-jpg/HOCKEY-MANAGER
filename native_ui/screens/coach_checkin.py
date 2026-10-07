"""Coach check-in screen: the quarterly temperature check with the head coach.

Native port of web_ui/screens/coach_checkin.py + coach_checkin.js (itself
a web port of the desktop CheckinView). Trust effects are the real
situational deltas from coach_checkins.py, applied live per beat exactly
like the desktop -- the voice lines are ported verbatim from the desktop
window, flavor over the same mechanics.

The web version queued answers through a command queue and polled for
results with a nonce. Native calls the game object directly, so each
answer resolves synchronously; a short QTimer delay keeps the
"coach is thinking" beat of the conversation (answer -> result ->
next beat) without blocking the UI.
"""
import html
import random as _random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QProgressBar, QSplitter, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _ckm():
    try:
        import coach_checkins as _m
        return _m
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ported verbatim from web_ui/screens/coach_checkin.py (itself verbatim from
# the desktop coach_checkin_window.py): tone-keyed coach replies and the GM
# framing options per beat.
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
BEAT_ORDER = ["expectations", "room", "rookies", "tactics"]

_BEAT_DELTA_FNS = {
    "expectations": "checkin_expectation_delta",
    "room": "checkin_room_delta",
    "rookies": "checkin_rookie_delta",
    "tactics": "checkin_tactics_delta",
}


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
    pool = _COACH_LINES.get(tone) or _COACH_LINES.get("track_honest")
    rng = _random.Random(seed) if seed is not None else _random
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


class CoachCheckinScreen(BaseScreen):
    """Multi-beat quarterly conversation with the head coach."""

    title = "Coach Check-In"

    def __init__(self, game, main_window, parent=None):
        self._state = None
        self._busy = False
        self._beat_rows = {}
        super().__init__(game, main_window, parent)

    # ------------------------------------------------------------------
    # game access
    # ------------------------------------------------------------------
    def _gm(self):
        return getattr(self.game, "game_manager", None) or self.game

    def _team(self):
        gm = self._gm()
        return (_safe(lambda: gm.user_team)
                or _safe(lambda: getattr(self.game, "user_team", None)))

    def _head_coach(self, team, m):
        try:
            fn = getattr(m, "get_head_coach", None)
            if callable(fn):
                coach = fn(team)
                if coach is not None:
                    return coach
        except Exception:
            pass
        try:
            return (getattr(team, "staff", None) or [None])[0]
        except Exception:
            return None

    def _draft(self, team, m):
        """Resume-or-fresh draft, keyed to the pending quarter."""
        try:
            pending_q = None
            try:
                pending_q = m.get_pending_quarter(team)
            except Exception:
                pass
            d = getattr(team, "checkin_draft", None)
            if isinstance(d, dict) and d.get("quarter") == pending_q \
                    and pending_q is not None:
                return d
            gp = _safe(lambda: m.team_games_played(team), 0)
            d = {"quarter": pending_q, "game": gp, "stage": "opening",
                 "chosen": [], "topics": [], "deltas": {}, "notes": [],
                 "done": False}
            try:
                team.checkin_draft = d
            except Exception:
                pass
            return d
        except Exception:
            return {"quarter": None, "game": 0, "stage": "opening",
                    "chosen": [], "topics": [], "deltas": {}, "notes": [],
                    "done": False}

    # ------------------------------------------------------------------
    # state (port of web _checkin_state)
    # ------------------------------------------------------------------
    def _load_state(self):
        team = self._team()
        m = _ckm()
        state = {"pending": False, "quarter": None,
                 "quarter_label": "Quarterly",
                 "coach_name": "your head coach", "coach_trust": 70,
                 "game": 0, "mandate": "", "beats": {}, "transcript": [],
                 "done_beats": [], "all_done": False, "message": ""}
        if team is None or m is None:
            state["message"] = ("No team loaded." if team is None
                                else "Check-in system unavailable.")
            return state
        try:
            state["pending"] = bool(m.is_checkin_pending(team))
        except Exception:
            pass
        if not state["pending"]:
            state["message"] = ("No check-in is due right now. The next one "
                                "is armed after games ~20, ~40 and ~60.")
            return state
        q = _safe(lambda: m.get_pending_quarter(team))
        state["quarter"] = q
        state["quarter_label"] = _safe(lambda: m.quarter_label(q),
                                       "Quarterly")
        coach = self._head_coach(team, m)
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
                     "behind": "behind",
                     "far": "well behind"}.get(band, band)
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
        stance_word = {"heavy": "heavy rookie minutes",
                       "earned": "earned ice time",
                       "sheltered": "sheltered minutes",
                       "none": "an AHL year for the kids"}.get(stance, stance)
        if honored:
            intro = (f"the plan was {stance_word}, and the kids are getting "
                     f"their share ({share:.0%}).")
        else:
            intro = (f"the plan was {stance_word}, but the kids' share is "
                     f"only {share:.0%}.")
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
                     f"{tact_actual:.3f} against {tact_expected:.3f} "
                     f"expected.")
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
                done_beats = [r.get("beat")
                              for r in draft.get("chosen", [])]
                state["done_beats"] = done_beats
                state["all_done"] = all(
                    b in done_beats for b in BEAT_ORDER)
        except Exception:
            pass
        return state

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        self._empty = QLabel("")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet("color: #6b7488; font-size: 15px; "
                                  "padding: 40px;")
        self._empty.hide()
        self._layout.addWidget(self._empty)

        splitter = QSplitter(Qt.Horizontal)
        self._splitter = splitter

        # -- conversation column --
        convo = QWidget()
        cl = QVBoxLayout(convo)
        cl.setContentsMargins(0, 0, 8, 0)

        self._sub = QLabel("")
        self._sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        cl.addWidget(self._sub)

        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setMinimumHeight(280)
        cl.addWidget(self._transcript, 1)

        self._beat_box = QWidget()
        self._beat_layout = QVBoxLayout(self._beat_box)
        self._beat_layout.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self._beat_box)

        self._finish_box = QWidget()
        fl = QVBoxLayout(self._finish_box)
        fl.setContentsMargins(0, 0, 0, 0)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._wrap_btn = QPushButton("Wrap Up the Check-In")
        self._wrap_btn.setObjectName("primary-btn")
        self._wrap_btn.clicked.connect(self._on_wrap_up)
        fl.addWidget(self._summary)
        fl.addWidget(self._wrap_btn)
        self._finish_box.hide()
        cl.addWidget(self._finish_box)

        self._result = QLabel("")
        self._result.setWordWrap(True)
        self._result.hide()
        cl.addWidget(self._result)

        # -- sidebar --
        side = QFrame()
        side.setObjectName("tile")
        side.setFixedWidth(280)
        sl = QVBoxLayout(side)
        side_title = QLabel("THE CHECK-IN SO FAR")
        side_title.setStyleSheet("color: #9aa4b8; font-size: 11px; "
                                 "font-weight: 700; letter-spacing: 1px;")
        sl.addWidget(side_title)

        trust_row = QHBoxLayout()
        trust_lbl = QLabel("Coach trust")
        trust_lbl.setStyleSheet("color: #c7d0e0; font-size: 13px;")
        trust_row.addWidget(trust_lbl)
        self._trust_val = QLabel("—")
        self._trust_val.setStyleSheet("font-weight: 700; font-size: 14px;")
        trust_row.addWidget(self._trust_val)
        trust_row.addStretch()
        sl.addLayout(trust_row)
        self._trust_bar = QProgressBar()
        self._trust_bar.setRange(0, 100)
        self._trust_bar.setTextVisible(False)
        self._trust_bar.setFixedHeight(8)
        sl.addWidget(self._trust_bar)

        self._beats_checklist = QVBoxLayout()
        sl.addLayout(self._beats_checklist)

        note = QLabel("Leave any time — the check-in waits for you here. "
                      "Nothing here blocks the day.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6b7488; font-size: 12px; margin-top: 8px;")
        sl.addWidget(note)
        sl.addStretch()

        splitter.addWidget(convo)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self._layout.addWidget(splitter, 1)
        self._splitter.hide()

        self.refresh()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def refresh(self):
        self._state = self._load_state()
        self._busy = False
        self._render()

    def _render(self):
        s = self._state
        if not s["pending"]:
            self._empty.setText(s["message"] or
                                "No check-in is due right now.")
            self._empty.show()
            self._splitter.hide()
            return
        self._empty.hide()
        self._splitter.show()

        self._sub.setText(f"Game {s['game']} · mandate: {s['mandate']} · "
                          f"with {s['coach_name']}")
        self._trust_val.setText(str(int(s["coach_trust"])))
        self._trust_bar.setValue(int(max(0, min(100, s["coach_trust"]))))

        # transcript
        self._transcript.clear()
        coach_last = s["coach_name"].split()[-1]
        for r in s["transcript"]:
            self._append_gm(r.get("gm_line", ""))
            self._append_coach(coach_last, r.get("coach_line", ""))
            delta = r.get("delta")
            if delta:
                self._append_note(
                    f"Trust {'+' if delta >= 0 else ''}{delta}")
        sb = self._transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

        # beats checklist
        while self._beats_checklist.count():
            child = self._beats_checklist.takeAt(0).widget()
            if child is not None:
                child.deleteLater()
        self._beat_rows = {}
        deltas = {r.get("beat"): r.get("delta") for r in s["transcript"]}
        for b in BEAT_ORDER:
            done = b in s["done_beats"]
            title = _BEAT_TITLES[b]
            if done:
                d = deltas.get(b) or 0
                txt = (f"✓  {title}   "
                       f"({'+' if d >= 0 else ''}{d})")
                color = "#4CAF50"
            else:
                txt = f"○  {title}"
                color = "#6b7488"
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; "
                              f"padding: 4px 0;")
            self._beats_checklist.addWidget(lbl)
            self._beat_rows[b] = lbl

        # current beat or wrap-up
        while self._beat_layout.count():
            child = self._beat_layout.takeAt(0).widget()
            if child is not None:
                child.deleteLater()

        if s["all_done"]:
            self._beat_box.hide()
            total = sum(int(r.get("delta") or 0) for r in s["transcript"])
            self._summary.setText(
                f"All four beats covered. Net coach trust "
                f"{'+' if total >= 0 else ''}{total}.")
            self._finish_box.show()
        else:
            self._finish_box.hide()
            self._beat_box.show()
            nxt = next((b for b in BEAT_ORDER
                        if b not in s["done_beats"]), None)
            if nxt:
                self._render_beat(nxt, s["beats"][nxt])
        self._result.hide()

    def _render_beat(self, beat, spec):
        head = QLabel(spec["title"].upper())
        head.setStyleSheet("color: #c7d0e0; font-size: 13px; "
                           "font-weight: 700; letter-spacing: 1px;")
        if spec.get("mandatory"):
            head.setText(head.text() + "   •  BRING IT UP")
        self._beat_layout.addWidget(head)
        intro = QLabel(f"You open on {spec['title'].lower()}: "
                       f"{spec['intro']}")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._beat_layout.addWidget(intro)
        for opt in spec["options"]:
            btn = QPushButton(f"{opt['label']}\n{opt['line']}")
            btn.setStyleSheet("text-align: left; padding: 10px 12px;")
            btn.setProperty("beat", beat)
            btn.setProperty("framing", opt["key"])
            btn.clicked.connect(self._on_option)
            self._beat_layout.addWidget(btn)
        hint = QLabel("Pick the approach that fits the room.")
        hint.setStyleSheet("color: #6b7488; font-size: 12px;")
        self._beat_layout.addWidget(hint)

    # ------------------------------------------------------------------
    # transcript helpers
    # ------------------------------------------------------------------
    def _append_gm(self, text):
        self._transcript.append(
            f"<div style='margin:8px 0 2px 0'>"
            f"<b style='color:#7fb3ff'>You:</b> "
            f"<span style='color:#e6ebf5'>{html.escape(text or '')}</span>"
            f"</div>")

    def _append_coach(self, name, text):
        self._transcript.append(
            f"<div style='margin:2px 0 8px 0'>"
            f"<b style='color:#ffd27f'>{html.escape(name)}:</b> "
            f"<span style='color:#e6ebf5'>{html.escape(text or '')}</span>"
            f"</div>")

    def _append_note(self, text):
        self._transcript.append(
            f"<div style='color:#8a93a8;font-size:12px;margin:0 0 8px 0'>"
            f"{html.escape(text)}</div>")

    def _show_result(self, ok, text):
        self._result.setText(text or "")
        color = "#4CAF50" if ok else "#F44336"
        self._result.setStyleSheet(f"color: {color}; font-size: 13px; "
                                   f"padding: 8px; border: 1px solid {color}; "
                                   f"border-radius: 6px;")
        self._result.show()

    # ------------------------------------------------------------------
    # answer flow: option -> (QTimer) -> result -> next beat
    # ------------------------------------------------------------------
    def _on_option(self):
        if self._busy:
            return
        btn = self.sender()
        beat = str(btn.property("beat") or "")
        framing = str(btn.property("framing") or "")
        if beat not in _BEAT_DELTA_FNS:
            return
        self._busy = True
        # disable all option buttons while the coach "thinks"
        for i in range(self._beat_layout.count()):
            w = self._beat_layout.itemAt(i).widget()
            if isinstance(w, QPushButton):
                w.setEnabled(False)

        m = _ckm()
        team = self._team()
        sit = {}
        if m is not None and team is not None:
            if beat == "room":
                sit["messy"] = bool(
                    _safe(lambda: (m.room_state(team) or {}).get("messy"),
                          False))
            elif beat == "rookies":
                sit["honored"] = bool(
                    _safe(lambda: m.rookie_stance_honored(team)[0], True))
            elif beat == "tactics":
                sit["working"] = bool(
                    _safe(lambda: m.tactics_working(team)[0], True))
        gm_line = gm_line_for(beat, framing, sit)
        self._append_gm(gm_line)
        sb = self._transcript.verticalScrollBar()
        sb.setValue(sb.maximum())
        # The web polled for the queued result; native resolves it
        # directly, but the short delay keeps the conversational beat.
        QTimer.singleShot(350,
                          lambda: self._resolve_beat(beat, framing, gm_line))

    def _resolve_beat(self, beat, framing, gm_line):
        m = _ckm()
        team = self._team()
        try:
            if m is None or team is None:
                raise RuntimeError("Check-in system unavailable.")
            fn_name = _BEAT_DELTA_FNS[beat]
            fn = getattr(m, fn_name, None)
            if not callable(fn):
                raise RuntimeError(f"Unknown beat: {beat}")
            coach = self._head_coach(team, m)
            if coach is None:
                raise RuntimeError("No head coach found.")

            delta, tone, note = fn(team, coach, framing)
            try:
                cur = float(getattr(coach, "gm_trust", 70) or 70)
                coach.gm_trust = max(0.0, min(100.0, cur + delta))
            except Exception:
                pass
            trust = round(float(getattr(coach, "gm_trust", 70) or 70), 1)

            draft = self._draft(team, m)
            coach_line = checkin_line(tone, coach,
                                      seed=len(draft.get("chosen", [])))
            rec = {"beat": beat, "framing": framing, "delta": delta,
                   "tone": tone, "note": note, "gm_line": gm_line,
                   "coach_line": coach_line}
            try:
                draft["chosen"].append(rec)
                draft["deltas"][beat] = delta
                if beat not in draft["topics"]:
                    draft["topics"].append(beat)
                if note and note not in draft["notes"]:
                    draft["notes"].append(note)
                team.checkin_draft = draft
            except Exception:
                pass

            coach_last = _coach_name(coach).split()[-1]
            self._append_coach(coach_last, coach_line)
            self._append_note(f"Trust {'+' if delta >= 0 else ''}{delta}")
            sb = self._transcript.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception as exc:
            self._show_result(False, f"Could not apply the answer: {exc}")
        finally:
            self._busy = False
            # reload state (draft may have advanced) and render next beat
            self._state = self._load_state()
            self._render()

    # ------------------------------------------------------------------
    # wrap-up
    # ------------------------------------------------------------------
    def _on_wrap_up(self):
        if self._busy:
            return
        self._busy = True
        m = _ckm()
        team = self._team()
        try:
            if m is None or team is None:
                raise RuntimeError("Check-in system unavailable.")
            draft = self._draft(team, m)
            mandate = _safe(lambda: m.get_active_mandate(team), {}) or {}
            fields = {
                "season": mandate.get("season"),
                "quarter": draft.get("quarter"),
                "topics": list(draft.get("topics", [])),
                "deltas": dict(draft.get("deltas", {})),
                "notes": list(draft.get("notes", [])),
            }
            for rec in draft.get("chosen", []):
                b, f = rec.get("beat"), rec.get("framing")
                if b == "expectations":
                    fields["expectation_framing"] = f
                elif b == "room":
                    fields["room_framing"] = f
                elif b == "rookies":
                    fields["rookie_framing"] = f
                elif b == "tactics":
                    fields["tactics_framing"] = f
            entry = m.complete_checkin(team, fields, apply_trust=True,
                                       per_beat_applied=True)
            if entry is None:
                raise RuntimeError("Check-in could not be saved -- no active "
                                   "season mandate. Nothing was recorded.")
            try:
                if hasattr(team, "checkin_draft"):
                    delattr(team, "checkin_draft")
            except Exception:
                pass
            total = sum(int(v) for v in draft.get("deltas", {}).values()
                        if isinstance(v, (int, float)))
            sign = "+" if total >= 0 else ""
            self._show_result(
                True,
                f"Check-in wrapped up. Net coach trust {sign}{total}. "
                f"Recorded in the season mandate history.")
        except Exception as exc:
            self._show_result(False, str(exc))
        finally:
            self._busy = False
            self._state = self._load_state()
            self._render()
