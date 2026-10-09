"""Full-page press conference experience (CustomTkinter).

Replaces the small PressConferenceDialog popup with a broadcast-style
press room: backdrop wall, journalist dais, podium, camera flashes and a
scrolling ticker. Used right before and right after user-team games.

API mirrors PressConferenceDialog:
    page = PressConferencePage(parent, questions, title=..., context={...})
    page.chosen  # list of chosen answer dicts (same shape as before)

Modal: grab_set + wait_window, so the sim flow stays sequential.
"""
import random
import tkinter as tk

import customtkinter as ctk

from ctk_theme import (
    init_ctk_theme, primary_button, heading, body,
    TEAL, BG, PANEL, CARD, BORDER,
    TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
)

TONE_COLORS = {
    "confident": GOLD,
    "respectful": GREEN,
    "calm": BLUE,
    "honest": TEAL,
    "defensive": "#8b8b94",
}

TONE_LABELS = {
    "confident": "Confident",
    "respectful": "Respectful",
    "calm": "Composed",
    "honest": "Honest",
    "defensive": "Guarded",
}

# Journalist personalities (2026-10-04): each reporter has a style that
# shapes their questions and reactions. Makes the room feel alive.
JOURNALIST_STYLES = {
    "hostile": {
        "label": "The Shark",
        "color": "#ff4444",
        "desc": "Smells blood. Presses hard on deflections.",
    },
    "friendly": {
        "label": "The Ally",
        "color": "#44ff44",
        "desc": "On your side. Softballs and praise.",
    },
    "analyst": {
        "label": "The Nerd",
        "color": "#4444ff",
        "desc": "Stats and systems. Wants substance.",
    },
    "tabloid": {
        "label": "The Vulture",
        "color": "#ffaa00",
        "desc": "Hunts controversy and drama.",
    },
}

# Follow-up questions when a hostile/tabloid journalist gets a
# defensive (dodging) answer. They don't let it go.
FOLLOW_UPS = [
    "That's not really an answer, coach. Let me ask again: ",
    "With respect, you're dodging the question. ",
    "The fans deserve a straight answer here. ",
]


