"""Trade Center: native Qt port of the web UI trade builder.

Ports web_ui/templates/trades.html + web_ui/screens/trades.py +
web_ui/static/js/trades.js. Calls the game object DIRECTLY -- no Flask,
no HTTP, no command queue.

Game methods used (all real, same as the web bridge called):
  - gm.league.teams, gm.user_team (team objects: team_name, city, name)
  - app.trade_block (players on the block)
  - team.roster / team.ahl_roster / team.prospects / team.draft_picks
  - trade_engine.evaluate_trade(user_assets, partner_assets,
      user_team=..., partner_team=..., perceiver_team=...)
  - trade_engine.ai_consider_trade(partner, give_assets, want_assets,
      user_team=..., retention={...})  (read-only AI verdict)
  - trade_engine.retention_slots_used(team), MAX_RETENTION_SLOTS,
      MAX_RETENTION_PCT
  - trade_engine.apply_retention_dry_run(team, player, pct, extra={...})
  - trade_engine.protection_label(code); codes "top-3"|"top-10"|"lottery"
  - trade_engine.trade_vetoes(from, to, [players], league)
  - trade_engine.will_waive_ntc(player, from, to, league)
  - trade_engine.clause_offer_label(kind)
  - trade_engine.pick_trade_value(pick)   (protection haircut heuristic)
  - transaction_windows.check_window("trade", date, ctx)
  - trade_negotiation.send_offer(app, partner, give, want,
      retention=..., pick_protection=...)
  - trade_negotiation.send_counter(app, neg, give, want,
      retention=..., pick_protection=...)
  - trade_negotiation.get_negotiation(app, id), .asset_summary(...),
      .accept_negotiation(app, id), .decline_negotiation(app, id),
      .find_team(app, name)
  - gm.trade_negotiations (open negotiation threads)
  - gm.trade_history (completed-trade log)
  - MP: game._mp_propose_trade(params, team, manager) on the host machine,
      mp_client.send_action("propose_trade", {...}) on a client machine;
      partner teams flagged via team.is_human_managed.
"""

from datetime import date

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen

# Engine's real protection codes -- never invent others.
PROTECTION_CODES = ("top-3", "top-10", "lottery")
# Retention pct choices offered in the UI (engine max is 50).
RETENTION_OPTIONS = (0, 25, 50)
# Protection valuation haircut for the verdict display (UI heuristic only;
# the engine's pick_trade_value does not price protection).
PROTECTION_HAIRCUT = {"top-3": 0.15, "top-10": 0.25, "lottery": 0.35}


# ---------------------------------------------------------------------------
# helpers (ported from web_ui/screens/trades.py, Flask removed)
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _fmt_money(n):
    try:
        n = int(n or 0)
    except Exception:
        return "$0"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"${round(n / 1_000)}K"
    return f"${n:,}"


def _pid(p):
    return str(_safe(lambda: getattr(p, "id", ""), "") or "")


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


def _league(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.league)
            or _safe(lambda: getattr(game, "league", None)))


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


def _today(game):
    gm = _resolve_gm(game)
    d = (_safe(lambda: gm.current_date)
         or _safe(lambda: getattr(game, "current_date", None)))
    if isinstance(d, date):
        return d
    return date.today()


def _player_name(p):
    return _safe(lambda: getattr(p, "full_name", "?"), "?") or "?"


_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
}


def _pos_str(p):
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    s = str(getattr(pos, "value", pos) or "")
    if "." in s:
        s = s.split(".")[-1]
    s = s.strip().upper()
    return _POSITION_ABBR.get(s, s or "?")


def _player_ovr(p):
    fn = _safe(lambda: getattr(p, "overall_rating", None))
    if callable(fn):
        v = _safe(fn, 0) or 0
        if v:
            return int(v)
    return _safe(lambda: int(getattr(p, "overall", 0) or 0), 0) or 0


def _player_age(p):
    return _safe(lambda: int(getattr(p, "age", 0) or 0), 0) or 0


def _player_cap_hit(p):
    hit = _safe(lambda: int(getattr(getattr(p, "contract", None),
                                   "salary", 0) or 0), 0)
    if not hit:
        hit = _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
    hit -= _safe(lambda: int(getattr(p, "retained_amount", 0) or 0), 0)
    return max(0, hit)


def _player_injured(p):
    return bool(_safe(lambda: getattr(p, "injured", False), False)
                or _safe(lambda: getattr(p, "is_injured", False), False))


def _player_captaincy(p):
    c = _safe(lambda: getattr(p, "captaincy", ""), "") or ""
    if c:
        return str(c)
    if _safe(lambda: getattr(p, "is_captain", False), False):
        return "C"
    if _safe(lambda: getattr(p, "is_alternate", False), False):
        return "A"
    return ""


def _team_trade_lists(team):
    """(players, picks) the game lets a team trade."""
    players = []
    for attr, level in (("roster", "NHL"), ("ahl_roster", "AHL"),
                        ("prospects", "Prospects")):
        for p in _safe(lambda: list(getattr(team, attr, None) or []), []) or []:
            players.append((p, level))
    picks = []
    by_year = _safe(lambda: dict(getattr(team, "draft_picks", None) or {}),
                    {}) or {}
    for year in sorted(by_year.keys()):
        for pk in _safe(lambda: list(by_year.get(year) or []), []) or []:
            picks.append(pk)
    return players, picks


def _find_team(game, team_id):
    """Match a team by name, city+name, or abbr."""
    if not team_id:
        return None
    league = _league(game)
    teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
    want = str(team_id).strip().lower()
    for t in teams:
        cands = {
            _team_name(t).lower(),
            f"{_safe(lambda: getattr(t, 'city', ''), '')} "
            f"{_safe(lambda: getattr(t, 'name', ''), '')}".strip().lower(),
        }
        if want in cands:
            return t
    return None


def _trade_engine():
    try:
        import trade_engine
        return trade_engine
    except Exception:
        return None


def _pick_label(pk):
    year = _safe(lambda: int(getattr(pk, "year", 0) or 0), 0)
    rnd = _safe(lambda: int(getattr(pk, "round", 0) or 0), 0)
    orig = _safe(lambda: str(getattr(pk, "original_team", "") or ""), "")
    cur = _safe(lambda: str(getattr(pk, "current_team", "") or ""), "")
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(rnd % 10, "th") \
        if not (11 <= (rnd % 100) <= 13) else "th"
    if orig and cur and orig != cur:
        return f"{year} {rnd}{suffix} (from {orig})"
    return f"{year} {rnd}{suffix}"


def _protection_label(code):
    te = _trade_engine()
    if te:
        lab = _safe(lambda: te.protection_label(code), "")
        if lab:
            return lab
    return code


def retention_slots_summary(team):
    """{used, max} retention slots for a club."""
    te = _trade_engine()
    used = _safe(lambda: int(te.retention_slots_used(team)), 0) if te else 0
    mx = _safe(lambda: int(te.MAX_RETENTION_SLOTS), 3) if te else 3
    return {"used": max(0, used), "max": max(1, mx)}


def parse_retention_terms(raw, valid_pids=None):
    """Sanitize retention terms -> {str pid: float pct} (0 < pct <= 50)."""
    te = _trade_engine()
    cap = _safe(lambda: float(te.MAX_RETENTION_PCT), 50.0) if te else 50.0
    out = {}
    items = raw.items() if isinstance(raw, dict) else []
    for k, v in items:
        pid = str(k)
        if valid_pids is not None and pid not in {str(x) for x in valid_pids}:
            continue
        try:
            pct = float(v)
        except Exception:
            continue
        if 0 < pct <= cap:
            out[pid] = pct
    return out


def parse_protection_terms(raw, valid_pick_ids=None):
    """Sanitize pick protection -> {str pick id: code} (real codes only)."""
    out = {}
    items = raw.items() if isinstance(raw, dict) else []
    for k, v in items:
        kid = str(k)
        if valid_pick_ids is not None and \
                kid not in {str(x) for x in valid_pick_ids}:
            continue
        code = str(v or "").strip()
        if code in PROTECTION_CODES:
            out[kid] = code
    return out


