"""Trade Deadline Center: countdown, stance, market, rumors.

Native port of the web UI deadline screen (web_ui/templates/deadline.html
+ web_ui/screens/deadline.py + web_ui/static/js/deadline.js). Calls the
game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - trade_deadline_manager: trade_deadline_date, get_deadline_manager,
    TradeDeadlineManager clock (start_clock / clock_active /
    clock_display / advance_clock / time_until_close / clock_progress)
  - media_rumors: generate_rumors, get_impact_players
  - league standings (wins/losses/ot_losses) for buyers/sellers thirds
  - league._web_deadline_stance (declared stance scratch)
"""

from datetime import date, datetime

from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

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
# game-data helpers (ported from web_ui/screens/deadline.py)
# ---------------------------------------------------------------------------

def _deadline_manager(game):
    try:
        from trade_deadline_manager import get_deadline_manager
        return get_deadline_manager(_resolve_gm(game))
    except Exception:
        return None


def _deadline_date(league):
    try:
        from trade_deadline_manager import trade_deadline_date
        return trade_deadline_date(league)
    except Exception:
        return None


def _today(game):
    d = _safe(lambda: getattr(_resolve_gm(game), "current_date", None))
    try:
        return d.date() if isinstance(d, datetime) else d
    except Exception:
        return date.today()


def _team_points(t):
    try:
        return 2 * int(getattr(t, "wins", 0) or 0) + int(
            getattr(t, "ot_losses", 0) or getattr(t, "otl", 0) or 0)
    except Exception:
        return 0


def _team_record(t):
    try:
        w = int(getattr(t, "wins", 0) or 0)
        l = int(getattr(t, "losses", 0) or 0)
        otl = int(getattr(t, "ot_losses", 0)
                  or getattr(t, "otl", 0) or 0)
        return f"{w}-{l}-{otl}"
    except Exception:
        return ""


def _compute_stance(game, league, gm):
    """Buyer/seller/tweener verdict + positional needs + cap space.
    Mirrors TradeDeadlineCenter._compute_stance on real data."""
    user = _safe(lambda: gm.user_team) or _safe(lambda: game.user_team)
    if user is None or league is None:
        return None
    teams = [t for t in (_safe(lambda: list(league.teams), []) or [])
             if hasattr(t, "wins") and hasattr(t, "team_name")]
    ordered = sorted(teams, key=_team_points, reverse=True)
    uname = _safe(lambda: user.team_name, "")
    rank = None
    for i, t in enumerate(ordered):
        if t is user or getattr(t, "team_name", None) == uname:
            rank = i + 1
            break
    n = len(ordered)
    games = (int(getattr(user, "wins", 0) or 0)
             + int(getattr(user, "losses", 0) or 0)
             + int(getattr(user, "ot_losses", 0)
                   or getattr(user, "otl", 0) or 0))
    if rank is None or n < 2 or games == 0:
        verdict, reason = ("TBD",
                           "Season hasn't started — no standings data yet.")
    elif rank / n <= 1 / 3:
        verdict, reason = ("BUYER",
                           f"{rank} of {n} in the standings — a contender "
                           "should load up.")
    elif rank / n >= 2 / 3:
        verdict, reason = ("SELLER",
                           f"{rank} of {n} in the standings — sell "
                           "rentals, stockpile picks.")
    else:
        verdict, reason = ("TWEENER",
                           f"{rank} of {n} in the standings — one move "
                           "either way.")

    needs = []
    try:
        groups = {"Forwards": ("C", "LW", "RW"),
                  "Defense": ("LD", "RD", "D"),
                  "Goalies": ("G",)}
        roster = list(getattr(user, "roster", []) or [])
        avgs = []
        for gname, codes in groups.items():
            ovrs = []
            for pl in roster:
                pp = getattr(pl, "primary_position", None)
                code = getattr(pp, "value", str(pp))
                if code in codes:
                    try:
                        ovrs.append(pl.overall_rating())
                    except Exception:
                        pass
            if ovrs:
                avgs.append((gname, sum(ovrs) / len(ovrs), len(ovrs)))
        avgs.sort(key=lambda x: x[1])
        needs = [{"group": g, "avg_ovr": round(a, 1), "count": c}
                 for g, a, c in avgs[:2]]
    except Exception:
        pass
    try:
        cap_space = int(getattr(user, "cap_space", 0) or 0)
    except Exception:
        cap_space = None
    return {
        "verdict": verdict, "reason": reason,
        "rank": rank, "of": n, "record": _team_record(user),
        "needs": needs, "cap_space": cap_space,
    }


