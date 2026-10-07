"""Media Center screen: native Qt port.

Ports main.py media_center_window.MediaCenterView (held back from the
Sept 27 merge; web-ui only had references in news.py).

Sections:
  - Journalists: media_engine reporters with relationship descriptors
  - Press conferences: upcoming/scheduled media events
  - Narratives & beefs: league.media_narratives, coach_media_beefs
  - Fines ledger: league.media_fines (same source as the fines tab)

Game data used (all real):
  - media_engine: ensure_media_state, reporters_for, Reporter
  - league.media_narratives, league.coach_media_beefs, league.media_fines
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


class MediaCenterScreen(BaseScreen):
    title = "Media Center"

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs, 1)

        # --- Tab 1: Journalists ---
        j_page = QWidget()
        j_layout = QVBoxLayout(j_page)
        j_note = QLabel(
            "The press corps covering your team. Relationships affect "
            "how stories are written.")
        j_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        j_note.setWordWrap(True)
        j_layout.addWidget(j_note)
        self._journalist_table = QTableWidget()
        self._journalist_table.setColumnCount(4)
        self._journalist_table.setHorizontalHeaderLabels(
            ["Journalist", "Outlet", "Style", "Relationship"])
        self._journalist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._journalist_table.setSelectionBehavior(QTableWidget.SelectRows)
        j_layout.addWidget(self._journalist_table, 1)
        self.tabs.addTab(j_page, "Journalists")

        # --- Tab 2: Press Conferences ---
        pc_page = QWidget()
        pc_layout = QVBoxLayout(pc_page)
        self._events_list = QListWidget()
        pc_layout.addWidget(self._events_list, 1)
        self.tabs.addTab(pc_page, "Press Conferences")

        # --- Tab 3: Narratives ---
        n_page = QWidget()
        n_layout = QVBoxLayout(n_page)
        self._narr_list = QListWidget()
        n_layout.addWidget(self._narr_list, 1)
        self.tabs.addTab(n_page, "Narratives")

        # --- Tab 4: Fines ---
        f_page = QWidget()
        f_layout = QVBoxLayout(f_page)
        self._fines_table = QTableWidget()
        self._fines_table.setColumnCount(4)
        self._fines_table.setHorizontalHeaderLabels(
            ["Date", "Player/Staff", "Amount", "Reason"])
        self._fines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._fines_table.setSelectionBehavior(QTableWidget.SelectRows)
        f_layout.addWidget(self._fines_table, 1)
        self.tabs.addTab(f_page, "Fines")

    @staticmethod
    def _relationship_descriptor(rel):
        try:
            r = float(rel)
        except (TypeError, ValueError):
            return str(rel or "—")
        if r >= 70:
            return "Friendly"
        if r >= 40:
            return "Neutral"
        return "Hostile"

    def refresh(self):
        gm = _resolve_gm(self.game)
        league = _safe(lambda: gm.league)
        team = _safe(lambda: gm.user_team)

        # Ensure media state exists
        try:
            import media_engine as me
            if league is not None:
                me.ensure_media_state(league)
        except Exception:
            pass

        # Journalists
        reporters = []
        try:
            import media_engine as me
            if hasattr(me, "reporters_for") and team is not None:
                reporters = me.reporters_for(team) or []
            elif league is not None:
                reporters = _safe(
                    lambda: list(getattr(league, "reporters", None) or []), [])
        except Exception:
            pass
        self._journalist_table.setRowCount(len(reporters))
        for i, r in enumerate(reporters):
            self._journalist_table.setItem(
                i, 0, QTableWidgetItem(
                    getattr(r, "name", str(r))))
            self._journalist_table.setItem(
                i, 1, QTableWidgetItem(
                    getattr(r, "outlet", getattr(r, "publication", "—"))))
            self._journalist_table.setItem(
                i, 2, QTableWidgetItem(
                    getattr(r, "style", getattr(r, "bias", "—"))))
            rel = getattr(r, "relationship", getattr(r, "rapport", None))
            self._journalist_table.setItem(
                i, 3, QTableWidgetItem(
                    self._relationship_descriptor(rel)))

        # Press conference events
        self._events_list.clear()
        events = []
        try:
            if league is not None:
                events = _safe(lambda: list(
                    getattr(league, "media_events", None)
                    or getattr(league, "press_conferences", None) or []), [])
        except Exception:
            pass
        for e in events[:50]:
            self._events_list.addItem(str(e))
        if not events:
            self._events_list.addItem("No scheduled press conferences.")

        # Narratives & beefs
        self._narr_list.clear()
        narrs = _safe(lambda: list(
            getattr(league, "media_narratives", None) or []), []) \
            if league is not None else []
        beefs = _safe(lambda: list(
            getattr(league, "coach_media_beefs", None) or []), []) \
            if league is not None else []
        for n in narrs:
            title = getattr(n, "title", getattr(n, "headline", str(n)))
            self._narr_list.addItem(f"📰 {title}")
        for b in beefs:
            self._narr_list.addItem(f"🥩 {b}")
        if not narrs and not beefs:
            self._narr_list.addItem("No active storylines.")

        # Fines ledger
        fines = _safe(lambda: list(
            getattr(league, "media_fines", None) or []), []) \
            if league is not None else []
        self._fines_table.setRowCount(len(fines))
        for i, f in enumerate(fines):
            if isinstance(f, dict):
                date = str(f.get("date", "—"))
                who = str(f.get("player", f.get("name", "—")))
                amt = f.get("amount", 0)
                reason = str(f.get("reason", "—"))
            else:
                date = str(getattr(f, "date", "—"))
                who = str(getattr(f, "player", getattr(f, "name", "—")))
                amt = getattr(f, "amount", 0)
                reason = str(getattr(f, "reason", "—"))
            try:
                amt_s = f"${int(amt):,}"
            except (TypeError, ValueError):
                amt_s = str(amt)
            self._fines_table.setItem(i, 0, QTableWidgetItem(date))
            self._fines_table.setItem(i, 1, QTableWidgetItem(who))
            self._fines_table.setItem(i, 2, QTableWidgetItem(amt_s))
            self._fines_table.setItem(i, 3, QTableWidgetItem(reason))
