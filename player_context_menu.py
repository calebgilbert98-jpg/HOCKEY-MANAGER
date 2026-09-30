# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Universal Player Context Menu System
Provides consistent right-click player interactions across all windows
"""

import tkinter as tk
from popup_system import messagebox, InGamePopup

# R2 (UI repairs, revised): the comparison tool works EHM/FM24-style --
# the "Compare with" list defaults to recently-viewed players plus the
# user's own club (NHL/AHL/prospects). Recently-viewed player IDs are
# recorded on player-card open (see main.open_player_profile hook),
# capped, and persisted on the save via save_load_system.
RECENTLY_VIEWED_CAP = 15


def record_recently_viewed(app, player):
    """Record a player-card view for the comparison tool. Additive; never raises."""
    try:
        pid = getattr(player, "id", None)
        if not pid:
            return
        gm = getattr(app, "game_manager", None) or app
        seen = getattr(gm, "recently_viewed_players", None)
        if not isinstance(seen, list):
            seen = []
        seen = [x for x in seen if x != pid]
        seen.insert(0, pid)
        gm.recently_viewed_players = seen[:RECENTLY_VIEWED_CAP]
    except Exception:
        pass


def get_recently_viewed_players(app, exclude=None):
    """Resolve recently-viewed IDs to player objects, most-recent first.

    IDs that no longer resolve (traded away, retired) are skipped.
    Never raises.
    """
    try:
        gm = getattr(app, "game_manager", None) or app
        ids = list(getattr(gm, "recently_viewed_players", None) or [])
        if not ids:
            return []
        league = getattr(gm, "league", None)
        by_id = {}
        try:
            pool = list(league.get_all_players()) if hasattr(league, "get_all_players") else []
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


def _player_sort_key(p):
    """OVR desc, then name -- most comparable players surface first."""
    try:
        ovr = int(p.overall_rating())
    except Exception:
        ovr = -1
    return (-ovr,
            getattr(p, "last_name", "") or "",
            getattr(p, "first_name", "") or "")


class PlayerContextMenu:
    """Universal player context menu for consistent player interactions across all windows"""
    
    def __init__(self, parent_window):
        self.parent = parent_window

    def _app(self):
        """Walk up .parent/.master chain to the app object (has user_team).
        Views hold the app as .app, so check that too."""
        seen = set()
        obj = self.parent
        for _ in range(10):
            if obj is None or id(obj) in seen:
                break
            seen.add(id(obj))
            if hasattr(obj, "user_team") and getattr(obj, "user_team") is not None:
                return obj
            _app = getattr(obj, "app", None)
            if _app is not None and hasattr(_app, "user_team"):
                return _app
            nxt = getattr(obj, "parent", None)
            if nxt is None:
                nxt = getattr(obj, "master", None)
            obj = nxt
        return self.parent
        
    def show_context_menu(self, event, player, additional_options=None,
                          quick_scout=False):
        """Show context menu for a player. Draft screens pass quick_scout=True
        so the Scout entry becomes an instant war-room take (the draft clock
        is ticking -- no scouting-window detour)."""
        context_menu = tk.Menu(self.parent, tearoff=0)
        
        # Configure menu styling to match parent window
        if hasattr(self.parent, 'CONTENT_BG'):
            context_menu.configure(
                bg=self.parent.CONTENT_BG,
                fg=self.parent.TEXT_COLOR,
                activebackground=self.parent.ACCENT_COLOR,
                activeforeground='white',
                font=('Segoe UI', 9)
            )
        
        # Standard player options
        context_menu.add_command(
            label=f"View {player.full_name}'s Profile",
            command=lambda: self._view_player_profile(player)
        )
        
        context_menu.add_separator()
        
        context_menu.add_command(
            label=("⚡ Quick Scout (war-room take)" if quick_scout
                   else "Scout Player"),
            command=lambda: (self._quick_scout_player(player) if quick_scout
                             else self._scout_player(player))
        )
        
        context_menu.add_command(
            label="Physio Report",
            command=lambda: self._physio_report(player)
        )
        
        context_menu.add_command(
            label="Add to Shortlist",
            command=lambda: self._add_to_shortlist(player)
        )
        
        context_menu.add_command(
            label="Compare with Another Player",
            command=lambda: self._compare_players(player)
        )

        # R6 (UI repairs): personal beefs are declared from the person's
        # card -- the Morale window's DeclareRivalPopup already points here.
        context_menu.add_command(
            label="Declare Rival",
            command=lambda: self._declare_rival(player)
        )
        
        context_menu.add_separator()
        
        # Development and training options
        context_menu.add_command(
            label="Assign Training Focus",
            command=lambda: self._assign_training_focus(player)
        )
        
        context_menu.add_command(
            label="View Development History",
            command=lambda: self._view_development_history(player)
        )
        
        # Contract and management options
        context_menu.add_separator()
        
        context_menu.add_command(
            label="Contract Details",
            command=lambda: self._view_contract_details(player)
        )
        
        context_menu.add_command(
            label="Propose Trade",
            command=lambda: self._propose_trade(player)
        )

        # R3(b) (UI repairs): surface the trade-value system's reasoning
        # for any player -- right-click in the trade interface and on
        # player names inside email bodies both land here.
        context_menu.add_command(
            label="Analyze Trade Value",
            command=lambda: self._analyze_trade_value(player)
        )
        
        # Check if player is on user's team for team-specific options
        _app = self._app()
        _uteam = getattr(_app, 'user_team', None)
        if _uteam:
            if (player in getattr(_uteam, 'roster', []) or
                player in getattr(_uteam, 'ahl_roster', []) or
                player in getattr(_uteam, 'prospects', [])):

                context_menu.add_command(
                    label="Move Between Rosters",
                    command=lambda: self._move_between_rosters(player)
                )
        
        # Add window-specific options if provided
        if additional_options:
            context_menu.add_separator()
            for label, command in additional_options:
                context_menu.add_command(label=label, command=command)
        
        # Show menu (Shift+F10 keyboard events carry no pointer
        # position -- fall back to the widget's center)
        x_root = getattr(event, "x_root", 0) or 0
        y_root = getattr(event, "y_root", 0) or 0
        if not x_root and not y_root:
            try:
                w = event.widget
                x_root = w.winfo_rootx() + w.winfo_width() // 2
                y_root = w.winfo_rooty() + w.winfo_height() // 2
            except Exception:
                pass
        try:
            context_menu.tk_popup(x_root, y_root)
        finally:
            context_menu.grab_release()
    
    def _view_player_profile(self, player):
        """Open the player profile as a full screen in the main instance.

        Delegates to the app's canonical open_player_profile (screen-first,
        popup only as a last resort). A messagebox summary is the final
        fallback so a right-click never silently dies inside a menu callback.
        """
        try:
            app = self._app()
            if hasattr(app, "open_player_profile"):
                app.open_player_profile(player)
                return
        except Exception:
            pass
        try:
            messagebox.showinfo(
                "Player Profile", 
                f"Player: {player.full_name}\n"
                f"Position: {player.primary_position.value}\n"
                f"Age: {player.age}\n"
                f"Overall Rating: {player.overall_rating()}\n"
                f"Potential: {getattr(player, 'potential', 'Unknown')}\n\n"
                f"Team: {getattr(player, 'team_name', 'Free Agent')}"
            )
        except Exception:
            pass
    
    def _scout_player(self, player):
        """Open scouting assignment dialog or show existing report"""
        app = self._app()
        # Check if player is already being scouted
        try:
            team = getattr(app, "user_team", None)
            reports = getattr(team, "scouting_reports", {}) if team else {}
            report = reports.get(getattr(player, "id", None))
            if report:
                # Show existing scouting report
                accuracy = getattr(report.scout, 'jpa', 75) if hasattr(report, 'scout') else 75
                potential = getattr(report, 'scouted_potential', 'Unknown')
                viewings = getattr(report, 'viewings', 1)

                messagebox.showinfo(
                    "Existing Scouting Report",
                    f"Scout Report: {player.full_name}\n\n"
                    f"Scout: {report.scout.full_name if hasattr(report, 'scout') else 'Unknown'}\n"
                    f"Accuracy: {accuracy}%\n"
                    f"Viewings: {viewings}\n"
                    f"Potential: {potential}\n\n"
                    f"Status: {'Complete' if viewings >= 3 else 'In Progress'}"
                )
                return
        except Exception:
            pass

        # Try to open scouting window or create assignment
        try:
            # Try to open or focus existing scouting window
            if hasattr(app, 'open_scouting_window'):
                app.open_scouting_window()
                messagebox.showinfo("Scout Assignment", f"Scouting window opened. Assign a scout to {player.full_name} from the prospects list.")
            else:
                # Create quick scout assignment dialog
                self._create_scout_assignment_dialog(player)
        except Exception as e:
            # Fallback to assignment dialog
            self._create_scout_assignment_dialog(player)
    
    def _quick_scout_player(self, player):
        """War-room take for draft screens: the best available scout files a
        single rushed viewing through the normal report machinery -- an
        honest rough take (accuracy stays low until viewings accumulate) --
        and a standing assignment is added so it keeps improving through
        the normal scouting loop. Never raises, never modal: the take lands
        on the draft ticker and the research strip refreshes inline.
        Returns the report, or None when there is no scout to ask."""
        app = self._app()
        try:
            team = getattr(app, "user_team", None)
            reports = getattr(team, "scouting_reports", {}) if team else {}
            pid = getattr(player, "id", None)
            report = reports.get(pid) if pid is not None else None
            if report is None:
                # Best scout: amateur scouts first, then highest JPA+JPP.
                from game_classes import StaffRole
                import scouting as scmod
                scouts = [s for s in (getattr(team, "staff", []) or [])
                          if scmod.is_scout(s)]
                if not scouts:
                    self._draft_note("War room has no scouts -- hire one "
                                     "for a mid-draft take.")
                    return None

                def _key(s):
                    role_bonus = (100 if getattr(s, "role", None)
                                  == StaffRole.AMATEUR_SCOUT else 0)
                    return (role_bonus
                            + getattr(s, "judging_player_ability", 10)
                            + getattr(s, "judging_player_potential", 10))
                scout = max(scouts, key=_key)
                from game_classes import ScoutingReport
                report = ScoutingReport(player=player, scout=scout)
                # One rushed viewing -- a war-room glance, not a finished
                # report. The standing assignment builds it up normally.
                report.update_report(player, scout)
                note = ("War-room take (single rushed viewing) -- "
                        "standing assignment added.")
                report.notes = (note if not report.notes
                                else report.notes + " " + note)
                reports[pid] = report
                assigns = getattr(app, "scouting_assignments", None)
                if isinstance(assigns, dict) and player not in assigns \
                        and len(assigns) < 30:
                    assigns[player] = scout
            self._draft_note(self._take_line(player, report))
            return report
        except Exception:
            return None

    @staticmethod
    def _take_line(player, report):
        acc = getattr(report, "accuracy", "?") or "?"
        pot = getattr(report, "scouted_potential", "?") or "?"
        views = getattr(report, "viewings", 0) or 0
        scout_name = getattr(getattr(report, "scout", None),
                             "full_name", "Your scout")
        return (f"War-room take: {scout_name} on "
                f"{getattr(player, 'full_name', '?')}: {pot} potential, "
                f"accuracy {acc} ({views} viewing"
                f"{'s' if views != 1 else ''})")

    def _draft_note(self, line):
        """Non-modal feedback for a war-room take: a ticker line plus an
        inline research-strip refresh on the open entry-draft view, if
        one is up. Never a popup -- the draft clock is ticking."""
        try:
            view = self._draft_view()
            if view is None:
                return
            try:
                view._ticker(line)
            except Exception:
                pass
            try:
                view._refresh_draft_research()
            except Exception:
                pass
        except Exception:
            pass

    def _draft_view(self):
        """Find the open entry-draft war-room view by duck-typing the
        widget tree (it owns _refresh_draft_research)."""
        try:
            app = self._app()
            stack = list(app.winfo_children())
        except Exception:
            return None
        seen = set()
        while stack:
            w = stack.pop()
            if id(w) in seen:
                continue
            seen.add(id(w))
            if hasattr(w, "_refresh_draft_research"):
                return w
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass
        return None

    def _create_scout_assignment_dialog(self, player):
        """Create a dialog for scout assignment"""
        dialog = InGamePopup(self.parent)
        dialog.title(f"Scout Assignment - {player.full_name}")
        dialog.geometry("400x300")
        dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header
        header = tk.Label(dialog, text=f"Assign Scout to {player.full_name}", 
                         font=('Segoe UI', 12, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header.pack(pady=20)
        
        # Get available scouts
        available_scouts = []
        try:
            app = self._app()
            team = getattr(app, "user_team", None)
            staff = getattr(team, "staff", []) if team else []
            from game_classes import StaffRole
            _scout_roles = {str(r) for r in StaffRole
                            if "SCOUT" in getattr(r, "name", "")}
            available_scouts = [s for s in staff
                                if hasattr(s, 'role') and str(s.role) in _scout_roles]
        except Exception:
            available_scouts = []
        
        if available_scouts:
            # Scout selection
            select_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
            select_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(select_frame, text="Select Scout:", 
                    fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                    bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
            
            from tkinter import ttk
            scout_var = tk.StringVar()
            scout_combo = ttk.Combobox(select_frame, textvariable=scout_var,
                                     values=[f"{s.full_name} (JPA: {getattr(s, 'jpa', 75)})" for s in available_scouts],
                                     state='readonly')
            scout_combo.pack(fill='x', pady=5)
            
            def assign_scout():
                if scout_var.get():
                    selected_scout = available_scouts[scout_combo.current()]
                    try:
                        app = self._app()
                        if getattr(app, "scouting_assignments", None) is None:
                            app.scouting_assignments = {}
                        app.scouting_assignments[player] = selected_scout
                    except Exception as e:
                        print(f"Scout assignment failed: {e}")
                    messagebox.showinfo("Scout Assigned",
                                      f"{selected_scout.full_name} assigned to scout {player.full_name}!")
                    dialog.destroy()
            
            assign_btn = ttk.Button(select_frame, text="Assign Scout", command=assign_scout)
            assign_btn.pack(pady=10)
        else:
            # No scouts available
            no_scouts = tk.Label(dialog, text="No scouts available\nHire scouts in the Staff Management section",
                               fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                               bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
            no_scouts.pack(pady=20)
        
        # Close button
        from tkinter import ttk
        close_btn = ttk.Button(dialog, text="Close", command=dialog.destroy)
        close_btn.pack(pady=10)
    
    def _physio_report(self, player):
        """Show a physio/fitness report popup for the player."""
        try:
            import customtkinter as ctk
            from ctk_theme import init_ctk_theme, BG
            init_ctk_theme()
            app = self.parent
            # Unwrap: parent may be a window holding .parent -> app
            for _ in range(3):
                if hasattr(app, "open_player_profile"):
                    break
                app = getattr(app, "parent", app)
            win = ctk.CTkToplevel(self.parent)
            win.title(f"Physio Report — {player.full_name}")
            win.geometry("430x510")
            win.configure(fg_color=BG)
            try:
                win.transient(self.parent)
                win.grab_set()
            except Exception:
                pass
            from ctk_theme import (heading, body, PANEL, GREEN, RED)
            heading(win, "Physio Report", size=16).pack(anchor="w", padx=18, pady=(16, 2))
            body(win, player.full_name, dim=True).pack(anchor="w", padx=18, pady=(0, 12))
            card = ctk.CTkFrame(win, fg_color=PANEL, corner_radius=12)
            card.pack(fill="both", expand=True, padx=14, pady=(0, 14))

            injured = bool(getattr(player, "is_injured", False))
            body(card, "Status", dim=True, size=11).pack(anchor="w", padx=16, pady=(14, 0))
            ctk.CTkLabel(
                card, text="INJURED" if injured else "Fit to play",
                font=("Segoe UI", 15, "bold"),
                text_color=RED if injured else GREEN).pack(anchor="w", padx=16, pady=(2, 8))

            def _word(v):
                try:
                    v = float(v)
                except Exception:
                    return "Unknown"
                if v >= 40: return "Excellent"
                if v >= 34: return "Good"
                if v >= 27: return "Average"
                if v >= 20: return "Below average"
                return "Poor"

            rows = [
                ("Injury", str(getattr(player, "injury_type", "None") or "None")),
                ("Est. games out", str(getattr(player, "games_remaining_injured", 0) or 0) if injured else "—"),
                ("Last injury", str(getattr(player, "last_injury", "None") or "None")),
                ("Career games missed", str(getattr(player, "career_games_missed", 0))),
                ("Days missed (season)", str(getattr(player, "days_missed", 0))),
                ("Durability", _word(getattr(player, "durability", 30))),
                ("Injury proneness", _word(50 - (getattr(player, "injury_proneness", 10) or 0))),
                ("Stamina", _word(getattr(player, "stamina", 30))),
            ]
            for label, value in rows:
                r = ctk.CTkFrame(card, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=3)
                body(r, label, dim=True, size=12).pack(side="left")
                ctk.CTkLabel(r, text=value, font=("Segoe UI", 12, "bold"),
                             text_color="white").pack(side="right")
            note = ""
            if injured:
                note = "Follow the medical team's timeline — rushing him back risks re-injury."
            elif (getattr(player, "injury_proneness", 0) or 0) > 12:
                note = "Injury-prone: consider managing his minutes in back-to-backs."
            if note:
                body(card, note, dim=True, size=11).pack(anchor="w", padx=16, pady=(10, 4))
            ctk.CTkButton(card, text="Close", width=120, fg_color="#00ceb8",
                          hover_color="#00b3a0", text_color="#0b0e11",
                          command=win.destroy).pack(pady=(8, 14))
        except Exception as e:
            print(f"Physio report failed: {e}")

    def _add_to_shortlist(self, player):
        """Add player to shortlist with category selection"""
        # Create shortlist dialog
        shortlist_dialog = InGamePopup(self.parent)
        shortlist_dialog.title("Add to Shortlist")
        shortlist_dialog.geometry("400x300")
        shortlist_dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        shortlist_dialog.resizable(False, False)
        
        # Make modal
        shortlist_dialog.transient(self.parent)
        shortlist_dialog.grab_set()
        
        # Title
        title_label = tk.Label(shortlist_dialog, 
                              text=f"Add {player.full_name} to Shortlist",
                              font=(getattr(self.parent, 'FONT_FAMILY', 'Segoe UI'), 14, 'bold'),
                              fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                              bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        title_label.pack(pady=10)
        
        # Category selection
        category_frame = tk.LabelFrame(shortlist_dialog, text="Category", 
                                      fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                      bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        category_frame.pack(fill='x', padx=20, pady=10)
        
        from shortlist_system import ShortlistManager
        category_var = tk.StringVar(value="Trade Targets")
        
        from tkinter import ttk
        category_combo = ttk.Combobox(category_frame, textvariable=category_var,
                                     values=ShortlistManager.CATEGORIES,
                                     state="readonly")
        category_combo.pack(fill='x', padx=10, pady=5)
        
        # Priority selection
        priority_frame = tk.LabelFrame(shortlist_dialog, text="Priority",
                                      fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                      bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        priority_frame.pack(fill='x', padx=20, pady=5)
        
        priority_var = tk.StringVar(value="Medium Priority")
        priority_combo = ttk.Combobox(priority_frame, textvariable=priority_var,
                                     values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                     state="readonly")
        priority_combo.pack(fill='x', padx=10, pady=5)
        
        # Notes
        notes_frame = tk.LabelFrame(shortlist_dialog, text="Notes",
                                   fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                   bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        notes_frame.pack(fill='both', expand=True, padx=20, pady=5)
        
        notes_text = tk.Text(notes_frame, height=4, wrap="word",
                            bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'),
                            fg=getattr(self.parent, 'TEXT_COLOR', 'white'))
        notes_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Buttons
        button_frame = tk.Frame(shortlist_dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def add_player():
            category = category_var.get()
            priority_text = priority_var.get()
            priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items() 
                           if v == priority_text), 2)
            notes = notes_text.get("1.0", "end-1c")
            
            # Get shortlist manager
            if hasattr(self.parent, 'shortlist_manager'):
                shortlist_manager = self.parent.shortlist_manager
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'shortlist_manager'):
                shortlist_manager = self.parent.parent.shortlist_manager
            else:
                messagebox.showerror("Error", "Shortlist manager not available.")
                shortlist_dialog.destroy()
                return
            
            # Add to shortlist
            if shortlist_manager.add_player(player.id, player.full_name, category, notes, priority):
                messagebox.showinfo("Added to Shortlist", 
                                   f"{player.full_name} added to {category}!")
                shortlist_dialog.destroy()
            else:
                messagebox.showwarning("Already on Shortlist", 
                                      f"{player.full_name} is already in {category}.")
        
        ttk.Button(button_frame, text="Add to Shortlist", command=add_player).pack(side="left")
        ttk.Button(button_frame, text="Cancel", command=shortlist_dialog.destroy).pack(side="right")
    
    def _compare_players(self, player):
        """Open enhanced player comparison tool"""
        # R8 (UI repairs): busy cursor while the comparison window builds.
        try:
            from ctk_theme import busy_cursor
            with busy_cursor(self.parent):
                self._create_enhanced_comparison_window(player)
        except Exception:
            self._create_enhanced_comparison_window(player)

    def _declare_rival(self, player):
        """Declare a personal rivalry with an opposing player (R6).

        Wires the context menu into the EXISTING rivalry system
        (reputation_system.declare_rivalry) -- the same entry point the
        Morale window's DeclareRivalPopup uses for team/coach declarations.
        Own-club players are refused with an explanation. Feed + inbox go
        through headlines.announce_rivalry_declaration like every other
        declaration. Never raises.
        """
        try:
            app = self._app()
            gm = getattr(app, "game_manager", None) or app
            league = getattr(gm, "league", None)
            team = getattr(app, "user_team", None)
            if league is None or team is None:
                messagebox.showwarning(
                    "Declare Rival",
                    "No active league to declare a rivalry in.")
                return
            own_ids = set()
            for attr in ("roster", "ahl_roster", "prospects"):
                for p in (getattr(team, attr, None) or []):
                    own_ids.add(getattr(p, "id", None))
            if getattr(player, "id", None) in own_ids:
                messagebox.showinfo(
                    "Declare Rival",
                    f"{getattr(player, 'full_name', 'That player')} plays "
                    "for your club.\n\nDeclare rival is for opposing players "
                    "and staff -- right-click their card to start a "
                    "personal beef.")
                return
            import reputation_system as rs
            try:
                existing = rs.rivalry_between(
                    getattr(league, "rivalries", None) or [],
                    rs.gm_persona(team), player, kind="gm_coach")
            except Exception:
                existing = None
            if existing and existing.get("user_declared"):
                messagebox.showinfo(
                    "Declare Rival",
                    f"You already declared "
                    f"{getattr(player, 'full_name', 'them')} a personal "
                    f"rival (heat {existing.get('intensity', 0):.0f}).")
                return
            # NOTE: kind="gm_coach" is the existing personal-beef kind the
            # rivalry system already understands (GM vs a person); _ekey
            # keys the player as ('player', id) so it never collides with
            # a coach record.
            rec = rs.declare_rivalry(league, rs.gm_persona(team), player,
                                     kind="gm_coach")
            if not rec:
                messagebox.showwarning("Declare Rival",
                                       "Could not register the rivalry.")
                return
            try:
                import headlines as hl
                gui = app if hasattr(app, "add_news") else (
                    getattr(app, "app", None) or app)
                target_team_name = "?"
                for t in (getattr(league, "teams", None) or []):
                    rosters = [getattr(t, a, None) or []
                               for a in ("roster", "ahl_roster", "prospects")]
                    if any(getattr(p, "id", None) == getattr(player, "id", None)
                           for r in rosters for p in r):
                        target_team_name = getattr(t, "team_name", "?")
                        break
                hl.announce_rivalry_declaration(
                    gui, getattr(team, "team_name", "?"), target_team_name,
                    getattr(player, "full_name", "?"), "coach")
            except Exception:
                pass
            messagebox.showinfo(
                "Rival Declared",
                f"Declared: {getattr(player, 'full_name', '?')} "
                f"(heat {rec.get('intensity', 70):.0f}). "
                "Those games just got personal.")
        except Exception as e:
            try:
                messagebox.showerror("Declare Rival",
                                     f"Could not declare rival: {e}")
            except Exception:
                pass
    
    def _show_comparison_results(self, player1, player2, compare_window):
        """Legacy entry point: render results into a frame in the given window."""
        results_frame = compare_window
        # If the window already has content, add a fresh results area
        try:
            import tkinter as tk
            results_frame = tk.Frame(compare_window)
            results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        except Exception:
            pass
        self._show_enhanced_comparison_results(player1, player2, results_frame)

    def _create_comparison_window(self, player):
        """Create comparison window (legacy; delegates to enhanced version)."""
        return self._create_enhanced_comparison_window(player)

    def _create_comparison_window_legacy(self, player):
        """Original comparison window (kept for reference)."""
        compare_window = InGamePopup(self.parent)
        compare_window.title(f"Compare Players - {player.full_name}")
        compare_window.geometry("600x500")
        
        # Configure window colors if parent has them
        if hasattr(self.parent, 'BG_COLOR'):
            compare_window.configure(bg=self.parent.BG_COLOR)
        
        # Header
        header_label = tk.Label(compare_window, 
                               text=f"Player Comparison - {player.full_name}",
                               font=('Segoe UI', 16, 'bold'))
        if hasattr(self.parent, 'HEADER_COLOR'):
            header_label.configure(fg=self.parent.HEADER_COLOR, bg=self.parent.BG_COLOR)
        header_label.pack(pady=20)
        
        # Instructions
        instructions = tk.Label(compare_window,
                               text="Select another player to compare attributes and potential",
                               font=('Segoe UI', 10))
        if hasattr(self.parent, 'TEXT_COLOR'):
            instructions.configure(fg=self.parent.TEXT_COLOR, bg=self.parent.BG_COLOR)
        instructions.pack(pady=10)
        
        # Player selection frame
        selection_frame = tk.Frame(compare_window)
        if hasattr(self.parent, 'BG_COLOR'):
            selection_frame.configure(bg=self.parent.BG_COLOR)
        selection_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Get all players for comparison
        all_players = []
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
        
        # Player selection
        select_label = tk.Label(selection_frame, text="Compare with:", font=('Segoe UI', 11, 'bold'))
        if hasattr(self.parent, 'TEXT_COLOR'):
            select_label.configure(fg=self.parent.TEXT_COLOR, bg=self.parent.BG_COLOR)
        select_label.pack(anchor='w')
        
        from tkinter import ttk
        compare_var = tk.StringVar()
        compare_combo = ttk.Combobox(selection_frame, textvariable=compare_var,
                                   values=[p.full_name for p in all_players if p != player],
                                   state='readonly', width=40)
        compare_combo.pack(anchor='w', pady=10, fill='x')
        
        def do_comparison():
            selected_name = compare_var.get()
            if selected_name:
                compare_player = next((p for p in all_players if p.full_name == selected_name), None)
                if compare_player:
                    self._show_comparison_results(player, compare_player, compare_window)
        
        compare_btn = ttk.Button(selection_frame, text="Compare Players", command=do_comparison)
        compare_btn.pack(pady=10)
    
    def _show_enhanced_comparison_results(self, player1, player2, results_frame):
        """Show enhanced comparison results in the provided frame"""
        # Clear existing results
        for widget in results_frame.winfo_children():
            widget.destroy()
        
        # Header
        header = tk.Label(results_frame, 
                         text=f"{player1.full_name} vs {player2.full_name}",
                         font=('Segoe UI', 14, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        header.pack(pady=10)
        
        # Create scrollable comparison
        from tkinter import ttk
        
        # Treeview for comparison
        columns = ('Attribute', player1.full_name, player2.full_name, 'Advantage')
        tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Attribute':
                tree.column(col, width=120)
            elif col == 'Advantage':
                tree.column(col, width=80)
            else:
                tree.column(col, width=100)
        
        # Comparison data
        comparison_data = [
            ("Overall Rating", player1.overall_rating(), player2.overall_rating()),
            ("Age", player1.age, player2.age),
            ("Potential", getattr(player1, 'potential', 10), getattr(player2, 'potential', 10)),
            ("Skating", getattr(player1, 'skating', 10), getattr(player2, 'skating', 10)),
            ("Shooting", getattr(player1, 'shooting', 10), getattr(player2, 'shooting', 10)),
            ("Passing", getattr(player1, 'passing', 10), getattr(player2, 'passing', 10)),
            ("Defense", getattr(player1, 'defense', 10), getattr(player2, 'defense', 10)),
            ("Hockey IQ", getattr(player1, 'hockey_iq', 10), getattr(player2, 'hockey_iq', 10)),
            ("Physical", getattr(player1, 'physical', 10), getattr(player2, 'physical', 10)),
        ]
        
        for stat, val1, val2 in comparison_data:
            # Determine advantage
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if val1 > val2:
                    advantage = player1.full_name[:10] + "..."
                elif val2 > val1:
                    advantage = player2.full_name[:10] + "..."
                else:
                    advantage = "Tied"
            else:
                advantage = "N/A"
            
            tree.insert('', 'end', values=(stat, str(val1), str(val2), advantage))
        
        tree.pack(fill='both', expand=True, pady=10)
        
        # Summary
        summary_frame = tk.Frame(results_frame, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        summary_frame.pack(fill='x', pady=10)
        
        # Calculate overall advantage
        p1_advantages = sum(1 for _, v1, v2 in comparison_data 
                           if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v1 > v2)
        p2_advantages = sum(1 for _, v1, v2 in comparison_data 
                           if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v2 > v1)
        
        if p1_advantages > p2_advantages:
            winner = player1.full_name
            margin = "significant" if p1_advantages - p2_advantages > 3 else "slight"
        elif p2_advantages > p1_advantages:
            winner = player2.full_name
            margin = "significant" if p2_advantages - p1_advantages > 3 else "slight"
        else:
            winner = "Neither player"
            margin = "very close"
        
        summary_text = f"Summary: {winner} has a {margin} advantage overall."
        
        summary_label = tk.Label(summary_frame, text=summary_text, font=('Segoe UI', 11, 'bold'),
                               fg=getattr(self.parent, 'ACCENT_COLOR', '#D13438'),
                               bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        summary_label.pack()
    
    def _assign_training_focus(self, player):
        """Open training focus assignment"""
        try:
            # Try to open development window with player pre-selected
            if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'open_development_window'):
                self.parent.parent.open_development_window()
                messagebox.showinfo("Development Window", f"Development window opened. Select {player.full_name} for training assignment.")
            elif hasattr(self.parent, 'open_development_window'):
                self.parent.open_development_window()
                messagebox.showinfo("Development Window", f"Development window opened. Select {player.full_name} for training assignment.")
            else:
                # Create training assignment dialog
                self._create_training_assignment_dialog(player)
        except Exception:
            self._create_training_assignment_dialog(player)
    
    def _create_training_assignment_dialog(self, player):
        """Create training assignment dialog"""
        dialog = InGamePopup(self.parent)
        dialog.title(f"Training Assignment - {player.full_name}")
        dialog.geometry("400x350")
        dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header
        header = tk.Label(dialog, text=f"Assign Training for {player.full_name}", 
                         font=('Segoe UI', 12, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header.pack(pady=15)
        
        # Current attributes display
        current_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        current_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(current_frame, text="Current Attributes:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        attributes = [
            ('Skating', getattr(player, 'skating', 10)),
            ('Shooting', getattr(player, 'shooting', 10)),
            ('Passing', getattr(player, 'passing', 10)),
            ('Defense', getattr(player, 'defense', 10)),
        ]
        
        for attr_name, value in attributes:
            attr_text = f"{attr_name}: {value}"
            tk.Label(current_frame, text=attr_text, font=('Segoe UI', 9),
                    fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                    bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        # Training focus selection
        focus_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        focus_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(focus_frame, text="Select Training Focus:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        from tkinter import ttk
        focus_var = tk.StringVar()
        focus_options = ["Skating", "Shooting", "Passing", "Defense", "Physical Conditioning", "Hockey IQ"]
        focus_combo = ttk.Combobox(focus_frame, textvariable=focus_var,
                                 values=focus_options, state='readonly')
        focus_combo.pack(fill='x', pady=5)
        
        # Training intensity
        intensity_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        intensity_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(intensity_frame, text="Training Intensity:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        intensity_var = tk.StringVar(value="Medium")
        intensities = ["Light", "Medium", "Heavy"]
        for intensity in intensities:
            tk.Radiobutton(intensity_frame, text=intensity, variable=intensity_var, value=intensity,
                         fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                         bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                         selectcolor=getattr(self.parent, 'ACCENT_COLOR', '#D13438')).pack(anchor='w')
        
        def assign_training():
            # Real assignment: mirror the Development Center's _assign_training
            # -- write to the shared training registry (ACTIVE_TRAINING_PROGRAMS
            # + the persistent game-manager mirror), gated by can_practice, and
            # run a real first session through the practice engine.
            if not focus_var.get():
                messagebox.showwarning("No Focus Selected",
                                       "Select a training focus first.")
                return
            try:
                from enhanced_practice_system import (
                    PracticeEngine, PracticeType, PracticeIntensity,
                    ACTIVE_TRAINING_PROGRAMS)
            except Exception:
                messagebox.showwarning(
                    "Training Unavailable",
                    "The training system isn't available right now.")
                return
            focus_label = focus_var.get()
            intensity_label = intensity_var.get()
            focus_map = {
                "Skating": PracticeType.SKATING,
                "Shooting": PracticeType.SHOOTING,
                "Passing": PracticeType.PASSING,
                "Defense": PracticeType.DEFENSE,
                "Physical Conditioning": PracticeType.CONDITIONING,
                "Hockey IQ": PracticeType.HOCKEY_IQ,
            }
            intensity_map = {
                "Light": PracticeIntensity.LIGHT,
                "Medium": PracticeIntensity.MODERATE,
                "Heavy": PracticeIntensity.INTENSE,
            }
            practice_type = focus_map.get(focus_label)
            intensity = intensity_map.get(intensity_label,
                                          PracticeIntensity.MODERATE)
            if practice_type is None:
                messagebox.showwarning("Unknown Focus",
                                       f"No training program for '{focus_label}'.")
                return
            engine = PracticeEngine()
            can, reason = engine.can_practice(player, practice_type,
                                              intensity)
            if not can:
                messagebox.showwarning("Cannot Train Right Now", reason)
                return
            # Record the program (shared registry; survives window close),
            # stamped with the game date and mirrored into the persistent
            # game-manager dict so it survives saves/restarts.
            app = self._app()
            from datetime import date as _date
            game_date = getattr(app, 'current_date', None) or _date.today()
            prog = {
                'focus': focus_label,
                'intensity': intensity_label,
                'assigned': game_date,
                'player_name': player.full_name,
            }
            try:
                ACTIVE_TRAINING_PROGRAMS[player.id] = prog
                gm = getattr(app, 'game_manager', None)
                if gm is not None:
                    if not getattr(gm, 'training_programs', None):
                        gm.training_programs = {}
                    gm.training_programs[player.id] = prog
            except Exception:
                pass
            # Run the first session for real through the practice engine.
            try:
                session = engine.execute_practice(player, practice_type,
                                                  intensity, 60, 12)
                result_text = (f"{player.full_name} assigned to "
                               f"{intensity_label.lower()} {focus_label.lower()} "
                               f"training.\n\nFirst session complete: "
                               f"+{session.skill_gain:.2f} skill, "
                               f"+{session.fatigue_cost}% fatigue.")
            except Exception:
                result_text = (f"{player.full_name} assigned to "
                               f"{intensity_label.lower()} {focus_label.lower()} "
                               f"training.\n\nThe program is recorded; the "
                               f"first session will run at the next practice.")
            messagebox.showinfo("Training Assigned", result_text)
            dialog.destroy()
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        button_frame.pack(fill='x', padx=20, pady=15)
        
        ttk.Button(button_frame, text="Assign Training", command=assign_training).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def _view_development_history(self, player):
        """Show player development history -- built only from real stores.

        Sources: the shared training registry (current program) and the
        practice engine's per-player session history. Anything without a
        real record is omitted, never invented."""
        lines = [f"Development History - {player.full_name}", ""]
        app = self._app()
        prog = None
        try:
            from enhanced_practice_system import (
                PracticeEngine, ACTIVE_TRAINING_PROGRAMS)
            gm = getattr(app, 'game_manager', None)
            if gm is not None and getattr(gm, 'training_programs', None):
                prog = gm.training_programs.get(player.id)
            if prog is None:
                prog = ACTIVE_TRAINING_PROGRAMS.get(player.id)
        except Exception:
            prog = None
            PracticeEngine = None
        if prog:
            lines.append(
                f"Current program: {prog.get('focus', '?')} -- "
                f"{prog.get('intensity', '?')} intensity "
                f"(assigned {prog.get('assigned', 'unknown date')})")
        else:
            lines.append("Current program: none assigned")
        lines.append("")
        history = None
        try:
            if PracticeEngine is not None:
                history = PracticeEngine().get_player_history(player.id)
        except Exception:
            history = None
        sessions = (history.recent_sessions[-5:]
                    if history and history.recent_sessions else [])
        if sessions:
            lines.append("Recent sessions:")
            for s in reversed(sessions):
                try:
                    ptype = (s.practice_type.value.replace('_', ' ').title()
                             if hasattr(s.practice_type, 'value')
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
            lines.append(f"Total recorded sessions: "
                         f"{getattr(history, 'total_sessions', 0)}")
        else:
            lines.append("No recorded practice sessions yet.")
        messagebox.showinfo("Development History", "\n".join(lines))
    
    def _view_contract_details(self, player):
        """Open the player profile screen with the contract tab selected."""
        try:
            app = self._app()
            view = None
            if hasattr(app, "open_player_profile"):
                view = app.open_player_profile(player)
            # Focus on the contract tab (tab index 3 based on order: Overview, Attributes, Stats, Contract, Development)
            if view is not None and hasattr(view, "notebook"):
                view.notebook.select(3)
                return
            raise RuntimeError("profile screen did not return a view")
        except (ImportError, Exception) as e:
            # Fallback to message box if profile window unavailable --
            # real fields only; no contract on file is stated honestly,
            # never fabricated.
            contract = getattr(player, 'contract', None)
            if contract:
                salary = f"${getattr(contract, 'salary', 0):,}"
                years = getattr(contract, 'years_remaining', 0)
                clauses = []
                if getattr(contract, 'no_movement_clause', False):
                    clauses.append("no-movement clause")
                elif getattr(contract, 'no_trade_clause', False):
                    clauses.append("no-trade clause")
                prot = f"\nTrade Protection: {', '.join(clauses)}" if clauses else ""
                status = "Active"
            else:
                salary = "No contract on file"
                years = 0
                prot = ""
                status = "Unsigned"
            messagebox.showinfo(
                "Contract Details",
                f"Contract Information - {player.full_name}\n\n"
                f"Salary: {salary}\n"
                f"Contract Length: {years} year(s) remaining{prot}\n"
                f"Status: {status}"
            )
    
    def _move_between_rosters(self, player):
        """Move player between rosters via the real transaction machinery.

        NHL -> AHL goes through app.send_to_ahl (waivers/NMC rules);
        AHL -> NHL through app.call_up_to_nhl (paper-transaction rule);
        an unsigned rights-held prospect goes to the real ELC signing flow.
        No invented roster logic -- anything without a real path says so."""
        app = self._app()
        team = getattr(app, 'user_team', None) if app is not None else None
        if team is None:
            messagebox.showwarning("Roster Management",
                                   "No team loaded -- can't move anyone.")
            return
        in_nhl = player in (getattr(team, 'roster', []) or [])
        in_ahl = player in (getattr(team, 'ahl_roster', []) or [])
        in_prospects = player in (getattr(team, 'prospects', []) or [])
        if in_nhl:
            if hasattr(app, 'send_to_ahl'):
                app.send_to_ahl(player)
            else:
                messagebox.showwarning(
                    "Roster Management",
                    "Demotion isn't available from here right now.")
        elif in_ahl:
            if hasattr(app, 'call_up_to_nhl'):
                app.call_up_to_nhl(player)
            else:
                messagebox.showwarning(
                    "Roster Management",
                    "Call-up isn't available from here right now.")
        elif in_prospects:
            if hasattr(app, 'open_contract_negotiation_window'):
                app.open_contract_negotiation_window(player, is_elc=True)
            else:
                messagebox.showwarning(
                    "Roster Management",
                    "ELC signing isn't available from here right now.")
        else:
            messagebox.showinfo(
                "Roster Management",
                f"{player.full_name} isn't on your NHL roster, AHL roster, "
                f"or prospect list -- there's nothing to move.")

    def _analyze_trade_value(self, player):
        """R3(b): show the trade-value reasoning breakdown for a player.

        Surfaces trade_engine.player_trade_value_breakdown(): what drives
        the value -- OVR base, age curve, potential, contract efficiency,
        volatility, goalie premium, RFA-impasse rights. Read-only; never
        raises (falls back to a plain note when the engine is unhappy).
        """
        total, comps = None, []
        try:
            import trade_engine as _te
            total, comps = _te.player_trade_value_breakdown(player)
        except Exception:
            total, comps = None, []
        pname = getattr(player, 'full_name', str(player))
        dialog = InGamePopup(self.parent)
        dialog.title(f"Trade Value - {pname}")
        dialog.geometry("520x480")
        _bg = getattr(self.parent, 'BG_COLOR', '#1E1E1E')
        _fg = getattr(self.parent, 'TEXT_COLOR', 'white')
        _dim = getattr(self.parent, 'TEXT_SECONDARY', '#a1a1aa')
        _acc = getattr(self.parent, 'ACCENT_COLOR', '#4FC3F7')
        dialog.configure(bg=_bg)

        tk.Label(dialog, text=f"{pname}",
                 font=('Segoe UI', 13, 'bold'), fg=_fg, bg=_bg
                 ).pack(anchor='w', padx=20, pady=(16, 2))
        try:
            _pos = player.primary_position.value
            _age = getattr(player, 'age', '?')
            _sub = f"{_pos} - age {_age}"
        except Exception:
            _sub = ""
        if _sub:
            tk.Label(dialog, text=_sub, font=('Segoe UI', 10),
                     fg=_dim, bg=_bg).pack(anchor='w', padx=20)

        if total is None:
            tk.Label(dialog, text="Value analysis unavailable.",
                     font=('Segoe UI', 11), fg=_dim, bg=_bg,
                     wraplength=460, justify='left'
                     ).pack(anchor='w', padx=20, pady=16)
        else:
            tk.Label(dialog, text=f"Trade value: {total} pick-points",
                     font=('Segoe UI', 12, 'bold'), fg=_acc, bg=_bg
                     ).pack(anchor='w', padx=20, pady=(8, 2))
            tk.Label(dialog, text="(a 1st-round pick ~= 1000)",
                     font=('Segoe UI', 9), fg=_dim, bg=_bg
                     ).pack(anchor='w', padx=20, pady=(0, 8))
            body = tk.Frame(dialog, bg=_bg)
            body.pack(fill='both', expand=True, padx=20, pady=(0, 8))
            for c in comps:
                row = tk.Frame(body, bg=_bg)
                row.pack(fill='x', pady=3)
                _d = c.get('delta', 0)
                _sign = "+" if _d >= 0 else ""
                tk.Label(row, text=f"{_sign}{_d}",
                         font=('Segoe UI', 10, 'bold'),
                         fg='#6fcf7f' if _d >= 0 else '#e5484d',
                         bg=_bg, width=7, anchor='e'
                         ).pack(side='left')
                tk.Label(row, text=c.get('label', ''),
                         font=('Segoe UI', 10, 'bold'), fg=_fg, bg=_bg,
                         anchor='w').pack(side='left', padx=(8, 0))
                tk.Label(body, text=c.get('detail', ''),
                         font=('Segoe UI', 9), fg=_dim, bg=_bg,
                         wraplength=460, justify='left'
                         ).pack(anchor='w', padx=(52, 0), pady=(0, 4))

        tk.Button(dialog, text="Close", command=dialog.destroy,
                  font=('Segoe UI', 10, 'bold'),
                  bg=_acc, fg='white', relief='flat',
                  padx=18, pady=6).pack(pady=(4, 16))

    def _propose_trade(self, player):
        """Open the Trade Center with this player pre-loaded on the table.

        The fake 'proposal sent' fallback dialog is gone: if the real trade
        window can't be reached, say so honestly instead of inventing a
        sent proposal."""
        app = None
        if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'open_trade_window'):
            app = self.parent.parent
        elif hasattr(self.parent, 'open_trade_window'):
            app = self.parent
        if app is None or not hasattr(app, 'open_trade_window'):
            messagebox.showwarning(
                "Trade Center Unavailable",
                "The Trade Center can't be opened from here right now -- "
                "no proposal was created.")
            return
        try:
            user_team = getattr(app, 'user_team', None)
            rosters = []
            if user_team is not None:
                rosters = (list(getattr(user_team, 'roster', []) or []) +
                           list(getattr(user_team, 'ahl_roster', []) or []) +
                           list(getattr(user_team, 'prospects', []) or []))
            own = player in rosters
            preset = {"partner": self._trade_partner_for(app, player, own),
                      "user_assets": [player] if own else [],
                      "partner_assets": [] if own else [player],
                      "mode": "new"}
            app.open_trade_window(preset=preset)
        except Exception as e:
            messagebox.showwarning(
                "Trade Center Unavailable",
                f"Couldn't open the Trade Center ({e}) -- "
                "no proposal was created.")

    @staticmethod
    def _trade_partner_for(app, player, own):
        """Best-guess trade partner: the player's team (or first rival)."""
        try:
            league = getattr(getattr(app, 'game_manager', app), 'league', None)
            if league is not None and not own:
                for t in getattr(league, 'teams', []) or []:
                    rosters = (list(getattr(t, 'roster', []) or []) +
                               list(getattr(t, 'ahl_roster', []) or []) +
                               list(getattr(t, 'prospects', []) or []))
                    if player in rosters:
                        return t
            teams = [t for t in getattr(league, 'teams', []) or []
                     if t is not getattr(app, 'user_team', None)]
            return teams[0] if teams else None
        except Exception:
            return None
    
    def _create_enhanced_comparison_window(self, player):
        """Create enhanced comparison window with better styling and functionality"""
        compare_window = InGamePopup(self.parent)
        compare_window.title(f"Player Comparison - {player.full_name}")
        compare_window.geometry("900x700")
        compare_window.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header frame
        header_frame = tk.Frame(compare_window, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header_frame.pack(fill='x', pady=10)
        
        header_label = tk.Label(header_frame, 
                               text=f"Player Comparison Tool",
                               font=('Segoe UI', 18, 'bold'))
        header_label.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'), 
                              bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header_label.pack()
        
        # Main content frame with notebook
        from tkinter import ttk
        notebook = ttk.Notebook(compare_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Quick Compare tab
        quick_tab = ttk.Frame(notebook)
        notebook.add(quick_tab, text="Quick Compare")
        self._create_quick_compare_tab(quick_tab, player)
        
        # Detailed Analysis tab
        detailed_tab = ttk.Frame(notebook)
        notebook.add(detailed_tab, text="Detailed Analysis")
        self._create_detailed_analysis_tab(detailed_tab, player)
        
        # Position Comparison tab
        position_tab = ttk.Frame(notebook)
        notebook.add(position_tab, text="Position Peers")
        self._create_position_comparison_tab(position_tab, player)
    
    def _create_quick_compare_tab(self, parent, player1):
        """Create quick comparison tab"""
        # Player selection frame
        selection_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        selection_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(selection_frame, text="Compare with:", 
                font=('Segoe UI', 12, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A')).pack(anchor='w', pady=5)
        
        # Get all available players (recently-viewed + own club first,
        # R2 revised; subject excluded at the source).
        all_players = self._get_all_players(exclude=player1)
        
        from tkinter import ttk
        compare_var = tk.StringVar()
        compare_combo = ttk.Combobox(selection_frame, textvariable=compare_var,
                                   values=[p.full_name for p in all_players],
                                   state='readonly', width=40, font=('Segoe UI', 10))
        compare_combo.pack(anchor='w', pady=5, fill='x')
        
        # Results frame
        results_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        def do_quick_comparison():
            selected_name = compare_var.get()
            if selected_name:
                compare_player = next((p for p in all_players if p.full_name == selected_name), None)
                if compare_player:
                    self._show_enhanced_comparison_results(player1, compare_player, results_frame)
        
        compare_btn = ttk.Button(selection_frame, text="Compare Players", command=do_quick_comparison)
        compare_btn.pack(pady=10)
    
    def _create_detailed_analysis_tab(self, parent, player):
        """Create detailed analysis tab"""
        content_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Player analysis
        analysis_text = self._generate_detailed_analysis(player)
        
        from tkinter import scrolledtext
        analysis_display = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=80, height=25,
                                                   font=('Consolas', 10),
                                                   bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                                                   fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                                   insertbackground=getattr(self.parent, 'TEXT_COLOR', 'white'))
        analysis_display.pack(fill='both', expand=True)
        analysis_display.insert('1.0', analysis_text)
        analysis_display.config(state='disabled')
    
    def _create_position_comparison_tab(self, parent, player):
        """Create position peers comparison tab"""
        content_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(content_frame, text=f"Position Peers - {player.primary_position.value}",
                font=('Segoe UI', 14, 'bold'),
                fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A')).pack(pady=10)
        
        # Get players of same position
        same_position_players = [p for p in self._get_all_players() 
                               if p.primary_position == player.primary_position and p != player]
        
        # Sort by overall rating
        same_position_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Display top 10 peers
        peers_text = f"Top {min(10, len(same_position_players))} {player.primary_position.value} players:\n\n"
        
        for i, peer in enumerate(same_position_players[:10], 1):
            peers_text += f"{i:2}. {peer.full_name:<25} OVR: {peer.overall_rating():2} Age: {peer.age:2}\n"
        
        peers_text += f"\n{player.full_name} ranks approximately #{same_position_players.index(player) + 1 if player in same_position_players else 'Unknown'} among {player.primary_position.value} players."
        
        from tkinter import scrolledtext
        peers_display = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=80, height=20,
                                                font=('Consolas', 10),
                                                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                                                fg=getattr(self.parent, 'TEXT_COLOR', 'white'))
        peers_display.pack(fill='both', expand=True, pady=10)
        peers_display.insert('1.0', peers_text)
        peers_display.config(state='disabled')
    
    def _get_all_players(self, exclude=None):
        """EHM/FM24-style default compare list (R2 revised).

        Order: recently-viewed players first (most-recent first), then the
        user's own club -- NHL roster, AHL, prospects -- sorted by OVR
        desc. Falls back to the league pool when the user team is
        unavailable so the dropdown is never empty. De-duped, capped at
        200 for performance.
        """
        app = self._app()
        team = getattr(app, "user_team", None) if app is not None else None
        excl_id = getattr(exclude, "id", None)

        ordered, seen = [], set()

        def _add(p):
            pid = getattr(p, "id", None)
            key = pid if pid is not None else id(p)
            if key in seen or (pid is not None and pid == excl_id):
                return
            seen.add(key)
            ordered.append(p)

        # 1. Recently viewed -- the FM24/EHM default.
        for rp in get_recently_viewed_players(app, exclude=exclude):
            _add(rp)

        # 2. Own club: NHL + AHL + prospects, best first.
        club = []
        if team is not None:
            for attr in ("roster", "ahl_roster", "prospects"):
                club.extend(getattr(team, attr, None) or [])
        if not club and app is not None:
            try:
                gm = getattr(app, "game_manager", None) or app
                league = getattr(gm, "league", None)
                for t in (getattr(league, "teams", None) or []):
                    club.extend(getattr(t, "roster", None) or [])
            except Exception:
                pass
        club.sort(key=_player_sort_key)
        for cp in club:
            _add(cp)

        return ordered[:200]

    def _generate_detailed_analysis(self, player):
        """Generate detailed player analysis text"""
        analysis = f"DETAILED PLAYER ANALYSIS\n"
        analysis += f"{'='*50}\n\n"
        
        analysis += f"Player: {player.full_name}\n"
        analysis += f"Position: {player.primary_position.value}\n"
        analysis += f"Age: {player.age}\n"
        analysis += f"Overall Rating: {player.overall_rating()}\n\n"
        
        # Attributes analysis
        analysis += f"ATTRIBUTES BREAKDOWN\n"
        analysis += f"{'-'*25}\n"
        
        attributes = [
            ('Skating', getattr(player, 'skating', 'N/A')),
            ('Shooting', getattr(player, 'shooting', 'N/A')),
            ('Passing', getattr(player, 'passing', 'N/A')),
            ('Defense', getattr(player, 'defense', 'N/A')),
            ('Hockey IQ', getattr(player, 'hockey_iq', 'N/A')),
            ('Physical', getattr(player, 'physical', 'N/A')),
        ]
        
        for attr_name, value in attributes:
            if value != 'N/A':
                rating = "Elite" if value >= 18 else "Excellent" if value >= 16 else "Good" if value >= 14 else "Average" if value >= 12 else "Below Average"
                analysis += f"{attr_name:<15}: {value:2} ({rating})\n"
        
        analysis += f"\nSTRENGTHS & WEAKNESSES\n"
        analysis += f"{'-'*25}\n"
        
        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for attr_name, value in attributes:
            if value != 'N/A':
                if value >= 16:
                    strengths.append(attr_name)
                elif value <= 10:
                    weaknesses.append(attr_name)
        
        if strengths:
            analysis += f"Strengths: {', '.join(strengths)}\n"
        if weaknesses:
            analysis += f"Weaknesses: {', '.join(weaknesses)}\n"
        
        analysis += f"\nDEVELOPMENT RECOMMENDATION\n"
        analysis += f"{'-'*25}\n"
        
        if player.age <= 20:
            analysis += "High development potential due to young age.\n"
        elif player.age <= 25:
            analysis += "Good development potential in prime years.\n"
        else:
            analysis += "Limited development potential due to age.\n"
        
        if weaknesses:
            analysis += f"Focus training on: {', '.join(weaknesses[:2])}\n"
        
        return analysis

def bind_player_context(widget, player_or_getter, parent_window):
    """Right-click (or Shift+F10) on ANY widget showing a player name.

    The EHM/FM24 interaction: every player name in the game opens the
    standard player menu. player_or_getter is either a player object or
    a callable(event) -> player (for rows/cells resolved at click time).

    One line per surface:
        bind_player_context(name_label, player, self)
    """
    mgr = PlayerContextMenu(parent_window)

    def _show(event):
        try:
            player = (player_or_getter(event) if callable(player_or_getter)
                      else player_or_getter)
        except Exception:
            player = None
        if player is not None:
            mgr.show_context_menu(event, player)

    try:
        widget.bind("<Button-3>", _show)
    except Exception:
        pass
    try:
        # Keyboard alternative (accessibility): Shift+F10 opens it too.
        widget.bind("<Shift-F10>", _show)
    except Exception:
        pass
    return mgr


def add_player_context_menu(treeview, parent_window):
    """
    Helper function to add player context menu to any treeview widget
    
    Args:
        treeview: The treeview widget containing players
        parent_window: The parent window instance
    """
    context_menu_manager = PlayerContextMenu(parent_window)
    
    def on_right_click(event):
        # Identify which item was right-clicked
        item_id = treeview.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item
        treeview.selection_set(item_id)
        
        # Get the player object from tree_maps
        player = None
        if hasattr(parent_window, 'parent') and hasattr(parent_window.parent, 'tree_maps'):
            player = parent_window.parent.tree_maps.get(treeview, {}).get(item_id)
        elif hasattr(parent_window, 'tree_maps'):
            player = parent_window.tree_maps.get(treeview, {}).get(item_id)
        
        if player:
            context_menu_manager.show_context_menu(event, player)
    
    treeview.bind('<Button-3>', on_right_click)
    return context_menu_manager