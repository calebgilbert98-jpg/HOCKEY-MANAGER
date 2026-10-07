"""Trade Block screen: full 3-tab management.

Tabs (matching the Tkinter TradeBlockWindow and the web port):
1. My Block -- your trade block with filters (position pills, min OVR,
   max age), add/remove, Shop, Simulate Offers, Generate Interest.
2. Interest -- AI teams interested in your block players, backed by the
   real league.trade_market store. Decline interest.
3. Other Teams -- other clubs' block players; Express Interest,
   Negotiate (jump to the trade center).

Native port of web_ui/templates/trade_block.html +
web_ui/screens/trade_block.py + web_ui/static/js/trade_block.js. Calls
the game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - game.trade_block (list; add/remove by id)
  - game.calculate_player_value(p)
  - game.process_trade_block_offers()
  - trade_market: get_market, add_target, _sync_user_block,
    _find_bidders, _today, deadline_heat, _heat_params
  - league.trade_history / add_news as needed
"""

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _pid(p):
    return str(_safe(lambda: getattr(p, "id", id(p)), ""))


def _player_name(p):
    return _safe(lambda: getattr(p, "full_name", "?"), "?")


def _pos_str(p):
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    raw = getattr(pos, "value", pos)
    try:
        return str(raw or "?").strip().upper()
    except Exception:
        return "?"


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
    except Exception:
        pass
    return _safe(lambda: int(getattr(p, "overall", 0) or 0), 0)


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,}"


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


def _user_league(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.league)
            or _safe(lambda: getattr(game, "league", None)))


# ---------------------------------------------------------------------------
# game-data helpers (ported from web_ui/screens/trade_block.py)
# ---------------------------------------------------------------------------

def _user_block(game):
    """User's trade block players (dedupe by id). Never raises."""
    block = _safe(lambda: list(getattr(game, "trade_block", None) or []),
                  []) or []
    seen, out = set(), []
    for p in block:
        try:
            pid = _pid(p)
        except Exception:
            pid = ""
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        out.append(p)
    return out


def _market_listings(game):
    try:
        import trade_market as tm
        league = _user_league(game)
        if league is None:
            return []
        market = tm.get_market(league)
        return _safe(lambda: list(market.get("listings", []) or []),
                     []) or []
    except Exception:
        return []


def _my_interest(game):
    """AI interest in the user's block players from the real
    trade_market store. Returns list of dicts; never raises."""
    out = []
    team = _user_team(game)
    my_name = _safe(lambda: getattr(team, "team_name", ""), "")
    for li in _market_listings(game):
        try:
            if not isinstance(li, dict):
                continue
            if li.get("source") != "user_block":
                continue
            seller = li.get("seller") or li.get("team") or ""
            if my_name and seller and seller != my_name:
                continue
            pname = li.get("player_name") or ""
            for r in (li.get("ai_interest") or []):
                if not isinstance(r, dict):
                    continue
                if r.get("status") == "Declined":
                    continue
                out.append({
                    "player": pname,
                    "player_id": str(li.get("player_id") or ""),
                    "team": r.get("team", ""),
                    "interest": r.get("interest") or r.get("level") or "",
                    "status": r.get("status") or "Open",
                })
        except Exception:
            continue
    return out


def _others_blocks(game):
    """Other teams' trade-block players: trade_market listings first,
    per-team trade_block attrs as fallback. Never raises."""
    out = []
    team = _user_team(game)
    my_name = _safe(lambda: getattr(team, "team_name", ""), "")
    for li in _market_listings(game):
        try:
            if not isinstance(li, dict):
                continue
            seller = li.get("seller") or li.get("team") or ""
            if not seller or (my_name and seller == my_name):
                continue
            if (li.get("source") or "") not in ("ai_block", "team_block",
                                                "block"):
                continue
            out.append({
                "player": li.get("player_name") or "?",
                "player_id": str(li.get("player_id") or ""),
                "team": seller,
                "position": li.get("position") or "?",
                "overall": int(li.get("overall") or 0),
            })
        except Exception:
            continue
    if not out:
        league = _user_league(game)
        teams = _safe(lambda: list(getattr(league, "teams", None) or []),
                      []) or []
        for t in teams:
            try:
                tn = _safe(lambda: getattr(t, "team_name", ""), "")
                if not tn or tn == my_name:
                    continue
                for p in (_safe(lambda: list(getattr(t, "trade_block",
                                                    None) or []), []) or []):
                    out.append({
                        "player": _player_name(p),
                        "player_id": _pid(p),
                        "team": tn,
                        "position": _pos_str(p),
                        "overall": _player_ovr(p),
                    })
            except Exception:
                continue
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return out


