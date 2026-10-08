"""Fantasy draft: snake redistribution of every NHL roster.

Native port of web_ui/templates/fantasy_draft.html +
web_ui/static/js/fantasy_draft.js + the fantasy-draft routes in
web_ui/screens/inbox_actions.py (which enqueue the bridge ops
fantasy_draft_begin / fantasy_draft_pick). Calls the game object
DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Features: Begin button (only when pending_fantasy_draft), 4 tabs
(Available / My Picks / Recent / Order), search + position pills
(with the LD/RD split for defensemen), draft-clock display,
per-prospect Draft buttons (only on the user's pick). Polling: a
2s QTimer runs while the draft is active and it is NOT the user's
pick (AI picks appear live) and stops on the user's turn.

MP contract (see native_ui/MP_FANTASY_DRAFT_BUG.md): this screen is
the SINGLE-PLAYER flow. It never reads or writes
pending_fantasy_draft for MP logic -- the multiplayer screen owns
that flag for MP games.

Game methods used (all real, same as the web bridge called):
  - fantasy_draft.get_fantasy_draft_manager / fantasy_session_valid /
    FantasyDraftManager (get_current_pick, is_draft_complete,
    get_available_players, make_pick, make_ai_pick,
    assign_drafted_player, normalize_post_draft_rosters,
    audit_fantasy_draft, draft_order, draft_picks, config.rounds)
  - gm.pending_fantasy_draft, gm.checkpoint_manager, gm.league,
    gm.user_team, gm._web_fantasy_completed (completion record)
  - coach_season_meeting.on_fantasy_draft_complete
"""

from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
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


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
        v = getattr(p, "overall", None)
        if v:
            return int(v)
    except Exception:
        pass
    return 0


def _clean_pos(p):
    """Position abbreviation with the LD/RD split (web _clean_position)."""
    try:
        pos = getattr(p, "primary_position", "")
        s = str(pos or "")
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        mapping = {"CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
                   "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD",
                   "GOALIE": "G"}
        return mapping.get(s, s or "?")
    except Exception:
        return "?"


def _same_team(a, b):
    if a is None or b is None:
        return False
    if a is b:
        return True
    na = _safe(lambda: getattr(a, "team_name", None))
    nb = _safe(lambda: getattr(b, "team_name", None))
    return na is not None and na == nb


def _fmt_salary(v):
    try:
        return f"${int(v or 0):,}"
    except Exception:
        return "$0"


# ---------------------------------------------------------------------------
# fantasy-draft manager lifecycle (ported from web_ui/bridge.py;
# web bridge ops: _fantasy_draft_manager / _fantasy_draft_begin /
# _fantasy_draft_pick / _fantasy_draft_run_ai / _fantasy_draft_complete)
# ---------------------------------------------------------------------------

def _fd_module():
    try:
        import fantasy_draft as _fd
        return _fd
    except Exception:
        return None


def _get_manager(game, create=False):
    """Attach to the league-owned live FantasyDraftManager. Never raises."""
    _fd = _fd_module()
    if _fd is None:
        return None, "fantasy_draft module unavailable"
    gm = _resolve_gm(game)
    league = _safe(lambda: gm.league) if gm is not None else None
    if league is None:
        return None, "no league loaded"
    mgr = _fd.get_fantasy_draft_manager(gm)
    if mgr is not None and _fd.fantasy_session_valid(mgr, league):
        try:
            mgr.user_team = _safe(lambda: gm.user_team)
        except Exception:
            pass
        return mgr, ""
    if mgr is not None:
        return None, ("The saved fantasy draft session is damaged and "
                      "can't be resumed. No new draft was started -- your "
                      "rosters are untouched.")
    if not create:
        return None, "no live draft session"
    pending = bool(_safe(lambda: getattr(gm, "pending_fantasy_draft",
                                        False), False))
    if not pending:
        return None, ("No fantasy draft is pending. No new draft was "
                      "started -- your rosters are untouched.")
    # Pre-draft safety checkpoint BEFORE the pool collection wipes rosters.
    try:
        cpm = getattr(gm, "checkpoint_manager", None)
        if cpm is not None:
            cpm.checkpoint("Before Fantasy Draft")
    except Exception as e:
        print(f"Pre-draft checkpoint failed (non-fatal): {e}")
    nhl_teams = [t for t in
                 (_safe(lambda: list(getattr(league, "teams", None)), [])
                  or [])
                 if _safe(lambda: getattr(t, "league_name", ""), "")
                 == "National Hockey League"]
    all_players = _collect_players(nhl_teams, gm)
    mgr = _fd.FantasyDraftManager(nhl_teams, all_players)
    try:
        mgr.user_team = _safe(lambda: gm.user_team)
    except Exception:
        pass
    try:
        league.fantasy_draft_manager = mgr
    except Exception:
        pass
    return mgr, ""


