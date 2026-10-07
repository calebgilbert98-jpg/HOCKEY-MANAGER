"""Systems: Clutch Factors (read-only).

Team clutch moves close games; this page shows WHAT the inputs are.

PUZZLE RULE (same as the web view): qualitative indicators only -- which
factors are lifting or dragging the room, never exact weights or
magnitudes. Signs come from team_clutch.clutch_breakdown(); the numbers
never reach the screen.
"""
from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QHBoxLayout,
                               QScrollArea, QWidget)
from PySide6.QtCore import Qt

from .base import BaseScreen
from .systems_common import (user_team, tone_color, explainer_label,
                             section_title, no_game_label, clear_layout)


class SystemsClutchScreen(BaseScreen):
    """Clutch Factors -- the close-game engine's seven inputs."""

    title = "Clutch"

    #: What each clutch input IS (design text, verbatim from the desktop view).
    _FACTOR_STORIES = {
        "talent": ("Marquee talent",
                   "Your best players' big-game pedigree. Stars who have "
                   "been there tilt close games."),
        "temperament": ("Big-game temperament",
                        "Composure under pressure from your key players "
                        "\u2014 who wants the puck late."),
        "traits": ("Earned identity",
                   "Clutch traits and playoff tags the room has earned "
                   "over the years."),
        "morale": ("Room state",
                   "Morale \u00d7 leadership. A tight room holds its nerve; "
                   "a fractured one doesn't."),
        "situation": ("Situation",
                      "The room's hunger and circumstance \u2014 contract "
                      "years, droughts, milestones."),
        "trend": ("Form",
                  "How the last stretch went. Winning breeds calm; losing "
                  "breeds gripping the stick."),
        "heat": ("Matchup heat",
                 "Rivalry and occasion. Big-game rooms rise to it; fragile "
                 "rooms shrink."),
    }
    _FACTOR_ORDER = ("talent", "temperament", "traits", "morale",
                     "situation", "trend", "heat")

    _SIGN_GLYPH = {"lifting": "\u25b2", "dragging": "\u25bc",
                   "neutral": "\u25ac"}
    _SIGN_TONE = {"lifting": "green", "dragging": "red",
                  "neutral": "slate"}

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

    def _build_body(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        self._content = QVBoxLayout(inner)
        self._content.setSpacing(12)
        scroll.setWidget(inner)
        self._layout.addWidget(scroll)
        self.refresh()

    def refresh(self):
        content = getattr(self, "_content", None)
        if content is None:
            return
        clear_layout(content)
        team = user_team(self.game)
        if team is None:
            content.addWidget(no_game_label())
            content.addStretch()
            return
        try:
            import team_clutch as tcl
            breakdown = tcl.clutch_breakdown(team) or {}
        except Exception:
            breakdown = {}
        try:
            total = float(breakdown.get("total", 1.0))
        except (TypeError, ValueError):
            total = 1.0
        # Verdict bands mirror the desktop view; the raw total never leaves.
        if total >= 1.02:
            label, tone = "Clutch edge", "green"
            blurb = ("This room tilts tight games its way more often "
                     "than not.")
        elif total <= 0.98:
            label, tone = "Shaky late", "red"
            blurb = ("Close games have been slipping \u2014 the room doesn't "
                     "hold its nerve yet.")
        else:
            label, tone = "Neutral", "blue"
            blurb = "No strong lean either way; close games are coin flips."

        content.addWidget(explainer_label("Your room in close games."))

        vcard = QFrame()
        vcard.setObjectName("tile")
        vl = QVBoxLayout(vcard)
        vt = QLabel(label)
        vt.setStyleSheet(
            f"color: {tone_color(tone)}; font-size: 18px; font-weight: 700;")
        vb = QLabel(blurb)
        vb.setObjectName("tile-sub")
        vb.setWordWrap(True)
        vl.addWidget(vt)
        vl.addWidget(vb)
        content.addWidget(vcard)

        content.addWidget(section_title("The seven inputs"))
        content.addWidget(explainer_label(
            "\u25b2 lifting the room \u00b7 \u25ac neutral "
            "\u00b7 \u25bc dragging it down"))

        for key in self._FACTOR_ORDER:
            fname, story = self._FACTOR_STORIES[key]
            sign = self._sign(breakdown.get(key, 0.0))
            row = QFrame()
            row.setObjectName("tile")
            rl = QHBoxLayout(row)
            glyph = QLabel(self._SIGN_GLYPH[sign])
            glyph.setStyleSheet(
                f"color: {tone_color(self._SIGN_TONE[sign])}; "
                "font-size: 20px;")
            glyph.setFixedWidth(28)
            glyph.setAlignment(Qt.AlignTop)
            txt = QVBoxLayout()
            nl = QLabel(fname)
            nl.setObjectName("tile-title")
            sl = QLabel(story)
            sl.setObjectName("tile-sub")
            sl.setWordWrap(True)
            txt.addWidget(nl)
            txt.addWidget(sl)
            rl.addWidget(glyph)
            rl.addLayout(txt)
            content.addWidget(row)

        content.addStretch()