class PressConferencePage(ctk.CTkToplevel):
    """Modal full-page press conference. Result: list of chosen answer dicts."""

    W, H = 1080, 760

    def __init__(self, parent, questions, title="Press Conference", context=None):
        init_ctk_theme()
        super().__init__(parent)
        self.questions = list(questions or [])
        self.chosen = []
        self.context = context or {}
        self.title(title)
        self.geometry(f"{self.W}x{self.H}")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.q_index = 0
        self.mood = 0  # media mood: -N..+N from fan/board effects
        self._flash_jobs = []
        self._ticker_job = None
        # Narrative arcs (2026-10-04): track answer patterns to build
        # storylines. defensive_count high = "coach on hot seat".
        self._tone_counts = {}
        self._narrative = None
        # Assign personalities to journalists (stable per conference)
        self._j_styles = {}
        _styles = list(JOURNALIST_STYLES.keys())
        for _i, _q in enumerate(self.questions):
            _jn = _q.get("journalist", "Press")
            if _jn not in self._j_styles:
                # Deterministic but varied: hash the name
                _h = sum(ord(c) for c in _jn) % len(_styles)
                self._j_styles[_jn] = _styles[(_h + _i) % len(_styles)]
        self._pending_followup = None

        self._build()
        self._show_question()
        self._start_ticker()
        # Center on parent
        try:
            self.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() - self.W) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.H) // 2
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass
        self.wait_window(self)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build(self):
        ctx = self.context

        # ---- Broadcast header ----
        header = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        header.pack(fill="x")
        live_dot = ctk.CTkLabel(header, text="●", text_color=RED,
                                font=("Segoe UI", 14))
        live_dot.pack(side="left", padx=(16, 4), pady=10)
        heading(header, ctx.get("banner_title", "PRESS CONFERENCE"),
                size=16).pack(side="left", pady=10)
        sub = ctx.get("banner_sub", "")
        if sub:
            body(header, sub, dim=True, size=12).pack(side="left", padx=(12, 0))
        date_str = ctx.get("date_str", "")
        if date_str:
            body(header, date_str, dim=True, size=12).pack(side="right", padx=16)

        # ---- Backdrop wall (canvas with repeating pattern) ----
        self.wall = tk.Canvas(self, height=104, highlightthickness=0, bg="#101014")
        self.wall.pack(fill="x", padx=0)
        self._draw_wall(ctx)
        self.bind("<Configure>", lambda e: None)

        # ---- Journalist dais ----
        dais_label = body(self, "ON THE DAIS", size=10, dim=True)
        dais_label.pack(anchor="w", padx=16, pady=(8, 2))
        self.dais = ctk.CTkFrame(self, fg_color="transparent")
        self.dais.pack(fill="x", padx=12)
        self._j_cards = []
        journalists = []
        for q in self.questions:
            j = q.get("journalist", "Press")
            if j not in journalists:
                journalists.append(j)
        for j in journalists:
            self._j_cards.append(self._journalist_card(self.dais, j))

        # ---- Main stage: question + answers ----
        self.stage = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        self.stage.pack(fill="both", expand=True, padx=16, pady=(10, 6))

        # progress row
        prog_row = ctk.CTkFrame(self.stage, fg_color="transparent")
        prog_row.pack(fill="x", padx=18, pady=(12, 0))
        self.prog_label = body(prog_row, "", size=11, dim=True)
        self.prog_label.pack(side="left")
        self.mood_label = body(prog_row, "Media mood: Neutral", size=11, dim=True)
        self.mood_label.pack(side="right")
        self.mood_bar = ctk.CTkProgressBar(prog_row, width=140, height=8,
                                           progress_color=TEAL, fg_color=BORDER)
        self.mood_bar.pack(side="right", padx=(0, 8))
        self.mood_bar.set(0.5)

        self.q_text = ctk.CTkLabel(self.stage, text="", wraplength=940,
                                   font=("Segoe UI", 15, "bold"), text_color=TEXT,
                                   anchor="w", justify="left")
        self.q_text.pack(fill="x", padx=22, pady=(10, 2))
        self.q_by = body(self.stage, "", size=12, dim=True)
        self.q_by.pack(anchor="w", padx=22, pady=(0, 8))

        self.ans_frame = ctk.CTkFrame(self.stage, fg_color="transparent")
        self.ans_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        # ---- Bottom ticker ----
        ticker_frame = ctk.CTkFrame(self, fg_color="#0a0a0d", corner_radius=0,
                                    height=30)
        ticker_frame.pack(fill="x", side="bottom")
        ticker_frame.pack_propagate(False)
        ctk.CTkLabel(ticker_frame, text="WIRE", font=("Segoe UI", 10, "bold"),
                     text_color=BG, fg_color=TEAL, corner_radius=4,
                     width=52).pack(side="left", padx=8, pady=4)
        self.ticker_text = ctk.CTkLabel(ticker_frame, text="", anchor="w",
                                        font=("Segoe UI", 11), text_color=TEXT_DIM)
        self.ticker_text.pack(side="left", fill="x", expand=True, padx=8)
        self._ticker_items = ctx.get("ticker", [])
        self._ticker_pos = 0

        # ---- Podium footer ----
        podium = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        podium.pack(fill="x", side="bottom")
        body(podium, ctx.get("podium_name", "Head Coach"),
             size=12, dim=False).pack(side="left", padx=16, pady=8)
        body(podium, ctx.get("podium_sub", "at the podium"),
             size=11, dim=True).pack(side="left", padx=(4, 0))

    def _draw_wall(self, ctx):
        """Repeating backdrop pattern like a real presser wall."""
        c = self.wall
        c.delete("all")
        w = self.W
        h = 104
        # subtle vertical gradient bands
        for i in range(0, w, 4):
            shade = 14 + int(4 * (i / w))
            c.create_line(i, 0, i, h, fill=f"#{shade:02x}{shade:02x}{shade+4:02x}")
        # repeating logo-ish pattern
        abbr = ctx.get("team_abbr", "PD")
        for x in range(40, w, 150):
            c.create_text(x, h // 2, text=abbr, font=("Segoe UI", 20, "bold"),
                          fill="#23232e")
        # center emblem
        c.create_oval(w / 2 - 28, h / 2 - 28, w / 2 + 28, h / 2 + 28,
                      outline="#2e2e38", width=2)
        c.create_text(w / 2, h / 2, text=abbr, font=("Segoe UI", 18, "bold"),
                      fill="#3a3a46")

    def _journalist_card(self, parent, name):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                            border_width=2, border_color=BORDER,
                            width=200, height=118)
        card.pack(side="left", padx=6, pady=2)
        card.pack_propagate(False)
        # initials avatar
        parts = name.replace("(", " ").replace(")", " ").split()
        initials = "".join(p[0] for p in parts[:2]).upper()
        outlet = ""
        if "(" in name and ")" in name:
            outlet = name[name.index("(") + 1:name.index(")")]
            disp_name = name[:name.index("(")].strip()
        else:
            disp_name = name
        av = ctk.CTkLabel(card, text=initials, font=("Segoe UI", 13, "bold"),
                          text_color=BG, fg_color=TEXT_FAINT, corner_radius=18,
                          width=36, height=36)
        av.pack(pady=(8, 2))
        ctk.CTkLabel(card, text=disp_name, font=("Segoe UI", 11, "bold"),
                     text_color=TEXT).pack()
        ctk.CTkLabel(card, text=outlet, font=("Segoe UI", 10),
                     text_color=TEXT_DIM).pack()
        # Personality badge (2026-10-04)
        _style_key = self._j_styles.get(name, "analyst")
        _style = JOURNALIST_STYLES[_style_key]
        ctk.CTkLabel(card, text=_style["label"],
                     font=("Segoe UI", 9, "italic"),
                     text_color=_style["color"]).pack(pady=(0, 8))
        card._avatar = av
        card._name = name
        card._style = _style_key
        return card

    def _highlight_journalist(self, name):
        for card in self._j_cards:
            active = (card._name == name)
            card.configure(border_color=TEAL if active else BORDER)
            card._avatar.configure(fg_color=TEAL if active else TEXT_FAINT)

    # ------------------------------------------------------------------
    # Question flow
    # ------------------------------------------------------------------
    def _show_question(self):
        for w in self.ans_frame.winfo_children():
            w.destroy()
        if self.q_index >= len(self.questions):
            self._show_summary()
            return
        q = self.questions[self.q_index]
        total = len(self.questions)
        self.prog_label.configure(
            text=f"Question {self.q_index + 1} of {total}")
        self._highlight_journalist(q.get("journalist", ""))
        self.q_by.configure(text=f"\u2014 {q.get('journalist', 'Press')}")
        self.q_text.configure(text=f"\u201c{q.get('question', '')}\u201d")
        for ans in q.get("answers", []):
            self._answer_button(ans)

    def _answer_button(self, ans):
        tone = ans.get("tone", "calm")
        color = TONE_COLORS.get(tone, TEAL)
        row = ctk.CTkFrame(self.ans_frame, fg_color="transparent")
        row.pack(fill="x", pady=5, padx=6)
        pill = ctk.CTkLabel(row, text=TONE_LABELS.get(tone, tone.title()),
                            font=("Segoe UI", 10, "bold"), text_color=BG,
                            fg_color=color, corner_radius=10, width=86)
        pill.pack(side="left", padx=(4, 10))
        btn = ctk.CTkButton(row, text=ans.get("label", ""), anchor="w",
                            font=("Segoe UI", 12), fg_color=PANEL,
                            hover_color=BORDER, text_color=TEXT,
                            corner_radius=8, height=44,
                            command=lambda a=ans: self._answer(a))
        btn.pack(side="left", fill="x", expand=True)

    def _answer(self, ans):
        self.chosen.append(ans)
        # Track tone for narrative arcs
        _tone = ans.get("tone", "calm")
        self._tone_counts[_tone] = self._tone_counts.get(_tone, 0) + 1
        self._update_narrative()
        # mood shift from fan + board effects
        delta = (ans.get("fan_effect", 0) or 0) + (ans.get("board_effect", 0) or 0)
        # Hostile/tabloid journalists react more strongly to dodges
        _q = self.questions[self.q_index] if self.q_index < len(self.questions) else {}
        _jn = _q.get("journalist", "")
        _js = self._j_styles.get(_jn, "analyst")
        if _tone == "defensive" and _js in ("hostile", "tabloid"):
            delta -= 1  # extra mood hit for dodging a shark
        elif _tone == "honest" and _js == "friendly":
            delta += 1  # allies reward candor
        self.mood += delta
        self._update_mood()
        # Follow-up: hostile/tabloid journalists press on defensive answers
        if (_tone == "defensive" and _js in ("hostile", "tabloid")
                and self._pending_followup is None):
            import random as _r
            _fu_text = _r.choice(FOLLOW_UPS)
            _orig_q = _q.get("question", "")
            self._pending_followup = {
                "journalist": _jn,
                "question": _fu_text + _orig_q,
                "answers": _q.get("answers", []),
                "is_followup": True,
            }
        self._camera_flashes()
        # clear the answer buttons; show the reaction in their place
        for w in self.ans_frame.winfo_children():
            w.destroy()
        tone = ans.get("tone", "calm")
        color = TONE_COLORS.get(tone, TEAL)
        you_row = ctk.CTkFrame(self.ans_frame, fg_color="transparent")
        you_row.pack(fill="x", pady=(4, 2), padx=6)
        body(you_row, "YOU SAID:", size=10, dim=True).pack(side="left", padx=(4, 10))
        ctk.CTkLabel(you_row, text=TONE_LABELS.get(tone, tone.title()),
                     font=("Segoe UI", 10, "bold"), text_color=BG,
                     fg_color=color, corner_radius=10, width=86).pack(side="left")
        ctk.CTkLabel(self.ans_frame, text=f"\u201c{ans.get('label', '')}\u201d",
                     font=("Segoe UI", 13, "italic"), text_color=TEXT,
                     anchor="w", wraplength=900, justify="left").pack(
                         fill="x", padx=10, pady=(0, 6))
        body(self.ans_frame, "MEDIA REACTION", size=10, dim=True).pack(
            anchor="w", padx=10)
        ctk.CTkLabel(self.ans_frame, text=ans.get("reaction", ""),
                     wraplength=900, font=("Segoe UI", 12),
                     text_color=TEXT_DIM, anchor="w",
                     justify="left").pack(fill="x", padx=10, pady=(2, 4))
        eff_bits = []
        me, be = ans.get("morale_effect", 0), ans.get("board_effect", 0)
        if me:
            eff_bits.append(f"Dressing room {'+' if me > 0 else ''}{me}")
        if be:
            eff_bits.append(f"Board {'+' if be > 0 else ''}{be}")
        body(self.ans_frame,
             "  ".join(eff_bits) if eff_bits else "No measurable fallout.",
             size=11, dim=not eff_bits).pack(anchor="w", padx=10, pady=(0, 6))
        # next button
        nxt = self.q_index + 1 >= len(self.questions)
        primary_button(self.ans_frame,
                       text="See how it played  \u2192" if nxt else "Next question  \u2192",
                       command=self._next).pack(pady=8)

    def _next(self):
        # Insert pending follow-up before advancing
        if self._pending_followup is not None:
            _fu = self._pending_followup
            self._pending_followup = None
            self.questions.insert(self.q_index + 1, _fu)
        self.q_index += 1
        self._show_question()

    def _update_narrative(self):
        """Build a media narrative from answer patterns."""
        _def = self._tone_counts.get("defensive", 0)
        _conf = self._tone_counts.get("confident", 0)
        _hon = self._tone_counts.get("honest", 0)
        _total = sum(self._tone_counts.values())
        if _total >= 2:
            if _def >= _total * 0.6:
                self._narrative = ("COACH ON HOT SEAT",
                                   "Dodge after dodge. The press smells fear.")
            elif _conf >= _total * 0.6:
                self._narrative = ("COACH IN CONTROL",
                                   "Commanding the room. Nothing rattles him.")
            elif _hon >= _total * 0.5:
                self._narrative = ("REFRESHING CANDOR",
                                   "Straight answers. The room respects it.")

    def _update_mood(self):
        # map mood (-6..+6 ish) to 0..1 bar + label
        v = max(0.0, min(1.0, 0.5 + self.mood / 12.0))
        self.mood_bar.set(v)
        if self.mood >= 3:
            label, color = "Media mood: Warm", GREEN
        elif self.mood >= 1:
            label, color = "Media mood: Fair", TEAL
        elif self.mood <= -3:
            label, color = "Media mood: Hostile", RED
        elif self.mood <= -1:
            label, color = "Media mood: Cool", GOLD
        else:
            label, color = "Media mood: Neutral", TEXT_DIM
        self.mood_label.configure(text=label, text_color=color)

    # ------------------------------------------------------------------
    # Atmosphere: camera flashes + ticker
    # ------------------------------------------------------------------
    def _camera_flashes(self):
        for _ in range(random.randint(2, 4)):
            self.after(random.randint(0, 350), self._flash_once)
        self._flash_once()

    def _flash_once(self):
        c = self.wall
        x = random.randint(30, self.W - 30)
        y = random.randint(15, 90)
        tag = f"flash{random.randint(0, 1 << 30)}"
        c.create_oval(x - 14, y - 14, x + 14, y + 14, fill="white",
                      outline="", tags=tag, stipple="gray50")
        self.after(120, lambda: c.delete(tag))
        if random.random() < 0.6:
            self.after(random.randint(150, 420), self._flash_once)

    def _start_ticker(self):
        if not self._ticker_items:
            return
        self._tick_ticker()

    def _tick_ticker(self):
        try:
            item = self._ticker_items[self._ticker_pos % len(self._ticker_items)]
            self.ticker_text.configure(text=item)
            self._ticker_pos += 1
            self._ticker_job = self.after(4000, self._tick_ticker)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _show_summary(self):
        for w in self.stage.winfo_children():
            w.destroy()
        for card in self._j_cards:
            card.configure(border_color=BORDER)
            card._avatar.configure(fg_color=TEXT_FAINT)
        heading(self.stage, "Press conference complete", size=20).pack(
            pady=(26, 4))
        body(self.stage, self._verdict_line(), size=13, dim=True).pack(pady=(0, 4))
        if self._narrative:
            _nl, _nd = self._narrative
            ctk.CTkLabel(self.stage, text=f"HEADLINE: {_nl}",
                         font=("Segoe UI", 14, "bold"),
                         text_color=GOLD).pack(pady=(0, 2))
            body(self.stage, _nd, size=12, dim=True).pack(pady=(0, 12))
        for i, ans in enumerate(self.chosen):
            tone = ans.get("tone", "calm")
            color = TONE_COLORS.get(tone, TEAL)
            row = ctk.CTkFrame(self.stage, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=22, pady=4)
            ctk.CTkLabel(row, text=f"Q{i + 1}", font=("Segoe UI", 11, "bold"),
                         text_color=TEXT_FAINT, width=34).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=ans.get("label", ""), font=("Segoe UI", 12),
                         text_color=TEXT, anchor="w").pack(side="left", fill="x",
                                                           expand=True, padx=4)
            ctk.CTkLabel(row, text=TONE_LABELS.get(tone, tone.title()),
                         font=("Segoe UI", 10, "bold"), text_color=BG,
                         fg_color=color, corner_radius=10, width=86).pack(
                             side="right", padx=10, pady=8)
        # totals
        tm = sum(a.get("morale_effect", 0) or 0 for a in self.chosen)
        tb = sum(a.get("board_effect", 0) or 0 for a in self.chosen)
        bits = []
        if tm:
            bits.append(f"Dressing room {'+' if tm > 0 else ''}{tm}")
        if tb:
            bits.append(f"Board confidence {'+' if tb > 0 else ''}{tb}")
        body(self.stage, "  •  ".join(bits) if bits else "No lasting effects.",
             size=12, dim=False).pack(pady=12)
        primary_button(self.stage, text=self.context.get("continue_text", "Continue  \u2192"),
                       command=self.destroy, width=220, height=44).pack(pady=10)

    def _verdict_line(self):
        if self.mood >= 3:
            return "You owned the room. The press is eating out of your hand."
        if self.mood >= 1:
            return "A solid showing. No damaging headlines tomorrow."
        if self.mood <= -3:
            return "A rough one. Expect some pointed columns in the morning."
        if self.mood <= -1:
            return "Terse and guarded. The press corps noticed."
        return "Professional and uneventful. Just how the PR team likes it."

    def destroy(self):
        for job in self._flash_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        if self._ticker_job:
            try:
                self.after_cancel(self._ticker_job)
            except Exception:
                pass
        super().destroy()


def launch_press_conference(parent, questions, title="Press Conference",
                            context=None):
    """Launch the intensive press conference experience.
    Replaces PressConferenceView (2026-10-04 per Caleb's call).
    Returns the list of chosen answer dicts."""
    page = PressConferencePage(parent, questions, title=title,
                               context=context)
    return page.chosen
