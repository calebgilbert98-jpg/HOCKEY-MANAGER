"""Trade Deadline Center: countdown, stance, market, rumors.

Native port of the web UI deadline screen (web_ui/templates/deadline.html
+ web_ui/screens/deadline.py + web_ui/static/js/deadline.js) plus the
mainline (Tkinter) TradeDeadlineCenter depth features from
trade_deadline_center.py:

  - Fire sale: lists your expiring contracts on the real trade block
    (trade_market.list_piece, source "user_block") so AI GMs can bid.
  - Player movement tracker: deadline-day deal log + movement stats from
    TradeDeadlineManager.trade_activity_log / get_deadline_summary.
  - Quick trade: streamlined offer workbench — live league partner list,
    your tradeable picks + expiring rentals vs. their real trade block,
    live trade_engine.evaluate_trade, send via trade_negotiation.send_offer
    (NTC veto + cap revalidation, consume-once).
  - Market analytics: 5-tab browser over
    TradeDeadlineManager.get_market_intelligence() /
    get_market_temperature() — overview + price trends (supply/demand),
    buyers & sellers, position needs, trade predictions, cap analysis.

Calls the game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - trade_deadline_manager: trade_deadline_date, get_deadline_manager,
    TradeDeadlineManager clock (start_clock / clock_active /
    clock_display / advance_clock / time_until_close / clock_progress)
  - media_rumors: generate_rumors, get_impact_players
  - league standings (wins/losses/ot_losses) for buyers/sellers thirds
  - league._web_deadline_stance (declared stance scratch)
  - trade_market: list_piece, refresh_trade_blocks, get_trade_blocks,
    resolve_player
  - trade_engine: asset_value, asset_label, evaluate_trade, trade_vetoes
  - trade_negotiation: send_offer, asset_summary
"""

from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen
from native_ui.safe import safe_call


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

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
    return safe_call(lambda: getattr(game, "game_manager", None),
                     context="deadline/_resolve_gm") or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: gm.user_team, context="deadline/_user_team/gm")
            or safe_call(lambda: getattr(game, "user_team", None),
                         context="deadline/_user_team/game"))