def validate_retention_terms(team, players, retention_terms):
    """Dry-run retention terms against the real engine rules.

    Returns (ok, [error strings]).
    """
    te = _trade_engine()
    if not retention_terms:
        return True, []
    if te is None or team is None:
        return False, ["Trade engine unavailable for retention check."]
    by_id = {}
    for p in players or []:
        by_id[_pid(p)] = p
    errors = []
    for pid, pct in retention_terms.items():
        player = by_id.get(str(pid))
        if player is None:
            errors.append(f"Retention target {pid} is not in the deal.")
            continue
        others = {k: v for k, v in retention_terms.items()
                  if str(k) != str(pid)}
        ok, msg = _safe(
            lambda: te.apply_retention_dry_run(team, player, pct,
                                              extra=others),
            (False, "retention check failed"))
        if not ok:
            errors.append(f"{_player_name(player)}: {msg}")
    return (len(errors) == 0), errors


def protection_value_adjustment(pick_objs, protection_terms, te=None):
    """Heuristic point discount for protected outgoing picks (display)."""
    te = te or _trade_engine()
    if not protection_terms or te is None:
        return 0
    adj = 0
    for pk in pick_objs or []:
        code = (protection_terms or {}).get(_pid(pk))
        haircut = PROTECTION_HAIRCUT.get(code)
        if not haircut:
            continue
        val = _safe(lambda: te.pick_trade_value(pk), 0) or 0
        adj += int(round(val * haircut))
    return adj


def deal_terms_note(give_players, give_pick_objs, retention_terms,
                    protection_terms, want_players=None, acquire_terms=None):
    """Human-readable summary of the deal's retention/protection terms."""
    te = _trade_engine()
    bits = []
    for p in give_players or []:
        pct = (retention_terms or {}).get(_pid(p))
        if pct:
            amt = int(round(_player_cap_hit(p)
                            * min(float(pct), 50.0) / 100.0))
            bits.append(f"you retain {float(pct):g}% "
                        f"({_fmt_money(amt)}) on {_player_name(p)}")
    for p in want_players or []:
        pct = (acquire_terms or {}).get(_pid(p))
        if pct:
            amt = int(round(_player_cap_hit(p)
                            * min(float(pct), 50.0) / 100.0))
            bits.append(f"they retain {float(pct):g}% "
                        f"({_fmt_money(amt)}) on {_player_name(p)}")
    for pk in give_pick_objs or []:
        code = (protection_terms or {}).get(_pid(pk))
        if code:
            label = _safe(lambda: te.protection_label(code), code) \
                if te else code
            bits.append(f"{_pick_label(pk)} is {str(label).lower()}")
    if not bits:
        return ""
    return "Deal terms: " + "; ".join(bits) + "."


def _trade_window_state(game):
    """(frozen: bool, reason: str). Never raises."""
    try:
        import transaction_windows as _tw
    except Exception:
        return False, ""
    try:
        league = _league(game)
        today = _today(game)
        allowed, reason = _tw.check_window(
            "trade", today, {"league": league, "date_str": str(today)})
        if not allowed:
            return True, str(reason or "Trades are frozen.")
        return False, ""
    except Exception:
        return False, ""


def _preflight_flag(te, player, from_team, to_team, league, partner_name):
    """One player's clause preflight. None when no clause bites."""
    try:
        vetoes = te.trade_vetoes(from_team, to_team, [player], league)
        if not vetoes:
            return None
        v = vetoes[0]
        kind = str(v.get("clause") or "")
        detail = str(v.get("detail") or "")
        name = _player_name(player)
        pid = _pid(player)
        if kind == "OFFER-SHEET-NO-TRADE":
            return {"player_id": pid, "name": name, "clause": kind,
                    "detail": detail, "waive_likely": False,
                    "waive_note": detail, "hard_block": True}
        try:
            wok, why = te.will_waive_ntc(player, from_team, to_team, league)
        except Exception:
            wok, why = False, "consent check unavailable"
        clause_label = _safe(
            lambda: te.clause_offer_label(
                {"nmc": "nmc", "ntc": "ntc", "M-NTC": "mntc"}.get(
                    kind, "none")),
            "none") or kind
        return {"player_id": pid, "name": name, "clause": kind,
                "clause_label": clause_label, "detail": detail,
                "waive_likely": bool(wok), "waive_note": str(why or ""),
                "hard_block": False}
    except Exception:
        return None

# ---------------------------------------------------------------------------
# NTC/NMC consent preflight dialog (desktop parity, windows.py:~6212)
# ---------------------------------------------------------------------------

