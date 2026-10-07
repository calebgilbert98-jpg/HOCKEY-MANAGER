"""Media Center screen: news wire, journalists, narratives, fines, fan buzz.

Native port of the web UI news screen (web_ui/templates/news.html +
web_ui/screens/news.py + web_ui/static/js/news.js). Calls the game object
DIRECTLY -- no Flask/HTTP, no command queue, no JSON. All read-only.

Game systems used (same as the web payloads):
  - News wire: app.news_log (fed by daily_news.py story generators via
    app.add_news(), plus trades/injuries/signings from the sim core).
  - Journalists: media_engine (Reporter, ensure_media_state, reporters_for,
    market_of) -- 3 real reporters per NHL market.
  - Narratives: league.media_narratives and league.coach_media_beefs.
  - Fines: league.media_fines.
  - Fan buzz: fan_sentiment (get_fan_sentiment, sentiment_label) +
    fan_narratives (sentiment_tier, media_tone_for_sentiment).
"""

import re
from datetime import date, datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QSplitter, QScrollArea, QFrame,
    QGroupBox, QTextEdit, QTabWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen
from ..widgets.attribute_bar import AttributeBar


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    gm = _resolve_gm(game)
    league = _safe(lambda: getattr(gm, "league", None))
    if league is None:
        league = _safe(lambda: getattr(game, "league", None))
    return league


def _teams(league):
    if league is None:
        return []
    return _safe(lambda: list(getattr(league, "teams", None) or []), []) or []


def _team_name(t):
    return _safe(lambda: str(getattr(t, "team_name", "") or ""), "") or ""


def _fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


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


# ---------------------------------------------------------------------------
# category colors (from news.js -- deep blue family + broadcast primaries)
# ---------------------------------------------------------------------------

CAT_COLORS = {
    'Prospects': '#3B82F6', 'Coaches': '#a78bfa', 'Rumors': '#f59e0b',
    'Draft': '#fb923c', 'Milestones': '#fbbf24', 'Players': '#4ade80',
    'Teams': '#f472b6', 'Injuries': '#f87171', 'Discipline': '#ef4444',
    'Signings': '#60a5fa', 'League': '#94a3b8',
}


def _cat_color(c):
    return CAT_COLORS.get(c, '#94a3b8')


# ---------------------------------------------------------------------------
# news wire payload (ported from web_ui/screens/news.py)
# ---------------------------------------------------------------------------

def _news_payload(game):
    """app.news_log -> newest-first list of dicts. Never raises."""
    raw = _safe(lambda: list(getattr(game, "news_log", None) or []), []) or []
    items = []
    for entry in raw:
        try:
            if isinstance(entry, dict):
                d = entry.get("date")
                story = entry.get("story", "")
            else:
                d, story = None, entry
            story_text = _safe(lambda: str(story), "") or ""
            if isinstance(d, (date, datetime)):
                date_iso = d.isoformat()
                date_label = d.strftime("%b %d, %Y")
            else:
                date_iso = ""
                date_label = _safe(lambda: str(d), "") or ""
            items.append({"date": date_iso, "date_label": date_label,
                          "story": story_text})
        except Exception:
            continue
    try:
        items.sort(key=lambda x: x["date"], reverse=True)
    except Exception:
        items.reverse()
    return items


_PREFIX_CATS = {
    "RISING STAR": "Prospects", "PROSPECT WATCH": "Prospects",
    "FUTURE WATCH": "Prospects", "DEVELOPMENT CAMP": "Prospects",
    "HOT SEAT": "Coaches", "COACHING MASTERCLASS": "Coaches",
    "SCRATCH WATCH": "Rumors", "RUMOR MILL": "Rumors",
    "CONTRACT WATCH": "Rumors", "DRAFT RISERS": "Draft",
    "MOCK DRAFT BUZZ": "Draft", "DRAFT DEPTH": "Draft",
    "MILESTONE WATCH": "Milestones", "GOALIE DEBATE": "Players",
    "UNDERDOG": "Players", "SCORCHING": "Players", "SLUMP WATCH": "Teams",
    "SCORING RACE": "League", "POWER RANKINGS": "League",
}

_GENERIC_PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9 /&.'-]{2,28}):\s")


