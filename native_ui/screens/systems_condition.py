"""Systems: Roster Condition (read-only).

The whole roster's condition on one surface, worst first. Every
number is an exact engine read (condition_system); nothing is
re-derived or invented.
"""
from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QHBoxLayout,
                               QScrollArea, QWidget, QTableWidget,
                               QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen
from .systems_common import (user_team, league_of, today_of, tone_color,
                             explainer_label, section_title, no_game_label,
                             clear_layout, pos_short, player_name)
from .systems_common import systems_nav_bar


class SystemsConditionScreen(BaseScreen):
    """Roster Condition -- fatigue watch for the whole roster."""

    title = "Condition"

    #: Tier tones (desktop used teal for GOOD; deep-blue family per UI rules).
    _TIER_TONES = {"FRESH": "green", "GOOD": "blue",
                   "WORN": "gold", "GASSED": "red"}
    _TIER_RANK = {"GASSED": 0, "WORN": 1, "GOOD": 2, "FRESH": 3}

    def _build_body(self):
        self._layout.addLayout(systems_nav_bar(self))
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
        league = league_of(self.game)
        if team is None:
            content.addWidget(no_game_label())
            content.addStretch()
            return
        try:
            import condition_system as cs
        except Exception:
            content.addWidget(explainer_label(
                "Engine unavailable -- condition data can't be read."))
            content.addStretch()
            return

        rows = []
        for p in list(getattr(team, "roster", None) or []):
            try:
                cond = cs.get_condition(p)
                tier = str(cs.condition_tier(p))
                energy = cs.get_game_energy(p)
                risk = cs.fatigue_injury_risk_mult(p)
                last_toi = float(getattr(p, "_w3_last_toi_min", 0.0) or 0.0)
                rows.append({"name": player_name(p), "pos": pos_short(p),
                             "cond": round(float(cond), 0), "tier": tier,
                             "tone": self._TIER_TONES.get(tier, "blue"),
                             "energy": round(float(energy), 0),
                             "risk": round(float(risk), 2),
                             "last_toi": round(last_toi, 0)})
            except Exception:
                continue
        # Worst first: gassed/worn at the top so the rest call is obvious.
        rows.sort(key=lambda r: (self._TIER_RANK.get(r["tier"], 4),
                                 r["cond"]))

        # --- Room at a glance ---
        content.addWidget(section_title("Room at a glance"))
        counts = {}
        for r in rows:
            counts[r["tier"]] = counts.get(r["tier"], 0) + 1
        gassed = [r["name"] for r in rows if r["tier"] == "GASSED"][:5]
        rest = None
        try:
            rest = cs.rest_days_after(
                getattr(league, "schedule", None), team, today_of(self.game))
        except Exception:
            pass
        gcard = QFrame()
        gcard.setObjectName("tile")
        gl = QVBoxLayout(gcard)
        bits = []
        for tier in ("FRESH", "GOOD", "WORN", "GASSED"):
            n = counts.get(tier, 0)
            if n:
                bits.append((tier, n, self._TIER_TONES[tier]))
        crow = QHBoxLayout()
        for tier, n, tone in bits:
            lbl = QLabel(f"{tier}: {n}")
            lbl.setStyleSheet(
                f"color: {tone_color(tone)}; font-size: 14px; "
                "font-weight: 700;")
            crow.addWidget(lbl)
        crow.addStretch()
        gl.addLayout(crow)
        if rest is not None:
            rl = QLabel(f"Rest days after next game window: {rest}")
            rl.setObjectName("tile-sub")
            gl.addWidget(rl)
        if gassed:
            gl_lbl = QLabel("Needs a rest: " + ", ".join(gassed))
            gl_lbl.setStyleSheet(
                f"color: {tone_color('red')}; font-size: 13px; "
                "font-weight: 600;")
            gl_lbl.setWordWrap(True)
            gl.addWidget(gl_lbl)
        content.addWidget(gcard)

        # --- Skater condition table ---
        content.addWidget(section_title("Skater condition"))
        content.addWidget(explainer_label(
            "Condition = season wear (0-100). Energy = current in-game "
            "pool. Injury risk = engine multiplier right now "
            "(1.00 = fresh)."))

        table = QTableWidget(len(rows), 7)
        table.setHorizontalHeaderLabels(
            ["PLAYER", "POS", "COND", "TIER", "ENERGY", "RISK", "LAST TOI"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, r in enumerate(rows):
            tier_item = QTableWidgetItem(r["tier"])
            tier_item.setForeground(QColor(tone_color(r["tone"])))
            vals = [r["name"], r["pos"], f"{r['cond']:.0f}", None,
                    f"{r['energy']:.0f}", f"{r['risk']:.2f}",
                    f"{r['last_toi']:.0f}"]
            for j, v in enumerate(vals):
                if j == 3:
                    table.setItem(i, j, tier_item)
                else:
                    table.setItem(i, j, QTableWidgetItem(v))
        table.setMinimumHeight(min(440, 30 + 26 * max(len(rows), 1)))
        content.addWidget(table)
        content.addStretch()
