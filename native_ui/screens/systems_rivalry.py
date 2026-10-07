"""Systems: Rivalry Dashboard (read-only).

Your team's rivalries ranked by intensity (with the story behind
each) plus the league's hottest team feuds. Reads the live rivalry
store (league.rivalries) via reputation_system.
"""
from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QScrollArea,
                               QWidget)

from .base import BaseScreen
from .systems_common import (user_team, league_of, tone_color, heat_band,
                             explainer_label, section_title, no_game_label,
                             clear_layout)


class SystemsRivalryScreen(BaseScreen):
    """Rivalry Dashboard -- bad blood, your team and league-wide."""

    title = "Rivalry"

    _KIND_LABELS = {
        "team_team": "Team feud",
        "gm_coach": "You vs their coach",
        "coach_coach": "Coaches' feud",
        "gm_gm": "GM feud",
        "gm_respect": "Mutual respect",
        "fan_player": "Fan storyline",
    }

    @staticmethod
    def _store(league):
        try:
            import reputation_system as rs
            return rs._rivalry_store(league)
        except Exception:
            return list(getattr(league, "rivalries", None) or [])

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

    def _rec_card(self, r):
        """One rivalry record as a card; None if it can't be parsed."""
        try:
            a = str(r.get("a_name", "?"))
            b = str(r.get("b_name", "?"))
            intensity = int(float(r.get("intensity", 0) or 0))
            grudge = int(float(r.get("grudge", 0) or 0))
            kind = self._KIND_LABELS.get(r.get("kind"), str(r.get("kind", "")))
            origin = str(r.get("origin", "") or "")
            story = str(r.get("story", "") or "").strip()[:280]
            date = str(r.get("date", "") or "")
        except Exception:
            return None
        band, tone = heat_band(intensity)

        card = QFrame()
        card.setObjectName("tile")
        cl = QVBoxLayout(card)
        title = QLabel(f"{a}  vs  {b}")
        title.setObjectName("tile-title")
        band_lbl = QLabel(f"{band}  \u00b7  Intensity {intensity}")
        band_lbl.setStyleSheet(
            f"color: {tone_color(tone)}; font-size: 13px; font-weight: 700;")
        meta_bits = [x for x in (kind, origin, date) if x]
        meta = QLabel("  \u00b7  ".join(meta_bits) +
                      (f"  \u00b7  Grudge {grudge}" if grudge else ""))
        meta.setObjectName("tile-sub")
        story_lbl = QLabel(story)
        story_lbl.setObjectName("tile-sub")
        story_lbl.setWordWrap(True)
        cl.addWidget(title)
        cl.addWidget(band_lbl)
        if meta_bits or grudge:
            cl.addWidget(meta)
        if story:
            cl.addWidget(story_lbl)
        return card

    def refresh(self):
        content = getattr(self, "_content", None)
        if content is None:
            return
        clear_layout(content)
        team = user_team(self.game)
        league = league_of(self.game)
        if team is None or league is None:
            content.addWidget(no_game_label())
            content.addStretch()
            return

        store = self._store(league)
        try:
            import reputation_system as rs
            mine = rs.get_rivalries_for(store, team)
        except Exception:
            mine = []
        my_name = getattr(team, "team_name", "")
        try:
            recs = [r for r in store
                    if isinstance(r, dict) and r.get("kind") == "team_team"
                    and my_name not in (r.get("a_name"), r.get("b_name"))]
            recs.sort(key=lambda r: -float(r.get("intensity", 0) or 0))
            hottest = recs[:8]
        except Exception:
            hottest = []

        # --- Your rivalries ---
        content.addWidget(section_title("Your rivalries"))
        mine_cards = [c for c in (self._rec_card(r)
                                  for r in (mine or [])[:12]) if c]
        if not mine_cards:
            content.addWidget(explainer_label(
                "No rivalries yet. Playoff heartbreak and dirty hits "
                "have a way of starting them."))
        for c in mine_cards:
            content.addWidget(c)

        # --- Around the league: hottest feuds ---
        content.addWidget(section_title("Around the league \u2014 hottest feuds"))
        content.addWidget(explainer_label(
            "Team-vs-team heat elsewhere. These games run hotter: more "
            "incidents, edgier physicality."))
        hot_cards = [c for c in (self._rec_card(r) for r in hottest) if c]
        if not hot_cards:
            content.addWidget(explainer_label(
                "The league is quiet right now."))
        for c in hot_cards:
            content.addWidget(c)

        content.addStretch()