def _categorize(story):
    """Category for a story string. Never raises."""
    try:
        s = story or ""
        for prefix, cat in _PREFIX_CATS.items():
            if s.startswith(prefix + ":") or s.startswith(prefix + " "):
                return cat
        m = _GENERIC_PREFIX_RE.match(s)
        if m:
            return m.group(1).strip().title()
        low = s.lower()
        if "trade" in low or "rumor" in low:
            return "Rumors"
        if "injur" in low:
            return "Injuries"
        if "suspend" in low or "fine" in low:
            return "Discipline"
        if "sign" in low or "extension" in low or "buyout" in low:
            return "Signings"
        if "coach" in low or "fired" in low or "hired" in low:
            return "Coaches"
        if "draft" in low:
            return "Draft"
        if "career" in low or "milestone" in low:
            return "Milestones"
        return "League"
    except Exception:
        return "League"


def _story_teams(story, team_names):
    """Team names mentioned in the story (longest match first, max 2)."""
    try:
        low = (story or "").lower()
        found = []
        for name in team_names:
            if name and name.lower() in low:
                found.append(name)
                if len(found) >= 2:
                    break
        return found
    except Exception:
        return []


def _wire_payload(game):
    items = _news_payload(game)
    names = [_team_name(t) for t in _teams(_league(game))]
    names = sorted([n for n in names if n], key=len, reverse=True)
    out = []
    for it in items:
        story = it["story"]
        out.append({
            "date": it["date"], "date_label": it["date_label"],
            "story": story, "category": _categorize(story),
            "teams": _story_teams(story, names),
        })
    categories = sorted({i["category"] for i in out})
    return out, categories


# ---------------------------------------------------------------------------
# journalists payload
# ---------------------------------------------------------------------------

_ARCHETYPE_BLURB = {
    "stirrer": "Pokes the bear. Asks the questions nobody wants asked.",
    "loyalist": "Homer press. Defends the team through thick and thin.",
    "neutral": "Straight down the middle. Just the facts.",
}


def _journalists_payload(game):
    league = _league(game)
    if league is None:
        return []
    try:
        import media_engine as me
    except Exception:
        return []
    try:
        me.ensure_media_state(league)
        markets = []
        for market in me.MARKET_PROFILES:
            prof = me.market_of(market)
            reps = me.reporters_for(market, league) or []
            reporters = []
            for r in reps:
                arch = _safe(lambda: str(getattr(r, "archetype", "") or ""),
                             "") or "neutral"
                reporters.append({
                    "name": _safe(lambda: str(getattr(r, "name", "") or ""),
                                  "") or "Unknown",
                    "archetype": arch,
                    "archetype_blurb": _ARCHETYPE_BLURB.get(arch, ""),
                    "credibility": round(_fnum(
                        getattr(r, "credibility", 50), 50.0), 1),
                    "fan_approval": round(_fnum(
                        getattr(r, "fan_approval", 50), 50.0), 1),
                })
            markets.append({
                "market": market,
                "intensity": int(prof.get("intensity", 0)),
                "adversarial": int(prof.get("adversarial", 0)),
                "loyalty": int(prof.get("loyalty", 0)),
                "patience": int(prof.get("patience", 0)),
                "reporters": reporters,
            })
        # Fishbowls first: the loudest markets lead the directory.
        markets.sort(key=lambda m: -m["intensity"])
        return markets
    except Exception:
        return []


# ---------------------------------------------------------------------------
# narratives payload
# ---------------------------------------------------------------------------

_NARR_KINDS = {
    "hot_seat": "Hot Seat", "leadership": "Leadership Questions",
    "goalie": "Goalie Controversy", "trade_rumor": "Trade Rumor",
    "prospect_watch": "Prospect Watch", "trust_process": "Trust the Process",
    "cup_window": "Cup Window", "legacy_chase": "Legacy Chase",
    "deadline_race": "Deadline Race", "fan_unrest": "Fan Unrest",
    "fan_buzz": "Fan Buzz",
}

_BEEF_LEVELS = {1: "Testy exchange", 2: "Open hostility", 3: "Full circus"}


def _player_index(league):
    idx = {}
    try:
        for t in _teams(league):
            for coll in ("roster", "prospects"):
                for p in _safe(lambda: list(getattr(t, coll, None) or []),
                               []) or []:
                    try:
                        pid = getattr(p, "id", None)
                        if pid is None or pid in idx:
                            continue
                        name = (_safe(lambda: str(
                            getattr(p, "full_name", "") or ""), "")
                                or (f"{_safe(lambda: str(getattr(p, 'first_name', '') or ''), '')} "
                                    f"{_safe(lambda: str(getattr(p, 'last_name', '') or ''), '')}".strip())
                                or "Unknown Player")
                        idx[pid] = name
                    except Exception:
                        continue
    except Exception:
        pass
    return idx


