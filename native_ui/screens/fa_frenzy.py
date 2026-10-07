"""Free Agent Frenzy hub: signing wire, top-UFA cards, done-deals feed,
cap snapshot.

Native port of web_ui/templates/fa_frenzy.html +
web_ui/static/js/fa_frenzy.js + the /api/fa_frenzy endpoint in
web_ui/screens/free_agents.py. Calls the game object DIRECTLY --
no Flask/HTTP, no JSON.

Data helpers are reused from the native free_agents screen
(native_ui/screens/free_agents.py::_frenzy_active / _frenzy_data),
which already ports the web bridge logic. Auto-refresh every 60s via
QTimer (web parity); the timer runs only while the frenzy is active.
Only meaningful on free-agency day (July 1) -- an empty state is
shown otherwise.

Game methods used (all real, same as the web bridge called):
  - event_day_hubs.is_free_agency_day(date) (via _frenzy_active)
  - league.free_agents pool (via _frenzy_data)
  - attribute_composites.talent_tier (via _frenzy_data)
  - game.news_log (signing wire / done deals)
  - salary_cap_system.total_cap_charge (cap snapshot)
"""

from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,}"


class FaFrenzyScreen(BaseScreen):
    """Free Agent Frenzy hub."""

    title = "FA Frenzy"

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def _build_body(self):
        # Header: title tagline + quick nav buttons (web: frenzy-head).
        head = QHBoxLayout()
        title_box = QVBoxLayout()
        kicker = QLabel("PUCK DYNASTY · EVENT DAY")
        kicker.setStyleSheet("color: #8a93a8; font-size: 11px; "
                             "letter-spacing: 2px;")
        title_box.addWidget(kicker)
        self._tagline = QLabel("FREE AGENT FRENZY")
        self._tagline.setStyleSheet("color: #e8ecf4; font-size: 13px;")
        self._tagline.setWordWrap(True)
        title_box.addWidget(self._tagline)
        head.addLayout(title_box, 1)

        self._btn_market = QPushButton("Open FA Market")
        self._btn_market.setObjectName("primary-btn")
        self._btn_market.clicked.connect(lambda: self._navigate("free_agents"))
        head.addWidget(self._btn_market)
        self._btn_cap = QPushButton("My Cap Space")
        self._btn_cap.clicked.connect(lambda: self._navigate("finances"))
        head.addWidget(self._btn_cap)
        self._btn_trades = QPushButton("Trade Center")
        self._btn_trades.clicked.connect(lambda: self._navigate("trades"))
        head.addWidget(self._btn_trades)
        self._layout.addLayout(head)

        # Empty state (only meaningful on free-agency day).
        self._empty = QLabel(
            "No free agent frenzy today.\n"
            "The market opens on July 1 — check the calendar.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet("color: #8a93a8; font-size: 16px;")
        self._empty.setVisible(False)
        self._layout.addWidget(self._empty, 1)

        # Three-column hub (web: frenzy-cols).
        self._cols = QSplitter(Qt.Horizontal)
        self._layout.addWidget(self._cols, 1)

        # LEFT: signing wire.
        self._wire_box = self._make_panel("📡 Signing wire")
        self._wire_list = QVBoxLayout()
        self._wire_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._wire_box, self._wire_list)
        self._cols.addWidget(self._wire_box)

        # CENTER: top-UFA cards with Offer buttons.
        self._ufas_box = self._make_panel("⭐ Top available free agents")
        self._ufas_list = QVBoxLayout()
        self._ufas_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._ufas_box, self._ufas_list)
        self._cols.addWidget(self._ufas_box)

        # RIGHT: done deals + cap snapshot.
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(12)
        self._deals_box = self._make_panel("🤝 Done deals")
        self._deals_list = QVBoxLayout()
        self._deals_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._deals_box, self._deals_list)
        right_l.addWidget(self._deals_box, 1)
        self._cap_box = self._make_panel("💰 Your cap picture")
        self._cap_list = QVBoxLayout()
        self._cap_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._cap_box, self._cap_list)
        right_l.addWidget(self._cap_box, 1)
        self._cols.addWidget(right)

        self._cols.setStretchFactor(0, 1)
        self._cols.setStretchFactor(1, 2)
        self._cols.setStretchFactor(2, 1)

        # Auto-refresh every 60s (web: setInterval(loadFrenzy, 60000)).
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._auto_refresh)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _make_panel(self, label):
        grp = QGroupBox(label)
        grp.setObjectName("tile")
        return grp

    def _navigate(self, name):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(name)
            except Exception:
                pass

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _auto_refresh(self):
        # The wire streams live during the frenzy (web parity). Guard
        # against the screen being destroyed while the timer fires.
        try:
            self.refresh()
        except Exception:
            pass

    def _frenzy(self):
        """Shared data builder from the native free_agents screen."""
        try:
            from .free_agents import _frenzy_active, _frenzy_data
            if not _frenzy_active(self.game):
                return None
            return _frenzy_data(self.game)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------
    def refresh(self):
        data = self._frenzy()
        active = bool(data and data.get("cards"))
        self._empty.setVisible(not active)
        self._cols.setVisible(active)
        self._tagline.setText("FREE AGENT FRENZY" if active
                              else "FREE AGENT FRENZY")
        if active:
            self._tagline.setText("The market is open. Every contender is "
                                  "on the phone. Don't get left behind.")
            self._render_wire(data)
            self._render_ufas(data)
            self._render_deals(data)
            self._render_cap(data)
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    # ------------------------------------------------------------------
    # render sections
    # ------------------------------------------------------------------
    def _render_wire(self, data):
        self._clear(self._wire_list)
        cards = data.get("cards") or []
        lines = ["The floodgates are open — teams are racing to call "
                 "agents."]
        if cards:
            lines.append("Headliners still available:")
            lines += [f"  {c['rank']}. {c['name']} ({c['position']}, "
                      f"age {c['age']})  {c.get('tier') or ''}"
                      for c in cards[:3]]
        else:
            lines = ["The market hasn't opened yet."]
        lines += ["", f"{data.get('count', 0)} free agents on the market.",
                  "Signings will stream in here live."]
        for line in lines:
            lbl = QLabel(line if line else " ")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #c7cede; font-size: 13px;")
            self._wire_list.addWidget(lbl)

    def _render_ufas(self, data):
        self._clear(self._ufas_list)
        cards = data.get("cards") or []
        if not cards:
            note = QLabel("No free agents on the market.")
            note.setStyleSheet("color: #8a93a8; font-size: 13px;")
            self._ufas_list.addWidget(note)
            return
        for c in cards:
            frame = QFrame()
            frame.setObjectName("tile")
            fl = QVBoxLayout(frame)
            fl.setSpacing(4)
            top = QHBoxLayout()
            rank = QLabel(f"#{c['rank']}")
            rank.setStyleSheet("font-weight: bold; color: #e8b93c;")
            top.addWidget(rank)
            name = QLabel(str(c["name"]))
            name.setStyleSheet("font-weight: bold; font-size: 14px;")
            name.setWordWrap(True)
            top.addWidget(name, 1)
            meta = QLabel(f"{c['position']} · Age {c['age']} · "
                          f"{c.get('fa_type', '')}")
            meta.setStyleSheet("color: #8a93a8; font-size: 12px;")
            top.addWidget(meta)
            fl.addLayout(top)

            mid = QHBoxLayout()
            tier = QLabel(str(c.get("tier") or "—"))
            tier.setStyleSheet("color: #7cc4ff; font-size: 12px;")
            mid.addWidget(tier)
            season = QLabel(str(c.get("season_line") or ""))
            season.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            season.setWordWrap(True)
            mid.addWidget(season, 1)
            fl.addLayout(mid)

            bot = QHBoxLayout()
            ask = QLabel(f"Ask: {_fmt_money(c.get('ask'))}/yr")
            ask.setStyleSheet("font-size: 13px;")
            bot.addWidget(ask, 1)
            offer = QPushButton("Make offer")
            offer.setObjectName("primary-btn")
            pid = c.get("id")
            offer.clicked.connect(lambda _=False, _pid=pid:
                                  self._on_offer(_pid))
            bot.addWidget(offer)
            fl.addLayout(bot)
            self._ufas_list.addWidget(frame)

    def _render_deals(self, data):
        self._clear(self._deals_list)
        for story in (data.get("deals") or []):
            lbl = QLabel(f"• {story}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #c7cede; font-size: 13px;")
            self._deals_list.addWidget(lbl)

    def _render_cap(self, data):
        self._clear(self._cap_list)
        rows = [
            ("Cap ceiling", data.get("cap", 0), False),
            ("Committed", data.get("committed", 0), False),
            ("Cap space", data.get("space", 0), True),
        ]
        for label, val, emph in rows:
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            row.addWidget(lab, 1)
            v = QLabel(_fmt_money(val))
            v.setStyleSheet("font-weight: bold; font-size: 14px;")
            if emph:
                v.setStyleSheet("font-weight: bold; font-size: 14px; "
                                "color: %s;" % (
                                    "#43d17c" if val >= 0 else "#e05252"))
            row.addWidget(v)
            wrap = QWidget()
            wrap.setLayout(row)
            self._cap_list.addWidget(wrap)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _on_offer(self, pid):
        # Web: /free_agents?offer=<id>. Navigate to the FA market and
        # open the real offer dialog for the player.
        self._navigate("free_agents")
        try:
            from .free_agents import OfferDialog
            dlg = OfferDialog(self.game, pid, self)
            dlg.exec()
        except Exception:
            pass


def _fill_panel(group_box, layout):
    """Put a scrollable list layout inside a panel."""
    wrap = QScrollArea()
    wrap.setWidgetResizable(True)
    wrap.setFrameShape(QScrollArea.NoFrame)
    inner = QWidget()
    inner.setLayout(layout)
    wrap.setWidget(inner)
    box_l = QVBoxLayout(group_box)
    box_l.setContentsMargins(8, 16, 8, 8)
    box_l.addWidget(wrap)
