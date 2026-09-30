"""TRACK C #5 -- Clutch / situations visibility.

team_clutch moves close games, but the user can never see what the inputs
are when one swings. PUZZLE RULE (analytics stays a puzzle): this screen
shows QUALITATIVE indicators only -- which factors are lifting or dragging
the room, never exact weights or magnitudes. Signs come from
team_clutch.clutch_breakdown; the numbers never reach the screen.
"""

import customtkinter as ctk

import trackc_common as tc

#: What each clutch input IS (design text only -- no weights, no bands).
_FACTOR_STORIES = {
    "talent": ("Marquee talent",
               "Your best players' big-game pedigree. Stars who have been there tilt close games."),
    "temperament": ("Big-game temperament",
                    "Composure under pressure from your key players — who wants the puck late."),
    "traits": ("Earned identity",
               "Clutch traits and playoff tags the room has earned over the years."),
    "morale": ("Room state",
               "Morale × leadership. A tight room holds its nerve; a fractured one doesn't."),
    "situation": ("Situation",
                 "The room's hunger and circumstance — contract years, droughts, milestones."),
    "trend": ("Form",
              "How the last stretch went. Winning breeds calm; losing breeds gripping the stick."),
    "heat": ("Matchup heat",
             "Rivalry and occasion. Big-game rooms rise to it; fragile rooms shrink."),
}

_FACTOR_ORDER = ("talent", "temperament", "traits", "morale",
                 "situation", "trend", "heat")


class TrackCClutchView(ctk.CTkFrame):
    TITLE = "Clutch Factors"
    SUBTITLE = "What tilts close games for your club — the shape of it, not the math"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self.body = tc.make_body(self)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        team = tc.user_team(self)
        if team is None:
            self._body(self.body, text="No team loaded.").pack(padx=16, pady=16)
            return
        breakdown = self._read_breakdown(team)
        self._verdict_card(breakdown)
        self._factors_card(breakdown)

    # ------------------------------------------------------------------
    # engine reads (signs only are rendered)
    # ------------------------------------------------------------------
    def _read_breakdown(self, team):
        try:
            import team_clutch as tcl
            return tcl.clutch_breakdown(team) or {}
        except Exception:
            return {}

    @staticmethod
    def _sign(term):
        try:
            t = float(term)
        except (TypeError, ValueError):
            return "neutral"
        if t > 0.0005:
            return "lifting"
        if t < -0.0005:
            return "dragging"
        return "neutral"

    def _verdict_card(self, breakdown):
        total = breakdown.get("total")
        try:
            t = float(total)
        except (TypeError, ValueError):
            t = 1.0
        if t >= 1.02:
            verdict, color, blurb = ("Clutch edge", "GREEN",
                                    "This room tilts tight games its way more often than not.")
        elif t <= 0.98:
            verdict, color, blurb = ("Shaky late", "RED",
                                    "Close games have been slipping — the room doesn't hold its nerve yet.")
        else:
            verdict, color, blurb = ("Neutral", "TEAL",
                                    "No strong lean either way; close games are coin flips.")
        card = tc.section(self, self.body, "Your room in close games")
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=4, pady=4)
        tc.chip(self, head, verdict.upper(), color).pack(side="left", padx=(0, 10))
        self._body(head, text=blurb).pack(side="left")
        self._body(card,
                   text="Built from seven live inputs below. The exact blend is the sim's business — "
                        "this is the shape of it.",
                   dim=True).pack(anchor="w", padx=4, pady=(4, 0))

    def _factors_card(self, breakdown):
        card = tc.section(self, self.body, "The seven inputs",
                          "▲ lifting the room   ·   ▬ neutral   ·   ▼ dragging it down")
        for key in _FACTOR_ORDER:
            label, story = _FACTOR_STORIES[key]
            sign = self._sign(breakdown.get(key, 0.0))
            glyph, color = {"lifting": ("▲", "GREEN"),
                            "dragging": ("▼", "RED"),
                            "neutral": ("▬", "TEAL")}[sign]
            rowf = ctk.CTkFrame(card, fg_color="transparent")
            rowf.pack(fill="x", padx=4, pady=3)
            tc.chip(self, rowf, f" {glyph} ", color).pack(side="left", padx=(0, 10))
            left = ctk.CTkFrame(rowf, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(left, text=f"{label} — {sign}", anchor="w",
                         font=("Segoe UI", 12, "bold")).pack(anchor="w")
            self._body(left, text=story, dim=True).pack(anchor="w")