def _block_add(game, pids):
    team = _user_team(game)
    if team is None:
        return
    if not hasattr(game, "trade_block"):
        try:
            game.trade_block = []
        except Exception:
            return
    block = getattr(game, "trade_block", None) or []
    pool = []
    for lst in ("roster", "ahl_roster", "prospects"):
        pool.extend(_safe(lambda: list(getattr(team, lst, None) or []),
                          []) or [])
    for pid in pids:
        pid = str(pid)
        for p in pool:
            try:
                if _pid(p) == pid and p not in block:
                    block.append(p)
                    break
            except Exception:
                continue


def _block_remove(game, pids):
    block = _safe(lambda: list(getattr(game, "trade_block", None) or []),
                  []) or []
    for pid in pids:
        pid = str(pid)
        for p in list(block):
            try:
                if _pid(p) == pid:
                    block.remove(p)
                    break
            except Exception:
                continue


def _shop(game, player):
    """Shop Player: value + interested teams for one block player.
    Port of /api/trade_block/shop. Never raises."""
    out = {"player": _player_name(player), "player_id": _pid(player),
           "market_value": 0, "block_value": 0, "interested": []}
    try:
        base = int(_safe(lambda: game.calculate_player_value(player),
                         0) or 0)
    except Exception:
        base = 0
    out["market_value"] = base
    out["block_value"] = int(base * 0.85)
    pid = _pid(player)
    for li in _market_listings(game):
        try:
            if not isinstance(li, dict):
                continue
            if str(li.get("player_id") or "") != pid:
                continue
            for r in (li.get("ai_interest") or []):
                if isinstance(r, dict) and r.get("status") != "Declined":
                    out["interested"].append({
                        "team": r.get("team", ""),
                        "interest": r.get("interest") or r.get("level")
                        or "",
                    })
        except Exception:
            continue
    return out


def _suggest_value(game, player):
    try:
        base = int(_safe(lambda: game.calculate_player_value(player),
                         0) or 0)
    except Exception:
        base = 0
    return {"player": _player_name(player), "market_value": base,
            "block_value": int(base * 0.85)}


def _simulate_offers(game):
    """Simulate Offers: the real game method. Returns (ok, message)."""
    try:
        fn = getattr(game, "process_trade_block_offers", None)
        if not callable(fn):
            return False, "Offer simulation unavailable."
        fn()
        return True, ""
    except Exception as e:
        return False, f"Simulation failed: {e}"


def _generate_interest(game):
    """Generate Interest: mirror of TradeBlockWindow.generate_trade_interest
    -- sync the manual block into real trade_market listings, then run the
    genuine AI bidder computation per listing. Returns (ok, message)."""
    try:
        import trade_market as tm
        league = _user_league(game)
        if league is None:
            return False, "No league."
        market = tm.get_market(league)
        today = tm._today(game)
        heat = tm.deadline_heat(game, league, today)
        params = tm._heat_params(heat)
        tm._sync_user_block(game, league, market, today, params)
        for li in list(market.get("listings", []) or []):
            try:
                if (isinstance(li, dict)
                        and li.get("source") == "user_block"):
                    bidders = tm._find_bidders(
                        game, league, li, today, heat >= 0.5)
                    if bidders:
                        ai = li.setdefault("ai_interest", [])
                        seen = {r.get("team") for r in ai
                                if isinstance(r, dict)}
                        for b in bidders:
                            tname = (b.get("team") if isinstance(b, dict)
                                     else str(b))
                            if tname not in seen:
                                ai.append({
                                    "team": tname,
                                    "interest": (b.get("interest")
                                                 if isinstance(b, dict)
                                                 else ""),
                                    "status": "Open",
                                })
            except Exception:
                continue
        return True, ""
    except Exception as e:
        return False, f"Could not generate interest: {e}"


def _decline_interest(game, player_name, team_name):
    """Mirror of TradeBlockWindow.decline_interest: mark the team's row
    Declined on the real listing so it never resurrects."""
    try:
        import trade_market as tm
        league = _user_league(game)
        if league is None:
            return
        market = tm.get_market(league)
        for li in list(market.get("listings", []) or []):
            try:
                if not isinstance(li, dict):
                    continue
                if (li.get("player_name") or "") != player_name:
                    continue
                for r in (li.get("ai_interest") or []):
                    if (isinstance(r, dict)
                            and r.get("team") == team_name
                            and r.get("status") != "Declined"):
                        r["status"] = "Declined"
                dteams = li.setdefault("declined_teams", [])
                if team_name not in dteams:
                    dteams.append(team_name)
            except Exception:
                continue
    except Exception:
        pass


