"""Puck Dynasty native main window (PySide6).

Steam-style native application shell. Hosts the hub dashboard and all
game screens as Qt widgets. No browser, no HTTP -- direct Python calls
into the game logic.
"""
import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence

from .theme import THEME_QSS


class TopBar(QWidget):
    """Application header: brand + nav + inbox/save."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self._main = main_window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # Brand
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("PUCK DYNASTY")
        brand.setObjectName("brand")
        brand_sub = QLabel("HOCKEY MANAGER")
        brand_sub.setObjectName("brand-sub")
        brand_box.addWidget(brand)
        brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)
        layout.addSpacing(24)

        # Nav buttons
        self._nav_buttons = {}
        for name in ["CLUB", "PERSONNEL", "LEAGUE", "TRANSACTIONS",
                     "FINANCES", "SYSTEMS"]:
            btn = QPushButton(name)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked, n=name: self._main.show_section(n))
            layout.addWidget(btn)
            self._nav_buttons[name] = btn

        layout.addStretch()

        # Inbox + Save
        self.inbox_btn = QPushButton("INBOX")
        self.inbox_btn.setObjectName("nav-btn")
        self.inbox_btn.setCursor(Qt.PointingHandCursor)
        self.inbox_btn.clicked.connect(self._main.show_inbox)
        layout.addWidget(self.inbox_btn)

        self.save_btn = QPushButton("SAVE")
        self.save_btn.setObjectName("nav-btn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(lambda: self._main.show_screen("save"))
        layout.addWidget(self.save_btn)

        self.mp_btn = QPushButton("MULTIPLAYER")
        self.mp_btn.setObjectName("nav-btn")
        self.mp_btn.setCursor(Qt.PointingHandCursor)
        self.mp_btn.clicked.connect(
            lambda: self._main.show_screen("multiplayer"))
        layout.addWidget(self.mp_btn)

        self.settings_btn = QPushButton("SETTINGS")
        self.settings_btn.setObjectName("nav-btn")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(
            lambda: self._main.show_screen("settings"))
        layout.addWidget(self.settings_btn)

        self.shortcuts_btn = QPushButton("?")
        self.shortcuts_btn.setObjectName("nav-btn")
        self.shortcuts_btn.setCursor(Qt.PointingHandCursor)
        self.shortcuts_btn.setToolTip("Keyboard shortcuts (?)")
        self.shortcuts_btn.clicked.connect(
            lambda: self._main.show_shortcuts_dialog())
        layout.addWidget(self.shortcuts_btn)

    def set_active(self, name):
        for n, btn in self._nav_buttons.items():
            btn.setChecked(n == name)


class HubPage(QWidget):
    """Main dashboard: team header, tiles, standings, leaders, ticker."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self.setObjectName("hub-central")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(16)

        # Team header
        self.team_label = QLabel("—")
        self.team_label.setStyleSheet(
            "font-size: 32px; font-weight: 900; color: #ffffff;")
        self.record_label = QLabel("—")
        self.record_label.setStyleSheet(
            "font-size: 14px; color: #8b95ab;")
        outer.addWidget(self.team_label)
        outer.addWidget(self.record_label)

        # Continue button row
        btn_row = QHBoxLayout()
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setObjectName("primary-btn")
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.clicked.connect(self._main.on_continue)
        btn_row.addWidget(self.continue_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # Tile grid
        tile_grid = QGridLayout()
        tile_grid.setSpacing(12)
        self._tiles = {}
        tile_defs = [
            ("record", "RECORD", 0, 0),
            ("standing", "DIVISION", 0, 1),
            ("streak", "STREAK", 0, 2),
            ("cap", "CAP SPACE", 0, 3),
            ("next_game", "NEXT GAME", 1, 0),
            ("top_scorer", "TOP SCORER", 1, 1),
            ("injuries", "INJURIES", 1, 2),
            ("morale", "MORALE", 1, 3),
        ]
        for key, title, r, c in tile_defs:
            tile = self._make_tile(title)
            tile_grid.addWidget(tile, r, c)
            self._tiles[key] = tile
        outer.addLayout(tile_grid)

        outer.addStretch()

        # Ticker at bottom (clickable -> news screen)
        self.ticker = QLabel("Loading scores…")
        self.ticker.setObjectName("ticker")
        self.ticker.setAlignment(Qt.AlignCenter)
        self.ticker.setCursor(Qt.PointingHandCursor)
        self.ticker.mousePressEvent = lambda e: self._main.show_screen("news")
        outer.addWidget(self.ticker)

    def _make_tile(self, title):
        frame = QFrame()
        frame.setObjectName("tile")
        frame.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        t = QLabel(title)
        t.setObjectName("tile-title")
        v = QLabel("—")
        v.setObjectName("tile-value")
        s = QLabel("")
        s.setObjectName("tile-sub")
        layout.addWidget(t)
        layout.addWidget(v)
        layout.addWidget(s)
        frame.mousePressEvent = lambda e, t=title: self._main.on_tile_click(t)
        # Store refs for updates
        frame._value_label = v
        frame._sub_label = s
        return frame

    def set_tile(self, key, value, sub=""):
        if key in self._tiles:
            self._tiles[key]._value_label.setText(str(value))
            self._tiles[key]._sub_label.setText(str(sub))

    def refresh(self, game):
        """Populate from the live game object. Direct Python access --
        no HTTP, no serialization."""
        try:
            # Resolve game manager (handles both app and gm objects)
            gm = getattr(game, "game_manager", None) or game
            team = getattr(gm, "user_team", None) or getattr(game, "user_team", None)
            if team:
                self.team_label.setText(
                    getattr(team, "team_name", "—").upper())
                # Record
                wins = getattr(team, "wins", 0) or 0
                losses = getattr(team, "losses", 0) or 0
                otl = getattr(team, "otl", 0) or getattr(team, "ties", 0) or 0
                self.record_label.setText(f"{wins}-{losses}-{otl}")
                self.set_tile("record", f"{wins}-{losses}-{otl}", "Season record")

                # Division rank
                try:
                    division = getattr(team, "division", "") or ""
                    league = getattr(self._main.game, "league", None)
                    if league and division:
                        div_teams = [t for t in getattr(league, "teams", [])
                                     if getattr(t, "division", "") == division]
                        # Sort by points
                        def _pts(t):
                            w = getattr(t, "wins", 0) or 0
                            o = getattr(t, "otl", 0) or 0
                            return w * 2 + o
                        div_teams.sort(key=_pts, reverse=True)
                        rank = next((i + 1 for i, t in enumerate(div_teams)
                                     if t is team), None)
                        if rank:
                            suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank, "th")
                            self.set_tile("standing", f"{rank}{suffix}",
                                          f"of {len(div_teams)} in {division}")
                        else:
                            self.set_tile("standing", division, "Division")
                    else:
                        self.set_tile("standing", division or "—", "Division")
                except Exception:
                    pass

                # Cap space
                try:
                    from salary_cap_system import cap_breakdown
                    bd = cap_breakdown(team)
                    space = bd.get("space", 0)
                    self.set_tile("cap", f"${space/1e6:.1f}M", "Cap space")
                except Exception:
                    pass

                # Injuries
                try:
                    roster = getattr(team, "roster", None) or []
                    injured = sum(1 for p in roster if getattr(p, "is_injured", False))
                    self.set_tile("injuries", str(injured), "Injured")
                except Exception:
                    pass

                # Streak (last 10 games)
                try:
                    recent = getattr(team, "recent_results", None) or []
                    if recent:
                        last10 = recent[-10:]
                        w = sum(1 for r in last10 if str(r).upper().startswith("W"))
                        l = sum(1 for r in last10 if str(r).upper().startswith("L"))
                        self.set_tile("streak", f"{w}-{l}", "Last 10")
                except Exception:
                    pass

                # Next game
                try:
                    league = getattr(self._main.game, "league", None)
                    sched = getattr(league, "schedule", None) or []
                    team_name = getattr(team, "team_name", "")
                    upcoming = [g for g in sched
                                if not getattr(g, "played", True)
                                and team_name in (getattr(g, "home_team", ""),
                                                  getattr(g, "away_team", ""))]
                    if upcoming:
                        g = upcoming[0]
                        opp = getattr(g, "away_team", "") if getattr(g, "home_team", "") == team_name else getattr(g, "home_team", "")
                        self.set_tile("next_game", opp[:12], "Next game")
                except Exception:
                    pass

                # Top scorer
                try:
                    roster = getattr(team, "roster", None) or []
                    if roster:
                        def _pts2(p):
                            return (getattr(p, "goals", 0) or 0) + (getattr(p, "assists", 0) or 0)
                        top = max(roster, key=_pts2)
                        name = getattr(top, "full_name", "?") or "?"
                        pts = _pts2(top)
                        # Shorten name to fit
                        parts = name.split()
                        short = f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else name
                        self.set_tile("top_scorer", short[:14], f"{pts} PTS")
                except Exception:
                    pass

                # Morale (average, 1-10 scale mapped to 10-100 like morale screen)
                try:
                    roster = getattr(team, "roster", None) or []
                    if roster:
                        morales = [getattr(p, "morale", 5) or 5 for p in roster]
                        avg = sum(morales) / len(morales) if morales else 5
                        self.set_tile("morale", f"{avg*10:.0f}", "Team morale")
                except Exception:
                    pass

                # Ticker: recent headlines
                try:
                    game = self._main.game
                    news = getattr(game, "news_log", None) or []
                    if news:
                        # Get latest headline
                        latest = news[-1] if isinstance(news, list) else None
                        if latest:
                            headline = getattr(latest, "headline", None) or str(latest)[:60]
                            self.ticker.setText(headline[:80])
                    else:
                        # Fall back to recent game results
                        league = getattr(game, "league", None)
                        sched = getattr(league, "schedule", None) or []
                        played = [g for g in sched if getattr(g, "played", False)]
                        if played:
                            g = played[-1]
                            ht = getattr(g, "home_team", "?")
                            at = getattr(g, "away_team", "?")
                            hs = getattr(g, "home_score", 0)
                            aws = getattr(g, "away_score", 0)
                            self.ticker.setText(f"Final: {at} {aws} - {ht} {hs}")
                except Exception:
                    pass
        except Exception as e:
            print(f"[hub] refresh failed: {e}")


