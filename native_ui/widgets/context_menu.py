"""Reusable context menu for players, teams, and staff.

Ports web_ui/static/js/context_menu.js plus the mainline extras from
player_context_menu.py (training focus, dev history, physio report,
trade-value breakdown, recently-viewed tracking, shortlist, scout
assignment). Right-click on any entity shows an NHL 14-styled menu.
Supports Caleb's "everything should be clickable" standard.
"""
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QTextEdit,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction


# ---------------------------------------------------------------------------
# Recently-viewed tracking (mainline parity: player_context_menu.py)
#
# Recorded when a profile is opened from this menu (mainline records on
# player-card open via the open_player_profile hook; native's profile
# screen lives in another file, so the hook point we own is the context
# menu's View Profile path). Capped, most-recent-first, persisted on the
# game manager so it survives save/load (game_manager owns save state).
# ---------------------------------------------------------------------------
RECENTLY_VIEWED_CAP = 15


def _resolve_gm(game):
    """Game manager (save owner) or the game object itself."""
    try:
        return getattr(game, "game_manager", None) or game
    except Exception:
        return game


def record_recently_viewed(game, player):
    """Record a profile view for the comparison/shortlist tooling.

    Additive; never raises. Mirrors mainline record_recently_viewed.
    """
    try:
        pid = getattr(player, "id", None)
        if not pid:
            return
        gm = _resolve_gm(game)
        seen = getattr(gm, "recently_viewed_players", None)
        if not isinstance(seen, list):
            seen = []
        seen = [x for x in seen if x != pid]
        seen.insert(0, pid)
        gm.recently_viewed_players = seen[:RECENTLY_VIEWED_CAP]
    except Exception:
        pass


def get_recently_viewed_players(game, exclude=None):
    """Resolve recently-viewed IDs to player objects, most-recent first.

    IDs that no longer resolve (traded away, retired) are skipped.
    Mirrors mainline get_recently_viewed_players. Never raises.
    """
    try:
        gm = _resolve_gm(game)
        ids = list(getattr(gm, "recently_viewed_players", None) or [])
        if not ids:
            return []
        league = getattr(gm, "league", None)
        by_id = {}
        try:
            pool = (list(league.get_all_players())
                    if hasattr(league, "get_all_players") else [])
        except Exception:
            pool = []
        if not pool:
            for t in (getattr(league, "teams", None) or []):
                for attr in ("roster", "ahl_roster", "prospects"):
                    pool.extend(getattr(t, attr, None) or [])
        for p in pool:
            _pid = getattr(p, "id", None)
            if _pid is not None and _pid not in by_id:
                by_id[_pid] = p
        excl_id = getattr(exclude, "id", None)
        out = []
        for _pid in ids:
            p = by_id.get(_pid)
            if p is None or _pid == excl_id:
                continue
            out.append(p)
        return out
    except Exception:
        return []