def _collect_players(nhl_teams, gm):
    """Every NHL/AHL/prospect player becomes draftable."""
    all_players = []
    for team in nhl_teams or []:
        team_players = []
        for attr in ("roster", "ahl_roster", "prospects"):
            try:
                team_players.extend(list(getattr(team, attr, None) or []))
            except Exception:
                pass
        for player in team_players:
            try:
                if hasattr(player, "full_name"):
                    player.former_team = getattr(team, "team_name", "")
                    all_players.append(player)
            except Exception:
                pass
    if not all_players and gm is not None:
        try:
            league = getattr(gm, "league", None)
            if hasattr(league, "get_all_players"):
                league_players = league.get_all_players() or []
                for p in league_players:
                    try:
                        p.former_team = getattr(p, "team_name", "") or ""
                    except Exception:
                        pass
                all_players = list(league_players)
        except Exception:
            pass
    return all_players


def begin_fantasy_draft(game):
    """Clear every club's rosters and mark the draft started. Re-entry on
    a started draft never wipes rosters. Returns "" on success, else an
    error message."""
    mgr, err = _get_manager(game, create=True)
    if mgr is None:
        return err or "draft unavailable"
    try:
        gm = _resolve_gm(game)
        if gm is not None and hasattr(gm, "_web_fantasy_completed"):
            gm._web_fantasy_completed = None  # fresh draft, clear old record
    except Exception:
        pass
    if bool(getattr(mgr, "draft_started", False)):
        try:
            gm = _resolve_gm(game)
            if gm is not None and hasattr(gm, "pending_fantasy_draft"):
                gm.pending_fantasy_draft = True
        except Exception:
            pass
        return ""
    try:
        for team in getattr(mgr, "teams", None) or []:
            for attr in ("roster", "ahl_roster", "prospects"):
                try:
                    lst = getattr(team, attr, None)
                    if isinstance(lst, list):
                        lst.clear()
                    else:
                        setattr(team, attr, [])
                except Exception:
                    pass
            try:
                players = getattr(team, "players", None)
                if isinstance(players, dict):
                    for _k, v in players.items():
                        if isinstance(v, list):
                            v.clear()
                elif isinstance(players, list):
                    players.clear()
            except Exception:
                pass
        mgr.draft_started = True
    except Exception as e:
        return f"could not start draft: {e}"
    return ""


def _run_ai(mgr, max_picks=4000):
    """Run AI picks until the user's next pick or draft completion."""
    n = 0
    while n < max_picks and not mgr.is_draft_complete():
        try:
            cur = mgr.get_current_pick()
        except Exception:
            break
        if cur is None:
            break
        if _same_team(getattr(cur, "team", None),
                      getattr(mgr, "user_team", None)):
            break
        try:
            ai_pick = mgr.make_ai_pick(cur.team)
        except Exception:
            break
        if ai_pick is None:
            break
        try:
            ok = mgr.make_pick(ai_pick)
        except Exception:
            break
        if not ok:
            break
        try:
            mgr.assign_drafted_player(cur.team, ai_pick)
        except Exception:
            pass
        n += 1


