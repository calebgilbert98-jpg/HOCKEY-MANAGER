"""Player comparison screen: side-by-side comparison of 2-4 players.

Native port of web_ui/screens/compare.py + compare.js.
Direct Python calls -- no HTTP. Winner highlighting per row is
direction-aware (higher_better per attribute/stat), matching the web
logic: best = green, worst = red, ties get no highlight.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QFrame, QPushButton,
    QScrollArea, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen
from ..widgets.attribute_bar import AttributeBar

try:
    import game_classes as _gc
except Exception:
    _gc = None


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _to100(v):
    if _gc is not None:
        return _safe(lambda: _gc.to_100_scale(v), 50) or 50
    try:
        return int(v)
    except Exception:
        return 50


# -- attribute field lists (verbatim from web_ui/screens/player.py) --------
_SKATER_TECHNICAL = [
    ("Shooting", "shooting"), ("Shot Accuracy", "shooting_accuracy"),
    ("Shot Power", "shooting_power"), ("Wrist Shot", "wristshot"),
    ("Slap Shot", "slapshot"), ("One Timer", "one_timer"),
    ("Backhand", "backhand"), ("Deflections", "deflections"),
    ("Passing", "passing"), ("Pass Accuracy", "passing_accuracy"),
    ("Passing Creativity", "passing_creativity"),
    ("Puck Handling", "puck_handling"), ("Stickhandling", "stickhandling"),
    ("Deking", "deking"), ("Off. Positioning", "offensive_positioning"),
    ("Faceoffs", "faceoffs"), ("First Pass", "first_pass"),
    ("Breakout Passes", "breakout_passes"),
    ("Puck Protection", "puck_protection"), ("Loose Puck", "loose_puck"),
    ("Pokecheck", "pokecheck"),
]
_SKATER_MENTAL = [
    ("Vision", "vision"), ("Hockey IQ", "hockey_iq"),
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Off. Awareness", "off_the_puck"),
    ("Def. Awareness", "defensive_awareness"),
    ("Creativity", "creativity"), ("Determination", "determination"),
    ("Composure", "composure"), ("Confidence", "confidence"),
    ("Focus", "focus"), ("Pressure Player", "pressure_player"),
    ("Teamwork", "teamwork"), ("Discipline", "discipline"),
    ("Flair", "flair"), ("Work Ethic", "work_ethic"),
    ("Coachability", "coachability"), ("Adaptability", "adaptability"),
]
_SKATER_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"), ("Checking", "checking"),
    ("Bodycheck", "bodycheck"), ("Shot Blocking", "shot_blocking"),
    ("Forechecking", "forechecking"), ("Screening", "screen_shots"),
    ("Work Rate", "work_rate"), ("Shoot Tendency", "shoot_pass_tendency"),
    ("Hitting Tendency", "hitting_tendency"),
]
_GOALIE_TECHNICAL = [
    ("Goaltending", "goaltending"), ("Positioning", "positioning"),
    ("Reflexes", "reflexes"), ("Glove Hand", "glove_hand"),
    ("Stick Side", "stick_side"), ("Rebound Ctrl", "rebound_control"),
    ("Breakaway Skill", "breakaway_skill"),
    ("Puck Handling", "puck_handling"), ("Passing", "passing"),
]
_GOALIE_MENTAL = [
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Vision", "vision"), ("Focus", "focus"),
    ("Determination", "determination"), ("Composure", "composure"),
    ("Confidence", "confidence"), ("Teamwork", "teamwork"),
    ("Discipline", "discipline"), ("Work Ethic", "work_ethic"),
    ("Adaptability", "adaptability"),
]
_GOALIE_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"),
]

# lower_is_better rows (direction-aware highlighting)
_STAT_DEFS_SKATER = [
    ("GP", "Games Played", "games_played", True),
    ("G", "Goals", "goals", True),
    ("A", "Assists", "assists", True),
    ("PTS", "Points", None, True),
    ("+/-", "Plus/Minus", "plus_minus", True),
    ("PIM", "Penalty Minutes", "penalties_in_minutes", False),
    ("HIT", "Hits", "hits", True),
    ("BLK", "Blocked Shots", "blocked_shots", True),
    ("SOG", "Shots on Goal", "shots", True),
]
_STAT_DEFS_GOALIE = [
    ("GP", "Games Played", "games_played", True),
    ("W", "Wins", "wins", True),
    ("SV%", "Save %", "save_percentage", True),
    ("GAA", "Goals Against Avg", "goals_against_avg", False),
    ("SO", "Shutouts", "shutouts", True),
    ("SA", "Shots Against", "shots_against", True),
]
STAT_ORDER = ["GP", "G", "A", "PTS", "+/-", "PIM", "HIT", "BLK", "SOG",
              "W", "SV%", "GAA", "SO", "SA"]

WIN_STYLE = ("QFrame { border: 2px solid #4CAF50; border-radius: 6px; "
             "background-color: rgba(76, 175, 80, 0.10); }")
LOSE_STYLE = ("QFrame { border: 2px solid #F44336; border-radius: 6px; "
              "background-color: rgba(244, 67, 54, 0.08); }")
NEUTRAL_STYLE = "QFrame { border: 2px solid transparent; border-radius: 6px; }"


def _compact_bar(value):
    """AttributeBar without the name label (labels live in column 0)."""
    bar = AttributeBar("", value)
    lay = bar.layout()
    if lay is not None and lay.count() >= 1:
        w = lay.itemAt(0).widget()
        if w is not None:
            w.hide()
    return bar


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M".rstrip("0").rstrip(".")
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v}" if v else "--"


class CompareScreen(BaseScreen):
    """Side-by-side player comparison, up to 4 players."""

    title = "Compare"
    MAX_PLAYERS = 4

    def __init__(self, game, main_window, parent=None):
        self._players = []          # resolved player objects
        self._active_slot = -1      # slot being filled by search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self._run_search)
        self._slot_frames = []
        super().__init__(game, main_window, parent)

    # ------------------------------------------------------------------
    # game access helpers
    # ------------------------------------------------------------------
    def _gm(self):
        return getattr(self.game, "game_manager", None) or self.game

    def _league(self):
        gm = self._gm()
        return (_safe(lambda: getattr(gm, "league", None))
                or _safe(lambda: getattr(self.game, "league", None)))

    def _user_team(self):
        gm = self._gm()
        return (_safe(lambda: getattr(gm, "user_team", None))
                or _safe(lambda: getattr(self.game, "user_team", None)))

    def _is_goalie(self, p):
        return "GOALIE" in str(
            _safe(lambda: getattr(p, "primary_position", ""), "")).upper()

    def _overall(self, p):
        raw = _safe(lambda: getattr(p, "overall", 50), 50)
        return int(_to100(raw))

    def _pos_str(self, p):
        pos = _safe(lambda: getattr(p, "primary_position", None))
        if pos:
            return str(pos)
        pos = _safe(lambda: getattr(p, "position", "?"))
        return getattr(pos, "value", str(pos))

    def _find_player(self, pid):
        league = self._league()
        teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
        user_team = self._user_team()
        if user_team is not None and all(t is not user_team for t in teams):
            teams = [user_team] + teams
        for team in teams:
            for lname in ("roster", "ahl_roster", "prospects"):
                lst = _safe(lambda: list(getattr(team, lname, []) or []),
                            []) or []
                for p in lst:
                    if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid):
                        return p, team
        return None, None

    def _all_players(self):
        """Search index: every rostered/AHL/prospect player in the league."""
        league = self._league()
        teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
        user_team = self._user_team()
        if user_team is not None and all(t is not user_team for t in teams):
            teams = [user_team] + teams
        out, seen = [], set()
        for team in teams:
            tname = _safe(lambda: str(getattr(team, "team_name", "")), "")
            for lname in ("roster", "ahl_roster", "prospects"):
                lst = _safe(lambda: list(getattr(team, lname, []) or []),
                            []) or []
                for p in lst:
                    pid = str(_safe(lambda: getattr(p, "id", ""), ""))
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    out.append((p, tname))
        return out

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        hint = QLabel("Add up to 4 players. Best value in each row is "
                      "highlighted green, worst red.")
        hint.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(hint)

        # slots
        slots_row = QHBoxLayout()
        slots_row.setSpacing(10)
        for i in range(self.MAX_PLAYERS):
            frame = QFrame()
            frame.setObjectName("tile")
            frame.setMinimumHeight(86)
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(10, 8, 10, 8)
            self._slot_frames.append(frame)
            slots_row.addWidget(frame, 1)
        self._layout.addLayout(slots_row)
        self._render_slots()

        # search
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Type a player name to add… (click a slot first)")
        self._search.textChanged.connect(self._on_search_text)
        self._layout.addWidget(self._search)

        self._results = QListWidget()
        self._results.setMaximumHeight(200)
        self._results.hide()
        self._results.itemDoubleClicked.connect(self._on_result_chosen)
        self._layout.addWidget(self._results)

        # empty state
        self._empty = QLabel("Select at least two players to start comparing.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet("color: #6b7488; font-size: 15px; "
                                  "padding: 40px;")
        self._layout.addWidget(self._empty)

        # comparison table
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(False)
        self._table.hide()
        self._layout.addWidget(self._table, 1)

        self._rebuild_table()

    # ------------------------------------------------------------------
    # slots
    # ------------------------------------------------------------------
    def _render_slots(self):
        for i, frame in enumerate(self._slot_frames):
            lay = frame.layout()
            while lay.count():
                child = lay.takeAt(0).widget()
                if child is not None:
                    child.deleteLater()
            if i < len(self._players):
                p = self._players[i]
                name = _safe(lambda: getattr(p, "full_name", "?"), "?")
                meta = (f"{_safe(lambda: str(getattr(p, 'team_name', '')), '')} · "
                        f"{self._pos_str(p)} · {self._overall(p)} OVR")
                name_l = QLabel(str(name))
                name_l.setStyleSheet("font-weight: 700; font-size: 14px;")
                name_l.setWordWrap(True)
                meta_l = QLabel(meta)
                meta_l.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                rm = QPushButton("Remove")
                rm.setProperty("slot", i)
                rm.clicked.connect(self._on_remove_slot)
                lay.addWidget(name_l)
                lay.addWidget(meta_l)
                lay.addWidget(rm)
                frame.setStyleSheet(
                    "QFrame#tile { border: 1px solid #2a3a5f; "
                    "border-radius: 8px; background: #141c30; }")
            else:
                btn = QPushButton("+  Add player")
                btn.setProperty("slot", i)
                btn.setMinimumHeight(60)
                btn.clicked.connect(self._on_slot_clicked)
                lay.addWidget(btn)
                if i == self._active_slot:
                    frame.setStyleSheet(
                        "QFrame#tile { border: 2px solid #3B82F6; "
                        "border-radius: 8px; background: #141c30; }")
                else:
                    frame.setStyleSheet(
                        "QFrame#tile { border: 1px dashed #3a4a6e; "
                        "border-radius: 8px; background: transparent; }")

    def _on_slot_clicked(self):
        btn = self.sender()
        self._active_slot = int(btn.property("slot"))
        self._render_slots()
        self._search.setFocus()
        self._search.selectAll()

    def _on_remove_slot(self):
        btn = self.sender()
        idx = int(btn.property("slot"))
        if 0 <= idx < len(self._players):
            del self._players[idx]
        if self._active_slot >= len(self._players):
            self._active_slot = -1
        self._render_slots()
        self._rebuild_table()

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def _on_search_text(self, _text):
        self._search_timer.start()

    def _run_search(self):
        q = self._search.text().strip().lower()
        self._results.clear()
        if len(q) < 2:
            self._results.hide()
            return
        added_ids = {str(_safe(lambda: getattr(p, "id", ""), ""))
                     for p in self._players}
        shown = 0
        for p, tname in self._all_players():
            if shown >= 25:
                break
            name = _safe(lambda: getattr(p, "full_name", ""), "") or ""
            if q not in name.lower():
                continue
            pid = str(_safe(lambda: getattr(p, "id", ""), ""))
            item = QListWidgetItem(
                f"{name}  ·  {tname or 'Free Agent'}  ·  {self._pos_str(p)}"
                f"  ·  {self._overall(p)} OVR")
            item.setData(Qt.UserRole, p)
            if pid in added_ids:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self._results.addItem(item)
            shown += 1
        if shown == 0:
            self._results.addItem(QListWidgetItem("No matches"))
        self._results.show()

    def _on_result_chosen(self, item):
        p = item.data(Qt.UserRole)
        if p is None:
            return
        if len(self._players) >= self.MAX_PLAYERS:
            QMessageBox.information(self, "Compare",
                                    "You can compare at most 4 players.")
            return
        ids = {str(_safe(lambda: getattr(q, "id", ""), ""))
               for q in self._players}
        if str(_safe(lambda: getattr(p, "id", ""), "")) in ids:
            return
        slot = self._active_slot
        if 0 <= slot < self.MAX_PLAYERS:
            if slot < len(self._players):
                self._players[slot] = p
            else:
                while len(self._players) < slot:
                    self._players.append(None)
                self._players.append(p)
            self._players = [q for q in self._players if q is not None]
        else:
            self._players.append(p)
        self._active_slot = -1
        self._search.clear()
        self._results.hide()
        self._render_slots()
        self._rebuild_table()

    # ------------------------------------------------------------------
    # deep-link equivalent: web used ?p1=&p2=&p3=&p4=
    # ------------------------------------------------------------------
    def set_players(self, players):
        """Seed the comparison with player objects or id strings."""
        resolved = []
        seen = set()
        for entry in (players or [])[:self.MAX_PLAYERS]:
            if isinstance(entry, (str, int)):
                obj, _team = self._find_player(entry)
            else:
                obj = entry
            if obj is None:
                continue
            pid = str(_safe(lambda: getattr(obj, "id", ""), ""))
            if pid and pid in seen:
                continue
            seen.add(pid)
            resolved.append(obj)
        self._players = resolved
        self._active_slot = -1
        self._render_slots()
        self._rebuild_table()

    def refresh(self):
        self._render_slots()
        self._rebuild_table()

    # ------------------------------------------------------------------
    # player data (port of web _player_payload)
    # ------------------------------------------------------------------
    def _player_data(self, p):
        goalie = self._is_goalie(p)
        name = _safe(lambda: getattr(p, "full_name", "?"), "?")
        team_name = (_safe(lambda: str(getattr(p, "team_name", "")), "")
                     or "Free Agent")
        pos = self._pos_str(p)
        age = _safe(lambda: int(getattr(p, "age", 0) or 0), 0)

        # stats
        st = _safe(lambda: getattr(p, "stats", None))
        stats = []
        if goalie:
            for key, label, field, hb in _STAT_DEFS_GOALIE:
                raw = _safe(lambda: getattr(st, field, 0) or 0, 0)
                if key == "SV%":
                    disp, num = f"{float(raw):.3f}", float(raw)
                elif key == "GAA":
                    disp, num = f"{float(raw):.2f}", float(raw)
                else:
                    disp, num = str(int(raw)), int(raw)
                stats.append({"key": key, "label": label, "display": disp,
                              "numval": num, "higher_better": hb,
                              "bar": False})
        else:
            g = _safe(lambda: int(getattr(st, "goals", 0) or 0), 0)
            a = _safe(lambda: int(getattr(st, "assists", 0) or 0), 0)
            pm = _safe(lambda: int(getattr(p, "plus_minus", 0) or 0), 0)
            vals = {"G": g, "A": a, "PTS": g + a, "+/-": pm}
            for key, label, field, hb in _STAT_DEFS_SKATER:
                if key in vals:
                    num = vals[key]
                else:
                    num = _safe(lambda: int(getattr(st, field, 0) or 0), 0)
                stats.append({"key": key, "label": label,
                              "display": str(num), "numval": num,
                              "higher_better": hb, "bar": False})

        # contract
        c = _safe(lambda: getattr(p, "contract", None))
        sal = _safe(lambda: int(getattr(c, "salary", 0) or 0),
                    0) if c is not None else 0
        yrs = _safe(lambda: getattr(c, "years_remaining", None),
                    None) if c is not None else None
        contract = [
            {"key": "CAPHIT", "label": "Cap Hit",
             "display": _fmt_money(sal) if sal else "--",
             "numval": sal, "higher_better": False, "bar": False},
            {"key": "TERM", "label": "Term Remaining",
             "display": (f"{yrs} yr{'s' if yrs != 1 else ''}"
                         if yrs is not None else "--"),
             "numval": yrs if yrs is not None else -1,
             "higher_better": False, "bar": False},
        ]

        # attribute groups
        lists = ([("Technical", _GOALIE_TECHNICAL),
                  ("Mental", _GOALIE_MENTAL),
                  ("Physical", _GOALIE_PHYSICAL)] if goalie else
                 [("Technical", _SKATER_TECHNICAL),
                  ("Mental", _SKATER_MENTAL),
                  ("Physical", _SKATER_PHYSICAL)])
        attr_groups = []
        for gname, fields in lists:
            rows = []
            for label, field in fields:
                val = _safe(lambda: getattr(p, field, None))
                if val is None and field in ("offensive_positioning",
                                             "defensive_positioning"):
                    val = _safe(lambda: getattr(p, "positioning", None))
                if val is None:
                    continue
                rows.append((label, int(_to100(val))))
            attr_groups.append({"name": gname, "rows": rows})

        return {"obj": p, "name": str(name), "team": team_name,
                "position": pos, "age": age, "overall": self._overall(p),
                "is_goalie": goalie, "stats": stats, "contract": contract,
                "attr_groups": attr_groups}

    # ------------------------------------------------------------------
    # table
    # ------------------------------------------------------------------
    def _rebuild_table(self):
        datas = []
        for p in self._players:
            try:
                datas.append(self._player_data(p))
            except Exception:
                continue
        n = len(datas)
        if n < 2:
            self._table.hide()
            self._empty.show()
            return
        self._empty.hide()
        self._table.show()

        # Build unified row list:
        # ("section", title) | ("row", label, [cellspec...])
        # cellspec: {display, numval|None, higher_better, bar}
        rows = []
        def _cells_for(key, source):
            cells = []
            for d in datas:
                match = next((s for s in d[source] if s["key"] == key),
                             None)
                cells.append(match or {"display": "—", "numval": None,
                                       "higher_better": True, "bar": False})
            return cells

        rows.append(("section", "Season Stats"))
        stat_labels = {}
        for d in datas:
            for s in d["stats"]:
                stat_labels[s["key"]] = s["label"]
        for key in STAT_ORDER:
            if key not in stat_labels:
                continue
            rows.append(("row", stat_labels[key],
                         _cells_for(key, "stats")))

        rows.append(("section", "Contract"))
        for key in ("CAPHIT", "TERM"):
            label = "Cap Hit" if key == "CAPHIT" else "Term Remaining"
            rows.append(("row", label, _cells_for(key, "contract")))

        # -- attributes: union of labels per group, in profile order --
        groups = []
        for d in datas:
            for g in d["attr_groups"]:
                ex = next((x for x in groups if x["name"] == g["name"]),
                          None)
                if ex is None:
                    ex = {"name": g["name"], "labels": []}
                    groups.append(ex)
                for label, _v in g["rows"]:
                    if label not in ex["labels"]:
                        ex["labels"].append(label)
        for g in groups:
            rows.append(("section", f"{g['name']} Attributes"))
            for label in g["labels"]:
                cells = []
                for d in datas:
                    val = None
                    for gg in d["attr_groups"]:
                        if gg["name"] == g["name"]:
                            for rl, rv in gg["rows"]:
                                if rl == label:
                                    val = rv
                                    break
                    cells.append({"display": str(val) if val is not None
                                  else "—",
                                  "numval": val, "higher_better": True,
                                  "bar": val is not None})
                rows.append(("row", label, cells))

        t = self._table
        t.setSortingEnabled(False)
        t.clear()
        t.setRowCount(len(rows) + 1)   # + header row
        t.setColumnCount(n + 1)
        t.setHorizontalHeaderLabels([""] + [d["name"] for d in datas])
        t.horizontalHeader().setStretchLastSection(False)
        t.setColumnWidth(0, 190)
        for c in range(1, n + 1):
            t.setColumnWidth(c, 200)

        # header row (row 0): player cards
        for c, d in enumerate(datas, start=1):
            head = QLabel(
                f"<b style='font-size:14px'>{d['name']}</b><br>"
                f"<span style='color:#9aa4b8'>{d['team']} · {d['position']} "
                f"· Age {d['age']}</span><br>"
                f"<b style='color:#3B82F6'>{d['overall']} OVR</b>")
            head.setAlignment(Qt.AlignCenter)
            head.setWordWrap(True)
            t.setCellWidget(0, c, head)
        t.setRowHeight(0, 76)
        corner = QTableWidgetItem("")
        corner.setFlags(Qt.NoItemFlags)
        t.setItem(0, 0, corner)

        for r, row in enumerate(rows, start=1):
            if row[0] == "section":
                item = QTableWidgetItem(row[1].upper())
                item.setFlags(Qt.NoItemFlags)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.white)
                item.setBackground(Qt.darkBlue)
                t.setItem(r, 0, item)
                t.setSpan(r, 0, 1, n + 1)
                t.setRowHeight(r, 26)
                continue
            _tag, label, cells = row
            lab = QTableWidgetItem(label)
            lab.setFlags(Qt.NoItemFlags)
            lab.setForeground(Qt.lightGray)
            t.setItem(r, 0, lab)

            # winner highlighting (direction-aware)
            vals = [c["numval"] for c in cells
                    if isinstance(c["numval"], (int, float))]
            win_idx, lose_idx = set(), set()
            if len(vals) >= 2:
                hb = cells[0]["higher_better"]
                best = max(vals) if hb else min(vals)
                worst = min(vals) if hb else max(vals)
                if best != worst:
                    for i, c in enumerate(cells):
                        if c["numval"] == best:
                            win_idx.add(i)
                        elif c["numval"] == worst:
                            lose_idx.add(i)

            for c, cell in enumerate(cells, start=1):
                i = c - 1
                if cell.get("bar") and isinstance(cell["numval"],
                                                 (int, float)):
                    wrap = QFrame()
                    lay = QVBoxLayout(wrap)
                    lay.setContentsMargins(8, 2, 8, 2)
                    lay.addWidget(_compact_bar(int(cell["numval"])))
                    if i in win_idx:
                        wrap.setStyleSheet(WIN_STYLE)
                    elif i in lose_idx:
                        wrap.setStyleSheet(LOSE_STYLE)
                    else:
                        wrap.setStyleSheet(NEUTRAL_STYLE)
                    t.setCellWidget(r, c, wrap)
                    t.setRowHeight(r, 30)
                else:
                    item = QTableWidgetItem(str(cell["display"]))
                    item.setFlags(Qt.NoItemFlags)
                    item.setTextAlignment(Qt.AlignCenter)
                    if i in win_idx:
                        item.setForeground(Qt.green)
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    elif i in lose_idx:
                        item.setForeground(Qt.red)
                    t.setItem(r, c, item)
                    if t.rowHeight(r) < 24:
                        t.setRowHeight(r, 24)
