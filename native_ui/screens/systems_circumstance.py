"""Systems: Circumstance Shifts (read-only).

Shows "tonight's circumstance baseline": for each skater (and goalie),
the shift circumstance_shift() will apply per composite for the NEXT
game -- decomposed into energy / morale / home-ice / rivalry
components, verified to sum to the engine function's own output.

PUZZLE RULE: your own team's shifts are your info (shown). Opponent
detail stays qualitative (rivalry intensity band only).
"""
from types import SimpleNamespace

from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QHBoxLayout,
                               QComboBox, QTableWidget, QTableWidgetItem,
                               QHeaderView)
from PySide6.QtGui import QColor

from .base import BaseScreen
from .systems_common import (user_team, league_of, today_of, tone_color,
                             heat_band, explainer_label, section_title,
                             no_game_label, clear_layout, pos_short,
                             player_name,
                             add_scroll_content)

_COMPOSITE_LABELS = {
    "chance_creation": "Chance creation",
    "finishing": "Finishing",
    "skating": "Skating",
    "defensive_play": "Defensive play",
    "goalie_save": "Goalie save",
    "physicality": "Physicality",
    "discipline": "Discipline",
    "faceoff": "Faceoff",
    "puck_retrieval": "Puck retrieval",
}


class SystemsCircumstanceScreen(BaseScreen):
    """Circumstance Shifts -- tonight's game-state baseline per composite."""

    title = "Circumstance"

    def _build_body(self):
        self._layout.addLayout(systems_nav_bar(self))
        self._content = add_scroll_content(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Composite:"))
        self._combo = QComboBox()
        for key, label in _COMPOSITE_LABELS.items():
            self._combo.addItem(label, key)
        self._combo.setCurrentIndex(
            self._combo.findData("finishing"))
        self._combo.currentIndexChanged.connect(self._on_composite)
        row.addWidget(self._combo)
        row.addStretch()
        self._content.addLayout(row)

        self._body = QVBoxLayout()
        self._body.setSpacing(12)
        self._content.addLayout(self._body)
        self._content.addStretch()
        self.refresh()

    def _on_composite(self):
        # Guard: fired while the combo is still being built.
        if getattr(self, "_body", None) is None:
            return
        self.refresh()

    @staticmethod
    def _next_game(league, team, today):
        """Next scheduled game for the team: (date, home_team, away_team)."""
        my = getattr(team, "team_name", "")
        best = None
        try:
            for item in list(getattr(league, "schedule", None) or []):
                try:
                    if isinstance(item, dict):
                        d, h, a = (item.get("date"), item.get("home_team"),
                                   item.get("away_team"))
                    elif isinstance(item, (tuple, list)) and len(item) >= 3:
                        d, h, a = item[0], item[1], item[2]
                    else:
                        continue
                    hn = getattr(h, "team_name", h)
                    an = getattr(a, "team_name", a)
                    if my not in (hn, an):
                        continue
                    if today is not None and d is not None and d <= today:
                        continue
                    if best is None or (d is not None and d < best[0]):
                        best = (d, h, a)
                except Exception:
                    continue
        except Exception:
            return None
        return best

    def refresh(self):
        body = getattr(self, "_body", None)
        if body is None:
            return
        clear_layout(body)
        team = user_team(self.game)
        league = league_of(self.game)
        if team is None or league is None:
            body.addWidget(no_game_label())
            return
        try:
            import attribute_composites as acmp
            import condition_system as cs
        except Exception:
            body.addWidget(explainer_label(
                "Engine unavailable -- circumstance data can't be read."))
            return

        key = self._combo.currentData()
        if key not in _COMPOSITE_LABELS:
            key = "finishing"
        today = today_of(self.game)
        nxt = self._next_game(league, team, today)
        if nxt is None:
            fake = SimpleNamespace(
                home_team=None, away_team=None,
                rivalries=list(getattr(league, "rivalries", None) or []),
                period=1, clock=1200.0)
            is_home = False
        else:
            _d, h, a = nxt
            fake = SimpleNamespace(
                home_team=h, away_team=a,
                rivalries=list(getattr(league, "rivalries", None) or []),
                period=1, clock=1200.0)
            my_name = getattr(team, "team_name", "")
            home_name = getattr(h, "team_name", "") or ""
            is_home = bool(home_name) and home_name == my_name

        body.addWidget(explainer_label(
            "Composite points added per event at tonight's baseline. "
            "Components verified to sum to the engine's own total."))

        # Next-game note + opponent read (qualitative only).
        if nxt is None:
            body.addWidget(explainer_label(
                "Offseason / no fixture found \u2014 showing the energy + "
                "morale baseline only (home ice and rivalry apply once "
                "there's a next game)."))
        else:
            d, h, a = nxt
            hn = getattr(h, "team_name", h)
            an = getattr(a, "team_name", a)
            body.addWidget(explainer_label(
                f"Next game: {an} @ {hn} ({d}). "
                f"You are {'home' if is_home else 'away'}. Pre-game "
                "baseline (period 1) \u2014 the late/close-game clutch term "
                "applies in-game only."))
            try:
                import physicality as phys
                heat = float(phys.rivalry_heat_between(
                    getattr(league, "rivalries", None), h, a) or 0.0)
            except Exception:
                heat = 0.0
            band, tone = heat_band(heat)
            opp = QFrame()
            opp.setObjectName("tile")
            ol = QVBoxLayout(opp)
            ot = QLabel("Opponent read")
            ot.setObjectName("tile-title")
            my_name = getattr(team, "team_name", "")
            opp_name = str(an) if str(hn) == my_name else str(hn)
            ob = QLabel(f"{opp_name} \u2014 {band}")
            ob.setStyleSheet(
                f"color: {tone_color(tone)}; font-size: 14px; "
                "font-weight: 700;")
            os_ = QLabel("Qualitative only \u2014 their room is their "
                         "business.")
            os_.setObjectName("tile-sub")
            ol.addWidget(ot)
            ol.addWidget(ob)
            ol.addWidget(os_)
            body.addWidget(opp)

        body.addWidget(section_title("Applied shifts"))

        # Per-player decomposition from the documented engine terms
        # (same as the desktop view; sums to the real total).
        rows = []
        event_kinds = getattr(acmp, "_EVENT_KIND", {}) or {}
        for p in list(getattr(team, "roster", None) or []):
            try:
                energy = cs.get_game_energy(p)
                total = acmp.circumstance_shift(
                    p, key, sim=fake, team=team, energy=energy)
                e_term = -2.0 * (1.0 - max(0.0, min(100.0, energy)) / 100.0)
                try:
                    m = max(1.0, min(100.0,
                                     float(getattr(p, "morale", 70.0))))
                except (TypeError, ValueError):
                    m = 70.0
                mo_term = max(-1.0, min(1.0, (m - 70.0) / 30.0))
                h_term = 0.4 if is_home else 0.0
                r_term = 0.0
                kind = event_kinds.get(key, "neutral")
                if kind in ("physical", "discipline") and nxt is not None:
                    try:
                        import physicality as phys
                        hn = getattr(nxt[1], "team_name", nxt[1])
                        an = getattr(nxt[2], "team_name", nxt[2])
                        heat = float(phys.rivalry_heat_between(
                            getattr(league, "rivalries", None),
                            hn, an) or 0.0)
                        heat = max(0.0, min(100.0, heat)) / 100.0
                        r_term = (0.6 if kind == "physical"
                                  else -0.6) * heat
                    except Exception:
                        r_term = 0.0
                rows.append({"name": player_name(p), "pos": pos_short(p),
                             "total": round(float(total), 2),
                             "energy": round(e_term, 2),
                             "morale": round(mo_term, 2),
                             "home": round(h_term, 2),
                             "rivalry": round(r_term, 2)})
            except Exception:
                continue
        rows.sort(key=lambda r: r["total"])

        table = QTableWidget(len(rows), 7)
        table.setHorizontalHeaderLabels(
            ["PLAYER", "POS", "TOTAL", "ENERGY", "MORALE", "HOME", "RIVALRY"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        for i, r in enumerate(rows):
            total_item = QTableWidgetItem(f"{r['total']:+.2f}")
            t = r["total"]
            total_item.setForeground(QColor(
                tone_color("green" if t > 0.005
                           else "red" if t < -0.005 else "slate")))
            vals = [r["name"], r["pos"], None,
                    f"{r['energy']:+.2f}", f"{r['morale']:+.2f}",
                    f"{r['home']:+.2f}", f"{r['rivalry']:+.2f}"]
            for j, v in enumerate(vals):
                if j == 2:
                    table.setItem(i, j, total_item)
                else:
                    table.setItem(i, j, QTableWidgetItem(v))
        table.setMinimumHeight(min(420, 30 + 26 * max(len(rows), 1)))
        body.addWidget(table)
