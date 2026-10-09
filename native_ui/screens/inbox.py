"""Inbox screen: receive-only GM communications.

Native port of the web UI inbox (web_ui/templates/inbox.html +
web_ui/screens/inbox_actions.py + web_ui/static/js/inbox.js). Calls the
game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

RECEIVE-ONLY by Caleb's order (v0.26.16): no compose/reply/forward
anywhere on this screen.

Game methods used (same paths the web bridge's /api/command ops took):
  - inbox: team.inbox.messages / mark_all_read() / mark_message_read(mid) /
    delete_message(mid)
  - EmailMessage attrs: id, sender, sender_type, subject, content, category,
    date_sent, is_read, is_urgent, is_important, is_saved, requires_response,
    priority, action_type, action_data, action_done; is_overdue(),
    get_age_days()
  - trade_negotiation.accept_negotiation(app, neg_id) /
    trade_negotiation.decline_negotiation(app, neg_id)
  - app.accept_contract_counter(msg)
  - app._answer_bundle_presser(msg, q, a) / app._skip_bundle_presser(msg)
  - app._answer_bundle_team_talk(msg, option)
  - app._answer_bundle_instruction(msg, option_id)
  - app._answer_postmatch_presser(msg, q, a)
  - app.apply_rfa_qualifying_decision(msg, player_id, qualify)
  - app.apply_buyout_decision(msg, player_id, buyout)
  - app.apply_staff_renewal_decision(msg, staff_id, years_or_None)
  - media_engine.resolve_fine_appeal(app, action_data, choice)
  - app.apply_offer_sheet_match_decision(msg, match)
  - app.apply_offer_sheet_trade_alt_decision(msg, accept)
  - app.apply_arbitration_walkaway_decision(msg, walk_away)
  - app.advance_day() (gameday Quick Sim; fallback _on_continue_pressed)
"""

from native_ui.safe import safe_call
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QSplitter, QScrollArea, QFrame,
    QGroupBox, QTextEdit, QStackedWidget, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _fmt_money(v):
    try:
        return f"${int(v or 0):,}"
    except Exception:
        return "--"


def _resolve_gm(game):
    return safe_call(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: getattr(gm, "user_team", None))
            or safe_call(lambda: getattr(game, "user_team", None)))


def _user_league(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: getattr(gm, "league", None))
            or safe_call(lambda: getattr(game, "league", None)))


def _inbox_of(game):
    team = _user_team(game)
    return safe_call(lambda: getattr(team, "inbox", None))


def _all_messages(game):
    inbox = _inbox_of(game)
    return safe_call(lambda: list(getattr(inbox, "messages", None) or []),
                 []) or []


def _msg_id(m):
    return safe_call(lambda: str(getattr(m, "id", "")), "")


def _find_message(game, mid):
    mid_s = str(mid)
    for m in _all_messages(game):
        if _msg_id(m) == mid_s:
            return m
    return None


def _user_team_name(game):
    return safe_call(lambda: getattr(_user_team(game), "team_name", ""), "") or ""


def _today(game):
    gm = _resolve_gm(game)
    t = (safe_call(lambda: getattr(gm, "current_date", None))
         or safe_call(lambda: getattr(game, "current_date", None)))
    return t


def _today_iso(game):
    t = _today(game)
    try:
        if hasattr(t, "isoformat"):
            return t.isoformat()
    except Exception:
        pass
    return str(t or "")


# ---------------------------------------------------------------------------
# filters, indicators, search
# ---------------------------------------------------------------------------

_INBOX_FILTERS = [
    ("All", "all"), ("Unread", "unread"), ("Urgent", "urgent"),
    ("Saved", "saved"), ("Story", "story"),
    ("Trade", "Trade"), ("Scouting", "Scouting"),
    ("Contracts", "Contracts"), ("Injuries", "Injuries"),
    ("Media", "Media"), ("League", "League"),
]


def _filter_counts(game):
    """Live pill counts (desktop _FILTERS parity)."""
    counts = {}
    for m in _all_messages(game):
        try:
            cat = str(getattr(m, "category", "General") or "General")
            counts[cat] = counts.get(cat, 0) + 1
            if not bool(getattr(m, "is_read", True)):
                counts["unread"] = counts.get("unread", 0) + 1
            if bool(getattr(m, "is_urgent", False)):
                counts["urgent"] = counts.get("urgent", 0) + 1
            if bool(getattr(m, "is_saved", False)):
                counts["saved"] = counts.get("saved", 0) + 1
        except Exception:
            continue
    counts["all"] = len(_all_messages(game))
    return counts


def _matches_filter(m, fkey):
    try:
        if fkey == "all":
            return True
        if fkey == "unread":
            return not bool(getattr(m, "is_read", True))
        if fkey == "urgent":
            return bool(getattr(m, "is_urgent", False))
        if fkey == "saved":
            return bool(getattr(m, "is_saved", False))
        return str(getattr(m, "category", "General") or "General") == fkey
    except Exception:
        return False


def _matches_search(m, q):
    q = (q or "").strip().lower()
    if not q:
        return True
    hay = " ".join([
        str(getattr(m, "sender", "") or ""),
        str(getattr(m, "subject", "") or ""),
        str(getattr(m, "content", "") or "")[:2000],
    ]).lower()
    return q in hay


def _indicator(m):
    """red = action needed, gold = urgent/important, blue = unread."""
    try:
        if bool(safe_call(lambda: m.is_overdue(), False)):
            return "red"
        if bool(getattr(m, "requires_response", False)):
            return "red"
        prio = safe_call(lambda: int(getattr(m, "priority", 1) or 1), 1)
        if bool(getattr(m, "is_urgent", False)) or prio >= 4:
            return "gold"
        if bool(getattr(m, "is_important", False)) or prio >= 3:
            return "gold"
        if not bool(getattr(m, "is_read", False)):
            return "blue"
    except Exception:
        pass
    return "none"


_IND_COLORS = {"red": "#ef4444", "gold": "#f59e0b", "blue": "#3B82F6"}


def _date_label(m):
    try:
        age = int(safe_call(lambda: m.get_age_days(), 0) or 0)
    except Exception:
        age = 0
    if age <= 0:
        return "Today"
    if age == 1:
        return "Yesterday"
    try:
        return m.date_sent.strftime("%m/%d")
    except Exception:
        return ""


def _snippet(m, n=120):
    return safe_call(
        lambda: (getattr(m, "content", "") or "").replace("\n", " "
                ).strip()[:n], "")


