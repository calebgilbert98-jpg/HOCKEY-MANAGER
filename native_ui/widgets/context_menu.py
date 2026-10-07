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
                                game, player))
            menu.add_action("Sign Extension",
                            lambda p=player: EntityContextMenu._open_contracts(
                                main_window, p))
            menu.addSeparator()
            menu.add_action("Place on Waivers",
                            lambda: EntityContextMenu._place_waivers(
                                main_window, game, player),
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
    def _add_trade_block(game, player):
        try:
            if not hasattr(game, "trade_block"):
                game.trade_block = []
            if player not in game.trade_block:
                game.trade_block.append(player)
        except Exception as e:
            print(f"[ctx] trade block failed: {e}")

    @staticmethod
    def _place_waivers(main_window, game, player):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            main_window, "Waivers",
            "Place this player on waivers? Other teams can claim him.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # Add to waiver list and flag the player
                if hasattr(game, "waiver_list"):
                    if player not in game.waiver_list:
                        game.waiver_list.append(player)
                player.on_waivers = True
                # Remove from active roster if present
                user_team = getattr(game, "user_team", None)
                if user_team and hasattr(user_team, "roster"):
                    if player in user_team.roster:
                        user_team.roster.remove(player)
            except Exception as e:
                print(f"[ctx] waivers failed: {e}")

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
