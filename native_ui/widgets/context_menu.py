"""Reusable context menu for players, teams, and staff.

Ports web_ui/static/js/context_menu.js. Right-click on any entity shows
an NHL 14-styled menu. Supports Caleb's "everything should be clickable"
standard.
"""
from PySide6.QtWidgets import QMenu, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction


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
                        lambda: main_window.show_player(player))
        menu.add_action("Compare",
                        lambda p=player: EntityContextMenu._open_compare(
                            main_window, p))
        menu.add_action("Propose Trade",
                        lambda p=player: EntityContextMenu._open_trade_proposal(
                            main_window, player=p))

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
        """
        try:
            main_window.show_screen("trades")
            screen = main_window._screens.get("trades")
            widget = (screen.widget() if screen and hasattr(screen, "widget")
                      else screen)
            setter = getattr(widget, "set_teams", None) if widget else None
            if not callable(setter):
                raise RuntimeError("trade screen has no set_teams deep-link")
            pid = None
            if player is not None:
                pid = str(getattr(player, "id", "") or "")
            setter(team_name or "", pid or "")
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