def _user_league(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: gm.league, context="deadline/_user_league/gm")
            or safe_call(lambda: getattr(game, "league", None),
                         context="deadline/_user_league/league"))


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
    d = safe_call(lambda: getattr(_resolve_gm(game), "current_date", None),
                  context="deadline/_today")
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
    user = (safe_call(lambda: gm.user_team, context="deadline/stance/user_team")
            or safe_call(lambda: game.user_team,
                         context="deadline/stance/game_user_team"))
    if user is None or league is None:
        return None
    teams = [t for t in (safe_call(lambda: list(league.teams), [],
                                   context="deadline/stance/teams") or [])
             if hasattr(t, "wins") and hasattr(t, "team_name")]
    ordered = sorted(teams, key=_team_points, reverse=True)
    uname = safe_call(lambda: user.team_name, "",
                      context="deadline/stance/team_name")
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
    teams = [t for t in (safe_call(lambda: list(league.teams), [],
                                   context="deadline/market/teams") or [])
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
        hist = (safe_call(lambda: list(getattr(gm, "trade_history", None)
                                       or []), [],
                          context="deadline/market/trade_history")
                or [])
        for ct in reversed(hist[-8:]):
            s = safe_call(lambda: str(getattr(ct, "summary", "") or ""), "",
                          context="deadline/market/deal_summary")
            d = safe_call(lambda: str(getattr(ct, "date", "") or ""), "",
                          context="deadline/market/deal_date")
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
# mainline-depth features (ported from trade_deadline_center.py)
# ---------------------------------------------------------------------------

def _pos_code(p):
    """Position code for a player (mirrors QuickTradeInterface._pos_code)."""
    try:
        pos = getattr(p, "primary_position", None)
        return getattr(pos, "value", None) or getattr(pos, "name", "?")
    except Exception:
        return "?"


def _ovr(p):
    try:
        return int(p.overall_rating())
    except Exception:
        return 0


def _expiring_contracts(user):
    """Roster players with exactly 1 year left on their contract."""
    out = []
    for p in (safe_call(lambda: list(getattr(user, "roster", None) or []),
                        [], context="deadline/firesale/roster")
              or []):
        try:
            if getattr(getattr(p, "contract", None),
                       "years_remaining", 99) == 1:
                out.append(p)
        except Exception:
            continue
    return out


def _fire_sale(game):
    """Fire sale (port of EmergencyTradeInterface._fire_sale).

    Lists every expiring contract on the user's roster on the trade block
    via the real trade_market store (source "user_block") so AI GMs can
    bid immediately, and mirrors them into the canonical team block
    (user_team.trade_block, read by refresh_trade_blocks). Returns a
    dict {ok, message, listed, skipped}. Never raises.
    """
    gm = _resolve_gm(game)
    league = _user_league(game)
    user = _user_team(game)
    if gm is None or league is None or user is None:
        return {"ok": False, "listed": 0, "skipped": 0,
                "message": "No league loaded — nothing was listed."}
    expiring = _expiring_contracts(user)
    if not expiring:
        return {"ok": False, "listed": 0, "skipped": 0,
                "message": "No expiring contracts on your roster — "
                           "nothing to list."}
    try:
        import trade_market as tmk
    except Exception:
        return {"ok": False, "listed": 0, "skipped": 0,
                "message": "Trade market unavailable — nothing was listed."}
    listed, skipped = 0, 0
    for p in expiring:
        pid = safe_call(lambda: getattr(p, "id", None),
                        context="deadline/firesale/pid")
        try:
            # Canonical native store: user_team.trade_block (live list,
            # mirrored into league.trade_blocks by refresh_trade_blocks).
            block = getattr(user, "trade_block", None)
            if not isinstance(block, list):
                block = []
                user.trade_block = block
            if pid is not None and not any(
                    safe_call(lambda: getattr(e, "id", None),
                              context="deadline/firesale/entry_id") == pid
                    for e in block):
                block.append(p)
            # Legacy app-level store (mainline used app.trade_block).
            gm_block = getattr(gm, "trade_block", None)
            if isinstance(gm_block, list) and pid is not None and not any(
                    safe_call(lambda: getattr(e, "id", None),
                              context="deadline/firesale/gm_entry_id") == pid
                    for e in gm_block):
                gm_block.append(p)
            # Real market listing so AI GMs can bid (source "user_block"
            # always gets a slot; returns None if already listed).
            li = tmk.list_piece(gm, league, user, p, source="user_block")
            if li is not None:
                listed += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    names = ", ".join(str(safe_call(lambda: getattr(p, "full_name", "?"),
                                    context="deadline/firesale/name") or "?")
                      for p in expiring[:4])
    if len(expiring) > 4:
        names += f" (+{len(expiring) - 4} more)"
    msg = (f"Fire sale: {listed} expiring contract(s) listed on the "
           f"trade block: {names}.")
    if skipped:
        msg += f" ({skipped} already listed or on cooldown.)"
    return {"ok": True, "listed": listed, "skipped": skipped, "message": msg}


def _movement_data(game):
    """Player movement tracker data.

    Real deadline-day stats from TradeDeadlineManager.get_deadline_summary()
    plus the raw trade_activity_log (the deal-by-deal record mainline's
    recent-trades list renders). Honest "--" when a stat is not yet known.
    Never raises.
    """
    dm = _deadline_manager(game)

    def _fmt(value, money=False):
        if value is None:
            return "--"
        try:
            if money and not int(value):
                return "--"
        except Exception:
            return "--"
        return f"${int(value)}M" if money else str(value)

    stats, log = {}, []
    if dm is not None:
        summary = safe_call(lambda: dm.get_deadline_summary(), {},
                            context="deadline/tracker/summary") or {}
        stats = summary.get("statistics", {}) or {}
        log = (safe_call(lambda: list(getattr(dm, "trade_activity_log",
                                              None) or []), [],
                         context="deadline/tracker/log")
               or [])
    deals = []
    for entry in reversed(log[-15:]):
        teams = safe_call(lambda: list(entry.get("teams_involved", []) or []),
                          [], context="deadline/tracker/entry_teams")
        teams = [t for t in teams if t]
        stamp = entry.get("timestamp")
        try:
            stamp = (stamp.strftime("%H:%M") if hasattr(stamp, "strftime")
                     else str(stamp or ""))
        except Exception:
            stamp = ""
        count = safe_call(lambda: int(entry.get("players_count", 0) or 0),
                          0, context="deadline/tracker/entry_count")
        ttype = str(entry.get("trade_type", "standard") or "standard")
        tid = str(entry.get("trade_id", "") or "")
        label = (" ↔ ".join(teams) if teams else "Deal")
        detail = f"{label} — {count} player{'s' if count != 1 else ''} ({ttype})"
        if tid:
            detail = f"[{tid}] {detail}"
        if stamp:
            detail += f" · {stamp}"
        deals.append(detail)
    return {
        "players_moved": _fmt(stats.get("players_moved")),
        "total_trades": _fmt(stats.get("total_trades")),
        "biggest_deal": _fmt(stats.get("biggest_deal_value"), money=True),
        "deals": deals,
    }


def _market_intel(game):
    """TradeDeadlineManager.get_market_intelligence() — never raises."""
    dm = _deadline_manager(game)
    if dm is None:
        return {}
    return (safe_call(lambda: dm.get_market_intelligence(), {},
                      context="deadline/analytics/intel")
            or {})


def _market_temp(game):
    """TradeDeadlineManager.get_market_temperature() — never raises."""
    dm = _deadline_manager(game)
    if dm is None:
        return {}
    return (safe_call(lambda: dm.get_market_temperature(), {},
                      context="deadline/analytics/temp")
            or {})


def _nhl_partners(game, league, user):
    """Every NHL team except the user's, sorted — real league state
    (mirrors QuickTradeInterface._nhl_partners)."""
    out = []
    uname = safe_call(lambda: getattr(user, "team_name", ""),
                      context="deadline/quicktrade/user_name")
    for t in (safe_call(lambda: list(getattr(league, "teams", None) or []),
                        [], context="deadline/quicktrade/teams")
              or []):
        try:
            if t is None or t is user:
                continue
            if uname and getattr(t, "team_name", "") == uname:
                continue
            ln = str(getattr(t, "league_name", "") or "")
            if "National Hockey League" in ln or "NHL" in ln or not ln:
                out.append(t)
        except Exception:
            continue
    return sorted(out,
                  key=lambda t: str(getattr(t, "team_name", "")))


def _your_pool(user):
    """Your real offerable assets: tradeable picks + expiring contracts
    ("rentals"), best value first (mirrors QuickTrade._refresh_your_pool)."""
    try:
        import trade_engine as te
    except Exception:
        te = None
    pool = []
    if user is not None and te is not None:
        for yr in sorted(safe_call(
                lambda: getattr(user, "draft_picks", {}) or {}, {},
                context="deadline/quicktrade/picks") or {}):
            for pk in (safe_call(
                    lambda: user.draft_picks.get(yr) or [], [],
                    context="deadline/quicktrade/pick_year")
                       or []):
                try:
                    if (safe_call(lambda: getattr(pk, "current_team", ""),
                                  context="deadline/quicktrade/pick_team")
                            != getattr(user, "team_name", "")):
                        continue
                    if (hasattr(pk, "can_be_traded")
                            and not pk.can_be_traded()):
                        continue
                except Exception:
                    continue
                try:
                    label = (f"{te.asset_label(pk)}  "
                             f"[{te.asset_value(pk):,}]")
                except Exception:
                    label = "Draft pick"
                pool.append((label, pk))
        rentals = _expiring_contracts(user)
        try:
            rentals.sort(key=lambda p: te.asset_value(p), reverse=True)
        except Exception:
            pass
        for p in rentals[:12]:
            try:
                val = te.asset_value(p)
            except Exception:
                val = 0
            name = safe_call(lambda: getattr(p, "full_name", "?"),
                             context="deadline/quicktrade/rental_name")
            pool.append((f"{name} ({_pos_code(p)}, {_ovr(p)})  [{val:,}]", p))
    return pool


def _their_pool(game, league, partner):
    """The selected partner's real trade block (mirrors
    QuickTrade._refresh_their_pool)."""
    try:
        import trade_market as tmk
        import trade_engine as te
    except Exception:
        return []
    pool = []
    gm = _resolve_gm(game)
    if partner is None or league is None:
        return []
    try:
        tmk.refresh_trade_blocks(gm, league)
    except Exception:
        pass
    blocks = safe_call(lambda: tmk.get_trade_blocks(league), {},
                       context="deadline/quicktrade/blocks") or {}
    tname = str(safe_call(lambda: getattr(partner, "team_name", ""),
                          context="deadline/quicktrade/partner_name"))
    for pid in (blocks.get(tname, None) or []):
        player = safe_call(lambda: tmk.resolve_player(league, pid)[0],
                           context="deadline/quicktrade/resolve_player")
        if player is None:
            continue
        try:
            val = te.asset_value(player)
        except Exception:
            val = 0
        name = safe_call(lambda: getattr(player, "full_name", "?"),
                         context="deadline/quicktrade/block_name")
        pool.append((f"{name} ({_pos_code(player)}, {_ovr(player)})  "
                     f"[{val:,}]", player))
    return pool


def _evaluate_offer(user_team, partner_team, user_assets, partner_assets):
    """Run the real trade engine over the proposal. Returns
    (label, detail, verdict_key). Mirrors QuickTrade._update_evaluation."""
    try:
        import trade_engine as te
        ev = te.evaluate_trade(user_assets, partner_assets,
                               user_team=user_team,
                               partner_team=partner_team)
    except Exception:
        return "Unavailable", "", "unavailable"
    detail = (f"Your value: {ev.user_value:,}   |   "
              f"Their value: {ev.partner_value:,}")
    if not user_assets or not partner_assets:
        return ("Incomplete", "Add at least one asset to each side.",
                "incomplete")
    return ev.label, detail, ev.label


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class _QuickTradeDialog(QDialog):
    """Quick trade proposal dialog for deadline day.

    Port of mainline's QuickTradeInterface (trade_deadline_center.py):
    the partner list is every NHL team except yours (live league state),
    "Your Offer" is your real tradeable picks + expiring contracts,
    "Their Offer" is the selected partner's real trade block, the
    evaluation runs the real trade engine, and SEND PROPOSAL submits
    through the real negotiation machinery (trade_negotiation.send_offer)
    — the AI answers instantly on deadline day and the confirmation
    reflects the negotiation's real post-send status. Non-modal on
    close: closing defers, never sends.
    """

    def __init__(self, parent, game):
        super().__init__(parent)
        self.game = game
        self.main_window = getattr(parent, "main_window", None)
        self.gm = _resolve_gm(game)
        self.league = _user_league(game)
        self.user_team = _user_team(game)
        self.partner_team = None
        self.user_assets = []      # real Player / DraftPick objects (yours)
        self.partner_assets = []   # real Player objects (theirs)
        self._your_pool = []       # [(label, asset)] you can offer
        self._their_pool = []      # [(label, asset)] from partner's block
        self._team_objs = {}       # team name -> team object
        self._sent = False         # consume-once: never send twice
        self._build()
        self._refresh_your_pool()
        self._update_evaluation()

    # -- build --------------------------------------------------------
    def _build(self):
        self.setWindowTitle("Quick Trade")
        self.setMinimumWidth(760)
        lay = QVBoxLayout(self)

        remaining = ""
        try:
            remaining = (_deadline_manager(self.game)
                         .get_time_until_deadline().get("formatted", ""))
        except Exception:
            pass
        title = QLabel("QUICK TRADE"
                       + (f" — {remaining} REMAINING" if remaining else ""))
        title.setObjectName("section-header")
        lay.addWidget(title)

        lay.addWidget(QLabel("Select Trading Partner (live league):"))
        self._partner_list = QListWidget()
        self._partner_list.setMaximumHeight(110)
        for t in _nhl_partners(self.game, self.league, self.user_team):
            name = str(getattr(t, "team_name", "") or "")
            if not name:
                continue
            self._team_objs[name] = t
            self._partner_list.addItem(name)
        if not self._team_objs:
            self._partner_list.addItem("(no league loaded)")
        self._partner_list.itemSelectionChanged.connect(
            self._on_team_select)
        lay.addWidget(self._partner_list)

        cols = QHBoxLayout()
        self._your_pool_list, self._your_offer_list = self._asset_column(
            cols, "Your Offer (your real picks & rentals)", "user")
        self._their_pool_list, self._their_offer_list = self._asset_column(
            cols, "Their Offer (their real trade block)", "partner")
        lay.addLayout(cols)

        self._eval_label = QLabel("Incomplete")
        self._eval_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(self._eval_label)
        self._eval_detail = QLabel("")
        self._eval_detail.setWordWrap(True)
        lay.addWidget(self._eval_detail)

        btns = QHBoxLayout()
        send_btn = QPushButton("SEND PROPOSAL")
        send_btn.setStyleSheet("font-weight: bold;")
        send_btn.clicked.connect(self._send_proposal)
        btns.addWidget(send_btn)
        full_btn = QPushButton("FULL TRADE CENTER")
        full_btn.clicked.connect(self._open_full_trade_center)
        btns.addWidget(full_btn)
        btns.addStretch()
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.reject)
        btns.addWidget(close_btn)
        lay.addLayout(btns)

    def _asset_column(self, parent_layout, title, side):
        """One offer column: available pool + add/remove + chosen assets."""
        group = QGroupBox(title)
        gl = QVBoxLayout(group)
        gl.addWidget(QLabel("Available:"))
        pool_list = QListWidget()
        pool_list.setMinimumHeight(120)
        gl.addWidget(pool_list)
        row = QHBoxLayout()
        add_btn = QPushButton("Add ▼")
        add_btn.clicked.connect(lambda: self._add_asset(side))
        row.addWidget(add_btn)
        row.addStretch()
        rm_btn = QPushButton("▲ Remove")
        rm_btn.clicked.connect(lambda: self._remove_asset(side))
        row.addWidget(rm_btn)
        gl.addLayout(row)
        gl.addWidget(QLabel("In proposal:"))
        offer_list = QListWidget()
        offer_list.setMaximumHeight(72)
        gl.addWidget(offer_list)
        parent_layout.addWidget(group)
        return pool_list, offer_list

    @staticmethod
    def _render_listbox(lb, labels, empty=""):
        lb.clear()
        if labels:
            lb.addItems(labels)
        elif empty:
            lb.addItem(empty)

    def _asset_label(self, asset):
        try:
            from game_classes import DraftPick
            if isinstance(asset, DraftPick):
                import trade_engine as te
                return te.asset_label(asset)
        except Exception:
            pass
        name = safe_call(lambda: getattr(asset, "full_name", "?"),
                         context="deadline/quicktrade/asset_label")
        return f"{name} ({_pos_code(asset)}, {_ovr(asset)})"

    # -- live data ----------------------------------------------------
    def _refresh_your_pool(self):
        self._your_pool = _your_pool(self.user_team)
        self._render_listbox(self._your_pool_list,
                             [label for label, _ in self._your_pool],
                             empty="(no tradeable picks or rentals)")

    def _refresh_their_pool(self):
        self._their_pool = _their_pool(self.game, self.league,
                                       self.partner_team)
        self._render_listbox(self._their_pool_list,
                             [label for label, _ in self._their_pool],
                             empty="(nothing on their block)")

    # -- interactions -------------------------------------------------
    def _on_team_select(self):
        items = self._partner_list.selectedItems()
        if not items:
            return
        self.partner_team = self._team_objs.get(items[0].text())
        # Their side resets: those assets belong to the old partner.
        self.partner_assets = []
        self._refresh_their_pool()
        self._render_offer("partner")
        self._update_evaluation()

    def _add_asset(self, side):
        if side == "user":
            pool, pool_lb, assets = (self._your_pool, self._your_pool_list,
                                     self.user_assets)
        else:
            pool, pool_lb, assets = (self._their_pool, self._their_pool_list,
                                     self.partner_assets)
        items = pool_lb.selectedItems()
        if not items:
            return
        row = pool_lb.row(items[0])
        if row < 0 or row >= len(pool):
            return
        _label, asset = pool[row]
        if not any(a is asset for a in assets):
            assets.append(asset)
        self._render_offer(side)
        self._update_evaluation()

    def _remove_asset(self, side):
        if side == "user":
            offer_lb, assets = self._your_offer_list, self.user_assets
        else:
            offer_lb, assets = self._their_offer_list, self.partner_assets
        items = offer_lb.selectedItems()
        if not items:
            return
        row = offer_lb.row(items[0])
        if 0 <= row < len(assets):
            assets.pop(row)
        self._render_offer(side)
        self._update_evaluation()

    def _render_offer(self, side):
        if side == "user":
            assets, lb = self.user_assets, self._your_offer_list
        else:
            assets, lb = self.partner_assets, self._their_offer_list
        self._render_listbox(lb, [self._asset_label(a) for a in assets],
                             empty="(empty)")

    def _update_evaluation(self):
        label, detail, key = _evaluate_offer(self.user_team,
                                             self.partner_team,
                                             self.user_assets,
                                             self.partner_assets)
        colors = {"Fair deal": "#10b981", "You overpay": "#e5484d",
                  "They overpay": "#d4a017", "Incomplete": "#9ca3af",
                  "Unavailable": "#9ca3af"}
        self._eval_label.setText(label)
        self._eval_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: "
            f"{colors.get(key, '#ffffff')};")
        self._eval_detail.setText(detail)

    def _open_full_trade_center(self):
        try:
            show = getattr(self.main_window, "show_screen", None)
            if callable(show):
                show("trades")
                self.accept()
                return
        except Exception:
            pass
        QMessageBox.information(self, "Trade Center",
                                "The full Trade Center is unavailable "
                                "right now.")

    def _send_proposal(self):
        """Send the proposal through the real negotiation machinery."""
        if self.gm is None or self.user_team is None:
            QMessageBox.warning(self, "No League",
                                "No league loaded — cannot send a proposal.")
            return
        dm = _deadline_manager(self.game)
        if dm is not None and safe_call(
                lambda: dm.is_deadline_passed(), False,
                context="deadline/quicktrade/deadline_passed"):
            QMessageBox.warning(self, "Deadline passed",
                                "The deadline has passed — deals are locked.")
            return
        if self.partner_team is None:
            QMessageBox.warning(self, "No Partner",
                                "Select a trading partner first.")
            return
        if not self.user_assets or not self.partner_assets:
            QMessageBox.warning(
                self, "Incomplete",
                "Add at least one asset to each side of the deal first.")
            return
        # Consume-once: a double-click must not send the proposal twice.
        if self._sent:
            return
        # No-trade clauses block the deal before it leaves the building —
        # say so honestly instead of sending a dead proposal.
        try:
            import trade_engine as te
            vetoes = te.trade_vetoes(self.user_team, self.partner_team,
                                     self.user_assets, league=self.league)
        except Exception:
            vetoes = []
        if vetoes:
            names = ", ".join(
                str(getattr(v.get("player"), "full_name", "?"))
                for v in vetoes[:3])
            QMessageBox.warning(
                self, "No-trade protection",
                f"{names} cannot be moved to "
                f"{getattr(self.partner_team, 'team_name', 'them')} "
                f"({vetoes[0].get('clause', 'clause')} protection).\n\n"
                "Remove them from the offer, or ask for a waiver in the "
                "full Trade Center.")
            return
        # Transactional cap revalidation at the moment of send — the cap
        # may have moved since the workbench was built.
        try:
            import trade_engine as te
            cap_ok = safe_call(
                lambda: te._cap_ok_after(self.user_team, self.user_assets,
                                         self.partner_assets), True,
                context="deadline/quicktrade/cap_check")
            if not cap_ok:
                QMessageBox.warning(
                    self, "Cap check",
                    "The deal no longer fits under the salary cap — "
                    "your roster moved since the proposal was built. "
                    "Adjust the offer and try again.")
                return
        except Exception:
            pass
        try:
            import trade_negotiation as tn
            neg = tn.send_offer(self.gm, self.partner_team,
                                list(self.user_assets),
                                list(self.partner_assets))
        except Exception as e:
            QMessageBox.warning(self, "Send failed",
                                f"Could not send the proposal: {e}")
            return
        self._sent = True  # consume-once: the deal is in the inbox now
        # Confirmation reflects real post-send state: on deadline day the
        # AI answers instantly, so read the negotiation's actual status.
        pname = str(getattr(self.partner_team, "team_name", "them"))
        try:
            you = tn.asset_summary(neg.user_assets)
            them = tn.asset_summary(neg.partner_assets)
        except Exception:
            you, them = "your assets", "their assets"
        status = str(safe_call(lambda: getattr(neg, "status", ""),
                               context="deadline/quicktrade/neg_status"))
        if status == "accepted":
            title = "Deal accepted!"
            body = (f"{pname} accepted your offer on the spot.\n\n"
                    f"YOU SEND: {you}\nYOU GET: {them}")
        elif status == "declined":
            title = "Offer declined"
            body = (f"{pname} turned the offer down.\n\n"
                    f"YOU OFFERED: {you}\nYOU ASKED FOR: {them}\n\n"
                    "Their reply is in your inbox.")
        elif status == "awaiting_user":
            title = "Counter-offer waiting"
            body = (f"{pname} countered instantly — answer it from your "
                    f"inbox.\n\nYOUR OFFER: {you} for {them}")
        else:
            title = "Offer sent"
            body = (f"Your offer is with {pname}'s front office.\n\n"
                    f"YOU SEND: {you}\nYOU GET: {them}\n\n"
                    "The reply will land in your inbox.")
        QMessageBox.information(self, title, body)
        self.accept()


