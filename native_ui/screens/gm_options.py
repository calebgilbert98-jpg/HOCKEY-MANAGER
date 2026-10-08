"""GM Options Hub: executive management tools.

Port of mainline GMOptionsView (main.py, CustomTkinter rebuild) to the
native PySide6/Qt UI. Calls the game object directly -- no Flask/HTTP.

Sections (unchanged from mainline):
- Player Management: Player Shortlist -> "shortlist" screen,
  Set Captains -> "captains" screen.
- Executive Actions: GM Dashboard -> "manager" (GM hub) screen,
  Team Analytics -> "team_analytics" (Team 2's screen when it lands;
  falls back to the "analytics" hub meanwhile), Season Goals ->
  "season_goals" screen.
- Quick Actions: Auto-Negotiate Extensions (negotiates extensions with
  every player/staff with 1 year left, sends one inbox digest), Check
  Inbox -> "inbox" screen.
- Game Presentation: mode picker (Quick Sim / Ask Each Game / Watch
  Live) persisted via settings['simulation']['user_game_mode'] with the
  same legacy use_game_viewer migration mainline uses.
"""
from datetime import date

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


# Same labels/keys as mainline GAME_MODE_LABELS.
MODE_LABELS = (
    ("Quick Sim", "quick"),
    ("Ask Each Game", "ask"),
    ("Watch Live", "watch"),
)


