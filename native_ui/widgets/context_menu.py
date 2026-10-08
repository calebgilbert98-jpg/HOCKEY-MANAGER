"""Reusable context menu for players, teams, and staff.

Ports web_ui/static/js/context_menu.js. Right-click on any entity shows
an NHL 14-styled menu. Supports Caleb's "everything should be clickable"
standard.
"""
from PySide6.QtWidgets import QMenu
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
                        lambda: main_window.show_screen("trades"))

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
                        lambda: main_window.show_screen("trades"))
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
    def _open_compare(main_window, player):
        """Open compare screen with the player pre-loaded."""
        main_window.show_screen("compare")
        screen = main_window._screens.get("compare")
        if screen:
            widget = screen.widget() if hasattr(screen, "widget") else screen
            if hasattr(widget, "set_players"):
                try:
                    widget.set_players([player])
                except Exception:
                    pass

    @staticmethod
    def _open_contracts(main_window, player):
        """Open contracts screen with the player pre-loaded."""
        main_window.show_screen("contracts")
        screen = main_window._screens.get("contracts")
        if screen:
            widget = screen.widget() if hasattr(screen, "widget") else screen
            if hasattr(widget, "set_player"):
                try:
                    widget.set_player(player)
                except Exception:
                    pass

    @staticmethod
    def _open_staff_detail(main_window, staff):
        """Open staff detail screen with the staff pre-loaded."""
        main_window.show_screen("staff_detail")
        screen = main_window._screens.get("staff_detail")
        if screen:
            widget = screen.widget() if hasattr(screen, "widget") else screen
            if hasattr(widget, "set_staff"):
                try:
                    widget.set_staff(staff)
                except Exception:
                    pass

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