# ---------------------------------------------------------------------------
# special actions (fantasy draft / lottery reveal header buttons)
# ---------------------------------------------------------------------------

def _special_action(game, m):
    """Port of bridge._inbox_special_action: 'fantasy_draft',
    'lottery_reveal', or ''."""
    try:
        gm = _resolve_gm(game)
        subject = str(getattr(m, "subject", "") or "").upper()
        sender_type = str(getattr(m, "sender_type", "") or "")
        if "DRAFT RECAP" in subject and sender_type == "League":
            return "draft_recap"
        if ("FANTASY DRAFT" in subject and sender_type == "League"
                and gm is not None
                and bool(getattr(gm, "pending_fantasy_draft", False))):
            return "fantasy_draft"
        pending = getattr(gm, "_pending_lottery_reveal", None) if gm else None
        if ("DRAFT LOTTERY" in subject and sender_type == "Media"
                and pending):
            return "lottery_reveal"
    except Exception:
        pass
    return ""


def _gameday_is_preseason(game, team, today):
    """Mirror of inbox_window._is_preseason_game_day."""
    try:
        if team is None or today is None:
            return False
        gm = _resolve_gm(game)
        league = safe_call(lambda: getattr(gm, "league", None))
        tname = safe_call(lambda: getattr(team, "team_name", ""))
        for item in (getattr(league, "schedule", None) or []):
            try:
                if isinstance(item, dict):
                    d, h, a = (item.get("date"), item.get("home_team"),
                               item.get("away_team"))
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    d, h, a = item[0], item[1], item[2]
                else:
                    continue
                hn = getattr(h, "team_name", h) if h else ""
                an = getattr(a, "team_name", a) if a else ""
                if d == today and (h is team or a is team
                                   or hn == tname or an == tname):
                    return bool(item.get("preseason")) \
                        if isinstance(item, dict) else False
            except Exception:
                continue
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# story view (ported from web_ui/screens/inbox_actions.py)
# ---------------------------------------------------------------------------

_STORY_KIND_ICONS = {
    "rivalry": "🔥", "milestone": "🏆", "controversy": "⚡",
    "streak": "📈", "trade": "🔄", "injury": "🩹",
}


def _story_developing(game):
    """Live narrative state: active storylines + hot rivalries."""
    items = []
    gm = _resolve_gm(game)
    league = _user_league(game)
    now = safe_call(lambda: getattr(gm, "current_date", None))
    try:
        for n in (getattr(league, "media_narratives", None) or []):
            try:
                heat = float(getattr(n, "heat", 0) or 0)
                kind = str(getattr(n, "kind", "") or "")
                items.append({
                    "icon": _STORY_KIND_ICONS.get(kind, "📰"),
                    "title": str(getattr(n, "title",
                                        "Developing storyline") or ""),
                    "desc": f"{getattr(n, 'team_name', '')} · "
                            f"heat {heat:.0f}/100",
                    "heat": heat,
                })
            except Exception:
                continue
    except Exception:
        pass
    try:
        ms = safe_call(lambda: getattr(gm, "media_system", None))
        for s in (getattr(ms, "storylines", None) or []):
            try:
                try:
                    active = s.is_active(now) if now is not None else True
                except Exception:
                    active = True
                if not active:
                    continue
                inten = int(getattr(s, "intensity", 5) or 5)
                items.append({
                    "icon": "📰",
                    "title": str(getattr(s, "title", "") or "Storyline"),
                    "desc": f"intensity {inten}/10",
                    "heat": inten * 10.0,
                })
            except Exception:
                continue
    except Exception:
        pass
    try:
        seen = set()
        for r in (getattr(league, "rivalries", None) or []):
            try:
                if not isinstance(r, dict) or r.get("kind") != "team_team":
                    continue
                heat = float(r.get("intensity", 0) or 0)
                if heat < 50:
                    continue
                key = (r.get("a"), r.get("b"))
                if key in seen:
                    continue
                seen.add(key)
                label = "Bad blood" if heat >= 65 else "Heated"
                items.append({
                    "icon": "🔥",
                    "title": f"{r.get('a_name') or '?'} vs "
                            f"{r.get('b_name') or '?'}",
                    "desc": f"{label} · {heat:.0f}/100",
                    "heat": heat,
                })
            except Exception:
                continue
    except Exception:
        pass
    items.sort(key=lambda d: d.get("heat", 0), reverse=True)
    return items[:8]


def _story_feed(game, limit=60):
    """Chronological backbone: recent Media/League messages."""
    out = []
    try:
        msgs = [m for m in _all_messages(game)
                if str(getattr(m, "category", "") or "")
                in ("Media", "League")]
    except Exception:
        return out

    def _d(m):
        return (safe_call(lambda: getattr(m, "game_date_sent", None))
                or safe_call(lambda: getattr(m, "date_sent", None)))

    try:
        msgs.sort(key=lambda m: (_d(m) is None, _d(m)), reverse=True)
    except Exception:
        pass
    return msgs[:limit]


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        w = child.widget()
        if w is not None:
            w.deleteLater()
        sub = child.layout()
        if sub is not None:
            _clear_layout(sub)

# =====================================================================
# InboxScreen
# =====================================================================