def _market(game, league, gm):
    """Buyers/sellers from real standings thirds + impact players from
    the real trade market (media_rumors.get_impact_players) + recent
    deadline deals from trade history."""
    teams = [t for t in (_safe(lambda: list(league.teams), []) or [])
             if hasattr(t, "wins") and hasattr(t, "team_name")]
    ordered = sorted(teams, key=_team_points, reverse=True)
    n = len(ordered)

    def _card(t):
        try:
            cap = int(getattr(t, "cap_space", 0) or 0)
        except Exception:
            cap = None
        return {
            "team": getattr(t, "team_name", "?"),
            "is_user": bool(getattr(t, "is_user_team", False)),
            "record": _team_record(t),
            "points": _team_points(t),
            "cap_space": cap,
        }

    buyers = [_card(t) for t in ordered[:max(1, n // 3)]] if n else []
    sellers = ([_card(t) for t in ordered[-(max(1, n // 3)):]] if n else [])
    sellers.reverse()

    impact = []
    try:
        import media_rumors as mr
        for ip in mr.get_impact_players(game_manager=gm, league=league,
                                        count=8) or []:
            impact.append({
                "name": ip.get("name", "?"),
                "pos": ip.get("pos", ""),
                "team": ip.get("team", ""),
                "status": ip.get("status", ""),
                "value": ip.get("value", ""),
            })
    except Exception:
        pass

    recent_deals = []
    try:
        hist = _safe(lambda: list(getattr(gm, "trade_history", None)
                                   or []), []) or []
        for ct in reversed(hist[-8:]):
            s = _safe(lambda: str(getattr(ct, "summary", "") or ""), "")
            d = _safe(lambda: str(getattr(ct, "date", "") or ""), "")
            if s:
                recent_deals.append({"summary": s, "date": d})
    except Exception:
        pass
    return {"buyers": buyers, "sellers": sellers, "impact": impact,
            "recent_deals": recent_deals}


def _rumors(game, gm, league):
    try:
        import media_rumors as mr
        dm = _deadline_manager(game)
        if dm is None:
            return []
        return (mr.generate_rumors(deadline_manager=dm, game_manager=gm,
                                   league=league) or [])
    except Exception:
        return []


def _declare_stance(game, stance):
    """Declare deadline stance (mirrors /api/deadline/stance; stored on
    the league as web scratch). Returns (ok, message)."""
    stance = str(stance or "").strip().lower()
    if stance not in ("buyer", "seller", "stand pat", "tweener"):
        return False, "stance must be buyer/seller/stand pat/tweener"
    league = _user_league(game)
    if league is None:
        return False, "no league"
    try:
        league._web_deadline_stance = stance
    except Exception:
        return False, "could not save"
    return True, stance


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class DeadlineScreen(BaseScreen):
    """Trade Deadline Center: countdown + 30-minute game clock, stance
    pills, buyers/sellers market, impact players, rumors, recent deals."""

    title = "Deadline"

    _STANCES = (("Buyer", "buyer"), ("Seller", "seller"),
                ("Stand Pat", "stand pat"), ("Tweener", "tweener"))

    def _build_body(self):
        self._stance_btns = {}
        self._declared = ""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(12)
        scroll.setWidget(body)
        self._layout.addWidget(scroll, 1)

        # --- countdown ---
        count_group = QGroupBox("Countdown")
        cg = QVBoxLayout(count_group)
        self._date_lbl = QLabel("")
        cg.addWidget(self._date_lbl)
        count_row = QHBoxLayout()
        self._days_num = QLabel("—")
        self._days_num.setObjectName("section-header")
        self._days_num.setStyleSheet("font-size: 42px;")
        count_row.addWidget(self._days_num)
        self._count_lbl = QLabel("")
        self._count_lbl.setWordWrap(True)
        count_row.addWidget(self._count_lbl, 1)
        cg.addLayout(count_row)
        self._clock_row = QHBoxLayout()
        self._clock_lbl = QLabel("")
        self._clock_lbl.setWordWrap(True)
        self._clock_row.addWidget(self._clock_lbl, 1)
        self._advance_btn = QPushButton("+30 min")
        self._advance_btn.clicked.connect(self._on_advance_clock)
        self._clock_row.addWidget(self._advance_btn)
        cg.addLayout(self._clock_row)
        lay.addWidget(count_group)

        # --- stance ---
        stance_group = QGroupBox("Your stance")
        sg = QVBoxLayout(stance_group)
        pill_row = QHBoxLayout()
        for label, val in self._STANCES:
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _c, v=val: self._on_stance(v))
            self._stance_btns[val] = b
            pill_row.addWidget(b)
        pill_row.addStretch()
        sg.addLayout(pill_row)
        self._verdict_lbl = QLabel("")
        self._verdict_lbl.setWordWrap(True)
        sg.addWidget(self._verdict_lbl)
        self._needs_lbl = QLabel("")
        self._needs_lbl.setWordWrap(True)
        sg.addWidget(self._needs_lbl)
        lay.addWidget(stance_group)

        # --- market ---
        market_row = QHBoxLayout()
        buyers_group = QGroupBox("Buyers")
        bg = QVBoxLayout(buyers_group)
        self._buyers_lbl = QLabel("")
        self._buyers_lbl.setWordWrap(True)
        bg.addWidget(self._buyers_lbl)
        market_row.addWidget(buyers_group)
        sellers_group = QGroupBox("Sellers")
        sg2 = QVBoxLayout(sellers_group)
        self._sellers_lbl = QLabel("")
        self._sellers_lbl.setWordWrap(True)
        sg2.addWidget(self._sellers_lbl)
        market_row.addWidget(sellers_group)
        lay.addLayout(market_row)

        # --- impact players ---
        impact_group = QGroupBox("Impact players on the market")
        ig = QVBoxLayout(impact_group)
        self._impact_lbl = QLabel("")
        self._impact_lbl.setWordWrap(True)
        ig.addWidget(self._impact_lbl)
        lay.addWidget(impact_group)

        # --- rumors ---
        rumor_group = QGroupBox("Rumor mill")
        rg = QVBoxLayout(rumor_group)
        self._rumors_lbl = QLabel("")
        self._rumors_lbl.setWordWrap(True)
        rg.addWidget(self._rumors_lbl)
        lay.addWidget(rumor_group)

        # --- recent deals ---
        deals_group = QGroupBox("Recent deadline deals")
        dg = QVBoxLayout(deals_group)
        self._deals_lbl = QLabel("")
        self._deals_lbl.setWordWrap(True)
        dg.addWidget(self._deals_lbl)
        lay.addWidget(deals_group)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._paint_clock)
        self.refresh()

    # -- refresh ----------------------------------------------------------

    def refresh(self):
        try:
            game = self.game
            gm = _resolve_gm(game)
            league = _user_league(game)
            if league is None:
                self._status_lbl.setText(
                    "Deadline Center unavailable — no league loaded.")
                return
            dd = _deadline_date(league)
            today = _today(gm)
            days_left = (dd - today).days if dd and today else None
            is_day = bool(dd and today and dd == today)
            passed = bool(days_left is not None and days_left < 0)

            self._date_lbl.setText(
                (dd.strftime("%B %d, %Y") if dd else "TBD")
                + " · 3:00 PM ET")
            if passed:
                self._days_num.setText("✕")
                self._count_lbl.setText("the deadline has passed")
            elif is_day:
                self._days_num.setText("0")
                self._count_lbl.setText(
                    "DEADLINE DAY — deals lock at 3 PM ET")
            elif days_left is not None:
                self._days_num.setText(str(days_left))
                self._count_lbl.setText(
                    "day to the deadline" if days_left == 1
                    else "days to the deadline")
            else:
                self._count_lbl.setText("Deadline date TBD.")

            # stance + market + rumors
            self._paint_stance(_compute_stance(game, league, gm))
            self._paint_market(_market(game, league, gm))
            self._paint_rumors(_rumors(game, gm, league))

            # deadline-day game clock: start at 9 AM, advance +30 min.
            dm = _deadline_manager(game)
            self._dm = dm
            self._is_day = is_day
            self._today = today
            if is_day and dm is not None:
                try:
                    if not dm.clock_active(today):
                        dm.start_clock(today)
                except Exception:
                    pass
            self._paint_clock()
            if is_day and dm is not None:
                if not self._clock_timer.isActive():
                    self._clock_timer.start(30_000)
            else:
                self._clock_timer.stop()
        except Exception as e:
            self._status_lbl.setText(f"Could not load deadline center: {e}")

    # -- countdown / clock -------------------------------------------------

    def _paint_clock(self):
        dm = getattr(self, "_dm", None)
        if not dm or not getattr(self, "_is_day", False):
            self._clock_lbl.setText("")
            self._advance_btn.setEnabled(False)
            self._advance_btn.setVisible(False)
            return
        self._advance_btn.setVisible(True)
        try:
            info = dm.get_time_until_deadline()
            display = dm.clock_display()
            if info.get("expired"):
                self._clock_lbl.setText(
                    f"Game clock: {display} — DEADLINE PASSED.")
                self._advance_btn.setEnabled(False)
            else:
                left = info.get("formatted", "")
                self._clock_lbl.setText(
                    f"Game clock: {display} · {left} until the 3 PM ET "
                    "cutoff (30-minute increments)")
                self._advance_btn.setEnabled(True)
        except Exception:
            self._clock_lbl.setText("")
            self._advance_btn.setEnabled(False)

    def _on_advance_clock(self):
        dm = getattr(self, "_dm", None)
        if dm is None:
            return
        try:
            res = dm.advance_clock()  # +30 min default
        except Exception as e:
            QMessageBox.warning(self, "Deadline clock",
                                f"Could not advance the clock: {e}")
            return
        self._paint_clock()
        if res.get("expired"):
            self._status_lbl.setText(
                "The deadline has passed — deals are locked.")

    # -- stance ------------------------------------------------------------

    def _paint_stance(self, s):
        if not s:
            self._verdict_lbl.setText("No team data.")
            return
        verdict = s.get("verdict", "")
        cls = ("BUYER" if verdict == "BUYER"
               else "SELLER" if verdict == "SELLER" else "")
        color = {"BUYER": "#3fb950", "SELLER": "#e5484d"}.get(cls, "")
        self._verdict_lbl.setText(
            f"<b style='color:{color}'>{verdict}</b> — {s.get('reason', '')}"
            + (f"<br>{s.get('record', '')}"
               + (f" · {s['rank']} of {s['of']}"
                  if s.get("rank") else "")
               if s.get("record") else ""))
        needs = s.get("needs") or []
        cap = s.get("cap_space")
        bits = []
        if needs:
            bits.append("Weakest areas: " + "; ".join(
                f"{n['group']} (avg {n['avg_ovr']} OVR, "
                f"{n['count']} players)" for n in needs))
        if cap is not None:
            bits.append(f"Cap space: {_fmt_money(cap)}")
        self._needs_lbl.setText("<br>".join(bits))

        declared = (_safe(lambda: getattr(
            _user_league(self.game), "_web_deadline_stance", ""), "")
                    or "")
        self._declared = str(declared).strip().lower()
        for val, b in self._stance_btns.items():
            b.setChecked(val == self._declared)

    def _on_stance(self, val):
        # Optimistic toggle; revert on failure.
        prev = self._declared
        for v, b in self._stance_btns.items():
            b.setChecked(v == val)
        self._declared = val
        ok, msg = _declare_stance(self.game, val)
        if ok:
            self._status_lbl.setText(f"Deadline stance: {val.title()}.")
        else:
            for v, b in self._stance_btns.items():
                b.setChecked(v == prev)
            self._declared = prev
            QMessageBox.warning(self, "Deadline stance",
                                f"Could not save stance: {msg}")

    # -- market / rumors -----------------------------------------------------

    def _paint_market(self, m):
        def _rows(cards):
            out = []
            for t in cards:
                mark = " ★" if t.get("is_user") else ""
                out.append(
                    f"<b>{t['team']}</b>{mark} — {t['record']}, "
                    f"{t['points']} pts"
                    + (f" · {_fmt_money(t['cap_space'])} cap"
                       if t.get("cap_space") is not None else ""))
            return "<br>".join(out) if out else "—"

        self._buyers_lbl.setText(_rows(m.get("buyers") or []))
        self._sellers_lbl.setText(_rows(m.get("sellers") or []))

        impact = m.get("impact") or []
        if impact:
            self._impact_lbl.setText("<br><br>".join(
                f"<b>{i['name']}</b> ({i['pos']}) — {i['team']} · "
                f"{i['status']} · {i['value']} value" for i in impact))
        else:
            self._impact_lbl.setText("No impact players on the market "
                                     "right now.")

        deals = m.get("recent_deals") or []
        if deals:
            self._deals_lbl.setText("<br>".join(
                f"🤝 {d['summary']}"
                + (f" <i>({d['date']})</i>" if d.get("date") else "")
                for d in deals))
        else:
            self._deals_lbl.setText("No deadline deals yet.")

    def _paint_rumors(self, rumors):
        if rumors:
            self._rumors_lbl.setText("<br>".join(
                f"• {r if isinstance(r, str) else r.get('text') or r.get('title') or ''}"
                for r in rumors))
        else:
            self._rumors_lbl.setText("The mill is quiet… for now.")