def _complete_draft(game, mgr):
    """Port of FantasyDraftView.complete_draft (non-Tk parts)."""
    gm = _resolve_gm(game)
    league = _safe(lambda: gm.league) if gm is not None else None
    try:
        if gm is not None and hasattr(gm, "pending_fantasy_draft"):
            gm.pending_fantasy_draft = False
    except Exception:
        pass
    try:
        from coach_season_meeting import on_fantasy_draft_complete
        on_fantasy_draft_complete(gm)
    except Exception:
        pass
    try:
        mgr.normalize_post_draft_rosters()
    except Exception:
        pass
    # Backstop: no club skates with letters after the draft.
    try:
        for t in (getattr(league, "teams", None) or []):
            for p in (getattr(t, "roster", None) or []):
                try:
                    p.captaincy = ""
                    p.captain_tenure_years = 0
                    p.alternate_tenure_years = 0
                except Exception:
                    pass
    except Exception:
        pass
    try:
        if gm is not None:
            gm._fantasy_draft_captaincy_deferred = True
    except Exception:
        pass
    # Completion inbox message.
    try:
        from game_classes import EmailMessage
        from datetime import date as _date
        issues = []
        try:
            _fd = _fd_module()
            issues = _fd.audit_fantasy_draft(mgr, league) or []
        except Exception:
            pass
        audit_line = ""
        if issues:
            audit_line = ("\n\nLEAGUE AUDIT NOTE:\n"
                          + "\n".join(f"• {i}" for i in issues[:8])
                          + "\n")
        email = EmailMessage(
            sender="NHL Commissioner",
            sender_type="League",
            subject="🏆 Fantasy Draft Complete - Results Summary",
            content=(
                "Dear General Manager,\n\n"
                "The Fantasy Draft has been successfully completed!\n\n"
                "DRAFT RESULTS:\n"
                f"• Total players redistributed: "
                f"{len(getattr(mgr, 'all_players', None) or [])}\n"
                f"• Draft rounds completed: "
                f"{getattr(getattr(mgr, 'config', None), 'rounds', '?')}\n"
                f"• Your team's final roster has been updated\n"
                f"{audit_line}\n"
                "All players have been assigned to their new teams based on "
                "the draft results. You can now review your new roster and "
                "begin planning for the upcoming season.\n\n"
                "Thank you for participating in the Fantasy Draft!\n\n"
                "Best regards,\nNHL League Office"),
            date_sent=_date.today(),
            is_important=True,
            category="League",
            priority=3,
        )
        user_team = _safe(lambda: gm.user_team) if gm is not None else None
        inbox = _safe(lambda: getattr(user_team, "inbox", None))
        if inbox is not None:
            inbox.add_message(email)
    except Exception as e:
        print(f"Error adding completion message: {e}")
    # Draft recap (additive only): persist the full round-by-round recap
    # for the draft recap screen + inbox. Idempotent + guarded.
    try:
        from draft_recap import build_fantasy_draft_recap
        if league is not None:
            build_fantasy_draft_recap(league, mgr)
    except Exception as _e:
        print(f"Draft recap unavailable (non-fatal): {_e}")
    # Keep a completion record, then release the league-owned session.
    try:
        if gm is not None:
            gm._web_fantasy_completed = {
                "rounds": _safe(lambda: int(
                    getattr(getattr(mgr, "config", None), "rounds", 0)
                    or 0), 0),
                "total_picks": _safe(lambda: len(
                    getattr(mgr, "draft_picks", None) or []), 0),
            }
    except Exception:
        pass
    try:
        if (league is not None
                and getattr(league, "fantasy_draft_manager", None) is mgr):
            league.fantasy_draft_manager = None
    except Exception:
        pass


def make_fantasy_pick(game, player_id):
    """Human pick + AI auto-run until the next user pick. Returns ""
    on success, else an error message."""
    mgr, err = _get_manager(game, create=False)
    if mgr is None:
        return err or "no live draft session"
    try:
        cur = mgr.get_current_pick()
    except Exception:
        return "could not read draft state"
    if cur is None or mgr.is_draft_complete():
        return "the draft is already complete"
    user_team = getattr(mgr, "user_team", None)
    if user_team is None:
        try:
            user_team = _user_team(game)
            mgr.user_team = user_team
        except Exception:
            pass
    if not _same_team(getattr(cur, "team", None), user_team):
        tn = _safe(lambda: getattr(cur.team, "team_name", "?"), "?")
        return f"not your turn -- {tn} is on the clock"
    player = None
    try:
        for p in mgr.get_available_players():
            pid = _safe(lambda: getattr(p, "id", id(p)))
            if str(pid) == str(player_id):
                player = p
                break
    except Exception:
        pass
    if player is None:
        return "that player is not available"
    try:
        ok = mgr.make_pick(player)
    except Exception:
        return "pick failed"
    if not ok:
        return "pick failed"
    try:
        mgr.assign_drafted_player(cur.team, player)
    except Exception:
        pass
    _run_ai(mgr)
    if mgr.is_draft_complete():
        _complete_draft(game, mgr)
    return ""