def _narratives_payload(game):
    league = _league(game)
    if league is None:
        return [], []
    try:
        import media_engine as me
        me.ensure_media_state(league)
    except Exception:
        return [], []
    try:
        names = _player_index(league)
        raw_narrs = _safe(lambda: list(
            getattr(league, "media_narratives", None) or []), []) or []
        narratives = []
        for n in raw_narrs:
            try:
                kind = _safe(lambda: str(getattr(n, "kind", "") or ""), "")
                heat = _fnum(getattr(n, "heat", 0), 0.0)
                subjects = []
                for s in _safe(lambda: list(
                        getattr(n, "subjects", None) or []), []) or []:
                    if s:
                        subjects.append({
                            "id": str(s),
                            "name": names.get(s, names.get(str(s),
                                                       "Unknown Player")),
                        })
                narratives.append({
                    "kind": kind,
                    "kind_label": _NARR_KINDS.get(
                        kind, kind.replace("_", " ").title() or "Storyline"),
                    "team": _safe(lambda: str(
                        getattr(n, "team_name", "") or ""), ""),
                    "title": _safe(lambda: str(
                        getattr(n, "title", "") or ""), ""),
                    "subjects": subjects,
                    "heat": round(max(0.0, min(100.0, heat)), 1),
                })
            except Exception:
                continue
        narratives.sort(key=lambda x: -x["heat"])

        raw_beefs = _safe(lambda: list(
            getattr(league, "coach_media_beefs", None) or []), []) or []
        beefs = []
        for b in raw_beefs:
            try:
                level = int(_fnum(getattr(b, "level", 1), 1))
                beefs.append({
                    "coach": _safe(lambda: str(
                        getattr(b, "coach_name", "") or ""), ""),
                    "reporter": _safe(lambda: str(
                        getattr(b, "reporter_name", "") or ""), ""),
                    "team": _safe(lambda: str(
                        getattr(b, "team_name", "") or ""), ""),
                    "level": level,
                    "level_label": _BEEF_LEVELS.get(level,
                                                  f"Level {level}"),
                    "days_quiet": int(_fnum(getattr(b, "days_quiet", 0), 0)),
                })
            except Exception:
                continue
        beefs.sort(key=lambda x: -x["level"])
        return narratives, beefs
    except Exception:
        return [], []


# ---------------------------------------------------------------------------
# fines payload
# ---------------------------------------------------------------------------

def _fines_payload(game):
    league = _league(game)
    if league is None:
        return [], 0
    try:
        raw = _safe(lambda: list(
            getattr(league, "media_fines", None) or []), []) or []
        fines = []
        for f in raw:
            try:
                if not isinstance(f, dict):
                    continue
                d = f.get("date")
                if isinstance(d, (date, datetime)):
                    date_iso = d.isoformat()
                    date_label = d.strftime("%b %d, %Y")
                else:
                    date_iso = ""
                    date_label = _safe(lambda: str(d), "") or ""
                amount = int(_fnum(f.get("amount", 0), 0))
                fines.append({
                    "date": date_iso, "date_label": date_label,
                    "name": _safe(lambda: str(f.get("name", "") or ""), ""),
                    "team": _safe(lambda: str(f.get("team", "") or ""), ""),
                    "amount": amount,
                    "reason": _safe(lambda: str(
                        f.get("reason", "") or ""), ""),
                    "role": _safe(lambda: str(f.get("role", "") or ""), ""),
                })
            except Exception:
                continue
        fines.sort(key=lambda x: x["date"], reverse=True)
        return fines, sum(f["amount"] for f in fines)
    except Exception:
        return [], 0


# ---------------------------------------------------------------------------
# fan buzz payload
# ---------------------------------------------------------------------------

_SENT_COLORS = {
    'Electric': '#fbbf24', 'Happy': '#4ade80', 'Content': '#94a3b8',
    'Restless': '#f59e0b', 'Disgruntled': '#f87171', 'Toxic': '#ef4444',
}


