"""Draft Day Central: draft-day event hub — pick-by-pick wire, on-the-clock
panel, top-available prospect cards, draft-day deals feed, class snapshot.

Native port of main:event_day_hubs.py :: DraftDayCentral (Tkinter).
Calls the game object DIRECTLY -- no Flask/HTTP, no JSON.

Data helpers are reused from the native draft screen
(native_ui/screens/draft.py::get_draft_state / available_prospects /
buzz_items / trade_feed), which already ports the bridge logic.
Auto-refresh every 10s via QTimer (Tkinter refreshed every 4s; 10s is
plenty for a hub view); only meaningful around draft week (June 20-25)
or while an entry-draft session is active -- an empty state is shown
otherwise.

Game data used (all real, same as the Tkinter original read):
  - league.entry_draft_session board (via get_draft_state)
  - league.draft_prospects (via available_prospects)
  - league.draft_day_deals (via trade_feed)
  - draft_night / draft_stories storylines (via buzz_items)
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


class DraftCentralScreen(BaseScreen):
    """Draft Day Central hub."""

    title = "Draft Day Central"

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def _build_body(self):
        # Header: kicker + tagline + quick nav buttons (Tkinter: action bar).
        head = QHBoxLayout()
        title_box = QVBoxLayout()
        kicker = QLabel("PUCK DYNASTY · EVENT DAY")
        kicker.setStyleSheet("color: #8a93a8; font-size: 11px; "
                             "letter-spacing: 2px;")
        title_box.addWidget(kicker)
        self._tagline = QLabel("DRAFT DAY CENTRAL")
        self._tagline.setStyleSheet("color: #e8ecf4; font-size: 13px;")
        self._tagline.setWordWrap(True)
        title_box.addWidget(self._tagline)
        head.addLayout(title_box, 1)

        self._btn_board = QPushButton("Draft Board / War Room")
        self._btn_board.setObjectName("primary-btn")
        self._btn_board.clicked.connect(lambda: self._navigate("draft"))
        head.addWidget(self._btn_board)
        self._btn_trade = QPushButton("Trade This Pick")
        self._btn_trade.setToolTip(
            "Open the Trade Center to shop this pick")
        self._btn_trade.clicked.connect(self._open_trade_center)
        head.addWidget(self._btn_trade)
        self._btn_scout = QPushButton("Scouting Department")
        self._btn_scout.clicked.connect(lambda: self._navigate("scouting"))
        head.addWidget(self._btn_scout)
        self._layout.addLayout(head)

        # Empty state (only meaningful around draft week / live draft).
        self._empty = QLabel(
            "No draft day today.\n"
            "The entry draft runs June 23-25 — check the calendar.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet("color: #8a93a8; font-size: 16px;")
        self._empty.setVisible(False)
        self._layout.addWidget(self._empty, 1)

        # Three-column hub (Tkinter: left/center/right).
        self._cols = QSplitter(Qt.Horizontal)
        self._layout.addWidget(self._cols, 1)

        # LEFT: pick-by-pick wire.
        self._wire_box = self._make_panel("📡 Pick-by-pick wire")
        self._wire_list = QVBoxLayout()
        self._wire_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._wire_box, self._wire_list)
        self._cols.addWidget(self._wire_box)

        # CENTER: on-the-clock panel + top-available prospect cards.
        center = QWidget()
        center_l = QVBoxLayout(center)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(12)
        self._clock_box = self._make_panel("⏰ On the clock")
        self._clock_list = QVBoxLayout()
        self._clock_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._clock_box, self._clock_list)
        center_l.addWidget(self._clock_box, 0)
        self._prosp_box = self._make_panel("⭐ Top available prospects")
        self._prosp_list = QVBoxLayout()
        self._prosp_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._prosp_box, self._prosp_list)
        center_l.addWidget(self._prosp_box, 1)
        self._cols.addWidget(center)

        # RIGHT: draft-day deals + class snapshot.
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(12)
        self._deals_box = self._make_panel("🤝 Draft-day deals")
        self._deals_list = QVBoxLayout()
        self._deals_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._deals_box, self._deals_list)
        right_l.addWidget(self._deals_box, 1)
        self._snap_box = self._make_panel("📊 Class snapshot")
        self._snap_list = QVBoxLayout()
        self._snap_list.setAlignment(Qt.AlignTop)
        _fill_panel(self._snap_box, self._snap_list)
        right_l.addWidget(self._snap_box, 1)
        self._cols.addWidget(right)

        self._cols.setStretchFactor(0, 1)
        self._cols.setStretchFactor(1, 2)
        self._cols.setStretchFactor(2, 1)

        # Auto-refresh (Tkinter: after(4000, _live_tick)).
        self._timer = QTimer(self)
        self._timer.setInterval(10_000)
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

    def _open_trade_center(self):
        """Open the Trade Center for pick trading.

        The draft screen's war room doesn't handle pick trades; the
        Trade Center is the real trade flow. When the user's next pick
        can be resolved, it is preloaded into the "You give" side.
        """
        self._navigate("trades")
        pick_id = self._next_pick_id()
        if not pick_id:
            return
        try:
            screen = self.main_window._screens.get("trades")
        except Exception:
            screen = None
        if screen is None:
            return
        widget = screen.widget() if hasattr(screen, "widget") else screen
        give_picks = getattr(widget, "_give_picks", None)
        if not isinstance(give_picks, set):
            return
        give_picks.add(str(pick_id))
        for meth in ("_prune_terms", "_render_asset_lists",
                     "_update_slot_labels", "_render_deal_chips",
                     "_render_terms", "_schedule_evaluate"):
            fn = getattr(widget, meth, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

    def _next_pick_id(self):
        """ID of the user's next unmade draft pick, or None.

        Maps the draft board's overall pick number to the pick object
        in the user's ``draft_picks`` for the draft year.
        """
        try:
            from .draft import get_draft_state
            st = get_draft_state(self.game) or {}
        except Exception:
            return None
        ups = st.get("user_picks") or []
        if not ups:
            return None
        overall = int(ups[0])
        year = st.get("year")
        # Round from overall: 32 picks per round.
        rnd = (overall - 1) // 32 + 1
        gm = getattr(self.game, "game_manager", None) or self.game
        team = getattr(gm, "user_team", None)
        if team is None:
            return None
        try:
            by_year = dict(getattr(team, "draft_picks", None) or {})
            picks = list(by_year.get(year) or by_year.get(str(year)) or [])
        except Exception:
            return None
        for pk in picks:
            try:
                if int(getattr(pk, "round", -1) or -1) == rnd:
                    return str(getattr(pk, "id", "") or "")
            except Exception:
                continue
        return None

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _auto_refresh(self):
        # The wire streams live while the draft runs. Guard against the
        # screen being destroyed while the timer fires.
        try:
            self.refresh()
        except Exception:
            pass

    def _draft_active(self):
        """Meaningful when draft week is on or a draft session is live."""
        try:
            from .draft import get_draft_state
            if bool(get_draft_state(self.game).get("active")):
                return True
        except Exception:
            pass
        try:
            from .draft import available_prospects
            if available_prospects(self.game):
                return True
        except Exception:
            pass
        # Draft week fallback (Tkinter: is_draft_day June 23-25, buzz
        # window June 20-25).
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            d = getattr(gm, "current_date", None)
            if d is not None and getattr(d, "month", 0) == 6 \
                    and 20 <= getattr(d, "day", 0) <= 25:
                return True
        except Exception:
            pass
        return False

    def _clock_data(self):
        """(team, pickinfo) for the on-the-clock panel."""
        try:
            from .draft import get_draft_state
            st = get_draft_state(self.game) or {}
        except Exception:
            st = {}
        if not st.get("active"):
            gm = getattr(self.game, "game_manager", None) or self.game
            team = _safe(lambda: getattr(gm.user_team, "team_name", "")) \
                or "Your team"
            return (team,
                    "Your war room is ready — open the draft board to "
                    "make your picks.")
        cur = st.get("current_overall", 0) or 0
        owner = ""
        try:
            for b in (st.get("board") or []):
                if int(b.get("overall", -1)) == int(cur):
                    owner = str(b.get("owner", "") or "")
                    break
        except Exception:
            pass
        made = st.get("made_count", 0) or 0
        total = st.get("total_slots", 0) or 0
        info = f"Pick #{cur} of {total} · {made} made"
        ups = st.get("user_picks") or []
        if ups:
            info += f" · your next: #{ups[0]}"
        return (owner or "Draft in progress", info)

    def _prospect_rows(self, n=6):
        try:
            from .draft import available_prospects
            return (available_prospects(self.game) or [])[:n]
        except Exception:
            return []

    def _wire_lines(self):
        """Pick-by-pick wire from the live draft board; buzz when empty."""
        lines = []
        try:
            from .draft import get_draft_state
            st = get_draft_state(self.game) or {}
            for b in (st.get("board") or []):
                try:
                    if not b.get("made"):
                        continue
                    rec = b.get("prospect") or {}
                    pname = str(rec.get("name") or "?")
                    team = str(b.get("team") or b.get("owner") or "?")
                    lines.append(f"Pick #{b.get('overall')}: {team} "
                                 f"select {pname}")
                except Exception:
                    continue
            lines = lines[-30:]
        except Exception:
            lines = []
        if not lines:
            lines = ["The draft floor is buzzing. Picks will appear here "
                     "live,",
                     "selection by selection, as the night unfolds.",
                     "",
                     "Open the Draft Board to run your war room."]
            try:
                from .draft import buzz_items
                for item in (buzz_items(self.game) or [])[:4]:
                    text = item.get("text") if isinstance(item, dict) \
                        else str(item)
                    if text:
                        lines.append(f"BUZZ: {text}")
            except Exception:
                pass
        return lines

    def _deals_lines(self):
        try:
            from .draft import trade_feed
            deals = trade_feed(self.game) or []
        except Exception:
            deals = []
        if not deals:
            return ["No draft-day trades yet.",
                    "Pick swaps will be tracked here as they happen."]
        out = []
        for d in deals[:8]:
            text = d.get("text") if isinstance(d, dict) else str(d)
            if text:
                out.append(f"• {text}")
        return out or ["No draft-day trades yet."]

    def _snapshot_rows(self):
        prosp = self._prospect_rows(1000)
        if not prosp:
            return [("Prospects", "—")]
        from collections import Counter
        pos = Counter((p.get("position") or "?") for p in prosp)
        top3 = ", ".join(f"{k}: {v}" for k, v in pos.most_common(3))
        return [("Remaining prospects", str(len(prosp))),
                ("Top positions", top3 or "—"),
                ("Rounds", "7")]

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------
    def refresh(self):
        active = self._draft_active()
        self._empty.setVisible(not active)
        self._cols.setVisible(active)
        if active:
            self._tagline.setText(
                "Seven rounds. 224 picks. One future. Follow every "
                "selection live.")
            self._render_clock()
            self._render_prospects()
            self._render_wire()
            self._render_deals()
            self._render_snapshot()
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._tagline.setText("DRAFT DAY CENTRAL")
            self._timer.stop()

    # ------------------------------------------------------------------
    # render sections
    # ------------------------------------------------------------------
    def _render_clock(self):
        self._clear(self._clock_list)
        team, info = self._clock_data()
        t = QLabel(team)
        t.setStyleSheet("color: #e8ecf4; font-size: 16px; font-weight: bold;")
        t.setWordWrap(True)
        self._clock_list.addWidget(t)
        i = QLabel(info)
        i.setStyleSheet("color: #8a93a8; font-size: 12px;")
        i.setWordWrap(True)
        self._clock_list.addWidget(i)

    def _render_prospects(self):
        self._clear(self._prosp_list)
        cards = self._prospect_rows(6)
        if not cards:
            note = QLabel("No draft class generated yet.")
            note.setStyleSheet("color: #8a93a8; font-size: 13px;")
            self._prosp_list.addWidget(note)
            return
        for rank, p in enumerate(cards, 1):
            frame = QFrame()
            frame.setObjectName("tile")
            fl = QVBoxLayout(frame)
            fl.setSpacing(4)
            top = QHBoxLayout()
            r = QLabel(f"#{rank}")
            r.setStyleSheet("font-weight: bold; color: #e8b93c;")
            top.addWidget(r)
            name = QLabel(str(p.get("name") or "?"))
            name.setStyleSheet("font-weight: bold; font-size: 14px;")
            name.setWordWrap(True)
            top.addWidget(name, 1)
            meta = QLabel(f"{p.get('position') or '?'} · "
                          f"Age {p.get('age') or '?'} · "
                          f"OVR {p.get('overall') or '?'}")
            meta.setStyleSheet("color: #8a93a8; font-size: 12px;")
            top.addWidget(meta)
            fl.addLayout(top)

            mid = QHBoxLayout()
            pot = QLabel(f"POT {p.get('potential') or '—'}")
            pot.setStyleSheet("color: #7cc4ff; font-size: 12px; "
                              "font-weight: bold;")
            mid.addWidget(pot)
            fl.addLayout(mid)

            bot = QHBoxLayout()
            war = QPushButton("War room")
            war.setObjectName("primary-btn")
            war.clicked.connect(lambda _=False: self._navigate("draft"))
            bot.addWidget(war)
            fl.addLayout(bot)
            self._prosp_list.addWidget(frame)

    def _render_wire(self):
        self._clear(self._wire_list)
        for line in self._wire_lines():
            lbl = QLabel(line if line else " ")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #c7cede; font-size: 13px;")
            self._wire_list.addWidget(lbl)

    def _render_deals(self):
        self._clear(self._deals_list)
        for line in self._deals_lines():
            lbl = QLabel(line if line else " ")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #c7cede; font-size: 13px;")
            self._deals_list.addWidget(lbl)

    def _render_snapshot(self):
        self._clear(self._snap_list)
        for label, value in self._snapshot_rows():
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            row.addWidget(lab, 1)
            v = QLabel(value)
            v.setStyleSheet("color: #e8b93c; font-size: 13px; "
                            "font-weight: bold;")
            v.setWordWrap(True)
            row.addWidget(v)
            wrap = QWidget()
            wrap.setLayout(row)
            self._snap_list.addWidget(wrap)


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