class InboxScreen(BaseScreen):
    """Receive-only GM inbox: filters, search, two-pane reader, and the
    full set of per-message interactive action buttons. NO compose."""

    title = "Inbox"

    def __init__(self, game, main_window, parent=None):
        self._filter = "all"
        self._search = ""
        self._open_id = None
        self._pill_buttons = {}
        super().__init__(game, main_window, parent)

    # -- layout -------------------------------------------------------

    def _build_body(self):
        # legend (red = action needed, gold = urgent, blue = unread)
        legend = QHBoxLayout()
        legend.setSpacing(16)
        for color, text in (("#ef4444", "Action needed"),
                            ("#f59e0b", "Urgent"),
                            ("#3B82F6", "Unread")):
            lab = QLabel(f'<span style="color:{color}">●</span> {text}')
            lab.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            legend.addWidget(lab)
        legend.addStretch()
        self._layout.addLayout(legend)

        # toolbar: category pills + search + mark-all-read
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        pill_scroll = QScrollArea()
        pill_scroll.setWidgetResizable(True)
        pill_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pill_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pill_scroll.setFixedHeight(40)
        pill_host = QWidget()
        self._pill_layout = QHBoxLayout(pill_host)
        self._pill_layout.setContentsMargins(0, 4, 0, 4)
        self._pill_layout.setSpacing(6)
        pill_scroll.setWidget(pill_host)
        toolbar.addWidget(pill_scroll, 1)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search messages…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setMaximumWidth(260)
        self._search_box.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_box)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._apply_search)

        mark_all = QPushButton("Mark all read")
        mark_all.clicked.connect(self._on_mark_all_read)
        toolbar.addWidget(mark_all)
        self._layout.addLayout(toolbar)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._layout.addWidget(self._count_lbl)

        # pages: 0 = normal two-pane, 1 = story view
        self._pages = QStackedWidget()
        self._layout.addWidget(self._pages, 1)

        # -- page 0: list + reader --
        splitter = QSplitter(Qt.Horizontal)
        self._list = QListWidget()
        self._list.setMinimumWidth(360)
        self._list.itemClicked.connect(self._on_row_clicked)
        splitter.addWidget(self._list)

        self._reader = self._build_reader()
        splitter.addWidget(self._reader)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self._pages.addWidget(splitter)

        # -- page 1: story view --
        self._story_page = QScrollArea()
        self._story_page.setWidgetResizable(True)
        self._story_host = QWidget()
        self._story_layout = QVBoxLayout(self._story_host)
        self._story_layout.setSpacing(10)
        self._story_page.setWidget(self._story_host)
        self._pages.addWidget(self._story_page)

    def _build_reader(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setSpacing(8)

        self._r_meta = QLabel("")
        self._r_meta.setWordWrap(True)
        self._r_meta.setStyleSheet("color: #c8d0e0; font-size: 13px;")
        layout.addWidget(self._r_meta)

        self._r_body = QTextEdit()
        self._r_body.setReadOnly(True)
        self._r_body.setMinimumHeight(160)
        layout.addWidget(self._r_body)

        # dynamic per-message action buttons (the core of this screen)
        self._r_actions = QWidget()
        self._r_actions_layout = QVBoxLayout(self._r_actions)
        self._r_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._r_actions_layout.setSpacing(8)
        layout.addWidget(self._r_actions)

        # reader buttons: save / important / read / delete
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._r_save = QPushButton("Save")
        self._r_save.clicked.connect(self._on_toggle_save)
        btn_row.addWidget(self._r_save)
        self._r_important = QPushButton("Mark important")
        self._r_important.clicked.connect(self._on_toggle_important)
        btn_row.addWidget(self._r_important)
        self._r_read = QPushButton("Mark as read")
        self._r_read.clicked.connect(self._on_toggle_read)
        btn_row.addWidget(self._r_read)
        self._r_delete = QPushButton("Delete")
        self._r_delete.setStyleSheet("color: #f87171;")
        self._r_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(self._r_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        page.setWidget(host)
        page.setVisible(False)
        return page

    # -- data loading -------------------------------------------------

    def refresh(self):
        self._rebuild_pills()
        if self._filter == "story":
            self._show_story()
        else:
            self._pages.setCurrentIndex(0)
            self._reload_list()
        if self._open_id is not None:
            m = _find_message(self.game, self._open_id)
            if m is not None:
                self._paint_reader(m)
            else:
                self._close_reader()

    def _rebuild_pills(self):
        counts = _filter_counts(self.game)
        for key in list(self._pill_buttons):
            btn = self._pill_buttons.pop(key)
            self._pill_layout.removeWidget(btn)
            btn.deleteLater()
        for label, key in _INBOX_FILTERS:
            n = counts.get(key)
            text = f"{label} ({n})" if n is not None else label
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setChecked(key == self._filter)
            btn.setProperty("pill_key", key)
            btn.clicked.connect(self._on_pill_clicked)
            self._pill_layout.addWidget(btn)
            self._pill_buttons[key] = btn

    def _visible_messages(self):
        q = (self._search or "").strip()
        if q:
            return [m for m in _all_messages(self.game)
                    if _matches_search(m, q)]
        return [m for m in _all_messages(self.game)
                if _matches_filter(m, self._filter)]

    def _reload_list(self):
        msgs = self._visible_messages()
        if self._search.strip():
            self._count_lbl.setText(
                f'{len(msgs)} result{"s" if len(msgs) != 1 else ""} '
                f'for "{self._search.strip()}"')
        else:
            self._count_lbl.setText(
                f'{len(msgs)} message{"s" if len(msgs) != 1 else ""}')
        self._list.clear()
        if not msgs:
            item = QListWidgetItem("Nothing here. Enjoy the quiet.")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self._list.addItem(item)
            return
        for m in msgs:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, _msg_id(m))
            row = self._make_row(m)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _make_row(self, m):
        """Gmail-style row: indicator bar, sender/subject, flags, date."""
        row = QFrame()
        row.setFrameShape(QFrame.NoFrame)
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(8)

        ind = _indicator(m)
        bar = QLabel("┃")
        bar.setStyleSheet(
            f"color: {_IND_COLORS.get(ind, '#2a3140')}; font-size: 18px;")
        h.addWidget(bar)

        text = QVBoxLayout()
        text.setSpacing(1)
        sender = str(getattr(m, "sender", "") or "(no sender)")
        subject = str(getattr(m, "subject", "") or "(no subject)")
        snip = _snippet(m)
        bold = "" if bool(getattr(m, "is_read", False)) else "font-weight: bold;"
        s_lbl = QLabel(f'<span style="{bold}">{_esc(sender)}</span>')
        s_lbl.setStyleSheet("font-size: 13px;")
        text.addWidget(s_lbl)
        subj_html = f'<span style="{bold}">{_esc(subject)}</span>'
        if snip:
            subj_html += f' <span style="color:#8b95ab">— {_esc(snip)}</span>'
        j_lbl = QLabel(subj_html)
        j_lbl.setWordWrap(True)
        j_lbl.setStyleSheet("font-size: 12px;")
        text.addWidget(j_lbl)
        h.addLayout(text, 1)

        # flag buttons (★ save, ❗ important)
        flags = QHBoxLayout()
        flags.setSpacing(2)
        saved = bool(getattr(m, "is_saved", False))
        important = bool(getattr(m, "is_important", False))
        star = QPushButton("★")
        star.setFlat(True)
        star.setToolTip("Save")
        star.setStyleSheet(
            f"color: {'#f59e0b' if saved else '#4a5468'}; font-size: 14px;")
        mid = _msg_id(m)
        star.clicked.connect(lambda _c, i=mid: self._toggle_flag(i, "saved"))
        flags.addWidget(star)
        bang = QPushButton("❗")
        bang.setFlat(True)
        bang.setToolTip("Important")
        bang.setStyleSheet("font-size: 13px;")
        bang.setEnabled(important)
        bang.clicked.connect(
            lambda _c, i=mid: self._toggle_flag(i, "important"))
        flags.addWidget(bang)
        h.addLayout(flags)

        right = QVBoxLayout()
        right.setSpacing(1)
        d_lbl = QLabel(_date_label(m))
        d_lbl.setStyleSheet("color: #8b95ab; font-size: 12px;")
        d_lbl.setAlignment(Qt.AlignRight)
        right.addWidget(d_lbl)
        if bool(getattr(m, "requires_response", False)) or bool(
                safe_call(lambda: m.is_overdue(), False)):
            pill = QLabel("Action needed")
            pill.setStyleSheet(
                "color: #ef4444; border: 1px solid #ef4444; border-radius: 8px;"
                " padding: 1px 6px; font-size: 11px;")
            pill.setAlignment(Qt.AlignRight)
            right.addWidget(pill)
        h.addLayout(right)
        return row

    # -- toolbar handlers ----------------------------------------------

    def _on_pill_clicked(self):
        btn = self.sender()
        if btn is None:
            return
        key = btn.property("pill_key")
        self._filter = key
        for k, b in self._pill_buttons.items():
            b.setChecked(k == key)
        if key == "story":
            self._show_story()
        else:
            self._pages.setCurrentIndex(0)
            self._reload_list()

    def _on_search_changed(self, text):
        self._search = text
        self._search_timer.start()

    def _apply_search(self):
        self._pages.setCurrentIndex(0)
        self._reload_list()

    def _on_mark_all_read(self):
        try:
            inbox = _inbox_of(self.game)
            if inbox is not None:
                inbox.mark_all_read()
        except Exception:
            pass
        self.refresh()

    def _toggle_flag(self, mid, flag):
        m = _find_message(self.game, mid)
        if m is None:
            return
        try:
            if flag == "saved":
                m.is_saved = not bool(getattr(m, "is_saved", False))
            elif flag == "important":
                m.is_important = not bool(
                    getattr(m, "is_important", False))
        except Exception:
            pass
        self._reload_list()
        if str(self._open_id) == str(mid):
            self._paint_reader(m)

    # -- reader ---------------------------------------------------------

    def _on_row_clicked(self, item):
        mid = item.data(Qt.UserRole)
        if not mid:
            return
        m = _find_message(self.game, mid)
        if m is not None:
            self._open_message(m)

    def _open_message(self, m):
        self._open_id = _msg_id(m)
        self._paint_reader(m)
        self._reader.setVisible(True)

    def _close_reader(self):
        self._open_id = None
        self._reader.setVisible(False)

    def _paint_reader(self, m):
        sender = str(getattr(m, "sender", "") or "(no sender)")
        subject = str(getattr(m, "subject", "") or "(no subject)")
        category = str(getattr(m, "category", "General") or "General")
        try:
            date_s = m.date_sent.strftime("%b %d, %Y")
        except Exception:
            date_s = _date_label(m)
        self._r_meta.setText(
            f"<b>From:</b> {_esc(sender)}<br>"
            f"<b>Date:</b> {_esc(date_s)}<br>"
            f"<b>Subject:</b> {_esc(subject)}<br>"
            f"<b>Category:</b> {_esc(category)}")
        content = str(getattr(m, "content", "") or "") or _snippet(m, 2000) \
            or "(no content)"
        self._r_body.setPlainText(content)

        saved = bool(getattr(m, "is_saved", False))
        important = bool(getattr(m, "is_important", False))
        self._r_save.setText("Unsave" if saved else "Save")
        self._r_important.setText(
            "Unmark important" if important else "Mark important")
        self._r_read.setText(
            "Mark as unread" if bool(getattr(m, "is_read", False))
            else "Mark as read")

        _clear_layout(self._r_actions_layout)
        self._build_special(self._r_actions_layout, m)
        self._build_actions(self._r_actions_layout, m)

    def _current_message(self):
        if self._open_id is None:
            return None
        return _find_message(self.game, self._open_id)

    def _on_toggle_save(self):
        m = self._current_message()
        if m is not None:
            self._toggle_flag(_msg_id(m), "saved")

    def _on_toggle_important(self):
        m = self._current_message()
        if m is not None:
            self._toggle_flag(_msg_id(m), "important")

    def _on_toggle_read(self):
        m = self._current_message()
        if m is None:
            return
        try:
            inbox = _inbox_of(self.game)
            if bool(getattr(m, "is_read", False)):
                m.is_read = False
                try:
                    m.date_read = None
                except Exception:
                    pass
            elif inbox is not None:
                inbox.mark_message_read(_msg_id(m))
        except Exception:
            pass
        self._paint_reader(m)
        self._reload_list()

    def _on_delete(self):
        m = self._current_message()
        if m is None:
            return
        try:
            inbox = _inbox_of(self.game)
            if inbox is not None:
                inbox.delete_message(_msg_id(m))
        except Exception:
            pass
        self._close_reader()
        self.refresh()

    # -- story view -------------------------------------------------------

    def _show_story(self):
        self._pages.setCurrentIndex(1)
        self._count_lbl.setText("Season story")
        _clear_layout(self._story_layout)

        developing = _story_developing(self.game)
        h = QLabel("DEVELOPING STORYLINES")
        h.setObjectName("section-header")
        self._story_layout.addWidget(h)
        if developing:
            for s in developing:
                card = QGroupBox()
                cl = QVBoxLayout(card)
                title = QLabel(f"{s.get('icon', '📰')}  {s.get('title', '')}")
                title.setStyleSheet("font-weight: bold; font-size: 14px;")
                title.setWordWrap(True)
                cl.addWidget(title)
                desc = QLabel(s.get("desc", ""))
                desc.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                desc.setWordWrap(True)
                cl.addWidget(desc)
                self._story_layout.addWidget(card)
        else:
            empty = QLabel("No storylines yet — check back as the season "
                           "develops.")
            empty.setStyleSheet("color: #8b95ab; font-size: 13px;")
            self._story_layout.addWidget(empty)

        h2 = QLabel("STORY FEED")
        h2.setObjectName("section-header")
        self._story_layout.addWidget(h2)
        feed = _story_feed(self.game)
        if feed:
            for m in feed:
                row = QPushButton()
                row.setFlat(True)
                row.setStyleSheet("text-align: left; padding: 6px;")
                sender = str(getattr(m, "sender", "") or "")
                subject = str(getattr(m, "subject", "") or "")
                snip = _snippet(m, 90)
                bold = "font-weight: bold;" \
                    if not bool(getattr(m, "is_read", False)) else ""
                row.setText(
                    f'<div style="{bold}">{sender} — {subject}'
                    f' <span style="color:#8b95ab">— {snip}</span></div>'
                    f'<div style="color:#8b95ab; font-size:11px">'
                    f'{_date_label(m)}</div>')
                mid = _msg_id(m)
                row.clicked.connect(
                    lambda _c, i=mid: self._open_story_message(i))
                self._story_layout.addWidget(row)
        else:
            empty = QLabel("No media or league messages yet.")
            empty.setStyleSheet("color: #8b95ab; font-size: 13px;")
            self._story_layout.addWidget(empty)
        self._story_layout.addStretch()

    def _open_story_message(self, mid):
        m = _find_message(self.game, mid)
        if m is None:
            return
        self._pages.setCurrentIndex(0)
        self._open_message(m)

    # -- reader action buttons --------------------------------------------

    def _build_special(self, layout, m):
        sa = _special_action(self.game, m)
        if sa == "draft_recap":
            btn = QPushButton("▶  VIEW DRAFT RECAP")
            btn.setObjectName("primary-btn")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda: self.navigate_to("draft_recap"))
            layout.addWidget(btn)
        elif sa == "fantasy_draft":
            btn = QPushButton("▶  START FANTASY DRAFT")
            btn.setObjectName("primary-btn")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda: self.navigate_to("fantasy_draft"))
            layout.addWidget(btn)
        elif sa == "lottery_reveal":
            btn = QPushButton("▶  WATCH THE REVEAL")
            btn.setObjectName("primary-btn")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda: self.navigate_to("lottery"))
            layout.addWidget(btn)

    def _ia_btn(self, layout, label, callback, primary=False):
        btn = QPushButton(label)
        if primary:
            btn.setObjectName("primary-btn")
        btn.clicked.connect(callback)
        layout.addWidget(btn)
        return btn

    def _ia_section(self, layout, title):
        head = QLabel(title.upper())
        head.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                           "font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(head)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(6)
        layout.addWidget(box)
        return bl

    def _ia_note(self, layout, text):
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet("color: #9aa4b8; font-size: 12px; font-style: italic;")
        layout.addWidget(lab)

    def _ia_line(self, layout, text):
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet("font-size: 13px;")
        layout.addWidget(lab)

    def _build_actions(self, layout, m):
        at = safe_call(lambda: getattr(m, "action_type", None))
        if not at:
            return
        done = bool(safe_call(lambda: getattr(m, "action_done", False), False))
        d = safe_call(lambda: getattr(m, "action_data", None) or {}, {}) or {}
        builder = {
            "trade_offer": self._actions_trade,
            "trade_counter": self._actions_trade,
            "contract_counter": self._actions_contract,
            "game_day": self._actions_gameday,
            "postmatch_presser": self._actions_postmatch,
            "rfa_qualifying": self._actions_rfa,
            "buyout_window": self._actions_buyout,
            "staff_renewal": self._actions_staff,
            "media_fine_response": self._actions_fine,
            "offer_sheet_match": self._actions_offer_match,
            "offer_sheet_trade_alt": self._actions_offer_trade,
            "arbitration_walkaway": self._actions_arbitration,
        }.get(at)
        if builder is not None:
            try:
                builder(layout, m, d, done)
            except Exception:
                pass

    def _after_action(self):
        """Re-render the reader in place after an action ran."""
        mid = self._open_id
        m = _find_message(self.game, mid) if mid else None
        if m is not None:
            self._paint_reader(m)
        self._reload_list()

    # -- trade ------------------------------------------------------------

    def _actions_trade(self, layout, m, d, done):
        at = safe_call(lambda: getattr(m, "action_type", ""))
        if done:
            self._ia_note(layout, "This negotiation is no longer on the "
                                  "table.")
            return
        neg_id = d.get("negotiation_id")
        accept_label = "Accept Counter" if at == "trade_counter" \
            else "Accept Trade"
        decline_label = "Walk Away" if at == "trade_counter" else "Decline"

        def _accept():
            try:
                import trade_negotiation as tn
                if neg_id:
                    tn.accept_negotiation(self.game, neg_id)
                m.action_done = True
            except Exception:
                pass
            self._after_action()

        def _decline():
            try:
                import trade_negotiation as tn
                if neg_id:
                    tn.decline_negotiation(self.game, neg_id)
                m.action_done = True
            except Exception:
                pass
            self._after_action()

        row = QHBoxLayout()
        row.setSpacing(8)
        acc = QPushButton(accept_label)
        acc.setObjectName("primary-btn")
        acc.clicked.connect(_accept)
        row.addWidget(acc)
        dec = QPushButton(decline_label)
        dec.clicked.connect(_decline)
        row.addWidget(dec)
        review = QPushButton("Review & Adjust")
        review.clicked.connect(lambda: self.navigate_to("trades"))
        row.addWidget(review)
        layout.addLayout(row)

    # -- contract counter ---------------------------------------------------

    def _actions_contract(self, layout, m, d, done):
        if done:
            self._ia_note(layout, "This negotiation is closed.")
            return

        def _accept():
            try:
                fn = getattr(self.game, "accept_contract_counter", None)
                if callable(fn):
                    fn(m)
                m.action_done = True
            except Exception:
                pass
            self._after_action()

        def _walkaway():
            try:
                m.action_done = True
            except Exception:
                pass
            self._after_action()

        row = QHBoxLayout()
        row.setSpacing(8)
        acc = QPushButton("Accept")
        acc.setObjectName("primary-btn")
        acc.clicked.connect(_accept)
        row.addWidget(acc)
        new = QPushButton("Make New Offer")
        new.clicked.connect(lambda: self.navigate_to("contracts"))
        row.addWidget(new)
        walk = QPushButton("Walk Away")
        walk.clicked.connect(_walkaway)
        row.addWidget(walk)
        layout.addLayout(row)

    # -- game day -----------------------------------------------------------

    def _actions_gameday(self, layout, m, d, done):
        self._ia_line(layout,
                      f"Game Day: {d.get('away', '')} @ {d.get('home', '')}")
        team = _user_team(self.game)
        today = _today_iso(self.game)
        preseason = _gameday_is_preseason(self.game, team, _today(self.game))
        stale = bool(d.get("game_date") and today
                     and d.get("game_date") != today)
        if stale or done:
            self._ia_note(layout, "This game has already been played — "
                                  "these options are no longer available.")
            return

        # pre-match presser
        sec = self._ia_section(layout, "Pre-match presser")
        questions = d.get("presser") or []
        answered = d.get("presser_answered") or []
        reactions = d.get("presser_reactions") or {}
        all_answered = (len(questions) > 0
                        and len(answered) >= len(questions)
                        and all(answered))
        if not all_answered and questions:
            self._ia_btn(sec, "⏩ Skip presser", lambda: self._presser_skip(m))
        if d.get("presser_skipped"):
            self._ia_note(sec, "✓ Skipped — no comment for the press today.")
        else:
            for qi, q in enumerate(questions):
                is_a = qi < len(answered) and bool(answered[qi])
                self._ia_line(sec, f"Q{qi + 1}: {q.get('question', '')}")
                self._ia_note(sec, f"— {q.get('journalist', '')}")
                if is_a:
                    self._ia_note(sec, "✓ Answered")
                    react = reactions.get(str(qi), reactions.get(qi))
                    if react:
                        self._ia_note(sec, f"“{react}”")
                else:
                    qrow = QHBoxLayout()
                    qrow.setSpacing(6)
                    for ai, a in enumerate(q.get("answers") or []):
                        b = QPushButton(str(a.get("label", "")))
                        b.clicked.connect(
                            lambda _c, qq=qi, aa=ai, mm=m:
                            self._presser_answer(mm, qq, aa))
                        qrow.addWidget(b)
                    qrow.addStretch()
                    sec.addLayout(qrow)

        # team talk
        sec = self._ia_section(layout, "Dressing room: team talk")
        talks = d.get("talk_options") or []
        if d.get("talk_chosen") is not None:
            opt = talks[d["talk_chosen"]] if 0 <= int(
                d["talk_chosen"]) < len(talks) else {}
            self._ia_note(sec, f"✓ “{opt.get('label', '')}”")
            if d.get("talk_reaction"):
                self._ia_note(sec, f"“{d['talk_reaction']}”")
        else:
            self._ia_note(sec, "Rally the room before puck drop:")
            for oi, opt in enumerate(talks):
                fit = {"good": " ✓ looks ideal",
                       "risky": " ⚠ risky"}.get(opt.get("fit"), "")
                btn = QPushButton(f"{opt.get('label', '')}{fit}")
                btn.clicked.connect(
                    lambda _c, o=oi, mm=m: self._team_talk(mm, o))
                sec.addWidget(btn)
                note = QLabel(f"“{opt.get('text', '')}”")
                note.setWordWrap(True)
                note.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                sec.addWidget(note)

        # coach's instruction
        sec = self._ia_section(layout, "Coach's instruction")
        instrs = d.get("instruction_options") or []
        if d.get("instruction_chosen") is not None:
            chosen = next((o for o in instrs
                           if o.get("id") == d["instruction_chosen"]), {})
            self._ia_note(
                sec, f"✓ “{chosen.get('label', d['instruction_chosen'])}”")
        else:
            self._ia_note(sec, "The bench's marching orders for tonight:")
            for o in instrs:
                btn = QPushButton(str(o.get("label", "")))
                btn.clicked.connect(
                    lambda _c, oid=o.get("id"), mm=m:
                    self._instruction(mm, oid))
                sec.addWidget(btn)
                note = QLabel(f"“{o.get('text', '')}”")
                note.setWordWrap(True)
                note.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                sec.addWidget(note)

        # watch / quick
        sec = self._ia_section(layout, "How to play tonight")
        qrow = QHBoxLayout()
        qrow.setSpacing(8)
        watch_btn = QPushButton("▶ Watch Live")
        watch_btn.setObjectName("primary-btn")
        watch_btn.clicked.connect(lambda: self._gameday_resolve(m, True))
        if preseason:
            watch_btn.setEnabled(False)
            watch_btn.setToolTip("Preseason exhibitions aren't watchable")
        qrow.addWidget(watch_btn)
        quick_btn = QPushButton("⚡ Quick Sim")
        quick_btn.clicked.connect(lambda: self._gameday_resolve(m, False))
        qrow.addWidget(quick_btn)
        qrow.addStretch()
        sec.addLayout(qrow)
        if preseason:
            self._ia_note(sec, "Preseason exhibitions aren't watchable — "
                               "they're quick-simmed and no stats are "
                               "recorded.")

    def _presser_answer(self, m, q, a):
        try:
            self.game._answer_bundle_presser(m, int(q), int(a))
        except Exception:
            pass
        self._after_action()

    def _presser_skip(self, m):
        try:
            self.game._skip_bundle_presser(m)
        except Exception:
            pass
        self._after_action()

    def _team_talk(self, m, option):
        try:
            self.game._answer_bundle_team_talk(m, int(option))
        except Exception:
            pass
        self._after_action()

    def _instruction(self, m, option_id):
        try:
            self.game._answer_bundle_instruction(m, option_id)
        except Exception:
            pass
        self._after_action()

    def _resolve_gameday_bundle(self, m, watch):
        """Native port of bridge._resolve_gameday_bundle (desktop
        HockeyManagerGUI._resolve_game_day parity): mark the bundle done,
        record the GM's choices in app._game_day_resolution for the day
        advance, and let the day advance consume them."""
        app = self.game
        try:
            data = getattr(m, "action_data", None) or {}
            try:
                talk_boost = float(data.get("talk_boost", 1.0) or 1.0)
            except Exception:
                talk_boost = 1.0
            instruction = data.get("instruction_chosen")
            try:
                m.action_done = True
            except Exception:
                pass
            today = (safe_call(lambda: app.game_manager.current_date)
                     or safe_call(lambda: getattr(app, "current_date", None)))
            try:
                app._game_day_resolution = {
                    "watch": bool(watch), "talk_boost": talk_boost,
                    "instruction": instruction, "date": today,
                    "web": True,
                }
            except Exception:
                pass
            try:
                app._continue_after_bundle = True
            except Exception:
                pass
        except Exception:
            pass

    def _gameday_resolve(self, m, watch):
        self._resolve_gameday_bundle(m, watch)
        if watch:
            self.navigate_to("watch")
            return
        try:
            app = self.game
            fn = (getattr(app, "advance_day", None)
                  or getattr(app, "_on_continue_pressed", None)
                  or getattr(app, "_on_continue", None))
            if callable(fn):
                fn()
        except Exception:
            pass
        self._close_reader()
        self.refresh()
        try:
            self.navigate_to("hub")
        except Exception:
            pass

    # -- post-match presser -------------------------------------------------

    def _actions_postmatch(self, layout, m, d, done):
        self._ia_line(layout, "Post-match presser")
        questions = d.get("questions") or []
        answered = d.get("answered") or []
        reactions = d.get("reactions") or {}
        for qi, q in enumerate(questions):
            is_a = qi < len(answered) and bool(answered[qi])
            self._ia_line(layout, f"Q{qi + 1}: {q.get('question', '')}")
            self._ia_note(layout, f"— {q.get('journalist', '')}")
            if is_a:
                self._ia_note(layout, "✓ Answered")
                react = reactions.get(str(qi), reactions.get(qi))
                if react:
                    self._ia_note(layout, f"“{react}”")
            elif not done:
                qrow = QHBoxLayout()
                qrow.setSpacing(6)
                for ai, a in enumerate(q.get("answers") or []):
                    b = QPushButton(str(a.get("label", "")))
                    b.clicked.connect(
                        lambda _c, qq=qi, aa=ai, mm=m:
                        self._postmatch_answer(mm, qq, aa))
                    qrow.addWidget(b)
                qrow.addStretch()
                layout.addLayout(qrow)
        if done or (answered and all(answered)):
            self._ia_note(layout, "Presser complete — the story is filed.")

    def _postmatch_answer(self, m, q, a):
        try:
            self.game._answer_postmatch_presser(m, int(q), int(a))
        except Exception:
            pass
        self._after_action()

    # -- RFA qualifying -----------------------------------------------------

    def _actions_rfa(self, layout, m, d, done):
        self._ia_line(layout, "Qualifying offers")
        decided = d.get("decided") or {}
        rem = [c for c in (d.get("cards") or [])
               if str(c.get("player_id")) not in decided]
        if done or not rem:
            self._ia_note(layout, "All qualifying decisions are in.")
            return
        for c in rem:
            sec = self._ia_section(layout, str(
                c.get("name", "Unknown")).upper())
            self._ia_line(
                sec, f"Qualifying offer: {_fmt_money(c.get('qo_amount'))} "
                     f"(was {_fmt_money(c.get('prior_salary'))})")
            pid = c.get("player_id")
            qrow = QHBoxLayout()
            qrow.setSpacing(8)
            ext = QPushButton(f"Extend QO {_fmt_money(c.get('qo_amount'))}")
            ext.setObjectName("primary-btn")
            ext.clicked.connect(
                lambda _c, p=pid, mm=m: self._rfa_decide(mm, p, True))
            qrow.addWidget(ext)
            no = QPushButton("Don't qualify (walks as UFA)")
            no.clicked.connect(
                lambda _c, p=pid, mm=m: self._rfa_decide(mm, p, False))
            qrow.addWidget(no)
            qrow.addStretch()
            sec.addLayout(qrow)
        self._ia_note(layout, "Qualifying keeps his rights; declining makes "
                              "him a UFA.")

    def _rfa_decide(self, m, player_id, qualify):
        try:
            self.game.apply_rfa_qualifying_decision(
                m, player_id, bool(qualify))
        except Exception:
            pass
        self._after_action()

    # -- buyout window ------------------------------------------------------

    def _actions_buyout(self, layout, m, d, done):
        self._ia_line(layout, "Buyout window — June 15-30")
        decided = d.get("decided") or {}
        rem = [c for c in (d.get("cards") or [])
               if str(c.get("player_id")) not in decided]
        if done or not rem:
            self._ia_note(layout, "The window has closed.")
            return
        for c in rem:
            flag = "  ⚠️ Dead weight" if c.get("dead_weight") else ""
            sec = self._ia_section(
                layout, str(c.get("name", "Unknown")).upper() + flag)
            self._ia_line(
                sec, f"Age {c.get('age')} · {c.get('overall')} ovr · "
                     f"{_fmt_money(c.get('cap_hit'))}/yr × "
                     f"{c.get('years_left')} left")
            self._ia_line(
                sec, f"Buyout: {_fmt_money(c.get('buyout_cost'))} total → "
                     f"{_fmt_money(c.get('annual_dead'))}/yr dead cap × "
                     f"{c.get('dead_years')} yrs. "
                     f"Saves {_fmt_money(c.get('savings_y1'))} this season.")
            pid = c.get("player_id")
            last = str(c.get("name", "") or "").split(" ")[-1]
            brow = QHBoxLayout()
            brow.setSpacing(8)
            buy = QPushButton(f"Buy out ({last})")
            buy.setObjectName("primary-btn")
            buy.clicked.connect(
                lambda _c, p=pid, mm=m: self._buyout_decide(mm, p, True))
            brow.addWidget(buy)
            keep = QPushButton("Keep him")
            keep.clicked.connect(
                lambda _c, p=pid, mm=m: self._buyout_decide(mm, p, False))
            brow.addWidget(keep)
            brow.addStretch()
            sec.addLayout(brow)
        self._ia_note(layout, "Buyouts clear cap now but leave dead money "
                              "for years. Undecided players stay put.")

    def _buyout_decide(self, m, player_id, buyout):
        try:
            self.game.apply_buyout_decision(m, player_id, bool(buyout))
        except Exception:
            pass
        self._after_action()

    # -- staff renewal ------------------------------------------------------

    def _actions_staff(self, layout, m, d, done):
        self._ia_line(layout, "Staff contract renewals")
        decided = d.get("decided") or {}
        rem = [o for o in (d.get("offers") or [])
               if str(o.get("staff_id")) not in decided]
        if done or not rem:
            self._ia_note(layout, "All renewal decisions are in.")
            return
        for o in rem:
            sec = self._ia_section(
                layout,
                f"{o.get('name', 'Unknown')} — "
                f"{str(o.get('role', 'staffer')).upper()}")
            self._ia_line(
                sec, f"Age {o.get('age')} · career standing "
                     f"{o.get('reputation')}/100 · "
                     f"{o.get('years_with_team') or 0} yrs with the club · "
                     f"{_fmt_money(o.get('salary'))}/yr")
            self._ia_note(
                sec, "His deal expired. Re-sign him now on a fresh deal "
                     "(same role, same salary) or let him walk to the "
                     "free-agent pool.")
            sid = o.get("staff_id")
            for yrs, label, primary in (
                    (1, "Re-sign × 1 yr", False),
                    (2, "Re-sign × 2 yrs (recommended)", True),
                    (3, "Re-sign × 3 yrs", False),
                    (None, "Let him walk", False)):
                btn = QPushButton(label)
                if primary:
                    btn.setObjectName("primary-btn")
                btn.clicked.connect(
                    lambda _c, s=sid, y=yrs, mm=m:
                    self._staff_renew(mm, s, y))
                sec.addWidget(btn)
        self._ia_note(layout, "Undecided staff walk to the pool when the new "
                              "season starts.")

    def _staff_renew(self, m, staff_id, years):
        try:
            self.game.apply_staff_renewal_decision(m, staff_id, years)
        except Exception:
            pass
        self._after_action()

    # -- media fine ----------------------------------------------------------

    def _actions_fine(self, layout, m, d, done):
        self._ia_line(layout, "League fine")
        amount = d.get("fine_amount", 0)
        self._ia_line(layout,
                      f"{d.get('fine_name', '')} ({d.get('fine_team', '')})")
        self._ia_line(layout,
                      f"{_fmt_money(amount)} — {d.get('fine_reason', '')}")
        if done or d.get("responded"):
            self._ia_note(layout, str(
                d.get("outcome") or "This fine has been answered."))
            return
        if d.get("fine_team") != _user_team_name(self.game):
            self._ia_note(layout, "Not your club's fine — nothing for you to "
                                  "answer for.")
            return
        sec = self._ia_section(layout, "Your response")
        self._ia_note(sec, "The league office awaits your answer. An appeal "
                           "works about one time in four — and the head "
                           "office remembers who complains.")
        frow = QHBoxLayout()
        frow.setSpacing(8)
        appeal = QPushButton("Appeal the fine")
        appeal.clicked.connect(
            lambda: self._fine_respond(m, "appeal"))
        frow.addWidget(appeal)
        accept = QPushButton("Accept and move on")
        accept.setObjectName("primary-btn")
        accept.clicked.connect(lambda: self._fine_respond(m, "accept"))
        frow.addWidget(accept)
        frow.addStretch()
        sec.addLayout(frow)

    def _fine_respond(self, m, choice):
        try:
            import media_engine
            outcome = media_engine.resolve_fine_appeal(
                self.game, getattr(m, "action_data", None) or {},
                choice or "accept")
            try:
                data = getattr(m, "action_data", None) or {}
                data["outcome"] = outcome
                m.action_data = data
                m.action_done = True
            except Exception:
                pass
        except Exception:
            pass
        self._after_action()

    # -- offer sheet ---------------------------------------------------------

    def _actions_offer_match(self, layout, m, d, done):
        self._ia_line(layout, "Offer sheet")
        if done:
            self._ia_note(layout, "Decision made.")
            return
        self._ia_line(layout,
                      f"{_fmt_money(d.get('aav'))}/yr × {d.get('years') or 1}y.")
        self._ia_line(layout, f"Decline and take: {d.get('compensation', '')}")
        self._ia_note(layout, "Matching keeps him at these terms — he can't "
                              "be traded for a year without his consent.")
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        match = QPushButton("Match the offer sheet")
        match.setObjectName("primary-btn")
        match.clicked.connect(lambda: self._offer_match(m, True))
        mrow.addWidget(match)
        decline = QPushButton("Decline, take the picks")
        decline.clicked.connect(lambda: self._offer_match(m, False))
        mrow.addWidget(decline)
        mrow.addStretch()
        layout.addLayout(mrow)

    def _offer_match(self, m, match):
        try:
            self.game.apply_offer_sheet_match_decision(m, bool(match))
        except Exception:
            pass
        self._after_action()

    def _actions_offer_trade(self, layout, m, d, done):
        self._ia_line(layout, "Trade alternative")
        if done:
            self._ia_note(layout, "Decision made.")
            return
        pkg = d.get("package_player_ids") or []
        self._ia_line(layout,
                      f"{_fmt_money(d.get('aav'))}/yr × {d.get('years') or 1}y.")
        self._ia_line(
            layout, f"Trade offer: {len(pkg)} player(s) "
                    f"(~{_fmt_money(d.get('package_value'))} trade value) "
                    f"instead of: {d.get('compensation', '')}")
        self._ia_note(layout, "Accepting trades his rights for the package — "
                              "the picks stay with the offering club. "
                              "Declining takes the pick compensation, exactly "
                              "as the original decline.")
        trow = QHBoxLayout()
        trow.setSpacing(8)
        acc = QPushButton("Accept the trade")
        acc.setObjectName("primary-btn")
        acc.clicked.connect(lambda: self._offer_trade(m, True))
        trow.addWidget(acc)
        dec = QPushButton("Decline, take the picks")
        dec.clicked.connect(lambda: self._offer_trade(m, False))
        trow.addWidget(dec)
        trow.addStretch()
        layout.addLayout(trow)

    def _offer_trade(self, m, accept):
        try:
            self.game.apply_offer_sheet_trade_alt_decision(m, bool(accept))
        except Exception:
            pass
        self._after_action()

    # -- arbitration ----------------------------------------------------------

    def _actions_arbitration(self, layout, m, d, done):
        self._ia_line(layout, "Arbitration walk-away window")
        if done:
            self._ia_note(layout, "Decision made.")
            return
        self._ia_line(layout, f"Award: {_fmt_money(d.get('award_aav'))}/yr × "
                              f"{d.get('term_years') or 1}y.")
        self._ia_note(layout, "Walk away within 48 hours and he becomes a "
                              "UFA. Otherwise the award is binding.")
        arow = QHBoxLayout()
        arow.setSpacing(8)
        acc = QPushButton("Accept the award")
        acc.setObjectName("primary-btn")
        acc.clicked.connect(lambda: self._arbitration(m, False))
        arow.addWidget(acc)
        walk = QPushButton("Walk away (becomes UFA)")
        walk.clicked.connect(lambda: self._arbitration(m, True))
        arow.addWidget(walk)
        arow.addStretch()
        layout.addLayout(arow)

    def _arbitration(self, m, walk_away):
        try:
            self.game.apply_arbitration_walkaway_decision(m, bool(walk_away))
        except Exception:
            pass
        self._after_action()