class _MarketAnalyticsDialog(QDialog):
    """Market analytics browser for deadline day.

    Port of mainline's DeadlineMarketBrowser (trade_deadline_center.py):
    5 tabs over TradeDeadlineManager.get_market_intelligence() /
    get_market_temperature() — market overview + price trends
    (supply/demand guidance), buyers & sellers, position needs, trade
    predictions, salary cap analysis.

    DISPLAY HONESTY NOTE: every figure, prediction, cap number, and team
    need shown here is a SIMULATED scouting estimate — not official data
    for the teams in the user's league. The dialog therefore carries a
    visible disclaimer plus per-section estimate labels. Do NOT remove
    them without replacing the backing data with real league state.
    """

    # Visible disclaimer text — must stay attached to any numbers section.
    DISCLAIMER_TEXT = (
        "Scouting estimates — all figures, likelihoods, predictions, cap "
        "numbers, and team needs shown here are simulated estimates for "
        "league-wide context. They are NOT official league data, and team "
        "abbreviations may not match the teams in your league."
    )

    def __init__(self, parent, game):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Market Analytics")
        self.setMinimumWidth(720)
        self.setMinimumHeight(520)
        lay = QVBoxLayout(self)
        disclaimer = QLabel(self.DISCLAIMER_TEXT)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(
            "font-style: italic; color: #fbbf24; "
            "background: #3a2f10; padding: 6px; border: 1px solid #b45309;")
        lay.addWidget(disclaimer)
        tabs = QTabWidget()
        lay.addWidget(tabs)
        intel = _market_intel(game)
        temp = _market_temp(game)
        tabs.addTab(self._overview_tab(temp, intel), "Market Overview")
        tabs.addTab(self._buyers_sellers_tab(intel), "Buyers & Sellers")
        tabs.addTab(self._position_tab(intel), "Position Needs")
        tabs.addTab(self._predictions_tab(intel), "Trade Predictions")
        tabs.addTab(self._cap_tab(intel), "Salary Cap")
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

    @staticmethod
    def _tab_page(text):
        page = QWidget()
        lay = QVBoxLayout(page)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignTop)
        lay.addWidget(lbl)
        lay.addStretch()
        return page

    @staticmethod
    def _estimate_note():
        """Small per-section label so no numbers section reads as official
        league data."""
        return ("<br><i style='color:#9ca3af'>Estimates — simulated "
                "figures, not official league data.</i>")

    def _overview_tab(self, temp, intel):
        overall = temp.get("overall", "warm") if temp else "warm"
        colors = {"cold": "#60a5fa", "warm": "#fbbf24",
                  "hot": "#f87171", "blazing": "#dc2626"}
        color = colors.get(overall, "#fbbf24")
        trends = (intel.get("deadline_trends", {}) or {}) if intel else {}
        rental = (trends.get("rental_vs_futures", {}) or {}).get(
            "rental", "--")
        prices = trends.get("price_trends", {}) or {}
        lines = [
            f"<h3>Market Temperature: "
            f"<span style='color:{color}'>{str(overall).upper()}</span></h3>",
            self._estimate_note(),
        ]
        for plabel, ptemp in (("Forwards", temp.get("forwards")),
                              ("Defensemen", temp.get("defensemen")),
                              ("Goalies", temp.get("goalies"))):
            if ptemp:
                lines.append(f"• {plabel}: <b>{ptemp}</b>")
        lines += [
            f"<br>Most active position: "
            f"<b>{trends.get('most_active_position', '--')}</b>",
            f"Average trade size: "
            f"<b>{trends.get('average_trade_size', '--')}</b> players",
            f"Rental market: <b>{rental}%</b> rental",
            f"Market sentiment: <b>{trends.get('market_sentiment', '--')}</b>",
            "<br><b>Price guidance (supply/demand):</b>",
            f"• Rentals: {prices.get('rentals', '--')}",
            f"• Defensemen: {prices.get('defensemen', '--')}",
            f"• Goalies: {prices.get('goalies', '--')}",
            f"• Draft picks: {prices.get('picks', '--')}",
        ]
        return self._tab_page("<br>".join(lines))

    def _buyers_sellers_tab(self, intel):
        buyers = (intel.get("buyer_teams", []) or [])[:6] if intel else []
        sellers = (intel.get("seller_teams", []) or [])[:6] if intel else []
        lines = ["<h3 style='color:#10b981'>ACTIVE BUYERS (league-wide estimates)</h3>",
                 self._estimate_note()]
        if buyers:
            for b in buyers:
                lines.append(
                    f"• <b>{b.get('team', '?')}</b> — {b.get('likelihood', '')}"
                    f"<br>&nbsp;&nbsp;Need: {b.get('primary_need', '--')} | "
                    f"Cap: {b.get('cap_space', '--')} | "
                    f"{b.get('assets', '')}")
        else:
            lines.append("No active buyers identified.")
        lines.append("<br><h3 style='color:#e5484d'>ACTIVE SELLERS (league-wide estimates)</h3>")
        lines.append(self._estimate_note())
        if sellers:
            for s in sellers:
                lines.append(
                    f"• <b>{s.get('team', '?')}</b> — {s.get('likelihood', '')}"
                    f"<br>&nbsp;&nbsp;Asset: {s.get('notable_assets', '--')} | "
                    f"Price: {s.get('asking_price', '--')}")
        else:
            lines.append("No active sellers identified.")
        return self._tab_page("<br>".join(lines))

    def _position_tab(self, intel):
        needs = (intel.get("position_needs", {}) or {}) if intel else {}
        lines = ["<h3>POSITION NEEDS ANALYSIS (league-wide estimates)</h3>",
                 self._estimate_note()]
        for pname, key in (("Forwards", "forwards"),
                           ("Defensemen", "defensemen"),
                           ("Goalies", "goalies"),
                           ("Depth Players", "depth")):
            teams = needs.get(key, []) or []
            lines.append(f"• <b>{pname}:</b> "
                         + (", ".join(teams) if teams else "No active needs"))
        return self._tab_page("<br>".join(lines))

    def _predictions_tab(self, intel):
        preds = (intel.get("trade_predictions", []) or []) if intel else []
        lines = ["<h3>TRADE PREDICTIONS (illustrative estimates)</h3>",
                 self._estimate_note()]
        if preds:
            for p in preds:
                like = p.get("likelihood", 0)
                color = ("#10b981" if like >= 70 else "#fbbf24"
                         if like >= 50 else "#9ca3af")
                teams = " ↔ ".join(p.get("teams_involved", []) or [])
                lines.append(
                    f"• <b style='color:{color}'>{like}%</b> — "
                    f"<b>{p.get('description', '')}</b> ({teams})"
                    f"<br>&nbsp;&nbsp;Assets: {p.get('assets', '')}"
                    f"<br>&nbsp;&nbsp;<i>{p.get('reasoning', '')}</i><br>")
        else:
            lines.append("No trade predictions available.")
        return self._tab_page("<br>".join(lines))

    def _cap_tab(self, intel):
        cap = (intel.get("salary_cap_space", {}) or {}) if intel else {}
        lines = ["<h3>SALARY CAP ANALYSIS (illustrative estimates)</h3>",
                 self._estimate_note()]
        if cap:
            for team, data in cap.items():
                space = safe_call(lambda: int(data.get("cap_space", 0) or 0),
                                  0, context="deadline/analytics/cap_space")
                dspace = safe_call(
                    lambda: int(data.get("deadline_space", 0) or 0), 0,
                    context="deadline/analytics/deadline_space")
                flex = data.get("flexibility", "Medium")
                ret = safe_call(lambda: int(data.get("retention_slots", 0)
                                            or 0), 0,
                                context="deadline/analytics/retention")
                lines.append(
                    f"• <b>{team}</b>: cap {_fmt_money(space)} | "
                    f"deadline space {_fmt_money(dspace)} | "
                    f"flexibility {flex} | retention {ret}/3")
        else:
            lines.append("No cap analysis available.")
        return self._tab_page("<br>".join(lines))


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

        # --- deadline tools (mainline quick actions) ---
        tools_group = QGroupBox("Deadline tools")
        tg = QVBoxLayout(tools_group)
        tools_row = QHBoxLayout()
        self._quick_trade_btn = QPushButton("QUICK TRADE")
        self._quick_trade_btn.setStyleSheet("font-weight: bold;")
        self._quick_trade_btn.clicked.connect(self._on_quick_trade)
        tools_row.addWidget(self._quick_trade_btn)
        self._fire_sale_btn = QPushButton("FIRE SALE")
        self._fire_sale_btn.clicked.connect(self._on_fire_sale)
        tools_row.addWidget(self._fire_sale_btn)
        self._analytics_btn = QPushButton("MARKET ANALYTICS")
        self._analytics_btn.clicked.connect(self._on_market_analytics)
        tools_row.addWidget(self._analytics_btn)
        tools_row.addStretch()
        tg.addLayout(tools_row)
        self._tools_hint = QLabel(
            "Quick Trade: streamlined offer workbench. Fire Sale: list your "
            "expiring contracts on the trade block so AI GMs can bid. "
            "Market Analytics: supply/demand, buyers/sellers, predictions.")
        self._tools_hint.setWordWrap(True)
        tg.addWidget(self._tools_hint)
        lay.addWidget(tools_group)

        # --- player movement tracker ---
        tracker_group = QGroupBox("Player movement tracker")
        tk = QVBoxLayout(tracker_group)
        stats_row = QHBoxLayout()
        self._move_players_lbl = QLabel("—")
        self._move_players_lbl.setStyleSheet("font-weight: bold;")
        stats_row.addWidget(self._move_players_lbl)
        self._move_trades_lbl = QLabel("—")
        self._move_trades_lbl.setStyleSheet("font-weight: bold;")
        stats_row.addWidget(self._move_trades_lbl)
        self._move_biggest_lbl = QLabel("—")
        self._move_biggest_lbl.setStyleSheet("font-weight: bold;")
        stats_row.addWidget(self._move_biggest_lbl)
        stats_row.addStretch()
        tk.addLayout(stats_row)
        self._tracker_lbl = QLabel("")
        self._tracker_lbl.setWordWrap(True)
        tk.addWidget(self._tracker_lbl)
        lay.addWidget(tracker_group)

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

            # stance + market + rumors + movement tracker
            self._paint_stance(_compute_stance(game, league, gm))
            self._paint_market(_market(game, league, gm))
            self._paint_rumors(_rumors(game, gm, league))
            self._paint_tracker(_movement_data(game))

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

        declared = (safe_call(lambda: getattr(
            _user_league(self.game), "_web_deadline_stance", ""), "",
            context="deadline/stance/declared")
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

    # -- deadline tools --------------------------------------------------

    def _on_quick_trade(self):
        dlg = _QuickTradeDialog(self, self.game)
        dlg.exec()

    def _on_fire_sale(self):
        res = _fire_sale(self.game)
        self._status_lbl.setText(res.get("message", ""))
        # Refresh so the new block listings show in the market sections.
        self.refresh()
        # Also refresh any other open views (trade block etc.).
        try:
            mw = getattr(self, "main_window", None)
            refresh = getattr(mw, "refresh", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    def _on_market_analytics(self):
        dlg = _MarketAnalyticsDialog(self, self.game)
        dlg.exec()

    def _paint_tracker(self, m):
        if not m:
            return
        self._move_players_lbl.setText(
            f"Players moved today: {m.get('players_moved', '--')}")
        self._move_trades_lbl.setText(
            f"Trades completed: {m.get('total_trades', '--')}")
        biggest = m.get("biggest_deal", "--")
        self._move_biggest_lbl.setText(f"Biggest deal: {biggest}")
        deals = m.get("deals") or []
        if deals:
            self._tracker_lbl.setText("<br>".join(
                f"🤝 {d}" for d in deals))
        else:
            self._tracker_lbl.setText(
                "No deadline-day deals logged yet.")

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