class EntityContextMenu(QMenu):
    """Right-click menu for game entities."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self.setStyleSheet("""
            QMenu {
                background-color: #0d1320;
                border: 1px solid #2a3550;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                color: #e8edf5;
                font-size: 13px;
                padding: 8px 24px 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1e3a5f;
            }
            QMenu::separator {
                height: 1px;
                background: #2a3550;
                margin: 4px 8px;
            }
        """)

    def add_action(self, label, callback, danger=False):
        action = QAction(label, self)
        if danger:
            action.setProperty("danger", True)
        action.triggered.connect(callback)
        self.addAction(action)
        return action

    @staticmethod
    def player_menu(main_window, player, is_user_team=False):
        """Build the player context menu (15+ items in main)."""
        menu = EntityContextMenu(main_window)
        game = main_window.game

        menu.add_action("View Profile",
                        lambda: EntityContextMenu._view_profile(
                            main_window, player))
        menu.add_action("Scout Player",
                        lambda p=player: EntityContextMenu._scout_player(
                            main_window, p))
        menu.add_action("Physio Report",
                        lambda p=player: EntityContextMenu._physio_report(
                            main_window, p))
        menu.add_action("Add to Shortlist",
                        lambda p=player: EntityContextMenu._add_to_shortlist(
                            main_window, p))
        menu.add_action("Compare",
                        lambda p=player: EntityContextMenu._open_compare(
                            main_window, p))
        menu.addMenu(
            EntityContextMenu._recently_viewed_submenu(main_window, player))
        menu.addSeparator()
        menu.add_action("Assign Training Focus",
                        lambda p=player: EntityContextMenu._assign_training_focus(
                            main_window, p))
        menu.add_action("View Development History",
                        lambda p=player: EntityContextMenu._view_development_history(
                            main_window, p))
        menu.addSeparator()
        menu.add_action("Propose Trade",
                        lambda p=player: EntityContextMenu._open_trade_proposal(
                            main_window, player=p))
        menu.add_action("Analyze Trade Value",
                        lambda p=player: EntityContextMenu._analyze_trade_value(
                            main_window, p))

        if is_user_team:
            menu.addSeparator()
            menu.add_action("Edit Lines",
                            lambda: main_window.show_screen("lines"))
            menu.add_action("Add to Trade Block",
                            lambda: EntityContextMenu._add_trade_block(
                                main_window, game, player))
            menu.add_action("Sign Extension",
                            lambda p=player: EntityContextMenu._open_contracts(
                                main_window, p))
            # IR place/activate (ir_system.py) -- mirrors mainline
            # player_context_menu._ir_place/_ir_activate.
            try:
                import ir_system as _irs
                _ir_status = _irs.ir_status_of(player)
            except Exception:
                _ir_status = "None"
            if _ir_status in ("IR", "LTIR"):
                menu.add_action(
                    f"Activate from {_ir_status}",
                    lambda p=player: EntityContextMenu._ir_activate(
                        main_window, p))
            else:
                menu.add_action(
                    "Place on IR",
                    lambda p=player: EntityContextMenu._ir_place(
                        main_window, p, "IR"))
                menu.add_action(
                    "Place on LTIR",
                    lambda p=player: EntityContextMenu._ir_place(
                        main_window, p, "LTIR"))
            menu.addSeparator()
            menu.add_action("Place on Waivers",
                            lambda: EntityContextMenu._open_waivers(
                                main_window, player),
                            danger=True)
        return menu

    @staticmethod
    def team_menu(main_window, team_name):
        """Build the team context menu."""
        menu = EntityContextMenu(main_window)
        menu.add_action("Team Overview",
                        lambda: main_window.open_team(team_name))
        menu.add_action("Propose Trade",
                        lambda: EntityContextMenu._open_trade_proposal(
                            main_window, team_name=team_name))
        return menu

    @staticmethod
    def staff_menu(main_window, staff):
        """Build the staff context menu."""
        menu = EntityContextMenu(main_window)
        menu.add_action("View Details",
                        lambda s=staff: EntityContextMenu._open_staff_detail(
                            main_window, s))
        menu.add_action("Release",
                        lambda: EntityContextMenu._release_staff(
                            main_window, staff),
                        danger=True)
        return menu

    @staticmethod
    def _open_entity_screen(main_window, screen_name, setter_name, entity,
                            friendly_name="screen"):
        """Navigate to a screen and load an entity via its setter.

        Raises RuntimeError if the screen cannot load the entity so the
        caller can show an actionable error instead of failing silently.
        """
        main_window.show_screen(screen_name)
        screen = main_window._screens.get(screen_name)
        widget = screen.widget() if screen and hasattr(screen, "widget") else screen
        setter = getattr(widget, setter_name, None) if widget else None
        if callable(setter):
            setter(entity)
        else:
            raise RuntimeError(
                f"The {friendly_name} could not load the selected item "
                f"({screen_name} has no {setter_name}).")

    @staticmethod
    def _open_compare(main_window, player):
        """Open compare screen with the player pre-loaded."""
        try:
            EntityContextMenu._open_entity_screen(
                main_window, "compare", "set_players", [player],
                friendly_name="compare screen")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Could not open compare",
                f"The compare screen could not load this player: {exc}")

    @staticmethod
    def _open_contracts(main_window, player):
        """Open contracts screen with the player pre-loaded."""
        try:
            EntityContextMenu._open_entity_screen(
                main_window, "contracts", "set_player", player,
                friendly_name="contracts screen")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Could not open contracts",
                f"The contracts screen could not load this player: {exc}")

    @staticmethod
    def _open_trade_proposal(main_window, player=None, team_name=None):
        """Open the trade screen preloaded with a player or team.

        Uses the screen's set_teams deep-link so the clicked entity is
        preselected instead of forcing the user to find it again.

        Own-team guard (verification-audit MISSING item): a player on
        the user's own club is placed on the GIVE side of the trade --
        never set as the partner / wanted asset, which would build an
        invalid trade against your own team. The same applies when the
        menu is opened on the user's own team: no partner is
        preselected, since trading with yourself is not possible.
        """
        try:
            main_window.show_screen("trades")
            screen = main_window._screens.get("trades")
            widget = (screen.widget() if screen and hasattr(screen, "widget")
                      else screen)
            setter = getattr(widget, "set_teams", None) if widget else None
            if not callable(setter):
                raise RuntimeError("trade screen has no set_teams deep-link")

            game = getattr(main_window, "game", None)
            user_team = getattr(game, "user_team", None) if game else None
            user_team_name = str(
                getattr(user_team, "team_name", "") or "").strip()

            def _is_own_team(name):
                return bool(name) and str(name).strip() == user_team_name \
                    and bool(user_team_name)

            if player is not None:
                player_team = str(
                    getattr(player, "team_name", "") or "").strip()
                pid = str(getattr(player, "id", "") or "")
                if not player_team or player_team == "Free Agent":
                    name = (getattr(player, "full_name", None)
                            or getattr(player, "name", None)
                            or "This player")
                    QMessageBox.warning(
                        main_window, "Cannot trade",
                        f"{name} isn't on a team roster (unsigned or free "
                        "agent). Trades can only involve players under "
                        "contract with a club -- pick a player on a team's "
                        "roster instead.")
                    return
                if _is_own_team(player_team):
                    # Own-team player: never the partner/wanted side.
                    # Stage on the give side through the screen's public
                    # deep-link API (B NEW-2) -- one canonical pipeline,
                    # never raises; a missed stage is cosmetic, not an
                    # error. Convention matches draft_central (1cbc6fc).
                    fn = getattr(widget, "preload_give_asset", None)
                    if callable(fn):
                        try:
                            fn(player)
                        except Exception:
                            pass
                    return
                setter(team_name or "", pid or "")
            else:
                if _is_own_team(team_name):
                    # Own club can't be the trade partner -- leave the
                    # partner selector empty so the user picks a real team.
                    return
                setter(team_name or "", "")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Could not open trade proposal",
                f"The trade screen could not preload this selection: {exc}")

    @staticmethod
    def _open_staff_detail(main_window, staff):
        """Open staff detail screen with the staff pre-loaded."""
        try:
            EntityContextMenu._open_entity_screen(
                main_window, "staff_detail", "set_staff", staff,
                friendly_name="staff detail screen")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Could not open staff details",
                f"The staff screen could not load this staff member: {exc}")

    @staticmethod
    def _add_trade_block(main_window, game, player):
        """Primary path: open the TradeBlockScreen so the user gets the
        full trade-block workflow (shop, value, offers, interest).

        The player is added through the screen's own _block_add helper --
        the exact code path the screen's 'Add Players' dialog uses
        (pid-deduped, pool-validated) -- so the screen opens with the
        player already on the block. The verify-and-repair below covers
        a latent bug in that helper: `block = getattr(...) or []`
        rebinds to a throwaway list when the block starts empty, so the
        add is silently dropped. Not our file to fix; flagged for the
        owning team. Navigation always happens regardless.
        """
        try:
            from ..screens.trade_block import _block_add, _pid, _user_team
            pid = _pid(player)
            _block_add(game, [pid])
            block = getattr(game, "trade_block", None)
            if not isinstance(block, list):
                try:
                    game.trade_block = block = []
                except Exception:
                    block = []
            if all(_pid(p) != pid for p in block):
                # Repair for _block_add's empty-block rebind bug
                # (flagged for the owning team): pool-validated,
                # pid-deduped append so the add actually lands.
                pool = []
                for lst in ("roster", "ahl_roster", "prospects"):
                    try:
                        pool.extend(list(getattr(
                            _user_team(game), lst, None) or []))
                    except Exception:
                        pass
                target = next((p for p in pool if _pid(p) == pid), None)
                if target is not None:
                    block.append(target)
        except Exception as e:
            print(f"[ctx] trade block add failed: {e}")
        main_window.show_screen("trade_block")

    @staticmethod
    def _open_waivers(main_window, player):
        """Open the WaiversScreen instead of mutating the waiver list
        directly. The screen owns the real workflow: eligibility,
        NMC blocks, waiver-exempt demote-vs-waive, the 2-day wire, and
        news -- a confirm dialog here would bypass all of it.

        Preselect: WaiversScreen has no set_player; the player appears
        in its 'Place on waivers' section with Waive/Demote actions.
        """
        main_window.show_screen("waivers")
        screen = main_window._screens.get("waivers")
        if screen:
            widget = screen.widget() if hasattr(screen, "widget") else screen
            if hasattr(widget, "set_player"):
                try:
                    widget.set_player(player)
                except Exception:
                    pass

    @staticmethod
    def _ir_place(main_window, player, kind):
        """Place a player on IR/LTIR via ir_system. Never raises.

        Mirrors mainline player_context_menu._ir_place: calls
        ir_system.place_on_ir / place_on_ltir, shows the result,
        and refreshes the roster view.
        """
        from PySide6.QtWidgets import QMessageBox
        try:
            game = getattr(main_window, "game", None)
            team = getattr(game, "user_team", None) if game else None
            if team is None:
                QMessageBox.warning(main_window, "Injured Reserve",
                                    "No team loaded.")
                return
            import ir_system as _irs
            today = getattr(game, "current_date", None)
            if kind == "LTIR":
                ok, reason = _irs.place_on_ltir(team, player, today)
            else:
                ok, reason = _irs.place_on_ir(team, player, today)
            name = getattr(player, "full_name", "?")
            if ok:
                try:
                    _relief = _irs.ltir_relief(team) if kind == "LTIR" else 0
                    _extra = (f" Cap relief pool is now ${_relief:,}, "
                              f"raising your effective ceiling."
                              if kind == "LTIR" else
                              " He still counts against the cap, but not "
                              "the 23-man roster.")
                    QMessageBox.information(
                        main_window, "Injured Reserve",
                        f"{name} placed on {kind}.{_extra}")
                except Exception:
                    pass
                # News it.
                try:
                    if hasattr(game, "add_news"):
                        game.add_news(
                            f"{name} placed on {kind}."
                            if kind == "IR" else
                            f"{name} placed on LTIR -- cap relief activated.")
                except Exception:
                    pass
            else:
                QMessageBox.warning(main_window, "Injured Reserve",
                                    reason or f"Could not place on {kind}.")
            # Refresh the roster view.
            try:
                screen = main_window._screens.get("roster")
                if screen:
                    widget = (screen.widget()
                              if hasattr(screen, "widget") else screen)
                    if hasattr(widget, "refresh"):
                        widget.refresh()
            except Exception:
                pass
        except Exception as e:
            print(f"[ctx] IR place failed: {e}")

    @staticmethod
    def _ir_activate(main_window, player):
        """Activate a player off IR/LTIR via ir_system. Never raises.

        Mirrors mainline player_context_menu._ir_activate.
        """
        from PySide6.QtWidgets import QMessageBox
        try:
            game = getattr(main_window, "game", None)
            team = getattr(game, "user_team", None) if game else None
            if team is None:
                QMessageBox.warning(main_window, "Injured Reserve",
                                    "No team loaded.")
                return
            import ir_system as _irs
            today = getattr(game, "current_date", None)
            ok, reason = _irs.activate_player(team, player, today)
            name = getattr(player, "full_name", "?")
            if ok:
                QMessageBox.information(main_window, "Injured Reserve",
                                        f"{name} activated.")
            else:
                QMessageBox.warning(main_window, "Injured Reserve",
                                    reason or "Could not activate.")
            try:
                screen = main_window._screens.get("roster")
                if screen:
                    widget = (screen.widget()
                              if hasattr(screen, "widget") else screen)
                    if hasattr(widget, "refresh"):
                        widget.refresh()
            except Exception:
                pass
        except Exception as e:
            print(f"[ctx] IR activate failed: {e}")

    # ------------------------------------------------------------------
    # D-18 mainline extras (ported from player_context_menu.py)
    # ------------------------------------------------------------------
    @staticmethod
    def _view_profile(main_window, player):
        """Open the profile and record the view for recently-viewed.

        Mirrors mainline: player-card opens feed the recently-viewed
        list (capped, most-recent-first, persisted on the game manager).
        """
        try:
            record_recently_viewed(getattr(main_window, "game", None), player)
        except Exception:
            pass
        try:
            main_window.show_player(player)
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Could not open profile",
                f"The player profile could not be opened: {exc}")

    @staticmethod
    def _recently_viewed_submenu(main_window, player):
        """'Recently Viewed' submenu: shows tracked players, most-recent
        first; picking one opens their profile (which re-records the
        view). Skips IDs that no longer resolve."""
        game = getattr(main_window, "game", None)
        sub = QMenu("Recently Viewed", main_window)
        try:
            recent = get_recently_viewed_players(game, exclude=player)
        except Exception:
            recent = []
        if not recent:
            act = QAction("(none yet)", sub)
            act.setEnabled(False)
            sub.addAction(act)
        else:
            for p in recent:
                name = getattr(p, "full_name", None) or "?"
                pos, ovr = "", ""
                try:
                    pos = str(getattr(p.primary_position, "value", "") or "")
                    ovr = f" ({int(p.overall_rating())})"
                except Exception:
                    pass
                act = QAction(f"{name}{ovr}" + (f" - {pos}" if pos else ""),
                              sub)
                act.triggered.connect(
                    lambda _checked=False, pl=p:
                    EntityContextMenu._view_profile(main_window, pl))
                sub.addAction(act)
        return sub

    @staticmethod
    def _scouts_of_team(game):
        """Staff with a scout role on the user's team (native vocabulary,
        same filter the Scouting screen's AssignDialog uses)."""
        try:
            gm = _resolve_gm(game)
            team = getattr(gm, "user_team", None) or getattr(
                game, "user_team", None)
            out = []
            for s in (getattr(team, "staff", None) or []):
                role = str(getattr(getattr(s, "role", None), "value",
                                   getattr(s, "role", "") or ""))
                if "scout" in role.lower():
                    out.append(s)
            return out
        except Exception:
            return []

    @staticmethod
    def _scout_player(main_window, player):
        """Scout entry: if a report exists on the user club, show it
        (mainline _scout_player); otherwise open the scout-assignment
        dialog so the user picks a scout -- the write goes to
        game.scouting_assignments[player] = scout, the exact path the
        Scouting screen's 'New Assignment' uses."""
        game = getattr(main_window, "game", None)
        pid = getattr(player, "id", None)
        try:
            gm = _resolve_gm(game)
            team = getattr(gm, "user_team", None) or getattr(
                game, "user_team", None)
            reports = getattr(team, "scouting_reports", None) or {}
            report = reports.get(pid)
        except Exception:
            report = None
        if report is not None:
            try:
                scout = getattr(report, "scout", None)
                acc = getattr(scout, "jpa", 75) if scout is not None else 75
                QMessageBox.information(
                    main_window, "Existing Scouting Report",
                    f"Scout Report: {getattr(player, 'full_name', '?')}\n\n"
                    f"Scout: {getattr(scout, 'full_name', 'Unknown')}\n"
                    f"Accuracy: {acc}%\n"
                    f"Viewings: {getattr(report, 'viewings', 1)}\n"
                    f"Potential: {getattr(report, 'scouted_potential', 'Unknown')}\n\n"
                    f"Status: {'Complete' if getattr(report, 'viewings', 1) >= 3 else 'In Progress'}")
            except Exception:
                pass
            return
        scouts = EntityContextMenu._scouts_of_team(game)
        if not scouts:
            QMessageBox.warning(
                main_window, "No Scouts",
                "Your club has no scouts on staff.\n"
                "Hire scouts from the Staff screen first.")
            return
        dlg = QDialog(main_window)
        dlg.setWindowTitle(f"Scout Assignment - {getattr(player, 'full_name', '?')}")
        dlg.setMinimumWidth(420)
        lay = QFormLayout(dlg)
        combo = QComboBox(dlg)
        for s in scouts:
            jpa = getattr(s, "jpa", None)
            label = getattr(s, "full_name", "?")
            if jpa is not None:
                label += f" (JPA: {jpa})"
            combo.addItem(label, s)
        lay.addRow("Scout:", combo)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        scout = combo.currentData()
        if scout is None:
            return
        # Same write the Scouting screen performs (dict player -> scout),
        # with the module-function fallback the screen uses when the
        # dict is absent.
        try:
            assignments = getattr(game, "scouting_assignments", None)
            if assignments is not None:
                assignments[player] = scout
            else:
                import scouting as _sm
                if hasattr(_sm, "apply_player_assignment"):
                    _sm.apply_player_assignment(
                        game, getattr(player, "id", None),
                        getattr(scout, "id", None))
            QMessageBox.information(
                main_window, "Scout Assigned",
                f"{getattr(scout, 'full_name', '?')} assigned to scout "
                f"{getattr(player, 'full_name', '?')}.")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Assignment Failed",
                f"Could not create the scouting assignment: {exc}")

    @staticmethod
    def _physio_report(main_window, player):
        """Physio/fitness report for the player. Ports mainline
        PhysioReportView content verbatim (injury status + fitness words);
        read-only."""
        def _word(v):
            try:
                v = float(v)
            except Exception:
                return "Unknown"
            if v >= 40:
                return "Excellent"
            if v >= 34:
                return "Good"
            if v >= 27:
                return "Average"
            if v >= 20:
                return "Below average"
            return "Poor"

        injured = bool(getattr(player, "is_injured", False))
        rows = [
            ("Status", "INJURED" if injured else "Fit to play"),
            ("Injury", str(getattr(player, "injury_type", "None") or "None")),
            ("Est. games out",
             str(getattr(player, "games_remaining_injured", 0) or 0)
             if injured else "--"),
            ("Last injury", str(getattr(player, "last_injury", "None") or "None")),
            ("Career games missed",
             str(getattr(player, "career_games_missed", 0))),
            ("Days missed (season)", str(getattr(player, "days_missed", 0))),
            ("Durability", _word(getattr(player, "durability", 30))),
            ("Injury proneness",
             _word(50 - (getattr(player, "injury_proneness", 10) or 0))),
            ("Stamina", _word(getattr(player, "stamina", 30))),
        ]
        note = ""
        if injured:
            note = ("Follow the medical team's timeline -- rushing him back "
                    "risks re-injury.")
        elif (getattr(player, "injury_proneness", 0) or 0) > 12:
            note = ("Injury-prone: consider managing his minutes in "
                    "back-to-backs.")
        dlg = QDialog(main_window)
        dlg.setWindowTitle(f"Physio Report - {getattr(player, 'full_name', '?')}")
        dlg.setMinimumWidth(440)
        lay = QVBoxLayout(dlg)
        title = QLabel(f"Physio Report — {getattr(player, 'full_name', '?')}")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        grid = QGridLayout()
        for i, (k, v) in enumerate(rows):
            kl, vl = QLabel(k), QLabel(str(v))
            vl.setAlignment(Qt.AlignRight)
            vf = vl.font()
            vf.setBold(True)
            vl.setFont(vf)
            grid.addWidget(kl, i, 0)
            grid.addWidget(vl, i, 1)
        lay.addLayout(grid)
        if note:
            nl = QLabel(note)
            nl.setWordWrap(True)
            nl.setStyleSheet("color: #a1a1aa;")
            lay.addWidget(nl)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    @staticmethod
    def _shortlist_manager(game):
        """Build the ShortlistManager exactly the way the Shortlist
        screen's _manager() does (same per-save storage key)."""
        try:
            import shortlist_system as _ss
            gm = _resolve_gm(game)
            save_key = None
            try:
                import trade_market as _tm
                league = getattr(gm, "league", None)
                if league is not None and hasattr(_tm, "league_shortlist_key"):
                    save_key = _tm.league_shortlist_key(league)
            except Exception:
                pass
            return _ss.ShortlistManager(save_key=save_key)
        except Exception:
            return None

    @staticmethod
    def _add_to_shortlist(main_window, player):
        """Add the player to the shortlist with category / priority /
        notes. Ports mainline _add_to_shortlist; the entry is written
        through the real ShortlistManager (same as the Shortlist screen)
        and saved."""
        try:
            from ..screens.shortlist import CATEGORIES
        except Exception:
            CATEGORIES = ["Trade Targets", "Free Agent Targets",
                          "Draft Prospects", "Future Prospects",
                          "Development Watch", "Injury Replacements",
                          "Custom"]
        game = getattr(main_window, "game", None)
        dlg = QDialog(main_window)
        dlg.setWindowTitle(f"Add to Shortlist - {getattr(player, 'full_name', '?')}")
        dlg.setMinimumWidth(420)
        lay = QFormLayout(dlg)
        name = QLabel(getattr(player, "full_name", "?"))
        nf = name.font()
        nf.setBold(True)
        name.setFont(nf)
        lay.addRow("Player:", name)
        cat = QComboBox(dlg)
        cat.addItems(CATEGORIES)
        lay.addRow("Category:", cat)
        prio = QComboBox(dlg)
        prio.addItems(["High Priority", "Medium Priority", "Low Priority"])
        lay.addRow("Priority:", prio)
        notes = QTextEdit(dlg)
        notes.setMaximumHeight(80)
        notes.setPlaceholderText("Notes (optional)...")
        lay.addRow("Notes:", notes)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        prio_map = {"High Priority": 1, "Medium Priority": 2, "Low Priority": 3}
        try:
            mgr = EntityContextMenu._shortlist_manager(game)
            if mgr is None:
                raise RuntimeError("shortlist system unavailable")
            import shortlist_system as _ss
            e = _ss.ShortlistEntry(
                player_id=str(getattr(player, "id", "")),
                player_name=getattr(player, "full_name", "?"),
                category=cat.currentText(),
                priority=prio_map.get(prio.currentText(), 2),
                notes=notes.toPlainText().strip(),
            )
            mgr.entries.append(e)
            mgr.save_shortlist()
            QMessageBox.information(
                main_window, "Shortlist",
                f"{getattr(player, 'full_name', '?')} added to the "
                f"shortlist ({cat.currentText()}).")
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Shortlist",
                f"Failed to add to shortlist: {exc}")

    @staticmethod
    def _assign_training_focus(main_window, player):
        """Assign a training focus + intensity to the player. Ports
        mainline's training dialog and runs the same write path as the
        Development screen's 'Assign Training Program': gated by
        engine.can_practice, records to ACTIVE_TRAINING_PROGRAMS +
        gm.training_programs, runs a real first session immediately."""
        from datetime import date as _date
        try:
            from ..screens.development import DevelopmentScreen as _Dev
            focuses = list(getattr(_Dev, "DEV_FOCUSES", None) or [])
            intensities = list(getattr(_Dev, "DEV_INTENSITIES", None) or [])
        except Exception:
            focuses, intensities = [], []
        if not focuses:
            focuses = ["Skating & Speed", "Shooting Accuracy",
                       "Passing & Vision", "Defensive Positioning",
                       "Physical Conditioning", "Mental Toughness",
                       "Position-Specific Skills", "Hockey IQ Development"]
        if not intensities:
            intensities = ["Light", "Standard", "Intensive"]
        try:
            from enhanced_practice_system import (
                FOCUS_TO_PRACTICE_TYPE, INTENSITY_LABEL_TO_ENUM,
                PracticeEngine, ACTIVE_TRAINING_PROGRAMS)
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Training Unavailable",
                f"The training system isn't available: {exc}")
            return

        dlg = QDialog(main_window)
        dlg.setWindowTitle(
            f"Training Assignment - {getattr(player, 'full_name', '?')}")
        dlg.setMinimumWidth(420)
        lay = QFormLayout(dlg)
        focus_combo = QComboBox(dlg)
        focus_combo.addItems(focuses)
        lay.addRow("Training Focus:", focus_combo)
        int_grp = QGroupBox("Intensity")
        irow = QHBoxLayout(int_grp)
        int_btns = QButtonGroup(dlg)
        for i, iv in enumerate(intensities):
            rb = QRadioButton(iv)
            if iv == "Standard" or (i == 0 and "Standard" not in intensities):
                rb.setChecked(True)
            int_btns.addButton(rb, i)
            irow.addWidget(rb)
        lay.addRow(int_grp)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        focus = focus_combo.currentText()
        checked = int_btns.checkedId()
        intensity_label = intensities[checked] if checked >= 0 else intensities[0]
        ptype = FOCUS_TO_PRACTICE_TYPE.get(focus)
        pint = INTENSITY_LABEL_TO_ENUM.get(intensity_label)
        if ptype is None or pint is None:
            QMessageBox.warning(
                main_window, "Unknown Selection",
                f"No training program for '{focus}' / '{intensity_label}'.")
            return
        game = getattr(main_window, "game", None)
        engine = PracticeEngine()
        try:
            can, why = engine.can_practice(player, ptype, pint)
        except Exception as exc:
            QMessageBox.warning(
                main_window, "Cannot Assign", f"Eligibility check failed: {exc}")
            return
        if not can:
            QMessageBox.warning(main_window, "Cannot Train Right Now", str(why))
            return
        prog = {
            "focus": focus,
            "intensity": intensity_label,
            "assigned": getattr(game, "current_date", None) or _date.today(),
            "player_name": getattr(player, "full_name", "?"),
        }
        try:
            pkey = getattr(player, "id", None)
            ACTIVE_TRAINING_PROGRAMS[pkey] = prog
            gm = _resolve_gm(game)
            if gm is not None:
                if not getattr(gm, "training_programs", None):
                    gm.training_programs = {}
                gm.training_programs[pkey] = prog
        except Exception:
            pass
        try:
            session = engine.execute_practice(player, ptype, pint, 60, 12)
            result = (f"{getattr(player, 'full_name', '?')} assigned to "
                      f"{intensity_label.lower()} {focus.lower()} training.\n\n"
                      f"First session complete: +{session.skill_gain:.2f} skill, "
                      f"+{session.fatigue_cost}% fatigue.")
        except Exception:
            result = (f"{getattr(player, 'full_name', '?')} assigned to "
                      f"{intensity_label.lower()} {focus.lower()} training.\n\n"
                      f"The program is recorded; the first session will run "
                      f"at the next practice.")
        QMessageBox.information(main_window, "Training Assigned", result)

    @staticmethod
    def _view_development_history(main_window, player):
        """Show the player's development history -- built only from real
        stores (mainline _view_development_history): the training
        registry (current program) and the practice engine's per-player
        session history. No-history players get an honest empty state."""
        pid = getattr(player, "id", None)
        lines = [f"Development History - {getattr(player, 'full_name', '?')}", ""]
        game = getattr(main_window, "game", None)
        gm = _resolve_gm(game)
        prog, history, engine = None, None, None
        try:
            from enhanced_practice_system import (
                PracticeEngine, ACTIVE_TRAINING_PROGRAMS)
            if gm is not None and getattr(gm, "training_programs", None):
                prog = gm.training_programs.get(pid)
            if prog is None:
                prog = ACTIVE_TRAINING_PROGRAMS.get(pid)
            engine = PracticeEngine()
        except Exception:
            prog, engine = None, None
        if prog:
            lines.append(
                f"Current program: {prog.get('focus', '?')} -- "
                f"{prog.get('intensity', '?')} intensity "
                f"(assigned {prog.get('assigned', 'unknown date')})")
        else:
            lines.append("Current program: none assigned")
        lines.append("")
        try:
            if engine is not None and pid is not None:
                history = engine.get_player_history(pid)
        except Exception:
            history = None
        sessions = (history.recent_sessions[-5:]
                    if history and history.recent_sessions else [])
        if sessions:
            lines.append("Recent sessions:")
            for s in reversed(sessions):
                try:
                    ptype = (s.practice_type.value.replace("_", " ").title()
                             if hasattr(s.practice_type, "value")
                             else str(s.practice_type))
                except Exception:
                    ptype = "practice"
                try:
                    when = s.date_completed.isoformat()
                except Exception:
                    when = "?"
                lines.append(
                    f"  - {when}: {ptype} "
                    f"(+{getattr(s, 'skill_gain', 0):.2f} skill, "
                    f"+{getattr(s, 'fatigue_cost', 0)}% fatigue)")
            lines.append("")
            lines.append("Total recorded sessions: "
                         f"{getattr(history, 'total_sessions', 0)}")
        else:
            lines.append("No recorded practice sessions yet.")
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText("\n".join(lines))
        txt.setMinimumSize(480, 360)
        dlg = QDialog(main_window)
        dlg.setWindowTitle(f"Development History - {getattr(player, 'full_name', '?')}")
        lay = QVBoxLayout(dlg)
        lay.addWidget(txt)
        btns = QDialogButtonBox(QDialogButtonBox.Close, dlg)
        btns.rejected.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

    @staticmethod
    def _analyze_trade_value(main_window, player):
        """Show trade_engine.player_trade_value_breakdown(): what drives
        the value -- OVR base, age curve, potential, contract efficiency,
        volatility, goalie premium, RFA-impasse rights, recent
        performance. Read-only; never raises."""
        try:
            import trade_engine as _te
            total, comps = _te.player_trade_value_breakdown(player)
        except Exception:
            total, comps = None, []
        pname = getattr(player, "full_name", str(player))
        dlg = QDialog(main_window)
        dlg.setWindowTitle(f"Trade Value - {pname}")
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        title = QLabel(pname)
        f = title.font()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        try:
            _pos = player.primary_position.value
            _age = getattr(player, "age", "?")
            sub = QLabel(f"{_pos} - age {_age}")
            sub.setStyleSheet("color: #a1a1aa;")
            lay.addWidget(sub)
        except Exception:
            pass
        if total is None:
            lay.addWidget(QLabel("Value analysis unavailable."))
        else:
            tl = QLabel(f"Trade value: {total} pick-points")
            tf = tl.font()
            tf.setPointSize(12)
            tf.setBold(True)
            tl.setFont(tf)
            lay.addWidget(tl)
            nl = QLabel("(a 1st-round pick ~= 1000)")
            nl.setStyleSheet("color: #a1a1aa;")
            lay.addWidget(nl)
            for c in (comps or []):
                try:
                    _d = c.get("delta", 0)
                except Exception:
                    _d = 0
                sign = "+" if _d >= 0 else ""
                row = QHBoxLayout()
                dl = QLabel(f"{sign}{_d}")
                dl.setMinimumWidth(64)
                df = dl.font()
                df.setBold(True)
                dl.setFont(df)
                dl.setStyleSheet(
                    "color: #6fcf7f;" if _d >= 0 else "color: #e5484d;")
                row.addWidget(dl)
                try:
                    bl = QLabel(c.get("label", ""))
                    bf = bl.font()
                    bf.setBold(True)
                    bl.setFont(bf)
                    row.addWidget(bl, 1)
                except Exception:
                    pass
                lay.addLayout(row)
                try:
                    det = QLabel(c.get("detail", ""))
                    det.setWordWrap(True)
                    det.setStyleSheet("color: #a1a1aa; font-size: 11px;")
                    lay.addWidget(det)
                except Exception:
                    pass
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    @staticmethod
    def _release_staff(main_window, staff):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            main_window, "Release Staff",
            "Release this staff member?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                game = getattr(main_window, "game", None)
                if game and hasattr(game, "release_staff"):
                    game.release_staff(staff)
                else:
                    print(f"[ctx] no release_staff on game")
            except Exception as e:
                print(f"[ctx] release failed: {e}")


def enable_context_menu(widget, menu_factory):
    """Enable right-click context menu on a widget.

    Usage:
        enable_context_menu(table, lambda pos: EntityContextMenu.player_menu(
            main_window, player, is_user_team=True))
    """
    widget.setContextMenuPolicy(Qt.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        lambda pos: _show_at(widget, menu_factory, pos))


def _show_at(widget, menu_factory, pos):
    try:
        menu = menu_factory(pos)
        if menu:
            global_pos = widget.mapToGlobal(pos)
            menu.exec(global_pos)
    except Exception as e:
        print(f"[ctx] menu failed: {e}")