def _express_interest(game, player_name, team_name, player_id):
    """Mirror of TradeBlockWindow.express_interest: record genuine
    interest via trade_market.add_target (canonical user store)."""
    try:
        import trade_market as tm
        league = _user_league(game)
        if league is None:
            return
        player = None
        for t in (getattr(league, "teams", None) or []):
            try:
                if getattr(t, "team_name", "") != team_name:
                    continue
                for p in (getattr(t, "roster", None) or []):
                    if (_pid(p) == str(player_id)
                            or _player_name(p) == player_name):
                        player = p
                        break
                break
            except Exception:
                continue
        if player is not None:
            tm.add_target(
                player, source="user",
                note=f"Trade interest expressed ({team_name} block)")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# add-players dialog
# ---------------------------------------------------------------------------

class _AddPlayersDialog(QDialog):
    """Add modal with roster search: pick players to add to the block."""

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self._game = game
        self.setWindowTitle("Add to trade block")
        self.setMinimumWidth(520)
        self._pids = set()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select players to put on the trade block:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search your roster…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_check)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._add_btn = QPushButton("Add Selected")
        self._add_btn.setObjectName("primary-btn")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)
        layout.addLayout(btn_row)

        self._pool = []
        self._load()

    def _load(self):
        team = _user_team(self._game)
        pool = []
        for lst in ("roster", "ahl_roster", "prospects"):
            pool.extend(_safe(lambda: list(getattr(team, lst, None) or []),
                              []) or [])
        on_block = {_pid(p) for p in _user_block(self._game)}
        self._pool = [p for p in pool if _pid(p) not in on_block]
        self._filter("")

    def _filter(self, text):
        q = (text or "").lower()
        self._list.blockSignals(True)
        self._list.clear()
        self._pids = set()
        for p in self._pool:
            name = _player_name(p)
            if q and q not in name.lower():
                continue
            item = QListWidgetItem(
                f"{name}  ·  {_pos_str(p)} · {_player_ovr(p)} OVR")
            item.setData(Qt.UserRole, _pid(p))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_check(self, item):
        pid = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._pids.add(pid)
        else:
            self._pids.discard(pid)

    def _on_add(self):
        if not self._pids:
            QMessageBox.information(self, "Add to trade block",
                                    "Select at least one player.")
            return
        _block_add(self._game, list(self._pids))
        self.accept()


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class TradeBlockScreen(BaseScreen):
    """Three tabs: your block, AI interest in it, other teams' blocks."""

    title = "Trade Block"

    _POS_PILLS = ("All", "C", "W", "D", "G")

    def _build_body(self):
        self._pos_filter = "All"
        self._min_ovr = 0
        self._max_age = 0
        self._selected = None  # pid of the selected block player

        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        self._build_mine_tab()
        self._build_interest_tab()
        self._build_others_tab()

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)
        self._tabs.currentChanged.connect(self.refresh)

        self.refresh()

    # -- tab 1: my block -------------------------------------------------

    def _build_mine_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)

        filt_row = QHBoxLayout()
        self._pill_btns = {}
        for v in self._POS_PILLS:
            b = QPushButton(v)
            b.setCheckable(True)
            b.setChecked(v == "All")
            b.clicked.connect(lambda _c, val=v: self._set_pos(val))
            self._pill_btns[v] = b
            filt_row.addWidget(b)
        filt_row.addWidget(QLabel("Min OVR"))
        self._min_ovr_spin = QSpinBox()
        self._min_ovr_spin.setRange(0, 99)
        filt_row.addWidget(self._min_ovr_spin)
        filt_row.addWidget(QLabel("Max age"))
        self._max_age_spin = QSpinBox()
        self._max_age_spin.setRange(0, 60)
        filt_row.addWidget(self._max_age_spin)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_filters)
        filt_row.addWidget(apply_btn)
        filt_row.addStretch()
        lay.addLayout(filt_row)

        self._block_count = QLabel("")
        lay.addWidget(self._block_count)

        self._block_list = QListWidget()
        self._block_list.currentRowChanged.connect(self._on_block_select)
        lay.addWidget(self._block_list, 1)

        act_row = QHBoxLayout()
        add_btn = QPushButton("Add Players")
        add_btn.clicked.connect(self._on_add)
        act_row.addWidget(add_btn)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove)
        act_row.addWidget(remove_btn)
        self._shop_btn = QPushButton("Shop")
        self._shop_btn.clicked.connect(self._on_shop)
        act_row.addWidget(self._shop_btn)
        self._value_btn = QPushButton("Suggest Value")
        self._value_btn.clicked.connect(self._on_value)
        act_row.addWidget(self._value_btn)
        sim_btn = QPushButton("Simulate Offers")
        sim_btn.clicked.connect(self._on_simulate)
        act_row.addWidget(sim_btn)
        interest_btn = QPushButton("Generate Interest")
        interest_btn.clicked.connect(self._on_generate_interest)
        act_row.addWidget(interest_btn)
        act_row.addStretch()
        lay.addLayout(act_row)

        self._tabs.addTab(tab, "My Block")

    def _set_pos(self, val):
        self._pos_filter = val
        for v, b in self._pill_btns.items():
            b.setChecked(v == val)

    def _apply_filters(self):
        self._min_ovr = int(self._min_ovr_spin.value())
        self._max_age = int(self._max_age_spin.value())
        self._refresh_mine()

    def _block_entries(self):
        entries = []
        for p in _user_block(self.game):
            pos = _pos_str(p)
            ovr = _player_ovr(p)
            age = _safe(lambda: int(getattr(p, "age", 0) or 0), 0)
            if self._pos_filter != "All":
                hit = (pos == self._pos_filter
                       or (self._pos_filter == "W" and pos in ("LW", "RW"))
                       or (self._pos_filter == "D" and pos in ("LD", "RD")))
                if not hit:
                    continue
            if self._min_ovr and ovr < self._min_ovr:
                continue
            if self._max_age and age > self._max_age:
                continue
            entries.append((p, ovr))
        entries.sort(key=lambda e: e[1], reverse=True)
        return entries

    def _refresh_mine(self):
        entries = self._block_entries()
        self._block_list.clear()
        self._mine_players = [p for (p, _o) in entries]
        n = len(entries)
        self._block_count.setText(
            f"{n} player{'s' if n != 1 else ''} on your block")
        for p in self._mine_players:
            sal = _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
            age = _safe(lambda: int(getattr(p, "age", 0) or 0), 0)
            item = QListWidgetItem(
                f"{_player_ovr(p)} OVR  {_player_name(p)}  ·  "
                f"{_pos_str(p)} · Age {age} · {_fmt_money(sal)}")
            item.setData(Qt.UserRole, _pid(p))
            self._block_list.addItem(item)
        self._selected = None
        self._update_shop_state()

    def _on_block_select(self, row):
        if 0 <= row < len(getattr(self, "_mine_players", [])):
            self._selected = _pid(self._mine_players[row])
        else:
            self._selected = None
        self._update_shop_state()

    def _update_shop_state(self):
        self._shop_btn.setEnabled(self._selected is not None)
        self._value_btn.setEnabled(self._selected is not None)

    def _selected_player(self):
        if self._selected is None:
            return None
        for p in getattr(self, "_mine_players", []):
            if _pid(p) == self._selected:
                return p
        return None

    def _on_add(self):
        dlg = _AddPlayersDialog(self.game, self)
        if dlg.exec():
            self._refresh_mine()

    def _on_remove(self):
        if self._selected is None:
            QMessageBox.information(self, "Trade block",
                                    "Select a player first.")
            return
        _block_remove(self.game, [self._selected])
        self._refresh_mine()

    def _on_shop(self):
        p = self._selected_player()
        if p is None:
            return
        d = _shop(self.game, p)
        lines = [f"Market value: {_fmt_money(d['market_value'])}",
                 f"Trade-block value (15% discount): "
                 f"{_fmt_money(d['block_value'])}"]
        if d["interested"]:
            lines.append("\nInterested teams:")
            for i in d["interested"]:
                lines.append(f"  • {i['team']} — {i['interest']}")
        else:
            lines.append("\nNo teams showing significant interest yet. "
                         "Try Generate Interest.")
        QMessageBox.information(self, f"Shop: {d['player']}",
                                "\n".join(lines))

    def _on_value(self):
        p = self._selected_player()
        if p is None:
            return
        d = _suggest_value(self.game, p)
        QMessageBox.information(
            self, f"Trade value: {d['player']}",
            f"Market value: {_fmt_money(d['market_value'])}\n"
            f"Trade-block value: {_fmt_money(d['block_value'])} "
            "(15% discount)")

    def _on_simulate(self):
        ok, msg = _simulate_offers(self.game)
        if ok:
            QMessageBox.information(
                self, "Simulate offers",
                "Offer simulation complete — check your inbox for "
                "incoming offers.")
        else:
            QMessageBox.warning(self, "Simulate offers", msg)

    def _on_generate_interest(self):
        ok, msg = _generate_interest(self.game)
        if ok:
            QMessageBox.information(
                self, "Generate interest",
                "Interest generation complete — check the Trade "
                "Interest tab.")
            self._tabs.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "Generate interest", msg)

    # -- tab 2: interest --------------------------------------------------

    def _build_interest_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self._interest_list = QListWidget()
        lay.addWidget(self._interest_list, 1)
        btn_row = QHBoxLayout()
        neg_btn = QPushButton("Negotiate")
        neg_btn.clicked.connect(self._on_negotiate)
        btn_row.addWidget(neg_btn)
        dec_btn = QPushButton("Decline")
        dec_btn.clicked.connect(self._on_decline)
        btn_row.addWidget(dec_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        self._tabs.addTab(tab, "Interest")

    def _refresh_interest(self):
        self._interest_list.clear()
        self._interest_rows = _my_interest(self.game)
        if not self._interest_rows:
            self._interest_list.addItem(
                "No AI interest yet — use Generate Interest on your block.")
            return
        for r in self._interest_rows:
            bits = [r["player"], f"({r['team']})", r.get("interest") or ""]
            status = r.get("status") or "Open"
            if status != "Open":
                bits.append(f"[{status}]")
            item = QListWidgetItem(" ".join(b for b in bits if b))
            self._interest_list.addItem(item)

    def _interest_row(self):
        row = self._interest_list.currentRow()
        rows = getattr(self, "_interest_rows", [])
        if 0 <= row < len(rows):
            return rows[row]
        return None

    def _on_negotiate(self):
        # Jump to the trade center for this player.
        try:
            self.navigate_to("trades")
        except Exception:
            QMessageBox.information(
                self, "Negotiate",
                "Open the Trade Center to negotiate this deal.")

    def _on_decline(self):
        r = self._interest_row()
        if r is None:
            QMessageBox.information(self, "Decline interest",
                                    "Select an interest row first.")
            return
        _decline_interest(self.game, r["player"], r["team"])
        self._refresh_interest()

    # -- tab 3: other teams -----------------------------------------------

    def _build_others_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self._others_list = QListWidget()
        lay.addWidget(self._others_list, 1)
        btn_row = QHBoxLayout()
        exp_btn = QPushButton("Express Interest")
        exp_btn.clicked.connect(self._on_express)
        btn_row.addWidget(exp_btn)
        neg_btn = QPushButton("Negotiate")
        neg_btn.clicked.connect(self._on_negotiate)
        btn_row.addWidget(neg_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        self._tabs.addTab(tab, "Other Teams")

    def _refresh_others(self):
        self._others_list.clear()
        self._other_rows = _others_blocks(self.game)
        if not self._other_rows:
            self._others_list.addItem("No other block players listed.")
            return
        for d in self._other_rows:
            item = QListWidgetItem(
                f"{d['player']}  ·  {d['position']} · {d['overall']} OVR  "
                f"({d['team']})")
            self._others_list.addItem(item)

    def _on_express(self):
        row = self._others_list.currentRow()
        rows = getattr(self, "_other_rows", [])
        if not (0 <= row < len(rows)):
            QMessageBox.information(self, "Express interest",
                                    "Select a player first.")
            return
        d = rows[row]
        _express_interest(self.game, d["player"], d["team"],
                          d.get("player_id", ""))
        self._status(f"Interest expressed in {d['player']} "
                     f"({d['team']}).")

    # -- refresh ------------------------------------------------------------

    def refresh(self):
        try:
            idx = self._tabs.currentIndex()
        except Exception:
            idx = 0
        try:
            self._refresh_mine()
        except Exception:
            pass
        if idx == 1:
            try:
                self._refresh_interest()
            except Exception:
                pass
        if idx == 2:
            try:
                self._refresh_others()
            except Exception:
                pass

    def _status(self, text):
        self._status_lbl.setText(text)