def _fanbuzz_payload(game):
    league = _league(game)
    if league is None:
        return [], {}
    try:
        import fan_sentiment as fs
        import fan_narratives as fn
    except Exception:
        return [], {}
    try:
        current = _safe(lambda: getattr(game, "current_date", None))
        teams = []
        for t in _teams(league):
            try:
                name = _team_name(t)
                if not name:
                    continue
                value = max(0.0, min(100.0, _fnum(
                    fs.get_fan_sentiment(t, current), 60.0)))
                label = _safe(lambda: str(fs.sentiment_label(value) or ""),
                              "") or "Content"
                tier = _safe(lambda: str(fn.sentiment_tier(value) or ""),
                             "") or "content"
                tone = _safe(lambda: str(
                    fn.media_tone_for_sentiment(t, current) or ""),
                    "") or "neutral"
                trail = _safe(lambda: list(
                    getattr(t, "fan_sentiment_trail", None) or []), []) or []
                drivers = []
                for entry in reversed(trail[-4:]):
                    try:
                        if isinstance(entry, dict):
                            drivers.append({
                                "date": _safe(lambda: str(
                                    entry.get("date", "") or ""), ""),
                                "delta": round(_fnum(
                                    entry.get("delta", 0.0), 0.0), 1),
                                "reason": _safe(lambda: str(
                                    entry.get("reason", "") or ""), ""),
                            })
                    except Exception:
                        continue
                teams.append({
                    "name": name, "sentiment": round(value, 1),
                    "label": label, "tier": tier, "media_tone": tone,
                    "drivers": drivers,
                })
            except Exception:
                continue
        # Happiest fanbases first.
        teams.sort(key=lambda x: -x["sentiment"])
        summary = {}
        for tm in teams:
            summary[tm["label"]] = summary.get(tm["label"], 0) + 1
        return teams, summary
    except Exception:
        return [], {}

# =====================================================================
# NewsScreen
# =====================================================================

_ARCH_STYLE = {
    "stirrer": ("Stirrer", "#f87171"),
    "loyalist": ("Loyalist", "#4ade80"),
    "neutral": ("Neutral", "#94a3b8"),
}