def get_fantasy_status(game):
    """Status dict mirroring the web _fantasy_status. Never raises."""
    try:
        gm = _resolve_gm(game)
        pending = bool(_safe(lambda: getattr(gm, "pending_fantasy_draft",
                                            False), False))
        mgr, _err = _get_manager(game, create=False)
        if mgr is None:
            done_info = _safe(lambda: getattr(
                gm, "_web_fantasy_completed", None))
            if done_info:
                return {"active": False, "pending": False,
                        "started": False, "completed": True,
                        "rounds": done_info.get("rounds", 0),
                        "total_picks": done_info.get("total_picks", 0)}
            return {"active": False, "pending": pending, "started": False}
        try:
            cur = mgr.get_current_pick()
        except Exception:
            cur = None
        complete = bool(_safe(lambda: mgr.is_draft_complete(), False))
        user_team = getattr(mgr, "user_team", None) or _user_team(game)
        uname = _safe(lambda: getattr(user_team, "team_name", ""), "")
        status = {
            "active": True,
            "pending": pending,
            "started": bool(getattr(mgr, "draft_started", False)),
            "complete": complete,
            "completed": False,
            "rounds": _safe(lambda: int(getattr(
                getattr(mgr, "config", None), "rounds", 0) or 0), 0),
            "total_picks": _safe(lambda: len(
                getattr(mgr, "draft_picks", None) or []), 0),
            "picks_made": _safe(lambda: int(
                getattr(mgr, "current_pick", 0) or 0), 0),
            "user_team": uname,
        }
        if cur is not None and not complete:
            cteam = getattr(cur, "team", None)
            cname = _safe(lambda: getattr(cteam, "team_name", "?"), "?")
            status["current"] = {
                "overall": _safe(lambda: int(
                    getattr(cur, "overall_pick", 0) or 0), 0),
                "round": _safe(lambda: int(
                    getattr(cur, "round_num", 0) or 0), 0),
                "team": cname,
                "is_user_pick": _same_team(cteam, user_team),
            }
        try:
            status["draft_order"] = [
                _safe(lambda t=t: getattr(t, "team_name", "?"), "?")
                for t in (getattr(mgr, "draft_order", None) or [])]
        except Exception:
            status["draft_order"] = []
        # Available players: top 60 by overall (the real rating method).
        try:
            avail = mgr.get_available_players() or []
            scored = sorted(
                ((_player_ovr(p), p) for p in avail),
                key=lambda t: t[0], reverse=True)
            players = []
            for ovr, p in scored[:60]:
                players.append({
                    "id": _safe(lambda: str(getattr(p, "id", id(p))),
                                str(id(p))),
                    "name": _safe(lambda: getattr(p, "full_name", "?"),
                                  "?"),
                    "position": _clean_pos(p),
                    "age": _safe(lambda: int(getattr(p, "age", 0) or 0),
                                 0),
                    "overall": int(ovr),
                    "salary": _safe(lambda: int(
                        getattr(p, "salary", 0)
                        or getattr(getattr(p, "contract", None),
                                   "salary", 0) or 0), 0),
                    "former_team": _safe(lambda: getattr(
                        p, "former_team", ""), "") or "",
                })
            status["available"] = players
            status["available_count"] = len(avail)
        except Exception:
            status["available"] = []
            status["available_count"] = 0
        # Recent picks (last 12) for the draft board ticker.
        try:
            picks = getattr(mgr, "draft_picks", None) or []
            done = [pk for pk in picks
                    if _safe(lambda: getattr(pk, "player", None)) is not None]
            recent = []
            for pk in done[-12:]:
                pl = pk.player
                recent.append({
                    "overall": _safe(lambda: int(
                        getattr(pk, "overall_pick", 0) or 0), 0),
                    "team": _safe(lambda: getattr(
                        getattr(pk, "team", None), "team_name", "?"), "?"),
                    "player": _safe(lambda: getattr(pl, "full_name", "?"),
                                    "?"),
                    "ovr": _player_ovr(pl),
                })
            status["recent_picks"] = recent
            # User team's haul so far.
            status["my_picks"] = [{
                "overall": _safe(lambda: int(
                    getattr(pk, "overall_pick", 0) or 0), 0),
                "player": _safe(lambda: getattr(pk.player, "full_name",
                                                "?"), "?"),
                "ovr": _player_ovr(pk.player),
            } for pk in done
                if _safe(lambda: getattr(
                    getattr(pk, "team", None), "team_name", ""), "") == uname]
        except Exception:
            status["recent_picks"] = []
            status["my_picks"] = []
        return status
    except Exception:
        return {"active": False, "pending": False}


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