class MainWindow(QMainWindow):
    """Puck Dynasty native application window."""

    def __init__(self, game=None):
        super().__init__()
        self.game = game  # HockeyManagerGUI or game manager instance
        self.setWindowTitle("Puck Dynasty")
        self.setMinimumSize(1280, 800)

        # Top bar
        self.topbar = TopBar(self)
        self.addToolBar(Qt.TopToolBarArea, self._wrap_topbar())

        # Central stacked widget for screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Hub page
        self.hub = HubPage(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.hub)
        scroll.setFrameShape(QFrame.NoFrame)
        self.stack.addWidget(scroll)

        # Screen registry: name -> widget
        self._screens = {"hub": scroll}
        self._screen_classes = {}
        self._register_all_screens()

        # Apply theme
        self.setStyleSheet(THEME_QSS)

        # Keyboard shortcuts (Space, Ctrl+S, Esc, ?, 1-9)
        self._setup_keyboard_shortcuts()

    def _register_all_screens(self):
        """Register all ported screens for lazy instantiation."""
        # Map of screen name -> (module, class name)
        _registry = {
            "roster": ("native_ui.screens.roster", "RosterScreen"),
            "player": ("native_ui.screens.player_profile", "PlayerProfileScreen"),
            "lines": ("native_ui.screens.lines", "LinesScreen"),
            "setup": ("native_ui.screens.setup", "SetupScreen"),
            "multiplayer": ("native_ui.screens.multiplayer", "MultiplayerScreen"),
            "practice_center": ("native_ui.screens.practice_center", "PracticeCenterScreen"),
            "camp": ("native_ui.screens.camp", "CampScreen"),
            "captains": ("native_ui.screens.captains", "CaptainsScreen"),
            "staff": ("native_ui.screens.staff", "StaffScreen"),
            "staff_detail": ("native_ui.screens.staff_detail", "StaffDetailScreen"),
            "contracts": ("native_ui.screens.contracts", "ContractsScreen"),
            "morale": ("native_ui.screens.morale", "MoraleScreen"),
            "development": ("native_ui.screens.development", "DevelopmentScreen"),
            "tactics": ("native_ui.screens.tactics", "TacticsScreen"),
            "season_goals": ("native_ui.screens.season_goals", "SeasonGoalsScreen"),
            "offseason_programs": ("native_ui.screens.offseason_programs", "OffseasonProgramsScreen"),
            "jersey_numbers": ("native_ui.screens.jersey_numbers", "JerseyNumbersScreen"),
            "gm_relationships": ("native_ui.screens.gm_relationships", "GmRelationshipsScreen"),
            "trades": ("native_ui.screens.trades", "TradesScreen"),
            "free_agents": ("native_ui.screens.free_agents", "FreeAgentsScreen"),
            "waivers": ("native_ui.screens.waivers", "WaiversScreen"),
            "offer_sheets": ("native_ui.screens.offer_sheets", "OfferSheetsScreen"),
            "trade_block": ("native_ui.screens.trade_block", "TradeBlockScreen"),
            "deadline": ("native_ui.screens.deadline", "DeadlineScreen"),
            "standings": ("native_ui.screens.standings", "StandingsScreen"),
            "stats": ("native_ui.screens.stats", "StatsScreen"),
            "schedule": ("native_ui.screens.schedule", "ScheduleScreen"),
            "playoffs": ("native_ui.screens.playoffs", "PlayoffsScreen"),
            "draft": ("native_ui.screens.draft", "DraftScreen"),
            "lottery": ("native_ui.screens.lottery", "LotteryScreen"),
            "history": ("native_ui.screens.history", "HistoryScreen"),
            "season_summary": ("native_ui.screens.season_summary", "SeasonSummaryScreen"),
            "ahl": ("native_ui.screens.ahl", "AhIScreen"),
            "calendar": ("native_ui.screens.calendar", "CalendarScreen"),
            "team": ("native_ui.screens.team", "TeamScreen"),
            "inbox": ("native_ui.screens.inbox", "InboxScreen"),
            "news": ("native_ui.screens.news", "NewsScreen"),
            "finances": ("native_ui.screens.finances", "FinancesScreen"),
            "settings": ("native_ui.screens.settings", "SettingsScreen"),
            "save": ("native_ui.screens.save", "SaveScreen"),
            "watch": ("native_ui.screens.watch", "WatchScreen"),
            "replay": ("native_ui.screens.replay", "ReplayScreen"),
            "compare": ("native_ui.screens.compare", "CompareScreen"),
            "coach_checkin": ("native_ui.screens.coach_checkin", "CoachCheckinScreen"),
            "manager": ("native_ui.screens.manager", "ManagerScreen"),
            "fa_frenzy": ("native_ui.screens.fa_frenzy", "FaFrenzyScreen"),
            "fantasy_draft": ("native_ui.screens.fantasy_draft", "FantasyDraftScreen"),
            "scouting": ("native_ui.screens.scouting", "ScoutingScreen"),
            "contract_negotiation": ("native_ui.screens.contract_negotiation", "ContractNegotiationScreen"),
            "dressing_room": ("native_ui.screens.dressing_room", "DressingRoomScreen"),
            "media_center": ("native_ui.screens.media_center", "MediaCenterScreen"),
            "records": ("native_ui.screens.records", "RecordsScreen"),
            "shortlist": ("native_ui.screens.shortlist", "ShortlistScreen"),
            "shot_chart_viewer": ("native_ui.screens.shot_chart_viewer", "ShotChartViewerScreen"),
        }
        # Systems pages
        for sys_name in ["clutch", "circumstance", "discipline",
                         "rivalry", "deployment", "condition"]:
            _registry[f"systems_{sys_name}"] = (
                f"native_ui.screens.systems_{sys_name}",
                f"Systems{sys_name.title()}Screen")

        for name, (mod_path, cls_name) in _registry.items():
            try:
                mod = __import__(mod_path, fromlist=[cls_name])
                cls = getattr(mod, cls_name)
                self._screen_classes[name] = cls
            except Exception as e:
                print(f"[nav] failed to register {name}: {e}")

    def register_screen(self, name, screen_class):
        """Register a screen class for lazy instantiation."""
        self._screen_classes[name] = screen_class

    def show_screen(self, name):
        """Navigate to a registered screen, instantiating on first use."""
        if name in self._screens:
            self.stack.setCurrentWidget(self._screens[name])
            # Refresh the screen if it has a refresh method
            widget = self._screens[name]
            # Unwrap scroll area if present
            inner = widget.widget() if hasattr(widget, "widget") else widget
            if hasattr(inner, "refresh"):
                try:
                    inner.refresh()
                except Exception as e:
                    print(f"[nav] refresh {name} failed: {e}")
            return
        # Lazy instantiate
        cls = self._screen_classes.get(name)
        if cls:
            try:
                screen = cls(self.game, self)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(screen)
                scroll.setFrameShape(QFrame.NoFrame)
                self._screens[name] = scroll
                self.stack.addWidget(scroll)
                self.stack.setCurrentWidget(scroll)
                if hasattr(screen, "refresh"):
                    screen.refresh()
            except Exception as e:
                print(f"[nav] failed to create screen {name}: {e}")
        else:
            print(f"[nav] unknown screen: {name}")

    def show_player(self, player):
        """Open a player profile. Used by roster double-click, context menus."""
        self.show_screen("player")
        # Get the inner screen and set the player
        scroll = self._screens.get("player")
        if scroll and hasattr(scroll, "widget"):
            inner = scroll.widget()
            if hasattr(inner, "set_player"):
                inner.set_player(player)

    def open_player(self, player):
        """Alias for show_player (some screens call this)."""
        self.show_player(player)

    def open_team(self, team_name):
        """Open a team overview page."""
        self.show_screen("team")
        scroll = self._screens.get("team")
        if scroll and hasattr(scroll, "widget"):
            inner = scroll.widget()
            if hasattr(inner, "set_team"):
                inner.set_team(team_name)

    def _wrap_topbar(self):
        from PySide6.QtWidgets import QToolBar
        tb = QToolBar()
        tb.setMovable(False)
        tb.addWidget(self.topbar)
        tb.setStyleSheet("QToolBar { border: none; padding: 0; margin: 0; }")
        return tb

    # --- Navigation ---
    def show_section(self, name):
        self.topbar.set_active(name)
        # Map section names to screens (handle uppercase nav button names)
        section_map = {
            "CLUB": "team",
            "PERSONNEL": "staff",
            "LEAGUE": "standings",
            "TRANSACTIONS": "trades",
            "FINANCES": "finances",
            "SYSTEMS": "systems_clutch",
            # Lowercase aliases
            "hub": "hub",
            "roster": "roster",
            "lines": "lines",
            "team": "team",
            "league": "standings",
            "transactions": "trades",
            "inbox": "inbox",
        }
        screen = section_map.get(name, section_map.get(name.lower(), "hub"))
        self.show_screen(screen)

    def show_inbox(self):
        self.show_screen("inbox")

    def save_game(self):
        try:
            if self.game and hasattr(self.game, "save_manager"):
                self.game.save_manager.save_game()
        except Exception as e:
            print(f"[native] save failed: {e}")

    def on_tile_click(self, title):
        # Map hub tile titles to screens (titles are uppercase)
        tile_map = {
            "RECORD": "standings",
            "DIVISION": "standings",
            "STREAK": "schedule",
            "CAP SPACE": "finances",
            "NEXT GAME": "schedule",
            "TOP SCORER": "stats",
            "INJURIES": "roster",
            "MORALE": "morale",
        }
        screen = tile_map.get(title, "hub")
        self.show_screen(screen)

    def on_continue(self):
        """Direct Python call -- no HTTP round-trip."""
        if not self.game:
            return
        try:
            label, blockers = self.game.get_continue_state()
            if blockers:
                self.show_blockers(blockers)
            else:
                # Advance the day
                if hasattr(self.game, "simulate_day"):
                    self.game.simulate_day()
                # Refresh current screen
                current = self.stack.currentWidget() if hasattr(self, "stack") else None
                if current and hasattr(current, "refresh"):
                    current.refresh()
                elif hasattr(self, "hub"):
                    self.hub.refresh(self.game)
        except Exception as e:
            print(f"[native] continue failed: {e}")

    def show_blockers(self, blockers):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
        dlg = QDialog(self)
        dlg.setWindowTitle("Can't advance yet")
        dlg.setMinimumWidth(600)
        layout = QVBoxLayout(dlg)
        title = QLabel(f"{len(blockers)} things need your attention")
        title.setObjectName("dialog-title")
        layout.addWidget(title)
        for b in blockers:
            card = QFrame()
            card.setObjectName("blocker-card")
            cl = QVBoxLayout(card)
            t = QLabel(b.get("title", "Blocker"))
            t.setObjectName("blocker-title")
            d = QLabel(b.get("detail", ""))
            d.setObjectName("blocker-detail")
            d.setWordWrap(True)
            cl.addWidget(t)
            cl.addWidget(d)
            # Render action button if blocker provides one
            # New format: action_id + action_label (UI-agnostic)
            # Old format: action tuple (label, callable) - deprecated
            action_id = b.get("action_id")
            action_label = b.get("action_label", "Open")
            if action_id:
                try:
                    btn = QPushButton(action_label)
                    btn.setObjectName("primary-btn")
                    # Map action IDs to native screens
                    native_target = {
                        "fantasy_draft": "fantasy_draft",
                        "entry_draft": "draft",
                        "captaincy": "captains",
                    }.get(action_id)
                    if native_target:
                        btn.clicked.connect(
                            lambda _=False, n=native_target: (
                                dlg.accept(), self.show_screen(n)))
                    cl.addWidget(btn)
                except Exception:
                    pass
            else:
                # Fallback: old tuple format
                action = b.get("action")
                if action:
                    try:
                        label, callback = action
                        btn = QPushButton(label)
                        btn.setObjectName("primary-btn")
                        blocker_id = b.get("id", "")
                        native_target = {
                            "fantasy_draft": "fantasy_draft",
                            "entry_draft": "draft",
                            "captaincy_choice": "captains",
                            "captaincy": "captains",
                        }.get(blocker_id)
                        if native_target:
                            btn.clicked.connect(
                                lambda _=False, n=native_target: (
                                    dlg.accept(), self.show_screen(n)))
                        cl.addWidget(btn)
                    except Exception:
                        pass
                # Render auto_action button if present (e.g. Auto-pick Captains)
                auto_action = b.get("auto_action")
                if auto_action:
                    try:
                        auto_label, auto_cb = auto_action
                        # For captaincy auto-pick, we can't call the Tk closure.
                        # Instead, trigger the native captains screen which has
                        # its own auto-pick, or run the logic directly.
                        auto_btn = QPushButton(auto_label)
                        auto_btn.setObjectName("primary-btn")
                        bidder = b.get("id", "")
                        if bidder == "captaincy_choice":
                            # Navigate to captains screen; user can auto-pick there
                            auto_btn.clicked.connect(
                                lambda _=False: (
                                    dlg.accept(),
                                    self.show_screen("captains")))
                        else:
                            # Generic: close dialog and try the callback
                            # (may be Tk-bound; guarded)
                            def _run_auto(cb=auto_cb):
                                dlg.accept()
                                try:
                                    cb()
                                except Exception:
                                    pass
                            auto_btn.clicked.connect(_run_auto)
                        cl.addWidget(auto_btn)
                    except Exception:
                        pass
            layout.addWidget(card)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.exec()
        # If the club can't dress 18+2, offer the AHL recall picker.
        # maybe_open_recall_picker is a no-op when there's no shortfall.
        try:
            from .dialogs.recall_picker import maybe_open_recall_picker
            maybe_open_recall_picker(self.game, parent=self)
        except Exception as e:
            print(f"[native] recall picker failed: {e}")

    def refresh(self):
        if self.game:
            self.hub.refresh(self.game)
        else:
            # No game loaded — show the setup wizard
            self.show_screen("setup")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    _TEXT_INPUT_CLASSES = (
        "QLineEdit", "QTextEdit", "QPlainTextEdit", "QComboBox",
        "QSpinBox", "QDoubleSpinBox", "QDateEdit", "QTimeEdit",
        "QDateTimeEdit",
    )

    def _typing_in_field(self):
        """True when focus is in a text input (shortcuts stay quiet)."""
        try:
            from PySide6.QtWidgets import QApplication
            w = QApplication.focusWidget()
            if w is None:
                return False
            return w.__class__.__name__ in self._TEXT_INPUT_CLASSES
        except Exception:
            return False

    def _modal_dialog_open(self):
        """True when a modal dialog is open (shortcuts stay quiet)."""
        try:
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if w.isModal() and w.isVisible() and w is not self:
                    return True
            return False
        except Exception:
            return False

    def _setup_keyboard_shortcuts(self):
        """Wire up app-wide keyboard shortcuts via QShortcut."""
        if getattr(self, "_shortcuts_bound", False):
            return
        self._shortcuts_bound = True

        def _bind(key_seq, handler):
            sc = QShortcut(QKeySequence(key_seq), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(handler)
            return sc

        # Space: Continue (advance day) — not while typing or in a dialog
        _bind("Space", self._shortcut_continue)
        # Ctrl+S: Quick save
        _bind("Ctrl+S", self._shortcut_save)
        # Esc: Back to hub
        _bind("Escape", self._shortcut_escape)
        # ?: Shortcuts cheat-sheet
        _bind("?", self._shortcut_cheat_sheet)
        _bind("Shift+?", self._shortcut_cheat_sheet)

        # 1-9: Quick navigation
        nav_targets = {
            "1": "hub",
            "2": "roster",
            "3": "lines",
            "4": "team",
            "5": "inbox",
            "6": "standings",
            "7": "stats",
            "8": "trades",
            "9": "schedule",
        }
        for key, screen in nav_targets.items():
            _bind(key, lambda s=screen: self._shortcut_navigate(s))

    def _shortcut_continue(self):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        self.on_continue()

    def _shortcut_save(self):
        self.save_game()

    def _shortcut_escape(self):
        if self._modal_dialog_open():
            return  # Let the dialog handle Esc itself
        self.show_screen("hub")

    def _shortcut_cheat_sheet(self):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        try:
            from .dialogs.shortcuts import show_shortcuts
            show_shortcuts(self)
        except Exception as e:
            print(f"[native] shortcuts dialog failed: {e}")

    def _shortcut_navigate(self, screen):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        self.show_screen(screen)

    def show_shortcuts_dialog(self):
        """Public entry point for the shortcuts cheat-sheet."""
        self._shortcut_cheat_sheet()


def run(game=None):
    """Launch the native Puck Dynasty application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Puck Dynasty")
    app.setOrganizationName("Puck Dynasty")
    window = MainWindow(game=game)
    window.showMaximized()
    window.refresh()
    # Show setup wizard if no game
    if game is None:
        window.show_screen("setup")
    return app.exec()