class NewsScreen(BaseScreen):
    """Media Center: 5 tabs (wire, journalists, narratives, fines,
    fan buzz). All read-only."""

    title = "News"

    def __init__(self, game, main_window, parent=None):
        self._wire_filter = "All"
        self._wire_search = ""
        self._wire_items = []
        self._wire_categories = []
        self._cat_buttons = {}
        super().__init__(game, main_window, parent)

    # -- layout -------------------------------------------------------

    def _build_body(self):
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        # 1. wire
        self._wire_tab = QWidget()
        self._build_wire_tab(self._wire_tab)
        self._tabs.addTab(self._wire_tab, "News Wire")

        # 2. journalists
        self._jour_tab = self._scroll_page()
        self._tabs.addTab(self._jour_tab, "Journalists")

        # 3. narratives
        self._narr_tab = self._scroll_page()
        self._tabs.addTab(self._narr_tab, "Narratives")

        # 4. fines
        self._fines_tab = self._scroll_page()
        self._tabs.addTab(self._fines_tab, "Fines")

        # 5. fan buzz
        self._buzz_tab = self._scroll_page()
        self._tabs.addTab(self._buzz_tab, "Fan Buzz")

    def _scroll_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setSpacing(10)
        scroll.setWidget(host)
        # Keep a direct Python reference: findChild(QWidget) would return
        # the scroll viewport first, not our host widget.
        scroll._host_layout = layout
        return scroll

    def _host_layout(self, scroll):
        return scroll._host_layout

    # -- wire tab --------------------------------------------------------

    def _build_wire_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # toolbar: search + refresh
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._wire_search_box = QLineEdit()
        self._wire_search_box.setPlaceholderText("Search stories…")
        self._wire_search_box.setClearButtonEnabled(True)
        self._wire_search_box.setMaximumWidth(280)
        self._wire_search_box.textChanged.connect(
            self._on_wire_search_changed)
        toolbar.addWidget(self._wire_search_box)
        self._wire_refresh_btn = QPushButton("⟳ Refresh")
        self._wire_refresh_btn.clicked.connect(self._on_wire_refresh)
        toolbar.addWidget(self._wire_refresh_btn)
        self._wire_fresh = QLabel("")
        self._wire_fresh.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        toolbar.addWidget(self._wire_fresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # category chips
        self._chip_scroll = QScrollArea()
        self._chip_scroll.setWidgetResizable(True)
        self._chip_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self._chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chip_scroll.setFixedHeight(40)
        chip_host = QWidget()
        self._chip_layout = QHBoxLayout(chip_host)
        self._chip_layout.setContentsMargins(0, 4, 0, 4)
        self._chip_layout.setSpacing(6)
        self._chip_scroll.setWidget(chip_host)
        layout.addWidget(self._chip_scroll)

        # two-pane: headline list + reader
        splitter = QSplitter(Qt.Horizontal)
        self._wire_list = QListWidget()
        self._wire_list.setMinimumWidth(380)
        self._wire_list.itemClicked.connect(self._on_wire_row_clicked)
        splitter.addWidget(self._wire_list)

        self._wire_reader = QTextEdit()
        self._wire_reader.setReadOnly(True)
        splitter.addWidget(self._wire_reader)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._wire_empty = QLabel("")
        self._wire_empty.setAlignment(Qt.AlignCenter)
        self._wire_empty.setStyleSheet("color: #8b95ab; font-size: 13px;")
        layout.addWidget(self._wire_empty)

    def _on_wire_search_changed(self, text):
        self._wire_search = text
        self._render_wire()

    def _on_wire_refresh(self):
        """Re-pull the wire (read-only: the engine owns generation) and
        show a freshness signal."""
        self._wire_refresh_btn.setEnabled(False)
        try:
            items, cats = _wire_payload(self.game)
            self._wire_items = items
            self._wire_categories = cats
            latest = items[0].get("date_label", "") if items else ""
            self._wire_fresh.setText(
                f"{len(items)} stories"
                + (f" · latest {latest}" if latest else ""))
        except Exception:
            self._wire_fresh.setText("Refresh failed")
        self._wire_refresh_btn.setEnabled(True)
        self._render_wire()
        QTimer.singleShot(8000, lambda: self._wire_fresh.setText(""))

    def _filtered_wire(self):
        q = (self._wire_search or "").lower()
        out = []
        for it in self._wire_items:
            if (self._wire_filter != "All"
                    and it.get("category") != self._wire_filter):
                continue
            if q and q not in (it.get("story") or "").lower():
                continue
            out.append(it)
        return out

    def _render_wire(self):
        items = self._filtered_wire()
        self._wire_list.clear()
        self._wire_empty.setText(
            "" if self._wire_items else
            "No news yet — trades, injuries, suspensions, awards and the "
            "daily beat will be reported here as the season unfolds.")
        for it in items:
            cat = it.get("category", "League")
            color = _cat_color(cat)
            head = str(it.get("story", "") or "").split("\n")[0][:110]
            item = QListWidgetItem()
            # store the wire-item index on the item itself
            item.setData(Qt.UserRole, self._wire_items.index(it))
            row = QFrame()
            row.setFrameShape(QFrame.NoFrame)
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 6, 4, 6)
            h.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            h.addWidget(dot)
            txt = QLabel(
                f"{_esc(head)}<br><span style='color:#8b95ab; "
                f"font-size:11px'>{_esc(cat)} · "
                f"{_esc(it.get('date_label', ''))}</span>")
            txt.setWordWrap(True)
            txt.setTextFormat(Qt.RichText)
            h.addWidget(txt, 1)
            item.setSizeHint(row.sizeHint())
            self._wire_list.addItem(item)
            self._wire_list.setItemWidget(item, row)
        if items:
            self._paint_wire_item(items[0])

    def _on_wire_row_clicked(self, item):
        idx = item.data(Qt.UserRole)
        try:
            self._paint_wire_item(self._wire_items[int(idx)])
        except Exception:
            pass

    def _paint_wire_item(self, it):
        cat = it.get("category", "League")
        color = _cat_color(cat)
        story = _esc(it.get("story", ""))
        date_label = _esc(it.get("date_label", "") or "Unknown date")
        teams = it.get("teams") or []
        team_html = ""
        if teams:
            team_html = "<br><b>Teams:</b> " + ", ".join(_esc(t) for t in teams)
        html = (f"<h3 style='color:{color}'>{_esc(cat)}</h3>"
                f"<p>{story}</p>"
                f"{team_html}"
                f"<p><span style='color:#8b95ab'>Filed: {date_label}</span>"
                f"</p>")
        self._wire_reader.setHtml(html)

    def _open_team(self, name):
        try:
            self.main_window.open_team(name)
        except Exception:
            try:
                self.navigate_to("team")
            except Exception:
                pass

    # -- refresh (all tabs) ----------------------------------------------

    def refresh(self):
        self._refresh_wire()
        self._refresh_journalists()
        self._refresh_narratives()
        self._refresh_fines()
        self._refresh_fanbuzz()

    def _refresh_wire(self):
        try:
            items, cats = _wire_payload(self.game)
        except Exception:
            items, cats = [], []
        self._wire_items = items
        self._wire_categories = cats
        # category chips
        for key in list(self._cat_buttons):
            btn = self._cat_buttons.pop(key)
            self._chip_layout.removeWidget(btn)
            btn.deleteLater()
        for c in ["All"] + cats:
            btn = QPushButton(c)
            btn.setCheckable(True)
            btn.setChecked(c == self._wire_filter)
            btn.setProperty("cat", c)
            btn.clicked.connect(self._on_chip_clicked)
            self._chip_layout.addWidget(btn)
            self._cat_buttons[c] = btn
        self._chip_scroll.setVisible(bool(cats))
        self._render_wire()
        self._tabs.setTabText(
            0, f"News Wire ({len(items)})" if items else "News Wire")

    def _on_chip_clicked(self):
        btn = self.sender()
        if btn is None:
            return
        c = btn.property("cat")
        self._wire_filter = c
        for k, b in self._cat_buttons.items():
            b.setChecked(k == c)
        self._render_wire()

    # -- journalists tab ---------------------------------------------------

    def _refresh_journalists(self):
        layout = self._host_layout(self._jour_tab)
        _clear_layout(layout)
        markets = _journalists_payload(self.game)
        count = sum(len(m["reporters"]) for m in markets)
        self._tabs.setTabText(
            1, f"Journalists ({count})" if count else "Journalists")
        if not markets:
            lab = QLabel("No press corps — reporters assemble once the "
                         "league media state initializes.")
            lab.setWordWrap(True)
            lab.setStyleSheet("color: #8b95ab; font-size: 13px;")
            layout.addWidget(lab)
            layout.addStretch()
            return
        intro = QLabel(f"{count} reporters across {len(markets)} markets. "
                       "Markets ranked by media intensity — the fishbowls "
                       "lead.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        layout.addWidget(intro)
        for mk in markets:
            card = QGroupBox(mk["market"])
            cl = QVBoxLayout(card)
            cl.setSpacing(4)
            for label, val in (("Intensity", mk["intensity"]),
                               ("Adversarial", mk["adversarial"]),
                               ("Loyalty", mk["loyalty"]),
                               ("Patience", mk["patience"])):
                cl.addWidget(AttributeBar(label, max(0, min(100, val))))
            for r in mk["reporters"]:
                arch_label, arch_color = _ARCH_STYLE.get(
                    r["archetype"], _ARCH_STYLE["neutral"])
                rep = QFrame()
                rep.setFrameShape(QFrame.StyledPanel)
                rl = QVBoxLayout(rep)
                rl.setSpacing(2)
                head = QHBoxLayout()
                head.setSpacing(8)
                name = QLabel(r["name"])
                name.setStyleSheet("font-weight: bold; font-size: 13px;")
                head.addWidget(name)
                tag = QLabel(arch_label)
                tag.setStyleSheet(
                    f"color: {arch_color}; border: 1px solid {arch_color};"
                    f" border-radius: 8px; padding: 1px 8px; font-size: 11px;")
                head.addWidget(tag)
                head.addStretch()
                rl.addLayout(head)
                if r["archetype_blurb"]:
                    blurb = QLabel(r["archetype_blurb"])
                    blurb.setWordWrap(True)
                    blurb.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                    rl.addWidget(blurb)
                stats = QLabel(f"⭐ Credibility {r['credibility']}   "
                               f"👍 Fan approval {r['fan_approval']}")
                stats.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                rl.addWidget(stats)
                cl.addWidget(rep)
            layout.addWidget(card)
        layout.addStretch()

    # -- narratives tab ------------------------------------------------------

    def _heat_color(self, heat):
        if heat >= 70:
            return "#ef4444"
        if heat >= 40:
            return "#f59e0b"
        return "#3B82F6"

    def _refresh_narratives(self):
        layout = self._host_layout(self._narr_tab)
        _clear_layout(layout)
        narratives, beefs = _narratives_payload(self.game)
        count = len(narratives) + len(beefs)
        self._tabs.setTabText(
            2, f"Narratives ({count})" if count else "Narratives")
        if not narratives and not beefs:
            lab = QLabel("Quiet around the league — no ongoing media "
                         "narratives or coach-reporter feuds right now. "
                         "Slumps, controversies and heated losses will "
                         "start them.")
            lab.setWordWrap(True)
            lab.setStyleSheet("color: #8b95ab; font-size: 13px;")
            layout.addWidget(lab)
            layout.addStretch()
            return
        if narratives:
            h = QLabel("ONGOING STORYLINES")
            h.setObjectName("section-header")
            layout.addWidget(h)
            for n in narratives:
                card = QGroupBox()
                cl = QVBoxLayout(card)
                top = QHBoxLayout()
                top.setSpacing(8)
                kind = QLabel(n["kind_label"])
                kind.setStyleSheet(
                    "color: #3B82F6; border: 1px solid #3B82F6;"
                    " border-radius: 8px; padding: 1px 8px; font-size: 11px;")
                top.addWidget(kind)
                if n["team"]:
                    tbtn = QPushButton(n["team"])
                    tbtn.setFlat(True)
                    tbtn.setStyleSheet("color: #3B82F6; text-align: left;")
                    tbtn.clicked.connect(
                        lambda _c, name=n["team"]: self._open_team(name))
                    top.addWidget(tbtn)
                else:
                    top.addWidget(QLabel(n["team"]))
                top.addStretch()
                cl.addLayout(top)
                title = QLabel(n["title"])
                title.setWordWrap(True)
                title.setStyleSheet("font-weight: bold; font-size: 14px;")
                cl.addWidget(title)
                subs = n.get("subjects") or []
                if subs:
                    sub_lab = QLabel("Subjects: " + ", ".join(
                        s["name"] for s in subs))
                    sub_lab.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                    cl.addWidget(sub_lab)
                heat = max(0.0, min(100.0, n["heat"]))
                cl.addWidget(AttributeBar("Heat", int(heat)))
                layout.addWidget(card)
        if beefs:
            h = QLabel("COACH VS. MEDIA BEEFS")
            h.setObjectName("section-header")
            layout.addWidget(h)
            for b in beefs:
                color = ("#ef4444" if b["level"] >= 3
                         else "#f59e0b" if b["level"] == 2 else "#94a3b8")
                card = QGroupBox()
                cl = QVBoxLayout(card)
                lvl = QLabel(f"⚔️ {b['level_label']}")
                lvl.setStyleSheet(
                    f"color: {color}; border: 1px solid {color};"
                    f" border-radius: 8px; padding: 1px 8px; font-size: 11px;")
                cl.addWidget(lvl)
                title = QLabel(f"{b['coach']}  vs.  {b['reporter']}")
                title.setWordWrap(True)
                title.setStyleSheet("font-weight: bold; font-size: 14px;")
                cl.addWidget(title)
                if b["team"]:
                    tbtn = QPushButton(b["team"])
                    tbtn.setFlat(True)
                    tbtn.setStyleSheet("color: #3B82F6; text-align: left;")
                    tbtn.clicked.connect(
                        lambda _c, name=b["team"]: self._open_team(name))
                    cl.addWidget(tbtn)
                quiet = (f"{b['days_quiet']} quiet days"
                         if b["days_quiet"] else "Fresh exchange")
                qlab = QLabel(quiet)
                qlab.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                cl.addWidget(qlab)
                layout.addWidget(card)
        layout.addStretch()

    # -- fines tab ------------------------------------------------------------

    def _refresh_fines(self):
        layout = self._host_layout(self._fines_tab)
        _clear_layout(layout)
        fines, total = _fines_payload(self.game)
        self._tabs.setTabText(
            3, f"Fines ({len(fines)})" if fines else "Fines")
        if not fines:
            lab = QLabel("No fines this season — player outbursts and "
                         "skipped media availabilities land here, with a "
                         "running season total.")
            lab.setWordWrap(True)
            lab.setStyleSheet("color: #8b95ab; font-size: 13px;")
            layout.addWidget(lab)
            layout.addStretch()
            return
        summary = QLabel(f"Season total  ${total:,}")
        summary.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(summary)
        cnt = QLabel(f"{len(fines)} fine{'s' if len(fines) != 1 else ''} "
                     "handed down")
        cnt.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        layout.addWidget(cnt)
        for f in fines:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            h = QHBoxLayout(card)
            h.setSpacing(12)
            amt = QLabel(f"${f['amount']:,}")
            amt.setStyleSheet("font-weight: bold; font-size: 16px; "
                              "color: #ef4444;")
            amt.setMinimumWidth(110)
            h.addWidget(amt)
            main = QVBoxLayout()
            main.setSpacing(2)
            name_text = f["name"]
            if f["role"]:
                name_text += f"  ({f['role']})"
            name = QLabel(name_text)
            name.setStyleSheet("font-weight: bold; font-size: 13px;")
            main.addWidget(name)
            reason = QLabel(f["reason"])
            reason.setWordWrap(True)
            reason.setStyleSheet("font-size: 12px;")
            main.addWidget(reason)
            meta = QHBoxLayout()
            meta.setSpacing(6)
            if f["team"]:
                tbtn = QPushButton(f["team"])
                tbtn.setFlat(True)
                tbtn.setStyleSheet("color: #3B82F6; text-align: left; "
                                   "font-size: 12px;")
                tbtn.clicked.connect(
                    lambda _c, name=f["team"]: self._open_team(name))
                meta.addWidget(tbtn)
            if f["date_label"]:
                dl = QLabel(f"· {f['date_label']}")
                dl.setStyleSheet("color: #8b95ab; font-size: 12px;")
                meta.addWidget(dl)
            meta.addStretch()
            main.addLayout(meta)
            h.addLayout(main, 1)
            layout.addWidget(card)
        layout.addStretch()

    # -- fan buzz tab ----------------------------------------------------------

    def _refresh_fanbuzz(self):
        layout = self._host_layout(self._buzz_tab)
        _clear_layout(layout)
        teams, summary = _fanbuzz_payload(self.game)
        self._tabs.setTabText(
            4, f"Fan Buzz ({len(teams)})" if teams else "Fan Buzz")
        if not teams:
            lab = QLabel("No fan data — fan sentiment per team will appear "
                         "here once the season is underway.")
            lab.setWordWrap(True)
            lab.setStyleSheet("color: #8b95ab; font-size: 13px;")
            layout.addWidget(lab)
            layout.addStretch()
            return
        # summary pills
        order = ['Electric', 'Happy', 'Content', 'Restless', 'Disgruntled',
                 'Toxic']
        pills = QHBoxLayout()
        pills.setSpacing(8)
        for k in order:
            if summary.get(k):
                color = _SENT_COLORS.get(k, '#94a3b8')
                pill = QLabel(f"{k} · {summary[k]}")
                pill.setStyleSheet(
                    f"color: {color}; border: 1px solid {color};"
                    f" border-radius: 10px; padding: 2px 10px; "
                    f"font-size: 12px;")
                pills.addWidget(pill)
        pills.addStretch()
        layout.addLayout(pills)

        for t in teams:
            color = _SENT_COLORS.get(t["label"], '#94a3b8')
            card = QGroupBox()
            cl = QVBoxLayout(card)
            head = QHBoxLayout()
            head.setSpacing(8)
            tbtn = QPushButton(t["name"])
            tbtn.setFlat(True)
            tbtn.setStyleSheet("font-weight: bold; font-size: 14px; "
                               "color: #3B82F6; text-align: left;")
            tbtn.clicked.connect(
                lambda _c, name=t["name"]: self._open_team(name))
            head.addWidget(tbtn)
            tag = QLabel(t["label"])
            tag.setStyleSheet(
                f"color: {color}; border: 1px solid {color};"
                f" border-radius: 8px; padding: 1px 8px; font-size: 11px;")
            head.addWidget(tag)
            val = QLabel(str(t["sentiment"]))
            val.setStyleSheet("font-weight: bold; font-size: 14px;")
            head.addWidget(val)
            head.addStretch()
            cl.addLayout(head)
            cl.addWidget(AttributeBar("Sentiment",
                                      int(max(0, min(100,
                                                    t["sentiment"])))))
            tone = QLabel(f"Media tone: {t['media_tone']}")
            tone.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            cl.addWidget(tone)
            drivers = t.get("drivers") or []
            if drivers:
                dl = QLabel("Recent buzz")
                dl.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                                 "font-weight: bold;")
                cl.addWidget(dl)
                for dr in drivers:
                    delta = dr.get("delta", 0) or 0
                    sign = "+" if delta > 0 else ""
                    dcol = ("#4ade80" if delta > 0
                            else "#f87171" if delta < 0 else "#9aa4b8")
                    row = QLabel(
                        f"<span style='color:{dcol}; font-weight:bold'>"
                        f"{sign}{dr.get('delta')}</span>  "
                        f"{dr.get('reason') or '—'}"
                        f"<span style='color:#8b95ab'>"
                        f"{(' · ' + dr['date']) if dr.get('date') else ''}"
                        f"</span>")
                    row.setWordWrap(True)
                    row.setTextFormat(Qt.RichText)
                    row.setStyleSheet("font-size: 12px;")
                    cl.addWidget(row)
            else:
                none = QLabel("No recorded buzz drivers.")
                none.setStyleSheet("color: #8b95ab; font-size: 12px;")
                cl.addWidget(none)
            layout.addWidget(card)
        layout.addStretch()