_POS_PILLS = [("", "All"), ("C", "C"), ("LW", "LW"), ("RW", "RW"),
              ("LD", "LD"), ("RD", "RD"), ("G", "G")]


class FantasyDraftScreen(BaseScreen):
    """Fantasy draft: snake redistribution of every NHL roster."""

    title = "Fantasy Draft"

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def _build_body(self):
        sub = QLabel("League Event · snake-style redistribution")
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(sub)

        # Status block (draft clock + turn state).
        self._status_wrap = QFrame()
        self._status_wrap.setObjectName("tile")
        sl = QVBoxLayout(self._status_wrap)
        sl.setSpacing(2)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #8a93a8; font-size: 12px;")
        sl.addWidget(self._count_lbl)
        self._kicker_lbl = QLabel("")
        self._kicker_lbl.setStyleSheet("color: #8a93a8; font-size: 11px; "
                                       "letter-spacing: 2px;")
        sl.addWidget(self._kicker_lbl)
        self._big_lbl = QLabel("")
        self._big_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        self._big_lbl.setWordWrap(True)
        sl.addWidget(self._big_lbl)
        self._dim_lbl = QLabel("")
        self._dim_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._dim_lbl.setWordWrap(True)
        sl.addWidget(self._dim_lbl)
        self._layout.addWidget(self._status_wrap)

        # Begin button (only when pending).
        self._begin_wrap = QWidget()
        bl = QVBoxLayout(self._begin_wrap)
        bl.setSpacing(8)
        note = QLabel("Every NHL roster will be emptied into one draft pool "
                      "and redistributed snake-style over 40 rounds. "
                      "A safety checkpoint is taken first.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        bl.addWidget(note)
        self._btn_begin = QPushButton("Begin Draft")
        self._btn_begin.setObjectName("primary-btn")
        self._btn_begin.clicked.connect(self._on_begin)
        bl.addWidget(self._btn_begin, 0, Qt.AlignLeft)
        self._layout.addWidget(self._begin_wrap)

        # Tabs.
        self._tabs = QTabWidget()
        self._tabs.setVisible(False)
        self._layout.addWidget(self._tabs, 1)

        # -- Available tab: search + position pills + board.
        avail_tab = QWidget()
        al = QVBoxLayout(avail_tab)
        al.setContentsMargins(4, 4, 4, 4)
        flt = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search players…")
        self._search.textChanged.connect(self._on_filter_changed)
        flt.addWidget(self._search, 1)
        self._pos_group = QButtonGroup(self)
        self._pos_group.setExclusive(True)
        for pos, label in _POS_PILLS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("pos", pos)
            btn.clicked.connect(self._on_filter_changed)
            self._pos_group.addButton(btn)
            flt.addWidget(btn)
        self._pos_group.buttons()[0].setChecked(True)
        al.addLayout(flt)
        self._avail_scroll = QScrollArea()
        self._avail_scroll.setWidgetResizable(True)
        self._avail_inner = QWidget()
        self._avail_list = QVBoxLayout(self._avail_inner)
        self._avail_list.setAlignment(Qt.AlignTop)
        self._avail_scroll.setWidget(self._avail_inner)
        al.addWidget(self._avail_scroll, 1)
        self._tabs.addTab(avail_tab, "Available")

        # -- My Picks tab.
        self._mypicks_inner, self._mypicks_list = self._make_list_tab()
        self._tabs.addTab(self._mypicks_inner, "My Picks")

        # -- Recent tab.
        self._recent_inner, self._recent_list = self._make_list_tab()
        self._tabs.addTab(self._recent_inner, "Recent Picks")

        # -- Order tab.
        self._order_inner, self._order_list = self._make_list_tab()
        self._tabs.addTab(self._order_inner, "Draft Order")

        # Complete-state action.
        self._btn_roster = QPushButton("Review your roster →")
        self._btn_roster.setObjectName("primary-btn")
        self._btn_roster.clicked.connect(lambda: self._navigate("roster"))
        self._btn_roster.setVisible(False)
        self._layout.addWidget(self._btn_roster)

        # Poll every 2s while the draft is active and it is NOT the
        # user's pick (AI picks stream in live); stops on the user's turn.
        self._poll = QTimer(self)
        self._poll.setInterval(2000)
        self._poll.timeout.connect(self._poll_tick)

        self._state = None

    def _make_list_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lst = QVBoxLayout(inner)
        lst.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.addWidget(scroll)
        return wrap, lst

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
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

    def _current_pos_filter(self):
        btn = self._pos_group.checkedButton()
        return btn.property("pos") if btn is not None else ""

    def _on_filter_changed(self, *_args):
        st = self._state
        if st and st.get("active"):
            cur = (st.get("current") or {}).get("is_user_pick", False)
            self._render_available(st, cur)

    def _poll_tick(self):
        try:
            self.refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # refresh / render
    # ------------------------------------------------------------------
    def refresh(self):
        self._state = get_fantasy_status(self.game)
        st = self._state
        self._poll.stop()
        self._btn_roster.setVisible(False)

        if not st.get("active"):
            self._begin_wrap.setVisible(bool(st.get("pending")))
            self._tabs.setVisible(False)
            self._count_lbl.setText("")
            if st.get("completed"):
                self._kicker_lbl.setText("DRAFT COMPLETE")
                self._big_lbl.setText(
                    f"All {st.get('total_picks', '?')} picks are in.")
                self._dim_lbl.setText("Rosters have been redistributed.")
                self._btn_roster.setVisible(True)
            elif st.get("pending"):
                self._kicker_lbl.setText("DRAFT PENDING")
                self._big_lbl.setText("Your league is ready to draft.")
                self._dim_lbl.setText(
                    "Press Begin Draft when you're ready.")
            else:
                self._kicker_lbl.setText("")
                self._big_lbl.setText("No fantasy draft is pending.")
                self._dim_lbl.setText("Start a new game with the fantasy "
                                      "draft option to run one.")
            return

        if not st.get("started"):
            self._begin_wrap.setVisible(True)
            self._tabs.setVisible(False)
            self._count_lbl.setText("")
            self._kicker_lbl.setText("DRAFT PENDING")
            self._big_lbl.setText("Ready when you are.")
            self._dim_lbl.setText("")
            return

        if st.get("complete"):
            self._begin_wrap.setVisible(False)
            self._tabs.setVisible(False)
            self._count_lbl.setText("")
            self._kicker_lbl.setText("DRAFT COMPLETE")
            self._big_lbl.setText(
                f"All {st.get('total_picks', '?')} picks are in.")
            self._dim_lbl.setText("Rosters have been redistributed.")
            self._btn_roster.setVisible(True)
            return

        # Active draft.
        self._begin_wrap.setVisible(False)
        self._tabs.setVisible(True)
        cur = st.get("current") or {}
        mine = bool(cur.get("is_user_pick"))
        self._count_lbl.setText(
            f"Pick {cur.get('overall', '?')} of {st.get('total_picks', '?')} "
            f"· Round {cur.get('round', '?')}")
        self._kicker_lbl.setText("YOUR TURN" if mine else "ON THE CLOCK")
        self._big_lbl.setText(
            f"Pick #{cur.get('overall', '?')}: {cur.get('team', '')} "
            + ("— you are up!" if mine else "selecting…"))
        self._dim_lbl.setText(
            f"{st.get('picks_made', 0)} of {st.get('total_picks', 0)} "
            f"picks made · {st.get('available_count', 0)} players in the pool")

        self._render_available(st, mine)
        self._render_mypicks(st)
        self._render_recent(st)
        self._render_order(st)

        # While the AI chain runs (not your pick), keep polling until
        # it's your turn again or the draft completes.
        if not mine:
            self._poll.start()

    # -- tab renderers ---------------------------------------------------
    def _player_row(self, name, sub, ovr, extra=None, pid=None,
                    can_pick=False):
        frame = QFrame()
        frame.setObjectName("tile")
        h = QHBoxLayout(frame)
        h.setSpacing(12)
        main = QVBoxLayout()
        nm = QLabel(name)
        nm.setStyleSheet("font-weight: bold; font-size: 14px;")
        nm.setWordWrap(True)
        main.addWidget(nm)
        if sub:
            sb = QLabel(sub)
            sb.setStyleSheet("color: #8a93a8; font-size: 12px;")
            sb.setWordWrap(True)
            main.addWidget(sb)
        h.addLayout(main, 1)
        ov = QLabel(f"{ovr}\novr")
        ov.setAlignment(Qt.AlignCenter)
        ov.setStyleSheet("font-weight: bold; font-size: 14px;")
        h.addWidget(ov)
        if extra:
            ex = QLabel(extra)
            ex.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            h.addWidget(ex)
        if can_pick and pid is not None:
            btn = QPushButton("Draft")
            btn.setObjectName("primary-btn")
            btn.clicked.connect(lambda _=False, _pid=pid:
                                self._on_draft(_pid))
            h.addWidget(btn)
        return frame

    def _empty_note(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8a93a8; font-size: 13px;")
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _render_available(self, st, mine):
        self._clear(self._avail_list)
        q = self._search.text().strip().lower()
        pos = self._current_pos_filter()
        shown = 0
        for p in (st.get("available") or []):
            if pos and p.get("position") != pos:
                continue
            if q and q not in (p.get("name") or "").lower():
                continue
            sub = (f"{p.get('position')} · Age {p.get('age')} · "
                   f"{p.get('former_team')}")
            row = self._player_row(p.get("name"), sub, p.get("overall"),
                                   _fmt_salary(p.get("salary")),
                                   pid=p.get("id"), can_pick=mine)
            self._avail_list.addWidget(row)
            shown += 1
        if not shown:
            self._avail_list.addWidget(self._empty_note("No players match."))

    def _render_mypicks(self, st):
        self._clear(self._mypicks_list)
        mine = st.get("my_picks") or []
        if not mine:
            self._mypicks_list.addWidget(self._empty_note("No picks yet."))
            return
        for p in mine:
            self._mypicks_list.addWidget(self._player_row(
                f"#{p.get('overall')} — {p.get('player')}", "", p.get("ovr")))

    def _render_recent(self, st):
        self._clear(self._recent_list)
        recent = list(reversed(st.get("recent_picks") or []))
        if not recent:
            self._recent_list.addWidget(self._empty_note("No picks yet."))
            return
        for p in recent:
            self._recent_list.addWidget(self._player_row(
                f"#{p.get('overall')} — {p.get('player')}",
                str(p.get("team") or ""), p.get("ovr")))

    def _render_order(self, st):
        self._clear(self._order_list)
        order = st.get("draft_order") or []
        if not order:
            self._order_list.addWidget(self._empty_note("—"))
            return
        for i, t in enumerate(order, 1):
            self._order_list.addWidget(self._player_row(f"{i}. {t}", "",
                                                       ""))

    # -- actions ----------------------------------------------------------
    def _on_begin(self):
        confirm = QMessageBox.question(
            self, "Begin fantasy draft",
            "Begin the fantasy draft? Every NHL roster will be emptied "
            "into one draft pool (a safety checkpoint is taken first).",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self._btn_begin.setEnabled(False)
        self._btn_begin.setText("Starting…")
        err = begin_fantasy_draft(self.game)
        self._btn_begin.setEnabled(True)
        self._btn_begin.setText("Begin Draft")
        if err:
            QMessageBox.warning(self, "Draft failed", str(err))
        self.refresh()
        # Start polling (AI picks may need to run before the user's turn).
        st = self._state or {}
        cur = (st.get("current") or {}).get("is_user_pick", False)
        if st.get("active") and not cur and not st.get("complete"):
            self._poll.start()

    def _on_draft(self, pid):
        err = make_fantasy_pick(self.game, pid)
        if err:
            QMessageBox.warning(self, "Pick failed", str(err))
        self.refresh()