class _ConsentDialog(QDialog):
    """Modal consent preflight.

    Lists flagged clause players (ours = asked to waive; theirs = heads-up).
    Hard-block case (offer-sheet-match year) gets "Back to the deal" only.
    Dismiss = safe default (don't send). Returns True only via "Send anyway".
    """

    def __init__(self, parent, our_flags, their_flags, partner_name):
        super().__init__(parent)
        self.setWindowTitle("Trade protection")
        self.setMinimumWidth(560)
        self._send = False
        hard = any(f.get("hard_block") for f in our_flags + their_flags)

        layout = QVBoxLayout(self)
        title = QLabel("Trade blocked" if hard else "Trade protection")
        title.setObjectName("dialog-title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        def flag_card(f, ours):
            card = QGroupBox()
            cl = QVBoxLayout(card)
            head = QLabel(f"{f['name']}  —  "
                          f"{f.get('clause_label') or f.get('clause', '')}")
            head.setStyleSheet("font-weight: bold;")
            cl.addWidget(head)
            if f.get("detail"):
                d = QLabel(f["detail"])
                d.setWordWrap(True)
                d.setStyleSheet("color: #8b95ab;")
                cl.addWidget(d)
            if f.get("hard_block"):
                w = QLabel("Cannot be traded for one year — no consent ask "
                           "applies. Remove this player to send the offer.")
                w.setStyleSheet("color: #e5484d;")
            else:
                wt = (("Likely to waive" if f.get("waive_likely")
                       else "May refuse")
                      + (": " + f["waive_note"] if f.get("waive_note") else ""))
                w = QLabel(wt)
                w.setStyleSheet(
                    "color: #30a46c;" if f.get("waive_likely")
                    else "color: #f5a524;")
            w.setWordWrap(True)
            cl.addWidget(w)
            if ours and not f.get("hard_block"):
                a = QLabel("He will be asked to waive for a move to "
                           f"{partner_name or 'the other club'} when the "
                           "offer is sent.")
            elif not ours and not f.get("hard_block"):
                a = QLabel("Their camp will be asked to waive — a refusal "
                           "kills the deal 1-3 days from now.")
            else:
                a = None
            if a:
                a.setWordWrap(True)
                a.setStyleSheet("color: #8b95ab;")
                cl.addWidget(a)
            return card

        if our_flags:
            sec = QLabel("Your players with clauses — each will be asked "
                         "to waive:")
            sec.setStyleSheet("font-weight: bold; margin-top: 8px;")
            layout.addWidget(sec)
            for f in our_flags:
                layout.addWidget(flag_card(f, True))
        if their_flags:
            sec = QLabel("Their players with clauses — heads-up, refusal "
                         "kills the deal:")
            sec.setStyleSheet("font-weight: bold; margin-top: 8px;")
            layout.addWidget(sec)
            for f in their_flags:
                layout.addWidget(flag_card(f, False))
        if not our_flags and not their_flags:
            layout.addWidget(QLabel("No trade protection on either side."))

        btns = QDialogButtonBox()
        if hard:
            back = btns.addButton("Back to the deal",
                                  QDialogButtonBox.AcceptRole)
            back.clicked.connect(self.reject)
        else:
            btns.addButton("Keep editing (don't send)",
                           QDialogButtonBox.RejectRole)
            send = btns.addButton("Send anyway", QDialogButtonBox.AcceptRole)
            send.setObjectName("primary-btn")
            send.clicked.connect(self._on_send)
            btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_send(self):
        self._send = True
        self.accept()

    @property
    def send(self):
        return self._send


# ---------------------------------------------------------------------------
# Trades screen
# ---------------------------------------------------------------------------

class TradesScreen(BaseScreen):
    title = "Trades"

    def __init__(self, game, main_window, parent=None):
        # deal state
        self._teams = []
        self._partner = None          # team object
        self._partner_name = ""
        self._my_players = []         # [(player, level)]
        self._my_picks = []
        self._partner_players = []
        self._partner_picks = []
        self._give_pids = set()
        self._give_picks = set()
        self._want_pids = set()
        self._want_picks = set()
        self._retention = {}          # pid -> pct (our club, outgoing)
        self._retention_acquire = {}  # pid -> pct (ask partner, incoming)
        self._protection = {}         # pick id -> code (outgoing picks)
        self._slots_used = 0
        self._slots_max = 3
        self._partner_slots_used = 0
        self._partner_slots_max = 3
        self._frozen = False
        self._freeze_reason = ""
        self._updating = False
        self._last_verdict = None
        self._neg_timer = None
        super().__init__(game, main_window, parent)

    # -- layout ------------------------------------------------------------

    def _build_body(self):
        # freeze banner
        self._freeze_banner = QLabel("")
        self._freeze_banner.setWordWrap(True)
        self._freeze_banner.setStyleSheet(
            "background: #3a1d22; color: #f5a524; font-weight: bold; "
            "padding: 10px; border-radius: 6px;")
        self._freeze_banner.setVisible(False)
        self._layout.addWidget(self._freeze_banner)

        # retention slot pills + hint
        pill_row = QHBoxLayout()
        self._slots_lbl = QLabel("Retention: 0/3 slots")
        self._slots_lbl.setStyleSheet(
            "background: #1c2233; padding: 6px 12px; border-radius: 10px;")
        self._partner_slots_lbl = QLabel("Partner retention: 0/3 slots")
        self._partner_slots_lbl.setStyleSheet(
            "background: #1c2233; padding: 6px 12px; border-radius: 10px;")
        self._partner_slots_lbl.setVisible(False)
        hint = QLabel("Pick a partner, click players/picks to build the deal. "
                      "Proposing sends an offer — their answer (accept, "
                      "counter, reject) arrives in your inbox in 1-3 days.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b95ab;")
        pill_row.addWidget(self._slots_lbl)
        pill_row.addWidget(self._partner_slots_lbl)
        pill_row.addWidget(hint, 1)
        self._layout.addLayout(pill_row)

        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        self._build_builder_tab()
        self._build_negotiations_tab()
        self._build_completed_tab()

        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_builder_tab(self):
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)

        # -- team picker (search + tiles) --
        team_box = QGroupBox("Trade partner")
        team_box.setFixedWidth(240)
        team_l = QVBoxLayout(team_box)
        self._team_search = QLineEdit()
        self._team_search.setPlaceholderText("Search teams…")
        self._team_search.textChanged.connect(self._render_teams)
        team_l.addWidget(self._team_search)
        self._team_list = QListWidget()
        self._team_list.itemSelectionChanged.connect(
            self._on_team_selected)
        team_l.addWidget(self._team_list, 1)
        top.addWidget(team_box)

        # -- deal columns --
        cols = QHBoxLayout()
        cols.setSpacing(12)

        get_box = QGroupBox("You get")
        get_l = QVBoxLayout(get_box)
        self._partner_name_lbl = QLabel("Select a partner team above")
        self._partner_name_lbl.setStyleSheet("color: #8b95ab;")
        get_l.addWidget(self._partner_name_lbl)
        get_l.addWidget(QLabel("Players — click to add"))
        self._get_players = QListWidget()
        self._get_players.itemChanged.connect(
            lambda item: self._on_asset_toggled(item, "want"))
        get_l.addWidget(self._get_players, 1)
        get_l.addWidget(QLabel("Draft picks"))
        self._get_picks = QListWidget()
        self._get_picks.itemChanged.connect(
            lambda item: self._on_asset_toggled(item, "want"))
        get_l.addWidget(self._get_picks, 1)

        give_box = QGroupBox("You give")
        give_l = QVBoxLayout(give_box)
        self._my_name_lbl = QLabel("Your roster")
        self._my_name_lbl.setStyleSheet("color: #8b95ab;")
        give_l.addWidget(self._my_name_lbl)
        give_l.addWidget(QLabel("Players — click to add"))
        self._give_players = QListWidget()
        self._give_players.itemChanged.connect(
            lambda item: self._on_asset_toggled(item, "give"))
        give_l.addWidget(self._give_players, 1)
        give_l.addWidget(QLabel("Draft picks"))
        self._give_picks = QListWidget()
        self._give_picks.itemChanged.connect(
            lambda item: self._on_asset_toggled(item, "give"))
        give_l.addWidget(self._give_picks, 1)

        cols.addWidget(get_box, 1)
        cols.addWidget(give_box, 1)
        top.addLayout(cols, 1)
        root.addLayout(top, 3)

        # -- the deal (chips) --
        self._deal_group = QGroupBox("The deal")
        deal_l = QVBoxLayout(self._deal_group)
        chip_row = QHBoxLayout()
        self._deal_get_chips = QHBoxLayout()
        self._deal_give_chips = QHBoxLayout()
        # Wrap chip rows in scroll areas so blockbusters don't clip
        from PySide6.QtWidgets import QScrollArea, QWidget
        get_scroll = QScrollArea()
        get_scroll.setWidgetResizable(True)
        get_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        get_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        get_scroll.setMaximumHeight(80)
        get_container = QWidget()
        get_container.setLayout(self._deal_get_chips)
        get_scroll.setWidget(get_container)
        give_scroll = QScrollArea()
        give_scroll.setWidgetResizable(True)
        give_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        give_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        give_scroll.setMaximumHeight(80)
        give_container = QWidget()
        give_container.setLayout(self._deal_give_chips)
        give_scroll.setWidget(give_container)
        get_chips = QVBoxLayout()
        get_chips.addWidget(QLabel("You get"))
        get_chips.addWidget(get_scroll)
        give_chips = QVBoxLayout()
        give_chips.addWidget(QLabel("You give"))
        give_chips.addWidget(give_scroll)
        chip_row.addLayout(get_chips, 1)
        mid = QLabel("⇄")
        mid.setStyleSheet("font-size: 20px;")
        chip_row.addWidget(mid)
        chip_row.addLayout(give_chips, 1)
        deal_l.addLayout(chip_row)
        self._deal_group.setVisible(False)
        root.addWidget(self._deal_group)

        # -- terms (retention / protection selectors) --
        self._terms_group = QGroupBox("Deal terms — retention & protection")
        terms_l = QVBoxLayout(self._terms_group)
        self._terms_area = QScrollArea()
        self._terms_area.setWidgetResizable(True)
        self._terms_area.setFixedHeight(130)
        self._terms_inner = QWidget()
        self._terms_layout = QVBoxLayout(self._terms_inner)
        self._terms_layout.setSpacing(4)
        self._terms_area.setWidget(self._terms_inner)
        terms_l.addWidget(self._terms_area)
        self._terms_group.setVisible(False)
        root.addWidget(self._terms_group)

        # -- verdict --
        verdict_box = QGroupBox("AI GM verdict (advisory)")
        v_l = QVBoxLayout(verdict_box)
        self._verdict_badge = QLabel("—")
        self._verdict_badge.setStyleSheet("font-size: 16px; font-weight: bold;")
        v_l.addWidget(self._verdict_badge)
        self._verdict_reason = QLabel(
            "Select a partner team and add players or picks on both sides.")
        self._verdict_reason.setWordWrap(True)
        self._verdict_reason.setStyleSheet("color: #8b95ab;")
        v_l.addWidget(self._verdict_reason)
        bars = QVBoxLayout()
        bars.setSpacing(4)
        self._give_bar = QProgressBar()
        self._give_bar.setMaximum(1000)
        self._get_bar = QProgressBar()
        self._get_bar.setMaximum(1000)
        give_row = QHBoxLayout()
        give_row.addWidget(QLabel("You give:"), 0)
        give_row.addWidget(self._give_bar, 1)
        self._give_val_lbl = QLabel("")
        give_row.addWidget(self._give_val_lbl, 0)
        bars.addLayout(give_row)
        get_row = QHBoxLayout()
        get_row.addWidget(QLabel("You get:"), 0)
        get_row.addWidget(self._get_bar, 1)
        self._get_val_lbl = QLabel("")
        get_row.addWidget(self._get_val_lbl, 0)
        bars.addLayout(get_row)
        v_l.addLayout(bars)
        self._verdict_terms = QLabel("")
        self._verdict_terms.setWordWrap(True)
        self._verdict_terms.setStyleSheet("color: #8b95ab;")
        self._verdict_terms.setVisible(False)
        v_l.addWidget(self._verdict_terms)
        root.addWidget(verdict_box)

        # -- actions --
        act = QHBoxLayout()
        self._note = QLabel("")
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color: #8b95ab;")
        act.addWidget(self._note, 1)
        self._propose_btn = QPushButton("Propose trade")
        self._propose_btn.setObjectName("primary-btn")
        self._propose_btn.setCursor(Qt.PointingHandCursor)
        self._propose_btn.setEnabled(False)
        self._propose_btn.clicked.connect(self._on_propose)
        act.addWidget(self._propose_btn)
        root.addLayout(act)

        self._tabs.addTab(tab, "Deal builder")

    def _build_negotiations_tab(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        top = QHBoxLayout()
        hint = QLabel("Offers you sent are with the other GM — they answer "
                      "in 1-3 days via your inbox. Counters addressed to you "
                      "can be answered from the inbox, or countered again "
                      "with the builder.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b95ab;")
        top.addWidget(hint, 1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_negotiations)
        top.addWidget(refresh_btn)
        l.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._neg_inner = QWidget()
        self._neg_layout = QVBoxLayout(self._neg_inner)
        self._neg_layout.setSpacing(10)
        self._neg_layout.addStretch()
        scroll.setWidget(self._neg_inner)
        l.addWidget(scroll, 1)
        self._tabs.addTab(tab, "Open negotiations")

    def _build_completed_tab(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._log_inner = QWidget()
        self._log_layout = QVBoxLayout(self._log_inner)
        self._log_layout.setSpacing(8)
        self._log_layout.addStretch()
        scroll.setWidget(self._log_inner)
        l.addWidget(scroll, 1)
        self._tabs.addTab(tab, "Completed trades")

    # -- data loading --------------------------------------------------------

    def refresh(self):
        self._check_window()
        self._load_teams()
        self._load_my_assets()
        if self._partner is not None:
            self._load_partner_assets()
        self._load_negotiations()
        self._load_completed_log()

    def _load_teams(self):
        league = _league(self.game)
        teams = _safe(lambda: list(getattr(league, "teams", None) or []),
                      []) or []
        my = _user_team(self.game)
        my_name = _team_name(my) if my else ""
        block = _safe(lambda: list(getattr(
            _resolve_gm(self.game), "trade_block", None) or []), []) or []
        block_teams = set()
        for p in block:
            owner = _safe(lambda: getattr(p, "team", None)) or \
                _safe(lambda: getattr(p, "team_name", None))
            block_teams.add(_team_name(owner))
        self._teams = [t for t in teams if _team_name(t) != my_name]
        self._my_team_name = my_name
        self._my_name_lbl.setText(f"{my_name} — your roster" if my_name
                                  else "Your roster")
        self._block_teams = block_teams
        self._render_teams()

    def _render_teams(self):
        q = self._team_search.text().strip().lower()
        self._updating = True
        try:
            self._team_list.clear()
            for t in self._teams:
                name = _team_name(t)
                if q and q not in name.lower():
                    continue
                tag = "  [on block]" if name in getattr(
                    self, "_block_teams", set()) else ""
                item = QListWidgetItem(f"{name}{tag}")
                item.setData(Qt.UserRole, name)
                if name == self._partner_name:
                    item.setSelected(True)
                self._team_list.addItem(item)
        finally:
            self._updating = False

    def _on_team_selected(self):
        if self._updating:
            return
        items = self._team_list.selectedItems()
        if not items:
            return
        name = items[0].data(Qt.UserRole)
        self._select_partner(name)

    def _select_partner(self, name):
        self._partner = _find_team(self.game, name)
        self._partner_name = _team_name(self._partner) if self._partner \
            else (name or "")
        self._want_pids.clear()
        self._want_picks.clear()
        self._retention_acquire.clear()
        self._load_partner_assets()
        self._partner_name_lbl.setText(
            self._partner_name or "Select a partner team above")
        self._prune_terms()
        self._render_asset_lists()
        self._update_slot_labels()
        self._render_deal_chips()
        self._render_terms()
        self._schedule_evaluate()

    def _load_my_assets(self):
        my = _user_team(self.game)
        if my is None:
            return
        players, picks = _team_trade_lists(my)
        self._my_players = players
        self._my_picks = picks
        slots = retention_slots_summary(my)
        self._slots_used = slots["used"]
        self._slots_max = slots["max"]
        self._prune_terms()
        self._render_asset_lists()
        self._update_slot_labels()
        self._render_terms()

    def _load_partner_assets(self):
        if self._partner is None:
            self._partner_players = []
            self._partner_picks = []
            self._partner_slots_used = 0
            return
        players, picks = _team_trade_lists(self._partner)
        self._partner_players = players
        self._partner_picks = picks
        slots = retention_slots_summary(self._partner)
        self._partner_slots_used = slots["used"]
        self._partner_slots_max = slots["max"]

    # -- asset lists ----------------------------------------------------------

    def _asset_text(self, obj, kind, level=""):
        if kind == "pick":
            prot = _safe(lambda: getattr(obj, "protection", ""), "") or ""
            sub = f"{_pick_label(obj)}" + (f" · {prot}" if prot else "")
            return sub, None
        ovr = _player_ovr(obj)
        name = _player_name(obj)
        tags = []
        cap = _player_captaincy(obj)
        if cap:
            tags.append(f"({cap})")
        if _player_injured(obj):
            tags.append("[INJ]")
        if level:
            tags.append(f"[{level}]")
        tag_txt = " ".join(tags)
        txt = (f"{ovr}  {name}  ({_pos_str(obj)}, "
               f"Age {_player_age(obj)}) — {_fmt_money(_player_cap_hit(obj))}"
               + (f"  {tag_txt}" if tag_txt else ""))
        return txt, name

    def _fill_list(self, widget, items, kind, selected):
        self._updating = True
        try:
            widget.clear()
            if kind == "player":
                items = sorted(items, key=lambda pl: -_player_ovr(pl[0]))
            else:
                items = sorted(
                    items,
                    key=lambda pk: (
                        _safe(lambda: int(getattr(pk, "year", 0) or 0), 0),
                        _safe(lambda: int(getattr(pk, "round", 0) or 0), 0)))
            if not items:
                it = QListWidgetItem("— None —")
                it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable
                            & ~Qt.ItemIsEnabled)
                widget.addItem(it)
                return
            for obj, level in ([(o, l) for o, l in items]
                               if kind == "player" else [(o, "") for o in items]):
                txt, name = self._asset_text(obj, kind, level)
                it = QListWidgetItem(txt)
                pid = _pid(obj)
                it.setData(Qt.UserRole, (kind, pid))
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if pid in selected
                                 else Qt.Unchecked)
                widget.addItem(it)
        finally:
            self._updating = False

    def _render_asset_lists(self):
        self._fill_list(self._give_players, self._my_players, "player",
                        self._give_pids)
        self._fill_list(self._give_picks, self._my_picks, "pick",
                        self._give_picks)
        self._fill_list(self._get_players, self._partner_players, "player",
                        self._want_pids)
        self._fill_list(self._get_picks, self._partner_picks, "pick",
                        self._want_picks)

    def _on_asset_toggled(self, item, side):
        if self._updating:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        kind, pid = data
        if side == "give":
            s = self._give_pids if kind == "player" else self._give_picks
        else:
            s = self._want_pids if kind == "player" else self._want_picks
        if item.checkState() == Qt.Checked:
            s.add(pid)
        else:
            s.discard(pid)
        self._prune_terms()
        self._update_slot_labels()
        self._render_deal_chips()
        self._render_terms()
        self._schedule_evaluate()

    def _prune_terms(self):
        for k in list(self._retention):
            if k not in self._give_pids:
                del self._retention[k]
        for k in list(self._retention_acquire):
            if k not in self._want_pids:
                del self._retention_acquire[k]
        for k in list(self._protection):
            if k not in self._give_picks:
                del self._protection[k]

    def _slots_remaining(self):
        fresh = sum(1 for v in self._retention.values() if v > 0)
        return self._slots_max - self._slots_used - fresh

    def _slots_remaining_acquire(self):
        fresh = sum(1 for v in self._retention_acquire.values() if v > 0)
        return self._partner_slots_max - self._partner_slots_used - fresh

    def _update_slot_labels(self):
        fresh = sum(1 for v in self._retention.values() if v > 0)
        used = self._slots_used + fresh
        self._slots_lbl.setText(
            f"Retention: {used}/{self._slots_max} slots")
        afresh = sum(1 for v in self._retention_acquire.values() if v > 0)
        aused = self._partner_slots_used + afresh
        self._partner_slots_lbl.setVisible(bool(self._partner_name))
        self._partner_slots_lbl.setText(
            f"{(self._partner_name or 'Partner').split()[-1]} retention: "
            f"{aused}/{self._partner_slots_max} slots")

    def _note_err(self, msg):
        self._note.setText(msg)
        self._note.setStyleSheet("color: #e5484d;")

    def _note_ok(self, msg):
        self._note.setText(msg)
        self._note.setStyleSheet("color: #30a46c;")

    def _note_plain(self, msg):
        self._note.setText(msg)
        self._note.setStyleSheet("color: #8b95ab;")

    # -- deal chips ----------------------------------------------------------

    def _clear_layout(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def _asset_lookup(self, pid, side):
        src = (self._my_players if side == "give" else self._partner_players)
        for p, _lvl in src:
            if _pid(p) == pid:
                return p, "player"
        src = self._my_picks if side == "give" else self._partner_picks
        for pk in src:
            if _pid(pk) == pid:
                return pk, "pick"
        return None, None

    def _render_deal_chips(self):
        self._clear_layout(self._deal_get_chips)
        self._clear_layout(self._deal_give_chips)

        def chip(text, tooltip, on_remove):
            b = QPushButton(text + "  ✕")
            b.setToolTip(tooltip)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "text-align: left; padding: 5px 8px; border-radius: 8px; "
                "background: #232b45;")
            b.clicked.connect(on_remove)
            return b

        def add_chip(layout, obj, kind, side, pid):
            if kind == "pick":
                txt = _pick_label(obj)
            else:
                ret = ""
                if side == "give" and self._retention.get(pid):
                    ret = f" ({self._retention[pid]:g}% ret.)"
                elif side == "get" and self._retention_acquire.get(pid):
                    ret = (f" ({self._retention_acquire[pid]:g}% "
                           "ret. by them)")
                txt = f"{_player_ovr(obj)} {_player_name(obj)}{ret}"
            layout.addWidget(chip(
                txt, "Click to remove from the deal",
                lambda _=None, k=kind, p=pid, s=side:
                self._remove_from_deal(p, k, s)))

        count = 0
        for pid in sorted(self._want_pids):
            obj, kind = self._asset_lookup(pid, "get")
            if obj is not None:
                add_chip(self._deal_get_chips, obj, kind, "get", pid)
                count += 1
        for pid in sorted(self._want_picks):
            obj, kind = self._asset_lookup(pid, "get")
            if obj is not None:
                add_chip(self._deal_get_chips, obj, kind, "get", pid)
                count += 1
        for pid in sorted(self._give_pids):
            obj, kind = self._asset_lookup(pid, "give")
            if obj is not None:
                add_chip(self._deal_give_chips, obj, kind, "give", pid)
                count += 1
        for pid in sorted(self._give_picks):
            obj, kind = self._asset_lookup(pid, "give")
            if obj is not None:
                add_chip(self._deal_give_chips, obj, kind, "give", pid)
                count += 1
        self._deal_group.setVisible(count > 0)

    def _remove_from_deal(self, pid, kind, side):
        if side == "give":
            (self._give_pids if kind == "player"
             else self._give_picks).discard(pid)
        else:
            (self._want_pids if kind == "player"
             else self._want_picks).discard(pid)
        self._prune_terms()
        self._render_asset_lists()
        self._update_slot_labels()
        self._render_deal_chips()
        self._render_terms()
        self._schedule_evaluate()

    # -- terms (retention / protection selectors) ----------------------------

    def _render_terms(self):
        self._clear_layout(self._terms_layout)
        any_terms = False

        def retention_combo(pid, store, acquire):
            cur = store.get(pid, 0)
            remaining = (self._slots_remaining_acquire() if acquire
                         else self._slots_remaining())
            max_slots = (self._partner_slots_max if acquire
                         else self._slots_max)
            no_slots = remaining <= 0 and cur == 0
            combo = QComboBox()
            for pct in RETENTION_OPTIONS:
                combo.addItem(f"{'Ask ' if acquire else 'Retain '}{pct}%",
                              pct)
                if pct == cur:
                    combo.setCurrentIndex(combo.count() - 1)
                if pct > 0 and no_slots:
                    combo.model().item(combo.count() - 1).setEnabled(False)
            if no_slots:
                combo.setToolTip(
                    f"No retention slots left (max {max_slots} per club)")
            else:
                combo.setToolTip(
                    ("Salary you ask " +
                     (self._partner_name or "the partner") +
                     " to keep on this player (NHL max 50%)")
                    if acquire else
                    "Salary your club keeps on this player (NHL max 50%)")

            def on_change(idx, _pid=pid, _store=store,
                          _acq=acquire, _prev_holder=[cur],
                          _combo=combo, _max=max_slots):
                pct = _combo.itemData(idx) or 0
                prev = _prev_holder[0]
                if pct == 0:
                    _store.pop(_pid, None)
                else:
                    _store[_pid] = pct
                _prev_holder[0] = pct
                left = (self._slots_remaining_acquire() if _acq
                        else self._slots_remaining())
                if left < 0:
                    if prev == 0:
                        _store.pop(_pid, None)
                    else:
                        _store[_pid] = prev
                    _prev_holder[0] = prev
                    self._note_err(
                        f"Retention slot limit reached ({_max} per club) — "
                        "remove a term to add another.")
                    self._render_terms()
                    return
                self._update_slot_labels()
                self._render_terms()
                self._schedule_evaluate()

            combo.currentIndexChanged.connect(on_change)
            return combo

        for pid in sorted(self._give_pids):
            p, kind = self._asset_lookup(pid, "give")
            if kind != "player":
                continue
            any_terms = True
            row = QHBoxLayout()
            cur = self._retention.get(pid, 0)
            amt = _fmt_money(
                int(round(_player_cap_hit(p) * cur / 100))) if cur else ""
            lbl = QLabel(
                f"Retain on {_player_name(p)} "
                f"({_fmt_money(_player_cap_hit(p))})")
            row.addWidget(lbl, 1)
            row.addWidget(retention_combo(pid, self._retention, False))
            if amt:
                a = QLabel(f"you keep {amt}")
                a.setStyleSheet("color: #8b95ab;")
                row.addWidget(a)
            self._terms_layout.addLayout(row)

        for pid in sorted(self._want_pids):
            p, kind = self._asset_lookup(pid, "get")
            if kind != "player":
                continue
            any_terms = True
            row = QHBoxLayout()
            cur = self._retention_acquire.get(pid, 0)
            amt = _fmt_money(
                int(round(_player_cap_hit(p) * cur / 100))) if cur else ""
            lbl = QLabel(
                f"Ask {self._partner_name or 'partner'} to retain on "
                f"{_player_name(p)} ({_fmt_money(_player_cap_hit(p))})")
            row.addWidget(lbl, 1)
            row.addWidget(retention_combo(pid, self._retention_acquire, True))
            if amt:
                a = QLabel(f"they keep {amt}")
                a.setStyleSheet("color: #8b95ab;")
                row.addWidget(a)
            self._terms_layout.addLayout(row)

        for pid in sorted(self._give_picks):
            pk, kind = self._asset_lookup(pid, "give")
            if kind != "pick":
                continue
            any_terms = True
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Protection on {_pick_label(pk)}"), 1)
            combo = QComboBox()
            combo.addItem("No protection", "")
            for code in PROTECTION_CODES:
                combo.addItem(_protection_label(code), code)
            cur = self._protection.get(pid, "")
            idx = combo.findData(cur)
            combo.setCurrentIndex(max(0, idx))
            combo.setToolTip("Protection on this pick "
                             "(NHL: top-3 / top-10 / lottery)")

            def on_prot(idx, _pid=pid, _combo=combo):
                code = _combo.itemData(idx) or ""
                if code:
                    self._protection[_pid] = code
                else:
                    self._protection.pop(_pid, None)
                self._schedule_evaluate()

            combo.currentIndexChanged.connect(on_prot)
            row.addWidget(combo)
            self._terms_layout.addLayout(row)

        self._terms_group.setVisible(any_terms)

    # -- evaluate ------------------------------------------------------------

    def _schedule_evaluate(self):
        QTimer.singleShot(450, self._evaluate)

    def _evaluate(self):
        if not self._partner:
            return
        te = _trade_engine()
        my = _user_team(self.game)
        if te is None or my is None:
            self._reset_verdict("Trade engine unavailable.")
            return
        give_players = [p for p, _ in self._my_players
                        if _pid(p) in self._give_pids]
        give_picks = [pk for pk in self._my_picks
                      if _pid(pk) in self._give_picks]
        want_players = [p for p, _ in self._partner_players
                        if _pid(p) in self._want_pids]
        want_picks = [pk for pk in self._partner_picks
                      if _pid(pk) in self._want_picks]
        give_assets = give_players + give_picks
        want_assets = want_players + want_picks
        if not give_assets and not want_assets:
            self._reset_verdict(
                "Select a partner team and add players or picks on both "
                "sides.")
            self._update_propose_state(None)
            return
        try:
            retention_terms = parse_retention_terms(
                self._retention, {_pid(p) for p in give_players})
            protection_terms = parse_protection_terms(
                self._protection, {_pid(pk) for pk in give_picks})
            ret_ok, ret_errors = validate_retention_terms(
                my, give_players, retention_terms)
            acquire_terms = parse_retention_terms(
                self._retention_acquire, {_pid(p) for p in want_players})
            acq_ok, acq_errors = validate_retention_terms(
                self._partner, want_players, acquire_terms)
            prot_adj = protection_value_adjustment(
                give_picks, protection_terms, te)
            terms_note = deal_terms_note(
                give_players, give_picks, retention_terms, protection_terms,
                want_players=want_players, acquire_terms=acquire_terms)

            ev = _safe(lambda: te.evaluate_trade(
                give_assets, want_assets, user_team=my,
                partner_team=self._partner, perceiver_team=self._partner))
            gv = _safe(lambda: ev.user_value, 0) or 0
            pv = _safe(lambda: ev.partner_value, 0) or 0
            ratio = _safe(lambda: ev.ratio, 0.0) or 0.0
            label = _safe(lambda: ev.label, "Incomplete") or "Incomplete"

            all_retention = {**retention_terms, **acquire_terms}

            def _verdict_call():
                try:
                    return te.ai_consider_trade(
                        self._partner, give_assets, want_assets,
                        user_team=my, retention=all_retention)
                except TypeError:
                    return te.ai_consider_trade(
                        self._partner, give_assets, want_assets,
                        user_team=my)

            resp = _safe(_verdict_call)
            verdict = (_safe(lambda: resp.decision, "reject") or "reject")
            reason = _safe(lambda: resp.message, "") or ""
            data = {
                "verdict": verdict, "reason": reason,
                "give_value": gv, "get_value": pv, "ratio": ratio,
                "label": label,
                "retention_valid": ret_ok, "retention_errors": ret_errors,
                "retention_acquire_valid": acq_ok,
                "retention_acquire_errors": acq_errors,
                "protection_adjustment": prot_adj,
                "terms_note": terms_note,
            }
            self._last_verdict = data
            self._render_verdict(data)
            self._update_propose_state(data)
        except Exception as e:
            self._reset_verdict(f"Could not reach the trade evaluator: {e}")
            self._update_propose_state(None)

    def _reset_verdict(self, msg):
        self._verdict_badge.setText("—")
        self._verdict_badge.setStyleSheet(
            "font-size: 16px; font-weight: bold;")
        self._verdict_reason.setText(msg)
        self._give_bar.setValue(0)
        self._get_bar.setValue(0)
        self._give_val_lbl.setText("")
        self._get_val_lbl.setText("")
        self._verdict_terms.setVisible(False)

    def _render_verdict(self, d):
        v = str(d.get("verdict", "reject")).lower()
        if v == "accept":
            badge, color = "Likely: accepts", "#30a46c"
        elif v == "counter":
            badge, color = "Likely: counters", "#f5a524"
        else:
            badge, color = "Likely: rejects", "#e5484d"
        self._verdict_badge.setText(badge)
        self._verdict_badge.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};")
        self._verdict_reason.setText(d.get("reason", ""))
        gv = d.get("give_value", 0) or 0
        pv = d.get("get_value", 0) or 0
        mx = max(gv, pv, 1)
        self._give_bar.setValue(int(1000 * gv / mx))
        self._get_bar.setValue(int(1000 * pv / mx))
        self._give_val_lbl.setText(f"({gv} pts)" if gv else "")
        self._get_val_lbl.setText(f"({pv} pts)" if pv else "")
        bits = []
        if d.get("terms_note"):
            bits.append(d["terms_note"])
        if (d.get("protection_adjustment") or 0) > 0:
            bits.append("Pick protection discounts your offer by ≈"
                        f"{d['protection_adjustment']} pts to the receiving "
                        "GM (estimate).")
        if d.get("retention_errors"):
            bits.append("⚠ Retention problem: "
                        + " ".join(d["retention_errors"]))
        if d.get("retention_acquire_errors"):
            bits.append("⚠ Partner retention problem: "
                        + " ".join(d["retention_acquire_errors"]))
        self._verdict_terms.setText("\n".join(bits))
        self._verdict_terms.setVisible(bool(bits))

    def _update_propose_state(self, data):
        has_assets = bool(self._give_pids or self._give_picks
                          or self._want_pids or self._want_picks)
        ret_bad = False
        if data:
            ret_bad = (bool(data.get("retention_errors"))
                       or data.get("retention_valid") is False
                       or bool(data.get("retention_acquire_errors"))
                       or data.get("retention_acquire_valid") is False)
        self._propose_btn.setEnabled(
            has_assets and not ret_bad and not self._frozen)
        if self._frozen:
            self._propose_btn.setToolTip(self._freeze_reason
                                        or "Trades are frozen")
        else:
            self._propose_btn.setToolTip("")

    # -- trade window --------------------------------------------------------

    def _check_window(self):
        frozen, reason = _trade_window_state(self.game)
        self._frozen = frozen
        self._freeze_reason = reason
        self._freeze_banner.setVisible(frozen)
        if frozen:
            self._freeze_banner.setText(
                f"⛔ {reason or 'Trades are frozen.'}")
            self._propose_btn.setEnabled(False)
            self._propose_btn.setToolTip(reason or "Trades are frozen")

    # -- consent preflight ---------------------------------------------------

    def _consent_preflight(self):
        """Run the NTC/NMC preflight. Returns True if the user may send.

        Fail-open on engine trouble (like the desktop). Dismiss = don't send.
        """
        te = _trade_engine()
        if te is None:
            return True
        try:
            league = _league(self.game)
            my = _user_team(self.game)
            if my is None or self._partner is None:
                return True
            give_players = [p for p, _ in self._my_players
                            if _pid(p) in self._give_pids]
            want_players = [p for p, _ in self._partner_players
                            if _pid(p) in self._want_pids]
            our = [f for f in
                   (_preflight_flag(te, p, my, self._partner, league,
                                    self._partner_name)
                    for p in give_players) if f]
            theirs = [f for f in
                      (_preflight_flag(te, p, self._partner, my, league,
                                       self._my_team_name)
                       for p in want_players) if f]
            if not our and not theirs:
                return True
            dlg = _ConsentDialog(self, our, theirs, self._partner_name)
            dlg.exec()
            return dlg.send
        except Exception:
            return True  # fail-open on engine error

    # -- propose --------------------------------------------------------------

    def _mp_state(self):
        """(host, client) multiplayer objects if an MP session is active."""
        host = _safe(lambda: getattr(self.game, "mp_host", None))
        client = _safe(lambda: getattr(self.game, "mp_client", None))
        if host is None and client is None:
            try:
                from .multiplayer import MultiplayerScreen
                mw = self.main_window
                for scr in _safe(lambda: mw.findChildren(MultiplayerScreen),
                                []) or []:
                    host = host or _safe(lambda: scr._host)
                    client = client or _safe(lambda: scr._client)
            except Exception:
                pass
        return host, client

    def _mp_active(self):
        host, client = self._mp_state()
        if host is not None and _safe(lambda: host.running(), False):
            return True
        if client is not None and _safe(lambda: client.connected(), False):
            return True
        return False

    def _partner_is_human(self):
        return bool(_safe(lambda: getattr(self._partner, "is_human_managed",
                                        False), False))

    def _on_propose(self):
        if not self._propose_btn.isEnabled():
            return
        if self._frozen:
            self._note_err(self._freeze_reason or "Trades are frozen.")
            return
        # Batch D: NTC/NMC waiver-consent preflight (desktop parity).
        # Dismiss = safe default (don't send).
        if not self._consent_preflight():
            return
        self._propose_btn.setEnabled(False)
        self._propose_btn.setText("Proposing…")
        self._note_plain("")
        try:
            # Multiplayer (Batch E): human-run partner club -> route the
            # offer through the MP layer instead of the AI negotiation path.
            if self._partner_is_human() and self._mp_active():
                self._mp_propose()
                return
            self._ai_propose()
        finally:
            self._propose_btn.setText("Propose trade")

    def _collect_assets(self):
        give_players = [p for p, _ in self._my_players
                        if _pid(p) in self._give_pids]
        give_picks = [pk for pk in self._my_picks
                      if _pid(pk) in self._give_picks]
        want_players = [p for p, _ in self._partner_players
                        if _pid(p) in self._want_pids]
        want_picks = [pk for pk in self._partner_picks
                      if _pid(pk) in self._want_picks]
        return give_players, give_picks, want_players, want_picks

    def _validate_terms(self, my, partner, give_players, give_picks,
                        want_players):
        """Server-grade validation before an offer goes out. Returns
        (retention, retention_acquire, protection) or raises ValueError."""
        te = _trade_engine()
        if te is None:
            raise ValueError("Trade engine unavailable.")
        retention = parse_retention_terms(
            self._retention, {_pid(p) for p in give_players})
        acquire = parse_retention_terms(
            self._retention_acquire, {_pid(p) for p in want_players})
        protection = parse_protection_terms(
            self._protection, {_pid(pk) for pk in give_picks})
        ok, errs = validate_retention_terms(my, give_players, retention)
        if not ok:
            raise ValueError("retention invalid: " + "; ".join(errs))
        ok, errs = validate_retention_terms(partner, want_players, acquire)
        if not ok:
            raise ValueError("retention_acquire invalid: " + "; ".join(errs))
        return retention, acquire, protection

    def _ai_propose(self):
        te = _trade_engine()
        my = _user_team(self.game)
        if te is None or my is None or self._partner is None:
            self._note_err("Could not resolve teams or trade engine.")
            self._schedule_evaluate()
            return
        give_players, give_picks, want_players, want_picks = \
            self._collect_assets()
        if not (give_players or give_picks or want_players or want_picks):
            self._note_err("Empty proposal.")
            self._schedule_evaluate()
            return
        try:
            retention, acquire, protection = self._validate_terms(
                my, self._partner, give_players, give_picks, want_players)
        except ValueError as e:
            self._note_err(str(e))
            self._schedule_evaluate()
            return
        try:
            import trade_negotiation as tn
        except Exception:
            tn = None
        if tn is None:
            self._note_err("Negotiation machinery unavailable.")
            self._schedule_evaluate()
            return
        try:
            all_retention = {**retention, **acquire}
            neg = tn.send_offer(
                self.game, self._partner,
                give_players + give_picks, want_players + want_picks,
                retention=all_retention, pick_protection=protection)
        except Exception as e:
            self._note_err(f"Could not send offer: {e}")
            self._schedule_evaluate()
            return
        pname = _team_name(self._partner)
        if _safe(lambda: neg.status, "") == "awaiting_ai" and \
                _safe(lambda: getattr(neg, "response_due", None)) is not None:
            self._note_ok(f"Offer sent to {pname}. Their GM needs 1-3 "
                          "days — the answer lands in your inbox (accept, "
                          "counter, or reject). Track it under Open "
                          "negotiations.")
        else:
            self._note_ok(f"Deadline-day rush: {pname}'s GM answered "
                          "instantly — check your inbox.")
        self._clear_deal()
        self._load_my_assets()
        self._load_partner_assets()
        self._select_partner(self._partner_name)
        self._load_negotiations()

    def _mp_propose(self):
        """Human-to-human propose through the MP layer."""
        host, client = self._mp_state()
        my = _user_team(self.game)
        my_name = _team_name(my)
        offer = {
            "players_out": sorted(self._give_pids),
            "players_in": sorted(self._want_pids),
            "picks_out": sorted(self._give_picks),
            "picks_in": sorted(self._want_picks),
            "retention": {str(k): float(v)
                          for k, v in self._retention.items() if v > 0},
            "pick_protection": {str(k): v
                                for k, v in self._protection.items() if v},
        }
        try:
            if client is not None and host is None and \
                    _safe(lambda: client.connected(), False):
                # Client machine: the offer goes to the host for routing.
                client.send_action("propose_trade", {
                    "team_id": my_name,
                    "partner_team_id": self._partner_name,
                    "offer": offer})
                self._note_ok("Offer sent — the other (human) GM gets it "
                              "live. Their answer appears in the "
                              "multiplayer feed.")
                self._clear_deal()
                self._schedule_evaluate()
                return
            # Host machine (or local human GMs): run the real
            # _mp_propose_trade path directly.
            fn = _safe(lambda: getattr(self.game, "_mp_propose_trade", None))
            if fn is None:
                raise RuntimeError("MP trade routing unavailable.")
            params = {"partner_team_id": self._partner_name, "offer": offer}
            res = fn(params, my,
                     _safe(lambda: getattr(self.game, "gm_name", "Host"),
                           "Host"))
            ok = bool(res[0]) if isinstance(res, (list, tuple)) else bool(res)
            detail = (str(res[1]) if isinstance(res, (list, tuple))
                      and len(res) > 1 else "")
            if ok:
                self._note_ok("Done: " + (detail or "offer routed."))
                self._clear_deal()
            else:
                self._note_err("Failed: " + (detail or "offer rejected."))
        except Exception as e:
            self._note_err(f"Failed: {e}")
        finally:
            self._schedule_evaluate()

    def _clear_deal(self):
        self._give_pids.clear()
        self._give_picks.clear()
        self._want_pids.clear()
        self._want_picks.clear()
        self._retention.clear()
        self._retention_acquire.clear()
        self._protection.clear()
        self._prune_terms()
        self._render_asset_lists()
        self._update_slot_labels()
        self._render_deal_chips()
        self._render_terms()
        self._reset_verdict(
            "Select a partner team and add players or picks on both sides.")

    # -- open negotiations ----------------------------------------------------

    def _on_tab_changed(self, idx):
        if self._tabs.tabText(idx) == "Open negotiations":
            self._start_neg_timer()
            self._load_negotiations()
        else:
            self._stop_neg_timer()

    def _start_neg_timer(self):
        self._stop_neg_timer()
        self._neg_timer = QTimer(self)
        self._neg_timer.timeout.connect(self._load_negotiations)
        self._neg_timer.start(30000)

    def _stop_neg_timer(self):
        if self._neg_timer is not None:
            self._neg_timer.stop()
            self._neg_timer = None

    def _open_negotiations(self):
        gm = _resolve_gm(self.game)
        store = _safe(lambda: list(
            getattr(gm, "trade_negotiations", None) or []), []) or []
        out = []
        for n in store:
            try:
                status = str(_safe(lambda: getattr(n, "status", ""), ""))
                if status not in ("awaiting_ai", "awaiting_user"):
                    continue
                out.append(n)
            except Exception:
                continue

        def _created(n):
            c = _safe(lambda: getattr(n, "created", None))
            return str(c) if c is not None else ""

        out.sort(key=_created, reverse=True)
        return out

    def _load_negotiations(self):
        self._clear_layout(self._neg_layout)
        negs = self._open_negotiations()
        try:
            import trade_negotiation as tn
        except Exception:
            tn = None
        if not negs:
            lbl = QLabel("No open negotiations — propose a trade from the "
                         "Deal builder and the thread will appear here.")
            lbl.setStyleSheet("color: #8b95ab;")
            lbl.setWordWrap(True)
            self._neg_layout.addWidget(lbl)
            self._neg_layout.addStretch()
            return
        for n in negs:
            neg_id = str(_safe(lambda: getattr(n, "id", ""), ""))
            partner = str(_safe(lambda: getattr(
                n, "partner_team_name", "?"), "?"))
            status = str(_safe(lambda: getattr(n, "status", ""), ""))
            rounds = _safe(lambda: int(getattr(n, "rounds", 0) or 0), 0)
            patience = _safe(lambda: float(getattr(n, "patience", 1.0)
                                          or 1.0), 1.0)
            due = _safe(lambda: getattr(n, "response_due", None))
            last = str(_safe(lambda: getattr(n, "last_message", ""), "")
                       or "")
            if status == "awaiting_ai":
                status_txt = (f"With {partner}'s GM — answer due "
                              f"{due if due else 'soon'}")
            elif status == "awaiting_user":
                status_txt = "Their move — answer from the inbox or below"
            else:
                status_txt = status
            card = QGroupBox(f"{partner}  ·  round {rounds}  ·  "
                            f"patience {patience:.0%}")
            cl = QVBoxLayout(card)
            st = QLabel(status_txt)
            st.setStyleSheet("color: #f5a524; font-weight: bold;")
            cl.addWidget(st)
            if tn is not None:
                you_send = _safe(
                    lambda: tn.asset_summary(
                        getattr(n, "user_assets", []),
                        getattr(n, "retention", {}),
                        getattr(n, "pick_protection", {})),
                    "?")
                you_get = _safe(
                    lambda: tn.asset_summary(
                        getattr(n, "partner_assets", [])), "?")
            else:
                you_send = you_get = "?"
            terms = QLabel(f"You send: {you_send}\nYou get: {you_get}")
            terms.setWordWrap(True)
            cl.addWidget(terms)
            if last:
                lm = QLabel(last)
                lm.setWordWrap(True)
                lm.setStyleSheet("color: #8b95ab; font-style: italic;")
                cl.addWidget(lm)
            hist = _safe(lambda: list(getattr(n, "history", None) or []),
                         []) or []
            if hist:
                htxt = "\n".join(
                    f"{h.get('date', '')} — "
                    f"{'You' if h.get('by') == 'user' else h.get('by', '')}: "
                    f"{h.get('summary', '')}"
                    for h in hist if isinstance(h, dict))
                h = QLabel(htxt)
                h.setWordWrap(True)
                h.setStyleSheet("color: #8b95ab; font-size: 12px;")
                cl.addWidget(h)
            btns = QHBoxLayout()
            if status == "awaiting_user":
                acc = QPushButton("Accept")
                acc.setObjectName("primary-btn")
                acc.clicked.connect(
                    lambda _=None, nid=neg_id: self._neg_answer(nid, True))
                dec = QPushButton("Decline")
                dec.clicked.connect(
                    lambda _=None, nid=neg_id: self._neg_answer(nid, False))
                ctr = QPushButton("Counter with current builder terms")
                ctr.clicked.connect(
                    lambda _=None, nid=neg_id: self._neg_counter(nid))
                btns.addWidget(acc)
                btns.addWidget(dec)
                btns.addWidget(ctr)
            inbox = QPushButton("Open inbox to answer")
            inbox.clicked.connect(self._open_inbox)
            btns.addWidget(inbox)
            btns.addStretch()
            cl.addLayout(btns)
            self._neg_layout.addWidget(card)
        self._neg_layout.addStretch()

    def _open_inbox(self):
        try:
            self.main_window.show_inbox()
        except Exception as e:
            QMessageBox.information(self, "Inbox",
                                    f"Could not open the inbox: {e}")

    def _neg_answer(self, neg_id, accept):
        try:
            import trade_negotiation as tn
        except Exception:
            tn = None
        if tn is None:
            QMessageBox.warning(self, "Negotiation",
                                "Negotiation machinery unavailable.")
            return
        try:
            ok = (tn.accept_negotiation(self.game, neg_id) if accept
                  else tn.decline_negotiation(self.game, neg_id))
        except Exception as e:
            QMessageBox.warning(self, "Negotiation",
                                f"Could not answer: {e}")
            return
        if ok:
            self._note_ok("Trade accepted — done deal."
                          if accept else "Walked away from the table.")
        else:
            self._note_err("That negotiation is no longer open.")
        self._load_negotiations()
        self._load_my_assets()

    def _neg_counter(self, neg_id):
        has_assets = bool(self._give_pids or self._give_picks
                          or self._want_pids or self._want_picks)
        if not has_assets:
            self._note_err("Build your counter in the Deal builder first, "
                           "then press this button again.")
            return
        try:
            import trade_negotiation as tn
        except Exception:
            tn = None
        if tn is None:
            self._note_err("Negotiation machinery unavailable.")
            return
        neg = _safe(lambda: tn.get_negotiation(self.game, neg_id))
        if neg is None or not _safe(lambda: neg.is_open, False):
            self._note_err("That negotiation is no longer open.")
            return
        my = _user_team(self.game)
        partner = _safe(lambda: tn.find_team(
            self.game, getattr(neg, "partner_team_name", "")))
        if my is None or partner is None:
            self._note_err("Could not resolve teams.")
            return
        give_players, give_picks, want_players, want_picks = \
            self._collect_assets()
        if not (give_players or give_picks or want_players or want_picks):
            self._note_err("Empty counter-offer.")
            return
        try:
            retention, acquire, protection = self._validate_terms(
                my, partner, give_players, give_picks, want_players)
        except ValueError as e:
            self._note_err(str(e))
            return
        try:
            tn.send_counter(
                self.game, neg,
                give_players + give_picks, want_players + want_picks,
                retention={**retention, **acquire},
                pick_protection=protection)
            self._note_ok(
                f"Counter sent to {getattr(neg, 'partner_team_name', '')} — "
                "they answer in 1-3 days via your inbox.")
        except Exception as e:
            self._note_err(f"Counter failed: {e}")
        self._load_negotiations()

    # -- completed-trade log ---------------------------------------------------

    def _load_completed_log(self):
        self._clear_layout(self._log_layout)
        gm = _resolve_gm(self.game)
        recs = _safe(lambda: list(
            getattr(gm, "trade_history", None) or []), []) or []
        if not recs:
            lbl = QLabel("No completed trades yet this career — the log "
                         "fills in as deals get done.")
            lbl.setStyleSheet("color: #8b95ab;")
            lbl.setWordWrap(True)
            self._log_layout.addWidget(lbl)
            self._log_layout.addStretch()
            return
        for r in reversed(recs[-30:]):
            try:
                dt = str(_safe(lambda: getattr(r, "date", ""), "") or "")
                ta = str(_safe(lambda: getattr(r, "team_a", ""), "") or "")
                tb = str(_safe(lambda: getattr(r, "team_b", ""), "") or "")
                a_gave = [str(x) for x in
                          (_safe(lambda: list(
                              getattr(r, "a_gave", None) or []), []) or [])]
                b_gave = [str(x) for x in
                          (_safe(lambda: list(
                              getattr(r, "b_gave", None) or []), []) or [])]
                summ = str(_safe(lambda: getattr(r, "summary", ""),
                                 "") or "")
                card = QGroupBox(f"{ta} ⇄ {tb}  ·  {dt}")
                cl = QVBoxLayout(card)
                d1 = QLabel(f"{ta} sent: "
                            f"{', '.join(a_gave) if a_gave else '—'}")
                d2 = QLabel(f"{tb} sent: "
                            f"{', '.join(b_gave) if b_gave else '—'}")
                d1.setWordWrap(True)
                d2.setWordWrap(True)
                cl.addWidget(d1)
                cl.addWidget(d2)
                if summ:
                    s = QLabel(summ)
                    s.setWordWrap(True)
                    s.setStyleSheet("color: #8b95ab;")
                    cl.addWidget(s)
                self._log_layout.addWidget(card)
            except Exception:
                continue
        self._log_layout.addStretch()

    # -- deep-link --------------------------------------------------------------

    def set_teams(self, team_name, player_id, give_picks=None,
                  want_picks=None):
        """Preload a partner (from compare / draft deep-links).

        /trades?team=<name>&player=<id> (+ give_picks=/want_picks= for
        draft-day counter starting points).
        """
        target = (team_name or "").strip()
        if not target and player_id:
            target = self._team_for_player(player_id)
        if not target:
            return
        self._select_partner(target)
        if player_id and str(player_id) in {
                _pid(p) for p, _ in self._partner_players}:
            self._want_pids.add(str(player_id))
        touched = False
        for pid in (give_picks or []):
            if str(pid) in {_pid(pk) for pk in self._my_picks}:
                self._give_picks.add(str(pid))
                touched = True
        for pid in (want_picks or []):
            if str(pid) in {_pid(pk) for pk in self._partner_picks}:
                self._want_picks.add(str(pid))
                touched = True
        self._prune_terms()
        self._render_asset_lists()
        self._update_slot_labels()
        self._render_deal_chips()
        self._render_terms()
        self._schedule_evaluate()
        if touched:
            self._note_plain("Counter starting point loaded — adjust the "
                             "deal and propose.")

    def _team_for_player(self, player_id):
        league = _league(self.game)
        teams = _safe(lambda: list(getattr(league, "teams", None) or []),
                      []) or []
        for t in teams:
            players, _picks = _team_trade_lists(t)
            for p, _lvl in players:
                if _pid(p) == str(player_id):
                    return _team_name(t)
        return ""