class GMOptionsScreen(BaseScreen):
    title = "GM Options"

    def __init__(self, game, main_window, parent=None):
        # Collected for testing / debugging: records which navigation
        # names each button resolves to.
        self._nav_log = []
        super().__init__(game, main_window, parent)

    # ------------------------------------------------------------------
    # game access (mirrors mainline's self.app = HockeyManagerGUI)
    # ------------------------------------------------------------------
    def _app(self):
        """The app-level object (HockeyManagerGUI or GameManager instance).

        Both expose user_team, handle_contract_offer, and get_settings;
        the mode/inbox helpers use getattr with fallbacks because the
        GameManager does not carry the GUI's _get/_set_user_game_mode.
        """
        return self.game

    def _user_team(self):
        app = self._app()
        team = getattr(app, "user_team", None)
        if team is None:
            gm = getattr(self.game, "game_manager", None)
            team = getattr(gm, "user_team", None) if gm else None
        return team

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        sub = QLabel("Executive Management Tools")
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(sub)

        self._build_section("Player Management", [
            ("Player Shortlist", lambda: self._navigate_first(
                ["shortlist"], fallback=self._shortlist_unavailable)),
            ("Set Captains", lambda: self._go("captains")),
        ])
        self._build_section("Executive Actions", [
            ("GM Dashboard", lambda: self._go("manager")),
            ("Team Analytics", lambda: self._navigate_first(
                ["team_analytics", "analytics"])),
            ("Season Goals", lambda: self._go("season_goals")),
        ])
        self._build_section("Quick Actions", [
            ("Auto-Negotiate Extensions", self.auto_negotiate_extensions),
            ("Check Inbox", lambda: self._go("inbox")),
        ])
        self._build_presentation_section()

        self._layout.addStretch()

    def _build_section(self, title, buttons):
        """Tile card with a heading and full-width action buttons."""
        card = QFrame()
        card.setObjectName("tile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        head = QLabel(title.upper())
        head.setObjectName("section-header")
        layout.addWidget(head)

        for text, command in buttons:
            btn = QPushButton(text)
            btn.setObjectName("action-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton#action-btn {"
                " background-color: #162032; color: #e8edf5;"
                " border: 1px solid #2a3550; border-radius: 6px;"
                " font-size: 14px; font-weight: 700;"
                " padding: 10px 16px; text-align: left; }"
                "QPushButton#action-btn:hover {"
                " background-color: #1a2740; border-color: #3B82F6; }"
                "QPushButton#action-btn:pressed {"
                " background-color: #132034; }")
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(command)
            layout.addWidget(btn)
            # Keep a handle for adversarial / unit testing.
            self._nav_log.append((text, command))

        self._layout.addWidget(card)

    def _build_presentation_section(self):
        """Game-presentation mode picker (Quick Sim / Ask Each Game / Watch)."""
        card = QFrame()
        card.setObjectName("tile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)

        head = QLabel("GAME PRESENTATION")
        head.setObjectName("section-header")
        layout.addWidget(head)

        sub = QLabel("Your games:")
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        layout.addWidget(sub)

        self._mode_combo = QComboBox()
        self._mode_combo.setMinimumHeight(36)
        for label, key in MODE_LABELS:
            self._mode_combo.addItem(label, key)
        current = self._get_user_game_mode()
        for i, (_label, key) in enumerate(MODE_LABELS):
            if key == current:
                self._mode_combo.setCurrentIndex(i)
                break
        self._mode_combo.currentIndexChanged.connect(self._on_mode_pick)
        layout.addWidget(self._mode_combo)

        note = QLabel(
            "Quick Sim resolves instantly. Watch Live opens the real-time "
            "rink. Ask Each Game lets you choose on game day.")
        note.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._layout.addWidget(card)

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def _go(self, screen_name):
        """Navigate to a registered screen."""
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(screen_name)
            except Exception:
                pass

    def _navigate_first(self, names, fallback=None):
        """Navigate to the first registered screen name in `names`."""
        registry = getattr(self.main_window, "_screen_classes", None)
        for name in names:
            if registry is None or name in registry:
                self._go(name)
                return name
        if fallback is not None:
            fallback()
        return None

    def _shortlist_unavailable(self):
        QMessageBox.information(
            self, "Shortlist",
            "The shortlist screen is not registered yet.")

    # ------------------------------------------------------------------
    # game presentation mode (port of mainline _get/_set_user_game_mode)
    # ------------------------------------------------------------------
    def _get_user_game_mode(self):
        """How the user's own games are presented. Migrates legacy bool."""
        app = self._app()
        getter = getattr(app, "_get_user_game_mode", None)
        if callable(getter):
            try:
                mode = getter()
                if mode in ("quick", "watch", "ask"):
                    return mode
            except Exception:
                pass
        try:
            settings = self._settings()
            sim = settings.get("simulation", {}) if settings else {}
            mode = sim.get("user_game_mode")
            if mode in ("quick", "watch", "ask"):
                return mode
            if sim.get("use_game_viewer", False):
                return "watch"
        except Exception:
            pass
        return "ask"

    def _settings(self):
        app = self._app()
        getter = getattr(app, "get_settings", None)
        if callable(getter):
            try:
                return getter() or {}
            except Exception:
                return {}
        return {}

    def _on_mode_pick(self, index):
        key = self._mode_combo.itemData(index)
        if key not in ("quick", "watch", "ask"):
            return
        app = self._app()
        setter = getattr(app, "_set_user_game_mode", None)
        if callable(setter):
            try:
                setter(key)
                return
            except Exception:
                pass
        # Fallback: replicate mainline's settings persistence.
        try:
            settings = self._settings()
            settings.setdefault("simulation", {})["user_game_mode"] = key
            settings["simulation"]["use_game_viewer"] = (key == "watch")
            self._persist_settings(settings)
        except Exception:
            pass

    @staticmethod
    def _persist_settings(settings):
        import json
        import os
        try:
            import main as _main
            base = os.path.dirname(os.path.abspath(_main.__file__))
        except Exception:
            base = os.path.dirname(os.path.abspath(__file__))
            base = os.path.dirname(os.path.dirname(base))
        path = os.path.join(base, "settings.json")
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)

    # ------------------------------------------------------------------
    # auto-negotiate extensions (port of mainline's version)
    # ------------------------------------------------------------------
    @staticmethod
    def _person_name(person):
        return (getattr(person, "full_name", None)
                or getattr(person, "name", None) or "Unknown")

    @staticmethod
    def _years_left(person):
        """Years remaining on contract, same getattr chain as mainline."""
        years = getattr(person, "contract_years", None)
        if years is None:
            contract = getattr(person, "contract", None)
            years = getattr(contract, "years_remaining", 0) \
                if contract is not None else getattr(
                    person, "years_remaining", 0)
        return years or 0

    def _find_expiring(self):
        """Players and staff with exactly 1 year left on contract."""
        expiring = []
        team = self._user_team()
        if team is None:
            return expiring
        try:
            roster = list(getattr(team, "roster", None) or [])
            ahl = list(getattr(team, "ahl_roster", None) or [])
            staff = list(getattr(team, "staff", None) or [])
        except Exception:
            return expiring
        for person in roster + ahl + staff:
            try:
                if self._years_left(person) == 1:
                    expiring.append(person)
            except Exception:
                continue
        return expiring

    def auto_negotiate_extensions(self):
        """Auto-negotiate contract extensions with expiring players/staff."""
        expiring = self._find_expiring()

        if not expiring:
            QMessageBox.information(
                self, "No Extensions Needed",
                "No expiring contracts found.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Auto-Negotiate",
            f"Automatically negotiate extensions with "
            f"{len(expiring)} expiring contract(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        results = []
        for person in expiring:
            # Ensure salary and contract_years attributes exist.
            # Note: getattr's default is evaluated eagerly, so guard the
            # contract lookup - Staff objects have salary/contract_years
            # fields directly and never carry a .contract attribute.
            contract = getattr(person, "contract", None)
            if contract is not None:
                salary = getattr(person, "salary",
                                 getattr(contract, "salary", 750000))
                years = getattr(person, "contract_years",
                                getattr(contract, "years_remaining", 1))
            else:
                salary = getattr(person, "salary", 750000)
                years = getattr(person, "contract_years", 1)
            try:
                person.salary = salary
                person.contract_years = years
            except Exception:
                pass
            accepted = self._offer_extension(person)
            results.append(
                f"{self._person_name(person)}: "
                f"{'Accepted' if accepted else 'Rejected'}")

        # One inbox digest instead of a popup (FM24 style).
        self._send_negotiation_digest(results)
        QMessageBox.information(
            self, "Auto-Negotiate Complete",
            "Automatic extension negotiations complete. "
            "A digest was sent to your inbox.")

    def _offer_extension(self, person):
        """Route the extension offer through the app's contract handler."""
        app = self._app()
        handler = getattr(app, "handle_contract_offer", None)
        if callable(handler):
            try:
                return bool(handler(person, extension=True, notify="quiet"))
            except Exception:
                return False
        # Last resort: GameManager directly.
        try:
            gm = getattr(self.game, "game_manager", None)
            if gm is not None and hasattr(gm, "handle_contract_offer"):
                return bool(gm.handle_contract_offer(
                    person, extension=True, notify="quiet"))
        except Exception:
            pass
        return False

    def _send_negotiation_digest(self, results):
        try:
            from game_classes import EmailMessage
        except Exception:
            return
        message = EmailMessage(
            sender="System", sender_type="System", date_sent=date.today(),
            category="Contracts", priority=2,
            subject="Auto-Negotiation Results",
            content="Automatic extension negotiations complete:\n"
                    + "\n".join(f"\u2022 {r}" for r in results))
        app = self._app()
        sender = getattr(app, "send_email_to_user", None)
        if callable(sender):
            try:
                sender(message)
                return
            except Exception:
                pass
        # Fallback: deliver straight to the team inbox.
        try:
            team = self._user_team()
            inbox = getattr(team, "inbox", None)
            if inbox is not None:
                inbox.add_message(message)
                try:
                    updater = getattr(app, "update_inbox_notification", None)
                    if callable(updater):
                        updater()
                except Exception:
                    pass
        except Exception:
            pass
