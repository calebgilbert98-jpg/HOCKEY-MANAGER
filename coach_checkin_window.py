# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Quarterly coach check-in -- the CONVERSATION UI half.

The GM sits down with his head coach after games ~20/40/60 for a
temperature check: pace vs the preseason mandate, the room, rookie
usage vs the agreed stance, and the tactics. Personality-weighted coach
responses, small situational trust shifts.

This module owns:
  - CheckinView: a Tier-1 full-screen conversation (Eastside gating --
    non-modal; the user can leave via the menu bar and come back;
    in-progress state lives on team.checkin_draft so the conversation
    resumes where it left off). Non-blocking: nothing here gates Next Day.
  - open_coach_checkin(app): the entry point the dashboard banner wires
    its "Open Check-In" action to (lazy-import-safe signature).
  - build_coach_checkin_banner(parent, app): persistent dashboard entry
    point while a check-in is pending.

The check-in model, trigger hooks, expiry, the situational trust scale,
the mandate history and AI resolution live in the sibling module
coach_checkins.py (same-branch, same family). This file only CONSUMES
that contract, defensively: the sibling import is lazy and guarded, and
the view degrades to a no-op if the contract is absent.
"""

import random

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover - hard dependency in practice
    ctk = None

try:
    from coach_meeting_window import (_BG, _CARD, _PANEL, _TEXT, _MUTED,
                                      _BORDER, _GOLD, _font)
except Exception:  # pragma: no cover - degraded fallback palette
    _BG, _CARD, _PANEL = "#1a1d29", "#232738", "#2a3042"
    _TEXT, _MUTED = "#e8eaf0", "#9aa0b5"
    _BORDER, _GOLD = "#3a4056", "#d8a93c"

    def _font(app, size=13, weight="normal"):
        return ("Helvetica", size, weight)

__all__ = [
    "CheckinView",
    "open_coach_checkin",
    "build_coach_checkin_banner",
    "checkin_is_pending",
]


# ---------------------------------------------------------------------------
# Contract-consumption layer (sibling module: coach_checkins.py)
# ---------------------------------------------------------------------------

def _ck():
    """Lazy import of the sibling contract module; None if not landed yet."""
    try:
        import coach_checkins as _m
        return _m
    except Exception:
        return None


def checkin_is_pending(team):
    m = _ck()
    if m is not None:
        fn = getattr(m, "is_checkin_pending", None)
        if callable(fn):
            try:
                return bool(fn(team))
            except Exception:
                pass
    return bool(getattr(team, "checkin_pending", False))


def _checkin_draft(team):
    d = getattr(team, "checkin_draft", None)
    if isinstance(d, dict) and d.get("quarter") is not None:
        return d
    return {"quarter": None, "stage": "opening", "chosen": [],
            "topics": [], "deltas": {}, "notes": [], "done": False}


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
        return f"{getattr(coach, 'first_name', '')} " \
               f"{getattr(coach, 'last_name', '')}".strip() or "your head coach"
    except Exception:
        return "your head coach"


def _coach_fn(fn_name, team, coach, framing, default=(0, "flat", "")):
    m = _ck()
    if m is not None:
        fn = getattr(m, fn_name, None)
        if callable(fn):
            try:
                return fn(team, coach, framing)
            except Exception:
                pass
    return default


# ---------------------------------------------------------------------------
# Voice lines: tone-keyed coach replies.
# The model classifies each beat's situation (tone); the coach's
# personality picks the line. Two lines per tone; {name} = coach.
# ---------------------------------------------------------------------------

_COACH_LINES = {
    # --- expectation beat ---
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
    # --- room beat ---
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
    # --- rookie beat ---
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
    # --- tactics beat ---
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


def _coach_line(tone, coach, seed=None):
    pool = _COACH_LINES.get(tone) or _COACH_LINES.get("track_honest")
    rng = random.Random(seed) if seed is not None else random
    name = _coach_name(coach).split()[-1]
    return rng.choice(pool).format(name=name)


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


_STAGES = ["opening", "expectations", "room", "rookies", "tactics", "closing"]


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------

class CheckinView(ctk.CTkFrame):
    """Tier-1 full-screen quarterly check-in with the head coach.

    Non-modal by construction (shown via app.show_screen -- the menu bar
    stays live, so the user can leave and come back). In-progress state is
    kept on team.checkin_draft, including the full transcript, so a return
    visit replays the conversation exactly. The check-in NEVER gates Next
    Day -- it is a RESUMABLE pending item.
    """

    def __init__(self, parent, team=None, app=None):
        super().__init__(parent)
        if ctk is None:  # pragma: no cover
            raise RuntimeError("customtkinter is required")
        self.app = app if app is not None else parent
        self.team = team if team is not None else getattr(self.app, "user_team", None)
        self._close_screen = None  # set by show_screen()
        self._rng = random.Random()
        self._coach = None
        self._mandate = {}
        self._beat_rows = []   # side-panel beat summary rows
        self._trust_value = None
        self._beat_inputs = {}  # situational inputs, computed once
        self._build()

    # -- setup -----------------------------------------------------------
    def _load_context(self):
        m = _ck()
        team = self.team
        if m is not None:
            try:
                self._coach = m.get_head_coach(team) if hasattr(m, "get_head_coach") else None
            except Exception:
                self._coach = None
            try:
                self._mandate = m.get_active_mandate(team) if hasattr(m, "get_active_mandate") else {}
            except Exception:
                self._mandate = {}
        self._mandate = self._mandate or {}
        if self._coach is None:
            try:
                self._coach = getattr(team, "staff", [None])[0]
            except Exception:
                pass
        try:
            self._beat_inputs["pace_band"] = m.pace_band(team) if m else ("track", 0.5, 0.55, 0.0)
        except Exception:
            self._beat_inputs["pace_band"] = ("track", 0.5, 0.55, 0.0)
        try:
            self._beat_inputs["room"] = m.room_state(team) if m else {"messy": False}
        except Exception:
            self._beat_inputs["room"] = {"messy": False}
        try:
            self._beat_inputs["rookies"] = m.rookie_stance_honored(team) if m else (True, 0.0, "none")
        except Exception:
            self._beat_inputs["rookies"] = (True, 0.0, "none")
        try:
            self._beat_inputs["tactics"] = m.tactics_working(team) if m else (True, 0.5, 0.55)
        except Exception:
            self._beat_inputs["tactics"] = (True, 0.5, 0.55)

    def _draft(self):
        team = self.team
        d = getattr(team, "checkin_draft", None)
        m = _ck()
        try:
            pending_q = m.get_pending_quarter(team) if m else None
        except Exception:
            pending_q = None
        if not isinstance(d, dict) or d.get("quarter") != pending_q:
            try:
                gp = m.team_games_played(team) if m else 0
            except Exception:
                gp = 0
            d = {"quarter": pending_q, "game": gp, "stage": "opening",
                 "chosen": [], "topics": [], "deltas": {}, "notes": [],
                 "done": False, "seed": self._rng.randrange(1 << 30)}
            try:
                team.checkin_draft = d
            except Exception:
                pass
        return d

    # -- layout ----------------------------------------------------------
    def _build(self):
        self._load_context()
        self.configure(fg_color=_BG)
        outer = ctk.CTkFrame(self, fg_color=_BG)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure(0, weight=3)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        main = ctk.CTkFrame(outer, fg_color=_BG)
        main.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=24)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        m = _ck()
        try:
            q = m.get_pending_quarter(self.team) if m else None
            qlabel = m.quarter_label(q) if m else "Quarterly"
        except Exception:
            qlabel = "Quarterly"
        cname = _coach_name(self._coach)
        try:
            gp = m.team_games_played(self.team) if m else 0
        except Exception:
            gp = 0
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="w", pady=(0, 4))
        _ci_lbl = ctk.CTkLabel(header, text=f"{qlabel} Check-In -- {cname}",
                     font=_font(self.app, 20, "bold"),
                     text_color=_TEXT, anchor="w")
        _ci_lbl.pack(anchor="w")
        # EHM/FM24: right-click the coach name -> staff menu.
        try:
            from player_context_menu import bind_staff_context
            if self._coach is not None:
                bind_staff_context(_ci_lbl, self._coach, self)
        except Exception:
            pass
        ctk.CTkLabel(
            header,
            text=(f"Game {gp} -- a temperature check on the season mandate. "
                  "Nothing here blocks the day; take your time."),
            font=_font(self.app, 12), text_color=_MUTED,
            anchor="w").pack(anchor="w", pady=(2, 0))

        self._body = ctk.CTkScrollableFrame(main, fg_color=_CARD,
                                            border_color=_BORDER,
                                            border_width=1)
        self._body.grid(row=2, column=0, sticky="nsew", pady=(8, 12))

        side = ctk.CTkFrame(outer, fg_color=_PANEL, border_color=_BORDER,
                            border_width=1)
        side.grid(row=0, column=1, sticky="nsew", padx=(12, 24), pady=24)
        ctk.CTkLabel(side, text="The check-in so far",
                     font=_font(self.app, 14, "bold"),
                     text_color=_TEXT).pack(anchor="w", padx=16, pady=(16, 8))
        self._side_list = ctk.CTkFrame(side, fg_color="transparent")
        self._side_list.pack(fill="x", padx=16)
        trust = 0.0
        try:
            trust = float(getattr(self._coach, "gm_trust", 70) or 70)
        except Exception:
            pass
        self._trust_value = ctk.CTkLabel(
            side, text=f"Coach trust: {trust:.0f}",
            font=_font(self.app, 13, "bold"), text_color=_GOLD)
        self._trust_value.pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            side, text="Small shifts, honestly earned.",
            font=_font(self.app, 11), text_color=_MUTED,
            wraplength=200, justify="left").pack(anchor="w", padx=16)
        ctk.CTkButton(side, text="Back to Front Office",
                      fg_color="transparent", border_color=_BORDER,
                      border_width=1, text_color=_TEXT,
                      command=self._goto_dashboard).pack(
                          fill="x", padx=16, pady=(16, 8))
        note = ctk.CTkLabel(
            side, text="Leave any time -- the check-in waits for you here.",
            font=_font(self.app, 11), text_color=_MUTED,
            wraplength=200, justify="left")
        note.pack(anchor="w", padx=16, pady=(0, 16))

        self._render_stage()

    # -- transcript ------------------------------------------------------
    def _say(self, who, text):
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(10, 2))
        color = _GOLD if who == "gm" else _TEXT
        label = "You" if who == "gm" else _coach_name(self._coach).split()[-1]
        ctk.CTkLabel(row, text=label, font=_font(self.app, 11, "bold"),
                     text_color=color, anchor="w").pack(anchor="w")
        ctk.CTkLabel(row, text=text, font=_font(self.app, 13),
                     text_color=_TEXT, wraplength=640,
                     justify="left", anchor="w").pack(anchor="w")
        try:
            self._body._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _note(self, text):
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(10, 2))
        ctk.CTkLabel(row, text=text, font=_font(self.app, 12, "italic"),
                     text_color=_MUTED, wraplength=640,
                     justify="left", anchor="w").pack(anchor="w")

    # -- side panel ------------------------------------------------------
    def _side_add(self, beat_label, framing_label, delta):
        try:
            sign = "+" if delta >= 0 else ""
            color = "#8fd694" if delta >= 0 else "#e0705f" if delta < 0 else _MUTED
            row = ctk.CTkFrame(self._side_list, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=beat_label,
                         font=_font(self.app, 12, "bold"),
                         text_color=_TEXT, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=f"{framing_label}  ({sign}{delta})",
                         font=_font(self.app, 11),
                         text_color=color, anchor="w").pack(anchor="w")
            self._beat_rows.append(row)
        except Exception:
            pass

    def _set_trust(self):
        try:
            trust = float(getattr(self._coach, "gm_trust", 70) or 70)
            self._trust_value.configure(text=f"Coach trust: {trust:.0f}")
        except Exception:
            pass

    # -- stages ----------------------------------------------------------
    def _render_stage(self):
        draft = self._draft()
        if draft.get("done"):
            self._render_done()
            return
        stage = draft.get("stage", "opening")
        # replay transcript for resumed drafts
        if draft.get("chosen"):
            self._replay(draft)
        else:
            self._clear_body()
        fn = getattr(self, f"_stage_{stage}", None)
        if callable(fn):
            fn(draft)
        else:
            self._stage_closing(draft)

    def _clear_body(self):
        try:
            for w in self._body.winfo_children():
                w.destroy()
        except Exception:
            pass

    def _replay(self, draft):
        self._clear_body()
        for rec in draft.get("chosen", []):
            try:
                self._say("gm", rec.get("gm_line", ""))
                self._say("coach", rec.get("coach_line", ""))
            except Exception:
                continue

    def _stage_opening(self, draft):
        m = _ck()
        band, actual, expected, _g = self._beat_inputs["pace_band"]
        exp_label = str((self._mandate or {}).get("expectation", "playoffs"))
        m2 = _ck()
        last = None
        try:
            last = m2.last_checkin(self.team) if m2 else None
        except Exception:
            pass
        q = draft.get("quarter")
        try:
            qlabel = m.quarter_label(q) if m else "Quarterly"
        except Exception:
            qlabel = "Quarterly"
        opener = (f"{qlabel} check-in, game {draft.get('game', 0)}. "
                  f"The mandate we set was {exp_label} -- pace {actual:.3f} "
                  f"against an expected {expected:.3f}. Let's talk about "
                  "how the season's actually going.")
        self._say("gm", opener)
        if last:
            topics = ", ".join(last.get("topics", []) or [])
            ref = (f"Last time we talked through {topics or 'the season'}. "
                   f"{(last.get('notes') or [''])[0]}")
            self._say("coach", ref.strip())
        else:
            self._say("coach", "First one of these. Alright -- where do you want to start?")
        self._option_row([("Start the check-in", self._advance)], single=True)

    def _option_row(self, options, single=False):
        box = ctk.CTkFrame(self._body, fg_color="transparent")
        box.pack(fill="x", padx=16, pady=(14, 16))
        for label, cmd in options:
            ctk.CTkButton(box, text=label, command=cmd,
                          fg_color=_PANEL, hover_color="#343b52",
                          border_color=_BORDER, border_width=1,
                          text_color=_TEXT,
                          font=_font(self.app, 13),
                          anchor="w").pack(fill="x", pady=4)
        if not single:
            ctk.CTkLabel(box, text="Pick the approach that fits the room.",
                         font=_font(self.app, 11),
                         text_color=_MUTED).pack(anchor="w", pady=(4, 0))

    def _advance(self):
        draft = self._draft()
        order = ["opening", "expectations", "room", "rookies", "tactics", "closing"]
        try:
            nxt = order[order.index(draft.get("stage", "opening")) + 1]
        except (ValueError, IndexError):
            nxt = "closing"
        draft["stage"] = nxt
        try:
            self.team.checkin_draft = draft
        except Exception:
            pass
        self._render_stage()

    # -- beat helpers ----------------------------------------------------
    def _beat_intro(self, draft, title, intro):
        self._say("gm", f"{title} -- {intro}")

    def _apply_beat(self, beat, framing, gm_line, fn_name, topics_add=()):
        draft = self._draft()
        delta, tone, note = _coach_fn(fn_name, self.team, self._coach,
                                     framing)
        try:
            cur = float(getattr(self._coach, "gm_trust", 70) or 70)
            self._coach.gm_trust = max(0.0, min(100.0, cur + delta))
        except Exception:
            pass
        coach_line = _coach_line(tone, self._coach,
                                seed=(draft.get("seed") or 0) + len(draft.get("chosen", [])))
        self._say("gm", gm_line)
        self._say("coach", coach_line)
        rec = {"beat": beat, "framing": framing, "delta": delta,
               "tone": tone, "note": note, "gm_line": gm_line,
               "coach_line": coach_line}
        draft["chosen"].append(rec)
        draft["deltas"][beat] = delta
        for t in topics_add:
            if t not in draft["topics"]:
                draft["topics"].append(t)
        if note and note not in draft["notes"]:
            draft["notes"].append(note)
        try:
            self.team.checkin_draft = draft
        except Exception:
            pass
        label = {"expectations": "Pace vs mandate", "room": "The room",
                 "rookies": "Rookie usage", "tactics": "Tactics"}.get(beat, beat)
        fname = {"credit": "Shared credit", "honest": "Honest accounting",
                 "demand": "Demanded answers", "support": "Offered support",
                 "direct": "Direct", "praise": "Praised the room",
                 "skip": "Skipped", "accept": "Accepted his read",
                 "press": "Pressed him", "stay": "Stay the course",
                 "tweak": "Asked for tweaks",
                 "overhaul": "Demanded overhaul"}.get(framing, framing)
        self._side_add(label, fname, delta)
        self._set_trust()
        self._advance()

    def _stage_expectations(self, draft):
        band, actual, expected, _g = self._beat_inputs["pace_band"]
        band_word = {"ahead": "ahead of", "track": "tracking",
                     "behind": "behind", "far": "well behind"}[band]
        self._beat_intro(draft, "Pace vs the mandate",
                         f"we're {band_word} it -- {actual:.3f} against "
                         f"{expected:.3f} expected.")
        self._option_row([(label, lambda f=f, gl=gl: self._apply_beat(
            "expectations", f, gl, "checkin_expectation_delta",
            topics_add=("expectations",)))
            for f, label, gl in _BEAT_FRAMINGS["expectations"]])

    def _stage_room(self, draft):
        st = self._beat_inputs["room"]
        messy = bool(st.get("messy"))
        label = st.get("atmosphere_label", "Steady")
        if messy:
            self._beat_intro(
                draft, "The room",
                f"it's a mess in there -- {label}, morale "
                f"{st.get('avg_morale', 0):.0f}. You can't not bring it up.")
            self._note("The room is struggling -- this beat isn't optional.")
            key = "room_messy"
        else:
            self._beat_intro(draft, "The room",
                             f"it's in decent shape -- {label}.")
            key = "room_healthy"
        self._option_row([(label, lambda f=f, gl=gl: self._apply_beat(
            "room", f, gl, "checkin_room_delta", topics_add=("room",)))
            for f, label, gl in _BEAT_FRAMINGS[key]])

    def _stage_rookies(self, draft):
        honored, share, stance = self._beat_inputs["rookies"]
        stance_word = {"heavy": "heavy rookie minutes", "earned": "earned ice time",
                       "sheltered": "sheltered minutes",
                       "none": "an AHL year for the kids"}.get(stance, stance)
        if honored:
            self._beat_intro(draft, "Rookie usage",
                             f"the plan was {stance_word}, and the kids are "
                             f"getting their share ({share:.0%}).")
            key = "rookies_honored"
        else:
            self._beat_intro(draft, "Rookie usage",
                             f"the plan was {stance_word}, but the kids' "
                             f"share is only {share:.0%}.")
            key = "rookies_not_honored"
        self._option_row([(label, lambda f=f, gl=gl: self._apply_beat(
            "rookies", f, gl, "checkin_rookie_delta", topics_add=("rookies",)))
            for f, label, gl in _BEAT_FRAMINGS[key]])

    def _stage_tactics(self, draft):
        working, actual, expected = self._beat_inputs["tactics"]
        if working:
            self._beat_intro(draft, "Tactics",
                             f"the approach is delivering -- pace {actual:.3f} "
                             f"against {expected:.3f} expected.")
            key = "tactics_working"
        else:
            self._beat_intro(draft, "Tactics",
                             f"the approach isn't delivering -- pace "
                             f"{actual:.3f} against {expected:.3f} expected.")
            key = "tactics_not_working"
        self._option_row([(label, lambda f=f, gl=gl: self._apply_beat(
            "tactics", f, gl, "checkin_tactics_delta",
            topics_add=("tactics",)))
            for f, label, gl in _BEAT_FRAMINGS[key]])

    def _stage_closing(self, draft):
        deltas = draft.get("deltas", {})
        total = sum(deltas.values())
        sign = "+" if total >= 0 else ""
        parts = ", ".join(f"{b} ({d:+d})" for b, d in deltas.items()) or "no beats held"
        self._say("coach", "Anything else, or are we good?")
        self._note(f"Check-in summary: {parts}. Net trust {sign}{total}.")
        self._say("gm", "We're good. Keep me posted -- we'll do this again next quarter.")
        box = ctk.CTkFrame(self._body, fg_color="transparent")
        box.pack(fill="x", padx=16, pady=(14, 16))
        ctk.CTkButton(box, text="Wrap up the check-in",
                      command=self._finish,
                      fg_color=_GOLD, hover_color="#f0c75e",
                      text_color="#1a1d29", height=40,
                      font=_font(self.app, 14, "bold")).pack(fill="x", pady=4)
        # the closing button sits at the very bottom of the transcript --
        # make sure the scroll region includes it fully
        try:
            self.update_idletasks()
            self._body._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _finish(self):
        draft = self._draft()
        m = _ck()
        fields = {
            "season": (self._mandate or {}).get("season"),
            "quarter": draft.get("quarter"),
            "topics": list(draft.get("topics", [])),
            "deltas": dict(draft.get("deltas", {})),
            "notes": list(draft.get("notes", [])),
        }
        # mirror the AI framings the conversation actually used
        for rec in draft.get("chosen", []):
            beat, framing = rec.get("beat"), rec.get("framing")
            if beat == "expectations":
                fields["expectation_framing"] = framing
            elif beat == "room":
                fields["room_framing"] = framing
            elif beat == "rookies":
                fields["rookie_framing"] = framing
            elif beat == "tactics":
                fields["tactics_framing"] = framing
        try:
            if m is not None and hasattr(m, "complete_checkin"):
                m.complete_checkin(self.team, fields, apply_trust=True,
                                   per_beat_applied=True)
        except Exception as e:
            # Honest failure: trust deltas were NOT persisted. Keep the
            # draft (nothing silently lost), say so inline, and re-present
            # the wrap-up so the user can retry.
            self._note(f"Check-in could not be saved ({e}). Trust changes "
                       f"were NOT recorded -- wrap up again to retry.")
            self._say("coach", "Something went wrong on our end -- the "
                               "check-in didn't save. Let's try wrapping up "
                               "once more.")
            box = ctk.CTkFrame(self._body, fg_color="transparent")
            box.pack(fill="x", padx=16, pady=(14, 16))
            ctk.CTkButton(box, text="Wrap up the check-in",
                          command=self._finish,
                          fg_color=_GOLD, hover_color="#f0c75e",
                          text_color="#1a1d29", height=40,
                          font=_font(self.app, 14, "bold")).pack(fill="x",
                                                                pady=4)
            return
        try:
            if hasattr(self.team, "checkin_draft"):
                delattr(self.team, "checkin_draft")
        except Exception:
            pass
        # refresh the dashboard banner if it is showing
        try:
            refresh = getattr(self.app, "refresh_dashboard", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass
        self._render_done()

    def _render_done(self):
        self._clear_body()
        self._say("coach", "Appreciate the check-in. See you next quarter.")
        box = ctk.CTkFrame(self._body, fg_color="transparent")
        box.pack(fill="x", padx=16, pady=(14, 16))
        ctk.CTkButton(box, text="Back to Front Office",
                      command=self._goto_dashboard,
                      fg_color=_PANEL, hover_color="#343b52",
                      border_color=_BORDER, border_width=1,
                      text_color=_TEXT,
                      font=_font(self.app, 13)).pack(fill="x", pady=4)

    def _goto_dashboard(self):
        try:
            nav = getattr(self.app, "navigate", None)
            if callable(nav):
                nav("dashboard")
                return
        except Exception:
            pass
        try:
            if callable(self._close_screen):
                self._close_screen()
        except Exception:
            pass

    # -- test hook -------------------------------------------------------
    def debug_choose(self, framing):
        """QA hook: choose the framing for the current beat stage."""
        draft = self._draft()
        stage = draft.get("stage")
        mapping = {
            "expectations": ("expectations", "checkin_expectation_delta", ("expectations",)),
            "room": ("room", "checkin_room_delta", ("room",)),
            "rookies": ("rookies", "checkin_rookie_delta", ("rookies",)),
            "tactics": ("tactics", "checkin_tactics_delta", ("tactics",)),
        }
        if stage == "opening":
            self._advance()
            return True
        if stage == "closing":
            self._finish()
            return True
        spec = mapping.get(stage)
        if spec is None:
            return False
        beat, fn, topics = spec
        pool = _BEAT_FRAMINGS.get({
            "expectations": "expectations",
            "room": "room_messy", "rookies": "rookies_not_honored",
            "tactics": "tactics_not_working"}[stage], [])
        gm_line = next((gl for f, _l, gl in pool if f == framing), framing)
        self._apply_beat(beat, framing, gm_line, fn, topics_add=topics)
        return True


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def open_coach_checkin(app):
    """Open the quarterly check-in (lazy-import-safe).

    The dashboard banner wires its "Open Check-In" action here.
    """
    team = getattr(app, "user_team", None)
    if team is None:
        return None
    show = getattr(app, "show_screen", None)
    if callable(show):
        try:
            return show("coach_checkin", "Coach Check-In",
                        CheckinView, team)
        except Exception:
            pass
    # Fallback: standalone window if the app has no show_screen.
    try:
        top = ctk.CTkToplevel(app)
        top.title("Coach Check-In")
        top.geometry("1280x860")
        view = CheckinView(top, team=team, app=app)
        view.pack(fill="both", expand=True)
        view._close_screen = top.destroy
        return view
    except Exception:
        return None


def build_coach_checkin_banner(parent, app):
    """Persistent dashboard entry point while a check-in is pending.

    Non-blocking by design: the copy says the day advances normally.
    Returns a banner widget, or None when there is nothing pending.
    dashboard_home calls this (guarded) on every dashboard build.
    """
    try:
        import tkinter as tk
    except Exception:
        return None
    try:
        team = getattr(app, "user_team", None)
        if team is None or not checkin_is_pending(team):
            return None
        m = _ck()
        coach = None
        cname = "your head coach"
        qlabel = "Quarterly"
        gp = 0
        if m is not None:
            try:
                coach = m.get_head_coach(team) if hasattr(m, "get_head_coach") else None
                cname = _coach_name(coach)
                qlabel = m.quarter_label(m.get_pending_quarter(team))
                gp = m.team_games_played(team)
            except Exception:
                pass
        frame = tk.Frame(parent, bg="#24303d",
                         highlightbackground="#7fb3d5", highlightthickness=1)
        inner = tk.Frame(frame, bg="#24303d")
        inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text=f"{qlabel.upper()} CHECK-IN",
                 font=("Segoe UI", 11, "bold"),
                 fg="#a8d0f0", bg="#24303d").pack(side="left")
        tk.Label(inner,
                 text=(f"{cname} is due a check-in after game {gp}. "
                       "The day advances normally -- this one's on your time."),
                 font=("Segoe UI", 11), fg="#e8eaf0",
                 bg="#24303d", wraplength=700,
                 justify="left").pack(side="left", padx=(12, 0))
        tk.Button(inner, text="Open Check-In",
                  font=("Segoe UI", 11, "bold"),
                  fg="#1a1d29", bg="#7fb3d5", activebackground="#a8d0f0",
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=lambda: open_coach_checkin(app)).pack(side="right")
        return frame
    except Exception:
        return None
