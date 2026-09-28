"""
Enhanced Staff Management Window for Hockey Manager
Provides comprehensive staff hiring, firing, and management with EHM-style depth.

CustomTkinter rebuild: CTkToplevel, CTkTabview tabs, pill/segmented filters,
styled dark treeview with rating-tier and morale tags, CTk dialogs.
"""

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from typing import List

import customtkinter as ctk

from game_classes import Staff, StaffRole
from game_classes import debug_print
from ctk_theme import (
    init_ctk_theme, primary_button, secondary_button, heading, body,
    TEAL, TEAL_HOVER, TEAL_DARK, BG, PANEL, CARD, BORDER,
    TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
    ROW_HOVER, ROW_SELECTED,
)


class StaffManagementWindow(InGamePopup):
    """Comprehensive staff management interface with EHM-style functionality."""

    # Roles whose attributes are verifiably read by the sim engine (scouting.py)
    _SCOUT_ROLES = {StaffRole.HEAD_SCOUT, StaffRole.PROFESSIONAL_SCOUT,
                    StaffRole.AMATEUR_SCOUT, StaffRole.EUROPEAN_SCOUT,
                    StaffRole.ADVANCE_SCOUT}

    def __init__(self, parent):
        init_ctk_theme()
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, TEAL_DARK=TEAL_DARK,
                        BG=BG, PANEL=PANEL, CARD=CARD, BORDER=BORDER,
                        TEXT=TEXT, TEXT_DIM=TEXT_DIM, TEXT_FAINT=TEXT_FAINT,
                        GOLD=GOLD, GREEN=GREEN, RED=RED, BLUE=BLUE,
                        ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        self._ff = getattr(parent, 'FONT_FAMILY', 'Segoe UI')

        super().__init__(parent)
        self.parent = parent
        self.title("Staff Management - Hockey Manager")
        self.configure(fg_color=BG)
        self.geometry("1280x860")

        # Staff candidates hired through the Free Agency window land here briefly
        # during negotiation; the authoritative lists live on the team/league.
        self.available_staff: List[Staff] = []

        # Checkbox-style multi-select state (like the trade block)
        self.selected_staff = set()
        self.staff_map = {}
        self.sort_column = None
        self.sort_reverse = False

        self._setup_tree_style()
        self.create_widgets()

        # Update current staff view only (hiring is handled in the Free Agency window)
        self.update_current_staff_view()

        # Track window under the same key the main app uses
        self.parent.open_windows['staff_management'] = self
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Unregister from the main app's window tracker and close."""
        try:
            self.parent.open_windows.pop('staff_management', None)
        except Exception:
            pass
        self.destroy()

    def _get_user_team(self):
        """Return the user's team from live game state (never fabricated).

        Prefers the game manager's canonical user_team reference, falling back
        to the is_user_team scan used elsewhere in the codebase.
        """
        gm = getattr(self.parent, 'game_manager', None)
        team = getattr(gm, 'user_team', None) if gm is not None else None
        if team is not None:
            return team
        league = getattr(gm, 'league', None) if gm is not None else None
        if league is not None:
            return next((t for t in league.teams if t.is_user_team), None)
        return None

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the staff table (styled ttk.Treeview, per the
        migration guide -- the table carries 11 sortable columns and several
        color tags)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Staff.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=28,
                        font=(self._ff, 10))
        style.configure('Staff.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=(self._ff, 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Staff.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Staff.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Staff.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Staff.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _rating_tag(self, rating):
        """Tier tag for the staff table's Rating column.

        Staff overall_rating is a 0-20 computed property (displayed raw,
        matching the Free Agency staff list), so tiers are scaled to it.
        """
        if rating >= 16:
            return 'rating_elite'
        if rating >= 13:
            return 'rating_good'
        if rating >= 10:
            return 'rating_avg'
        return None

    def _card(self, parent, **kw):
        """Rounded dark card frame."""
        kw.setdefault('fg_color', self._ct['CARD'])
        kw.setdefault('corner_radius', 10)
        return ctk.CTkFrame(parent, **kw)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def create_widgets(self):
        """Create the main interface widgets."""
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header card
        header = self._card(main)
        header.pack(fill="x", pady=(0, 10))
        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        self._heading(top, text="Staff Management", size=20).pack(side="left")
        accent = ctk.CTkFrame(header, fg_color=ct['TEAL'], height=3, corner_radius=2)
        accent.pack(fill="x", padx=16, pady=(4, 12))

        # Tabs (CTkTabview instead of ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            main,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
            command=self._on_tabview_change,
        )
        self.tabview.pack(fill="both", expand=True)
        for name in ("Current Staff", "Hire Staff", "Organization"):
            self.tabview.add(name)

        self.create_current_staff_tab()
        self.create_available_staff_auto_redirect_tab()
        self.create_staff_overview_tab()

    def create_current_staff_tab(self):
        """Current staff management tab with trade-block-style interaction."""
        ct = self._ct
        frame = self.tabview.tab("Current Staff")
        frame.configure(fg_color=ct['PANEL'])

        # Staff summary card
        summary_card = self._card(frame)
        summary_card.pack(fill="x", padx=12, pady=(10, 0))
        self.staff_summary_label = ctk.CTkLabel(
            summary_card, text="", font=(self._ff, 11, "bold"),
            text_color=ct['TEXT'], anchor="w")
        self.staff_summary_label.pack(fill="x", padx=14, pady=10)

        # Filter card
        filter_card = self._card(frame)
        filter_card.pack(fill="x", padx=12, pady=(10, 0))
        finner = ctk.CTkFrame(filter_card, fg_color="transparent")
        finner.pack(fill="x", padx=14, pady=10)

        def _flabel(text):
            return ctk.CTkLabel(finner, text=text, font=(self._ff, 10),
                                text_color=ct['TEXT_DIM'])

        _flabel("Department:").pack(side="left")
        dept_options = ["All", "Management", "Coaching", "Development",
                        "Scouting", "Medical", "Analytics"]
        self.dept_combo = ctk.CTkComboBox(
            finner, values=dept_options, width=140, state="readonly",
            fg_color=ct['BG'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'],
            command=lambda v: self.update_current_staff_view())
        self.dept_combo.set("All")
        self.dept_combo.pack(side="left", padx=(4, 10))

        _flabel("Min Rating:").pack(side="left")
        self.min_rating_entry = ctk.CTkEntry(
            finner, width=56, placeholder_text="0",
            fg_color=ct['BG'], border_color=ct['BORDER'], text_color=ct['TEXT'])
        self.min_rating_entry.pack(side="left", padx=(4, 10))

        _flabel("Max Salary:").pack(side="left")
        self.max_salary_entry = ctk.CTkEntry(
            finner, width=90, placeholder_text="$",
            fg_color=ct['BG'], border_color=ct['BORDER'], text_color=ct['TEXT'])
        self.max_salary_entry.pack(side="left", padx=(4, 10))

        _flabel("Contract:").pack(side="left")
        self.contract_combo = ctk.CTkComboBox(
            finner, values=["All", "Expiring", "Long-term"], width=120,
            state="readonly",
            fg_color=ct['BG'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'],
            command=lambda v: self.update_current_staff_view())
        self.contract_combo.set("All")
        self.contract_combo.pack(side="left", padx=(4, 10))

        self._secondary_button(finner, text="Apply Filter",
                               command=self.update_current_staff_view,
                               width=110, height=32).pack(side="left", padx=8)

        # Main staff list card
        panel_card = self._card(frame)
        panel_card.pack(fill="both", expand=True, padx=12, pady=10)

        # Staff treeview with trade-block-style columns
        columns = {
            'sel': ('', 30),
            'name': ('Name', 170),
            'role': ('Position', 170),
            'dept': ('Department', 110),
            'overall': ('Rating', 60),
            'experience': ('Exp', 50),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'status': ('Status', 90),
            'key_skills': ('Key Skills', 200)
        }

        tree_holder = ctk.CTkFrame(panel_card, fg_color="transparent")
        tree_holder.pack(fill="both", expand=True, padx=10, pady=10)

        self.current_staff_tree = ttk.Treeview(
            tree_holder, columns=list(columns.keys()), show='headings',
            height=15, style='Staff.Treeview')

        for col, (text, width) in columns.items():
            self.current_staff_tree.heading(
                col, text=text, command=lambda c=col: self._sort_staff_treeview(c))
            self.current_staff_tree.column(
                col, width=width,
                anchor='center' if col != 'key_skills' else 'w')

        scrollbar = ttk.Scrollbar(tree_holder, orient="vertical",
                                  command=self.current_staff_tree.yview,
                                  style='Staff.Vertical.TScrollbar')
        self.current_staff_tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.current_staff_tree.pack(side="left", fill="both", expand=True)

        # Bind events like trade block
        self.current_staff_tree.bind("<Button-1>", self._handle_staff_checkbox_click)
        self.current_staff_tree.bind("<Double-1>", self._handle_staff_double_click)
        self.current_staff_tree.bind("<Button-3>", self.show_staff_context_menu)

        # Row tags: selection + morale + rating tiers
        self.current_staff_tree.tag_configure('selected',
                                              background=ct['ROW_SELECTED'])
        self.current_staff_tree.tag_configure('high_morale', foreground=ct['GREEN'])
        self.current_staff_tree.tag_configure('low_morale', foreground=ct['RED'])
        self.current_staff_tree.tag_configure('rating_elite', foreground=ct['GREEN'])
        self.current_staff_tree.tag_configure('rating_good', foreground=ct['TEAL'])
        self.current_staff_tree.tag_configure('rating_avg', foreground=ct['GOLD'])

        # Action buttons
        button_frame = ctk.CTkFrame(panel_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self._secondary_button(button_frame, text="View Details",
                               command=self.view_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Negotiate Contract",
                               command=self.negotiate_selected_staff,
                               width=160, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Reassign Role",
                               command=self.reassign_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Release Staff",
                               command=self.release_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Org Chart",
                               command=self.show_organizational_chart,
                               width=110, height=36).pack(side="right", padx=5)
        self._secondary_button(button_frame, text="Staff Report",
                               command=self.show_staff_report,
                               width=130, height=36).pack(side="right", padx=5)

    def create_available_staff_auto_redirect_tab(self):
        """The 'Hire Staff' tab jumps to the Free Agency staff page when selected."""
        frame = self.tabview.tab("Hire Staff")
        frame.configure(fg_color=self._ct['PANEL'])
        ctk.CTkLabel(
            frame, text="Opening Free Agency...", font=(self._ff, 12),
            text_color=self._ct['TEXT_DIM']).pack(expand=True, pady=40)

    def _on_tabview_change(self, tab_name):
        """Detect the Hire Staff tab selection and redirect to Free Agency."""
        if tab_name == "Hire Staff":
            self.after_idle(self._redirect_to_free_agency)

    def _redirect_to_free_agency(self):
        """Redirect to Free Agency staff page and close this window."""
        # Unregister this window before opening Free Agency
        try:
            self.parent.open_windows.pop('staff_management', None)
        except Exception:
            pass

        # Open the enhanced free agency window
        self.parent.open_free_agency_window()

        # Select the staff tab ("Free Agent Staff") once it is ready.
        # (The CTk rebuild dropped FA's old ttk `notebook` attribute, so the
        # legacy `notebook.select(1)` call is replaced with the tabview API.)
        def select_staff_tab():
            fa_window = self.parent.open_windows.get('free_agency')
            if fa_window is not None and hasattr(fa_window, 'tabview'):
                try:
                    if fa_window.winfo_exists():
                        fa_window.tabview.set("Free Agent Staff")
                        fa_window.focus_set()
                except Exception:
                    pass

        # Schedule the tab selection for after the window is fully created
        self.parent.after_idle(select_staff_tab)

        # Close this window
        self.destroy()

    def create_staff_overview_tab(self):
        """Staff overview and organizational chart."""
        ct = self._ct
        frame = self.tabview.tab("Organization")
        frame.configure(fg_color=ct['PANEL'])

        # Organizational chart card
        org_card = self._card(frame)
        org_card.pack(fill="both", expand=True, padx=12, pady=(10, 6))
        ctk.CTkLabel(org_card, text="Organizational Chart",
                     font=(self._ff, 13, "bold"),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=14, pady=(10, 6))

        chart_holder = ctk.CTkFrame(org_card, fg_color="transparent")
        chart_holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.org_text = ctk.CTkTextbox(
            chart_holder, font=(self._ff, 10), wrap="word",
            fg_color=ct['BG'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        self.org_text.pack(side="left", fill="both", expand=True)

        # Staff statistics card
        stats_card = self._card(frame)
        stats_card.pack(fill="x", padx=12, pady=(6, 10))
        ctk.CTkLabel(stats_card, text="Staff Statistics",
                     font=(self._ff, 13, "bold"),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=14, pady=(10, 4))
        self.stats_label = ctk.CTkLabel(
            stats_card, text="", font=(self._ff, 10),
            text_color=ct['TEXT_DIM'], anchor="w", justify="left")
        self.stats_label.pack(anchor="w", padx=14, pady=(0, 10))

    # ------------------------------------------------------------------
    # Data / filtering / sorting
    # ------------------------------------------------------------------
    def update_views(self):
        """Update all views with current data."""
        self.update_current_staff_view()
        self.update_staff_overview()
        self.update_staff_summary()

    def update_current_staff_view(self):
        """Update the current staff treeview with trade-block-style interaction."""
        # Clear existing items
        for item in self.current_staff_tree.get_children():
            self.current_staff_tree.delete(item)

        self.staff_map = {}

        user_team = self._get_user_team()
        if not user_team:
            return

        # Apply filters
        filtered_staff = self._filter_staff(user_team.staff)

        # Update summary like trade block
        total_staff = len(user_team.staff)
        filtered_count = len(filtered_staff)
        total_salary = sum(staff.salary for staff in user_team.staff)
        avg_rating = sum(staff.overall_rating for staff in user_team.staff) / total_staff if total_staff > 0 else 0
        selected_count = len(self.selected_staff)

        summary_text = f"Total Staff: {total_staff} | Showing: {filtered_count} | Selected: {selected_count} | "
        summary_text += f"Total Salary: ${total_salary:,} | Avg Rating: {avg_rating:.1f}"
        self.staff_summary_label.configure(text=summary_text)

        # Populate tree like trade block
        for staff in sorted(filtered_staff, key=lambda s: (s.role.value, s.overall_rating), reverse=True):
            # Checkbox like trade block
            sel = "☑" if staff.id in self.selected_staff else "☐"

            # Get department for staff
            department = self.get_staff_department(staff)

            # Calculate key skills display
            key_skills = self.get_key_skills_display(staff)

            # Get morale and status
            morale = getattr(staff, 'morale', 10)
            status = self.get_staff_status(staff)

            # Format salary
            salary_str = f"${staff.salary:,}"
            contract_str = f"{staff.contract_years}y"

            values = (
                sel,
                staff.full_name,
                staff.role.value,
                department,
                staff.overall_rating,
                f"{staff.experience}y",
                salary_str,
                contract_str,
                f"{morale}/20",
                status,
                key_skills
            )

            # Determine tags for visual styling
            tags = []
            if staff.id in self.selected_staff:
                tags.append('selected')
            rating_tag = self._rating_tag(staff.overall_rating)
            if rating_tag:
                tags.append(rating_tag)
            if morale >= 15:
                tags.append('high_morale')
            elif morale <= 5:
                tags.append('low_morale')

            item_id = self.current_staff_tree.insert('', 'end', values=values, tags=tags)
            self.staff_map[item_id] = staff

    def _filter_staff(self, staff_list):
        """Filter staff based on current filter settings."""
        filtered = []

        # Get filter values
        department = self.dept_combo.get() if hasattr(self, 'dept_combo') else "All"
        min_rating = self.min_rating_entry.get() if hasattr(self, 'min_rating_entry') else ""
        max_salary = self.max_salary_entry.get() if hasattr(self, 'max_salary_entry') else ""
        contract_status = self.contract_combo.get() if hasattr(self, 'contract_combo') else "All"

        for staff in staff_list:
            # Department filter
            if department != "All":
                staff_dept = self.get_staff_department(staff)
                if staff_dept != department:
                    continue

            # Rating filter
            if min_rating:
                try:
                    if staff.overall_rating < int(min_rating):
                        continue
                except ValueError:
                    pass

            # Salary filter
            if max_salary:
                try:
                    max_val = int(max_salary.replace(',', '').replace('$', ''))
                    if staff.salary > max_val:
                        continue
                except ValueError:
                    pass

            # Contract status filter
            if contract_status != "All":
                if contract_status == "Expiring" and staff.contract_years > 1:
                    continue
                elif contract_status == "Long-term" and staff.contract_years <= 1:
                    continue

            filtered.append(staff)

        return filtered

    def get_staff_department(self, staff):
        """Get department name for a staff member."""
        role_departments = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }

        return role_departments.get(staff.role, 'Other')

    def _sort_staff_treeview(self, col):
        """Sort staff treeview by column like trade block."""
        # Toggle sort order
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Sort items by column
        def get_val(item_id):
            val = self.current_staff_tree.set(item_id, col)
            # Handle different data types
            if col in ['overall', 'experience']:
                try:
                    return int(val.replace('y', ''))
                except ValueError:
                    return 0
            elif col == 'salary':
                try:
                    return int(val.replace('$', '').replace(',', ''))
                except ValueError:
                    return 0
            elif col == 'morale':
                try:
                    return int(val.split('/')[0])
                except (ValueError, IndexError):
                    return 0
            else:
                return val.lower() if isinstance(val, str) else val

        items = list(self.current_staff_tree.get_children())
        items.sort(key=get_val, reverse=self.sort_reverse)
        for idx, item_id in enumerate(items):
            self.current_staff_tree.move(item_id, '', idx)

    def _handle_staff_checkbox_click(self, event):
        """Handle checkbox clicks like trade block."""
        col = self.current_staff_tree.identify_column(event.x)
        if col == '#1':  # Checkbox column
            item_id = self.current_staff_tree.identify_row(event.y)
            if item_id:
                staff = self.staff_map.get(item_id)
                if staff:
                    if staff.id in self.selected_staff:
                        self.selected_staff.remove(staff.id)
                    else:
                        self.selected_staff.add(staff.id)
                    self.update_current_staff_view()

    def _handle_staff_double_click(self, event):
        """Handle double-click to view staff details."""
        item_id = self.current_staff_tree.identify_row(event.y)
        if item_id:
            staff = self.staff_map.get(item_id)
            if staff:
                self.show_staff_details_window(staff, is_current=True)

    def update_staff_overview(self):
        """Update the organizational chart and overview."""
        user_team = self._get_user_team()
        if not user_team:
            return

        # Clear text widget
        self.org_text.delete("1.0", "end")

        # Organize staff by category
        staff_by_category = {
            'Management': [],
            'Coaching': [],
            'Development': [],
            'Scouting': [],
            'Medical': [],
            'Analytics': [],
            'Other': []
        }

        role_categories = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics',

            # Other
            StaffRole.EQUIPMENT_MANAGER: 'Other'
        }

        # Categorize current staff
        for staff in user_team.staff:
            category = role_categories.get(staff.role, 'Other')
            staff_by_category[category].append(staff)

        # Build organizational chart text
        org_text = f"{user_team.team_name} Organizational Chart\n"
        org_text += "=" * 50 + "\n\n"

        # Add staff validation status
        validation_issues = user_team.validate_staff_structure()
        if validation_issues['errors'] or validation_issues['warnings']:
            org_text += "STAFF ISSUES:\n"
            for error in validation_issues['errors']:
                org_text += f"  ERROR: {error}\n"
            for warning in validation_issues['warnings']:
                org_text += f"  WARNING: {warning}\n"
            org_text += "\n"
        else:
            org_text += "Staff structure validated - No issues found.\n\n"

        for category, staff_list in staff_by_category.items():
            if staff_list:
                org_text += f"{category} Department:\n"
                org_text += "-" * 20 + "\n"
                for staff in staff_list:
                    org_text += f"  • {staff.full_name} - {staff.role.value} (Overall: {staff.overall_rating})\n"
                org_text += "\n"
            else:
                org_text += f"{category} Department: [VACANT]\n\n"

        # Add vacant positions
        all_roles = set(StaffRole)
        filled_roles = {staff.role for staff in user_team.staff}
        vacant_roles = all_roles - filled_roles

        if vacant_roles:
            org_text += "Vacant Positions:\n"
            org_text += "-" * 15 + "\n"
            for role in sorted(vacant_roles, key=lambda x: x.value):
                category = role_categories.get(role, 'Other')
                org_text += f"  • {role.value} ({category})\n"

        self.org_text.insert("1.0", org_text)

    def update_staff_summary(self):
        """Update the staff summary information."""
        user_team = self._get_user_team()
        if not user_team:
            return

        total_staff = len(user_team.staff)
        total_payroll = sum(staff.salary for staff in user_team.staff)
        avg_overall = sum(staff.overall_rating for staff in user_team.staff) / max(1, total_staff)
        avg_experience = sum(staff.experience for staff in user_team.staff) / max(1, total_staff)

        # Count by category
        coaching_count = sum(1 for s in user_team.staff if 'COACH' in s.role.value.upper())
        scouting_count = sum(1 for s in user_team.staff if 'SCOUT' in s.role.value.upper())

        summary_text = (
            f"Total Staff: {total_staff} | "
            f"Coaching: {coaching_count} | "
            f"Scouting: {scouting_count} | "
            f"Payroll: ${total_payroll:,} | "
            f"Avg Overall: {avg_overall:.1f} | "
            f"Avg Experience: {avg_experience:.1f} years"
        )

        self.staff_summary_label.configure(text=summary_text)

        # Update stats for organization tab
        if hasattr(self, 'stats_label'):
            stats_text = f"""Staff Statistics:
• Total Staff Members: {total_staff}
• Total Staff Payroll: ${total_payroll:,}
• Average Overall Rating: {avg_overall:.1f}
• Average Experience: {avg_experience:.1f} years
• Coaching Staff: {coaching_count} members
• Scouting Staff: {scouting_count} members
• Highest Paid: {max(user_team.staff, key=lambda s: s.salary).full_name if user_team.staff else 'N/A'} (${max((s.salary for s in user_team.staff), default=0):,})
• Most Experienced: {max(user_team.staff, key=lambda s: s.experience).full_name if user_team.staff else 'N/A'} ({max((s.experience for s in user_team.staff), default=0)} years)"""

            self.stats_label.configure(text=stats_text)

    def get_key_skills_display(self, staff: Staff) -> str:
        """Get a display string of the staff member's key skills."""
        # Define key attributes by role
        role_skills = {
            StaffRole.HEAD_COACH: ['tactical_knowledge', 'man_management', 'motivating'],
            StaffRole.ASSISTANT_COACH: ['coaching_forwards', 'coaching_defensemen', 'game_preparation'],
            StaffRole.GOALIE_COACH: ['coaching_goalies', 'technical_coaching', 'working_with_youngsters'],
            StaffRole.HEAD_SCOUT: ['judging_player_ability', 'judging_player_potential', 'determination'],
            StaffRole.PROFESSIONAL_SCOUT: ['judging_player_ability', 'adaptability'],
            StaffRole.AMATEUR_SCOUT: ['judging_player_potential', 'working_with_youngsters'],
            StaffRole.GENERAL_MANAGER: ['judging_player_ability', 'tactical_knowledge', 'media_handling']
        }

        skills = role_skills.get(staff.role, ['determination', 'adaptability', 'man_management'])
        skill_values = []

        for skill in skills[:3]:  # Top 3 skills
            if hasattr(staff, skill):
                value = getattr(staff, skill)
                skill_name = skill.replace('_', ' ').title()
                skill_values.append(f"{skill_name}: {value}")

        return " | ".join(skill_values)

    def _staff_impact_lines(self, staff: Staff):
        """What this staffer's attributes verifiably affect.

        Only effects confirmed by reading the sim code are reported;
        everything else gets an honest "no direct effect" line.
        Returns [(text, kind)] where kind is 'ok' | 'warn' | 'info'.
        """
        lines = []
        if staff.role in self._SCOUT_ROLES:
            ja = getattr(staff, 'judging_player_ability', 0) or 0
            jp = getattr(staff, 'judging_player_potential', 0) or 0
            eff = (ja + jp) / 40.0
            lines.append(
                (f"Judging Ability {ja} / Judging Potential {jp} drive the scouting engine: "
                 f"this scout files prospect reports at about {eff:.0%} efficiency, and higher "
                 "values raise report accuracy and reliability.", 'ok'))
            mm = getattr(staff, 'man_management', 0) or 0
            if mm > 12:
                lines.append(
                    ("Man Management 13+ unlocks prospect interviews once a report reaches "
                     "3+ viewings (further boosts report reliability).", 'ok'))
            else:
                lines.append(
                    (f"Man Management is {mm}: reaching 13 unlocks prospect interviews once a "
                     "report reaches 3+ viewings.", 'info'))
        else:
            key = self.get_key_skills_display(staff)
            if key:
                lines.append((f"Role focus: {key}.", 'info'))
            lines.append(
                ("No direct simulation effect currently: this role's attributes are tracked "
                 "and displayed, but the sim engine does not read them.", 'warn'))
        return lines

    # ------------------------------------------------------------------
    # Selection actions
    # ------------------------------------------------------------------
    def get_current_team_staff(self):
        """Get current team staff list."""
        user_team = self._get_user_team()
        return user_team.staff if user_team else []

    def get_staff_status(self, staff):
        """Determine staff status based on various factors."""
        morale = getattr(staff, 'morale', 10)
        years_left = staff.contract_years

        if years_left <= 1:
            return "Expiring"
        elif morale >= 15:
            return "Happy"
        elif morale >= 10:
            return "Content"
        elif morale >= 5:
            return "Concerned"
        else:
            return "Unhappy"

    def filter_current_staff(self, event=None):
        """Filter current staff based on selected category - updated for new system."""
        # This is now handled by the filter dropdowns in the new interface
        self.update_current_staff_view()

    def show_staff_context_menu(self, event):
        """Show right-click context menu for current staff like trade block."""
        item_id = self.current_staff_tree.identify_row(event.y)
        if not item_id:
            return

        self.current_staff_tree.selection_set(item_id)
        staff = self.staff_map.get(item_id)
        if not staff:
            return

        # Toggle selection when right-clicking
        if staff.id not in self.selected_staff:
            self.selected_staff.add(staff.id)
            self.update_current_staff_view()

        context_menu = tk.Menu(self, tearoff=0, bg=self._ct['PANEL'],
                               fg=self._ct['TEXT'],
                               activebackground=self._ct['ROW_SELECTED'],
                               activeforeground=self._ct['TEXT'])
        context_menu.add_command(label=f"View {staff.full_name} Details",
                                 command=lambda: self.show_staff_details_window(staff, True))
        context_menu.add_command(label="Negotiate Contract",
                                 command=self.negotiate_selected_staff)
        context_menu.add_command(label="Reassign Role",
                                 command=self.reassign_selected_staff)
        context_menu.add_separator()
        context_menu.add_command(label="Release Staff",
                                 command=self.release_selected_staff)

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def view_selected_staff(self):
        """View details of selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to view details.")
            return

        # If only one selected, show detailed view
        if len(self.selected_staff) == 1:
            staff_id = next(iter(self.selected_staff))
            staff = next((s for s in self.get_current_team_staff() if s.id == staff_id), None)
            if staff:
                self.show_staff_details_window(staff, is_current=True)
        else:
            # Multiple selected - show summary
            self.show_multiple_staff_summary()

    def negotiate_selected_staff(self):
        """Negotiate contracts with selected staff members.

        Each negotiation is a sequential modal dialog; results reflect what
        actually happened instead of assuming failure.
        """
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to negotiate contracts.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]
        results = []

        for staff in selected_staff_list:
            if self.open_contract_negotiation(staff, is_hiring=False):
                results.append(f"{staff.full_name}: agreement reached")
            else:
                results.append(f"{staff.full_name}: no agreement")

        if results:
            # One inbox digest instead of a popup (FM24/EHM style).
            try:
                from game_classes import EmailMessage
                from datetime import date
                self.parent.send_email_to_user(EmailMessage(
                    sender="System", sender_type="System",
                    date_sent=date.today(), category="Contracts", priority=2,
                    subject="Staff Negotiation Results",
                    content="Contract negotiations complete:\n" + "\n".join(
                        f"• {r}" for r in results)))
            except Exception:
                pass

        self.update_current_staff_view()

    def reassign_selected_staff(self):
        """Reassign roles for selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to reassign.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        if len(selected_staff_list) == 1:
            # Single staff - use detailed reassignment
            self.reassign_single_staff(selected_staff_list[0])
        else:
            # Multiple staff - bulk reassignment
            self.reassign_multiple_staff(selected_staff_list)

    def release_selected_staff(self):
        """Release selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to release.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        # Confirm release
        if len(selected_staff_list) == 1:
            staff_name = selected_staff_list[0].full_name
            msg = f"Are you sure you want to release {staff_name}?"
        else:
            msg = f"Are you sure you want to release {len(selected_staff_list)} staff members?"

        if not messagebox.askyesno("Confirm Release", msg):
            return

        user_team = self._get_user_team()
        if not user_team:
            return

        released_count = 0
        for staff in selected_staff_list:
            if staff in user_team.staff:
                user_team.staff.remove(staff)
                released_count += 1

        # Clear selection
        self.selected_staff.clear()

        messagebox.showinfo("Staff Released", f"Successfully released {released_count} staff member(s).")
        self.update_current_staff_view()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _dialog_card(self, parent, title):
        """Labeled card section inside a dialog; returns the inner frame."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=title, font=(self._ff, 11, "bold"),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=12, pady=(10, 4))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=(0, 10))
        return inner

    def _info_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=(self._ff, 10),
                     text_color=self._ct['TEXT_DIM'], anchor="w",
                     justify="left").pack(anchor="w", padx=4, pady=2)

    def show_staff_details_window(self, staff: Staff, is_current: bool):
        """Show detailed staff information window."""
        ct = self._ct
        details_window = InGamePopup(self)
        details_window.title(f"Staff Details - {staff.full_name}")
        details_window.configure(fg_color=ct['BG'])
        details_window.geometry("680x820")
        details_window.transient(self)

        # Main frame (scrollable so the tall dialog always fits)
        main_frame = ctk.CTkScrollableFrame(details_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=14, pady=14)

        # Header
        self._heading(main_frame, text=staff.full_name, size=18).pack(
            anchor="w", pady=(0, 2))
        ctk.CTkLabel(main_frame, text=f"{staff.role.value}  •  Rating {staff.overall_rating}",
                     font=(self._ff, 11), text_color=ct['TEAL']).pack(
                         anchor="w", pady=(0, 4))
        # FM24-style identity line: coaching style, ambition, boyhood team
        self._staff_identity_line(main_frame, staff, ct)

        # Basic info
        info_inner = self._dialog_card(main_frame, "Basic Information")
        self._info_label(info_inner, f"Age: {staff.age}")
        self._info_label(info_inner, f"Nationality: {staff.nationality}")
        self._info_label(info_inner, f"Experience: {staff.experience} years")
        self._info_label(info_inner, f"Overall Rating: {staff.overall_rating}")
        self._info_label(info_inner, f"Reputation: {staff.reputation}")

        # Contract info
        contract_inner = self._dialog_card(main_frame, "Contract Information")
        self._info_label(contract_inner, f"Salary: ${staff.salary:,}")
        self._info_label(contract_inner, f"Contract Length: {staff.contract_years} years")

        # Attributes -- FM24-style grouped bars (native 1-100 scale)
        attr_inner = self._dialog_card(main_frame, "Attributes")
        self._staff_attribute_groups(attr_inner, staff, ct)

        # Standing -- room status, trust, control, assistant effectiveness
        standing_inner = self._dialog_card(main_frame, "Standing")
        self._staff_standing_lines(standing_inner, staff, ct)

        # On-Ice Impact - what this staffer's attributes verifiably affect
        impact_inner = self._dialog_card(main_frame, "On-Ice Impact")
        for line, kind in self._staff_impact_lines(staff):
            fg = {'ok': ct['GREEN'], 'warn': ct['GOLD'],
                  'info': ct['TEXT_FAINT']}.get(kind, ct['TEXT_FAINT'])
            ctk.CTkLabel(impact_inner, text=f"•  {line}",
                         font=(self._ff, 9), text_color=fg,
                         wraplength=560, justify="left",
                         anchor="w").pack(anchor="w", padx=8, pady=2)

        # Role description
        desc_inner = self._dialog_card(main_frame, "Role Description")
        ctk.CTkLabel(desc_inner, text=staff.get_role_description(),
                     font=(self._ff, 10), text_color=ct['TEXT_DIM'],
                     wraplength=580, justify="left",
                     anchor="w").pack(anchor="w", padx=4, pady=4)

        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(4, 0))

        if is_current:
            self._secondary_button(button_frame, text="Negotiate Contract",
                                   command=lambda: self._negotiate_current_staff(staff, details_window),
                                   width=170, height=36).pack(side="left", padx=5)
            self._secondary_button(button_frame, text="Release",
                                   command=lambda: self.release_staff_action(staff, details_window),
                                   width=110, height=36).pack(side="left", padx=5)
        else:
            self._primary_button(button_frame, text="Make Offer",
                                 command=lambda: self.make_staff_offer_action(staff, details_window),
                                 width=130, height=36).pack(side="left", padx=5)

        self._secondary_button(button_frame, text="Close",
                               command=details_window.destroy,
                               width=110, height=36).pack(side="right", padx=5)

    # ------------------------------------------------------------------
    # FM24-style staff card sections
    # ------------------------------------------------------------------
    _STAFF_ATTR_GROUPS = [
        ("Coaching", ["coaching_forwards", "coaching_defensemen",
                      "coaching_goalies", "attacking_coaching",
                      "defensive_coaching", "technical_coaching",
                      "mental_coaching"]),
        ("Tactical", ["tactical_knowledge", "game_preparation",
                      "match_preparation"]),
        ("Development", ["working_with_youngsters", "player_development",
                         "judging_player_ability", "judging_player_potential"]),
        ("Management", ["man_management", "motivating", "discipline",
                        "level_of_discipline", "media_handling"]),
        ("Personality", ["leadership", "determination", "adaptability"]),
    ]

    def _staff_identity_line(self, parent, staff, ct):
        """FM24-style identity line: coaching style, ambition, boyhood team."""
        import reputation_system as rs
        bits = []
        try:
            if "COACH" in str(getattr(getattr(staff, "role", None), "name", "")):
                style = rs.coach_style(staff)
                label = style.get("label") if isinstance(style, dict) else None
                if label:
                    bits.append(label)
        except Exception:
            pass
        amb = getattr(staff, "ambition", None)
        if amb:
            bits.append(str(amb).replace("_", " ").title())
        fav = getattr(staff, "favorite_team", None)
        if fav:
            bits.append(f"Boyhood: {fav}")
        cn = getattr(staff, "control_need", None)
        if cn is not None:
            try:
                cn = float(cn)
                bits.append("Authoritarian" if cn >= 70 else
                            "Collaborative" if cn <= 35 else "Balanced control")
            except Exception:
                pass
        ctk.CTkLabel(parent,
                     text="   •   ".join(bits) if bits else "",
                     font=(self._ff, 10), text_color=ct['TEXT_DIM'],
                     anchor="w").pack(anchor="w", pady=(0, 12))

    def _attr_bar_ctk(self, parent, label, value, max_val=100):
        """Single attribute bar on the native 1-100 scale."""
        ct = self._ct
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=(self._ff, 10),
                     text_color=ct['TEXT_DIM'], width=130,
                     anchor="w").pack(side="left")
        bar = ctk.CTkProgressBar(row, width=110, height=8,
                                 progress_color=ct['TEAL'])
        bar.pack(side="left", padx=(4, 8))
        try:
            bar.set(max(0.0, min(1.0, float(value) / max_val)))
            vtext = str(int(value))
        except Exception:
            bar.set(0.0)
            vtext = "?"
        ctk.CTkLabel(row, text=vtext, font=(self._ff, 10, "bold"),
                     text_color=ct['TEXT'], width=28,
                     anchor="e").pack(side="left")

    def _staff_attribute_groups(self, parent, staff, ct):
        """FM24-style grouped attribute bars (native 1-100 scale)."""
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x")
        for gi, (gname, fields) in enumerate(self._STAFF_ATTR_GROUPS):
            col = ctk.CTkFrame(grid, fg_color="transparent")
            col.grid(row=gi // 2, column=gi % 2, sticky="nsew", padx=(0, 18),
                     pady=(0, 10))
            ctk.CTkLabel(col, text=gname, font=(self._ff, 10, "bold"),
                         text_color=ct['TEAL'], anchor="w").pack(anchor="w",
                                                                 pady=(0, 4))
            for f in fields:
                if not hasattr(staff, f):
                    continue
                self._attr_bar_ctk(col, f.replace("_", " ").title(),
                                   getattr(staff, f), 100)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

    def _staff_standing_lines(self, parent, staff, ct):
        """Room standing, GM trust, control, assistant effectiveness."""
        import reputation_system as rs
        lines = []
        try:
            st = rs.room_status(staff)
            if isinstance(st, dict):
                level = st.get("level", "Secure")
                risk = float(st.get("risk", 0.0) or 0.0)
                kind = "warn" if risk >= 0.45 else "info"
                lines.append((f"Room standing: {level} "
                              f"({risk:.0%} losing-the-room risk)", kind))
        except Exception:
            pass
        try:
            if str(getattr(getattr(staff, "role", None), "name", "")) == "HEAD_COACH":
                lines.append((f"GM trust: {getattr(staff, 'gm_trust', 70)}/100",
                              "info"))
        except Exception:
            pass
        try:
            eff = getattr(staff, "assistant_effect", None)
            if eff:
                lines.append((f"Assistant effectiveness: {float(eff):.0f}",
                              "ok"))
        except Exception:
            pass
        try:
            cn = getattr(staff, "control_need", None)
            if cn is not None:
                lines.append((f"Control need: {float(cn):.0f}/100", "info"))
        except Exception:
            pass
        if not lines:
            lines.append(("No standing data recorded.", "info"))
        for text, kind in lines:
            fg = {"ok": ct["GREEN"], "warn": ct["GOLD"],
                  "info": ct["TEXT_FAINT"]}.get(kind, ct["TEXT_FAINT"])
            ctk.CTkLabel(parent, text=f"•  {text}", font=(self._ff, 10),
                         text_color=fg, wraplength=560, justify="left",
                         anchor="w").pack(anchor="w", padx=8, pady=2)

    def _negotiate_current_staff(self, staff: Staff, details_window):
        """Negotiate with a current staffer from the details window (modal, honest result)."""
        if self.open_contract_negotiation(staff, is_hiring=False):
            # Result lands in the inbox (FM24/EHM style), not a popup.
            try:
                from game_classes import EmailMessage
                from datetime import date
                self.parent.send_email_to_user(EmailMessage(
                    sender="System", sender_type="System",
                    date_sent=date.today(), category="Contracts", priority=2,
                    subject=f"Staff re-signed: {staff.full_name}",
                    content=(f"Contract renegotiated with {staff.full_name} "
                             f"({staff.role.value}).")))
            except Exception:
                pass
            details_window.destroy()
            self.update_views()

    def format_staff_attributes(self, staff: Staff) -> str:
        """Format staff attributes for display."""
        attr_text = "COACHING ATTRIBUTES:\n"
        attr_text += f"Coaching Forwards: {staff.coaching_forwards}\n"
        attr_text += f"Coaching Defensemen: {staff.coaching_defensemen}\n"
        attr_text += f"Coaching Goalies: {staff.coaching_goalies}\n\n"

        attr_text += "TACTICAL KNOWLEDGE:\n"
        attr_text += f"Tactical Knowledge: {staff.tactical_knowledge}\n"
        attr_text += f"Game Preparation: {staff.game_preparation}\n"
        attr_text += f"Match Preparation: {staff.match_preparation}\n\n"

        attr_text += "PLAYER DEVELOPMENT:\n"
        attr_text += f"Working with Youngsters: {staff.working_with_youngsters}\n"
        attr_text += f"Player Development: {staff.player_development}\n\n"

        attr_text += "MANAGEMENT SKILLS:\n"
        attr_text += f"Man Management: {staff.man_management}\n"
        attr_text += f"Motivating: {staff.motivating}\n"
        attr_text += f"Discipline: {staff.discipline}\n\n"

        attr_text += "SCOUTING ABILITIES:\n"
        attr_text += f"Judging Player Ability: {staff.judging_player_ability}\n"
        attr_text += f"Judging Player Potential: {staff.judging_player_potential}\n\n"

        attr_text += "COMMUNICATION:\n"
        attr_text += f"Media Handling: {staff.media_handling}\n"
        attr_text += f"Determination: {staff.determination}\n"
        attr_text += f"Adaptability: {staff.adaptability}\n\n"

        attr_text += "SPECIALIZED COACHING:\n"
        attr_text += f"Level of Discipline: {staff.level_of_discipline}\n"
        attr_text += f"Attacking Coaching: {staff.attacking_coaching}\n"
        attr_text += f"Defensive Coaching: {staff.defensive_coaching}\n"
        attr_text += f"Mental Coaching: {staff.mental_coaching}\n"
        attr_text += f"Technical Coaching: {staff.technical_coaching}\n"

        return attr_text

    def open_contract_negotiation(self, staff: Staff, is_hiring: bool = False):
        """Open a modal contract negotiation window.

        Returns True when both sides reach an agreement, False otherwise
        (rejected offer or cancelled). The caller owns all follow-up
        messaging and view refreshes.
        """
        ct = self._ct
        nego_window = InGamePopup(self)
        nego_window.title(f"Contract Negotiation - {staff.full_name}")
        nego_window.configure(fg_color=ct['BG'])
        nego_window.geometry("500x470")
        nego_window.transient(self)

        # Result flag read after the modal loop exits
        nego_window._accepted = False

        # Main frame
        main_frame = ctk.CTkFrame(nego_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        # Staff info
        self._heading(main_frame,
                      text=f"Negotiating with {staff.full_name}",
                      size=14).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(main_frame, text=staff.role.value,
                     font=(self._ff, 11), text_color=ct['TEAL']).pack(
                         anchor="w", pady=(0, 14))

        # Current demands
        demands_inner = self._dialog_card(main_frame, "Current Demands")
        self._info_label(demands_inner, f"Asking Salary: ${staff.salary:,}")
        self._info_label(demands_inner, f"Contract Length: {staff.contract_years} years")

        # Offer frame
        offer_inner = self._dialog_card(main_frame, "Your Offer")
        offer_grid = ctk.CTkFrame(offer_inner, fg_color="transparent")
        offer_grid.pack(anchor="w")

        ctk.CTkLabel(offer_grid, text="Salary:",
                     font=(self._ff, 10), text_color=ct['TEXT_DIM']).grid(
                         row=0, column=0, padx=5, pady=5, sticky='w')
        salary_entry = ctk.CTkEntry(
            offer_grid, width=150, fg_color=ct['BG'],
            border_color=ct['BORDER'], text_color=ct['TEXT'])
        salary_entry.insert(0, str(staff.salary))
        salary_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(offer_grid, text="Years:",
                     font=(self._ff, 10), text_color=ct['TEXT_DIM']).grid(
                         row=1, column=0, padx=5, pady=5, sticky='w')
        years_entry = ctk.CTkEntry(
            offer_grid, width=150, fg_color=ct['BG'],
            border_color=ct['BORDER'], text_color=ct['TEXT'])
        years_entry.insert(0, str(staff.contract_years))
        years_entry.grid(row=1, column=1, padx=5, pady=5)

        # Result label
        result_label = ctk.CTkLabel(main_frame, text="",
                                    font=(self._ff, 10),
                                    text_color=ct['TEXT_DIM'],
                                    wraplength=440, justify="left")
        result_label.pack(fill="x", pady=(0, 12))

        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")

        def make_offer():
            try:
                offered_salary = int(salary_entry.get())
                offered_years = int(years_entry.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for salary and years.")
                return

            if offered_salary <= 0 or not 1 <= offered_years <= 5:
                messagebox.showerror("Invalid Input", "Salary must be positive and the term 1-5 years.")
                return

            if staff.negotiate_contract(offered_salary, offered_years):
                result_label.configure(text="Offer Accepted!", text_color=ct['GREEN'])

                if is_hiring:
                    # Add to team with role validation
                    user_team = self._get_user_team()
                    if user_team:
                        # Check for unique role violations before hiring
                        if Staff.is_unique_role(staff.role):
                            existing_with_role = [s for s in user_team.staff if s.role == staff.role]
                            if existing_with_role:
                                messagebox.showerror(
                                    "Role Conflict",
                                    f"Team already has a {staff.role.value}: {existing_with_role[0].full_name}.\n"
                                    f"You must reassign or release the existing {staff.role.value} first.")
                                return

                        staff.salary = offered_salary
                        staff.contract_years = offered_years
                        user_team.staff.append(staff)
                        try:
                            import assistant_coaches as _ac
                            _app = getattr(self, "app", None) or getattr(
                                self, "master", None)
                            _ac.on_assistant_hired(user_team, staff, app=_app)
                        except Exception:
                            pass
                        # New head coach, new whiteboard: he installs HIS
                        # systems (unless the GM owns tactics).
                        try:
                            _role = str(getattr(getattr(staff, "role", None),
                                                "value", ""))
                            if "Head Coach" in _role:
                                import tactics as _tx
                                _app = getattr(self, "app", None) or getattr(
                                    self, "master", None)
                                if _tx.get_tactics_control(user_team) == "coach":
                                    installed = _tx.install_coach_systems(
                                        user_team, staff, reason="hired")
                                    if installed and _app is not None:
                                        _cname = (f"{getattr(staff, 'first_name', '')} "
                                                  f"{getattr(staff, 'last_name', '')}").strip()
                                        _bits = ", ".join(
                                            f"{c}: {k.replace('_', ' ')}"
                                            for c, k in installed.items())
                                        try:
                                            _app.add_news(
                                                f"{_cname} is installing his systems "
                                                f"({len(installed)} changes: {_bits}). "
                                                f"The room starts learning -- familiarity reset.")
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        if staff in self.available_staff:
                            self.available_staff.remove(staff)
                else:
                    # Update existing contract
                    staff.salary = offered_salary
                    staff.contract_years = offered_years

                nego_window._accepted = True
                nego_window.destroy()
            else:
                result_label.configure(text="Offer Rejected. Try adjusting your offer.",
                                       text_color=ct['RED'])

        self._primary_button(button_frame, text="Make Offer", command=make_offer,
                             width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Cancel",
                               command=nego_window.destroy,
                               width=110, height=36).pack(side="right", padx=5)

        # Modal: block until the window closes, then report the outcome
        nego_window.grab_set()
        self.wait_window(nego_window)
        return bool(getattr(nego_window, "_accepted", False))

    def release_staff_action(self, staff: Staff, details_window=None):
        """Perform staff release action."""
        result = messagebox.askyesno("Confirm Release",
                                    f"Are you sure you want to release {staff.full_name}?\n"
                                    f"This will end their contract immediately.")

        if result:
            user_team = self._get_user_team()
            if user_team and staff in user_team.staff:
                user_team.staff.remove(staff)
                messagebox.showinfo("Staff Released", f"{staff.full_name} has been released.")

                if details_window:
                    details_window.destroy()

                self.update_views()

    def make_staff_offer_action(self, staff: Staff, details_window=None):
        """Make offer to a hiring candidate (modal negotiation, honest result)."""
        if details_window:
            details_window.destroy()
        if self.open_contract_negotiation(staff, is_hiring=True):
            messagebox.showinfo("Success", f"{staff.full_name} has been hired!")
            self.update_views()

    def categorize_staff(self, staff_list):
        """Categorize staff by their roles for filtering."""
        categories = {
            'Management': [],
            'Coaching': [],
            'Development': [],
            'Scouting': [],
            'Medical': [],
            'Analytics': []
        }

        role_categories = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }

        for staff in staff_list:
            category = role_categories.get(staff.role, 'Other')
            if category in categories:
                categories[category].append(staff)
            else:
                # Add to Analytics if no specific category
                categories[category].append(staff) if category in categories else categories['Analytics'].append(staff)

        return categories

    def show_multiple_staff_summary(self):
        """Show summary window for multiple selected staff."""
        ct = self._ct
        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        summary_window = InGamePopup(self)
        summary_window.title(f"Selected Staff Summary ({len(selected_staff_list)} staff)")
        summary_window.configure(fg_color=ct['BG'])
        summary_window.geometry("600x520")
        summary_window.transient(self)

        main_frame = ctk.CTkFrame(summary_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame,
                      text=f"Selected Staff Summary ({len(selected_staff_list)} staff)",
                      size=14).pack(anchor="w", pady=(0, 12))

        text_widget = ctk.CTkTextbox(
            main_frame, wrap="word", font=(self._ff, 11),
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        text_widget.pack(fill="both", expand=True)

        # Generate summary content
        summary_content = "SELECTED STAFF SUMMARY\n"
        summary_content += "=" * 30 + "\n\n"

        total_salary = sum(s.salary for s in selected_staff_list)
        avg_rating = sum(s.overall_rating for s in selected_staff_list) / len(selected_staff_list)
        avg_experience = sum(s.experience for s in selected_staff_list) / len(selected_staff_list)

        summary_content += f"Total Selected: {len(selected_staff_list)}\n"
        summary_content += f"Combined Salary: ${total_salary:,}\n"
        summary_content += f"Average Rating: {avg_rating:.1f}\n"
        summary_content += f"Average Experience: {avg_experience:.1f} years\n\n"

        # Department breakdown
        departments = {}
        for staff in selected_staff_list:
            dept = self.get_staff_department(staff)
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(staff)

        summary_content += "DEPARTMENT BREAKDOWN\n"
        summary_content += "-" * 20 + "\n"
        for dept, staff_list in departments.items():
            summary_content += f"{dept}: {len(staff_list)} staff\n"

        summary_content += "\nSTAFF DETAILS\n"
        summary_content += "-" * 20 + "\n"
        for staff in sorted(selected_staff_list, key=lambda s: s.role.value):
            morale = getattr(staff, 'morale', 10)
            summary_content += f"• {staff.full_name} ({staff.role.value})\n"
            summary_content += f"  Rating: {staff.overall_rating} | Salary: ${staff.salary:,} | Morale: {morale}/100\n\n"

        text_widget.insert('1.0', summary_content)
        text_widget.configure(state='disabled')

        # Close button
        self._secondary_button(main_frame, text="Close",
                               command=summary_window.destroy,
                               width=110, height=36).pack(pady=10)

    def reassign_single_staff(self, staff):
        """Reassign role for a single staff member."""
        ct = self._ct
        reassign_window = InGamePopup(self)
        reassign_window.title(f"Reassign {staff.full_name}")
        reassign_window.configure(fg_color=ct['BG'])
        reassign_window.geometry("420x340")
        reassign_window.transient(self)

        main_frame = ctk.CTkFrame(reassign_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame, text=f"Reassign {staff.full_name}",
                      size=14).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(main_frame, text=f"Current Role: {staff.role.value}",
                     font=(self._ff, 10), text_color=ct['TEXT_DIM']).pack(
                         anchor="w", pady=(0, 12))

        ctk.CTkLabel(main_frame, text="New Role:",
                     font=(self._ff, 10), text_color=ct['TEXT_DIM']).pack(anchor='w')
        role_combo = ctk.CTkComboBox(
            main_frame, values=[role.value for role in StaffRole],
            state='readonly',
            fg_color=ct['CARD'], border_color=ct['BORDER'],
            button_color=ct['PANEL'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'])
        role_combo.set(staff.role.value)
        role_combo.pack(fill='x', pady=(4, 0))

        def confirm_reassignment():
            new_role_name = role_combo.get()
            new_role = next((role for role in StaffRole if role.value == new_role_name), None)

            if new_role and new_role != staff.role:
                # Guard unique roles (e.g. only one Head Coach / GM)
                if Staff.is_unique_role(new_role):
                    team = self._get_user_team()
                    conflict = [s for s in (team.staff if team else [])
                                if s.role == new_role and s.id != staff.id]
                    if conflict:
                        messagebox.showerror(
                            "Role Conflict",
                            f"Team already has a {new_role.value}: {conflict[0].full_name}.\n"
                            f"Reassign or release them first.")
                        return
                staff.role = new_role
                messagebox.showinfo("Success", f"{staff.full_name} has been reassigned to {new_role.value}")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showwarning("No Change", "Please select a different role.")

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=20)

        self._primary_button(button_frame, text="Confirm",
                             command=confirm_reassignment,
                             width=120, height=36).pack(side='left', padx=5)
        self._secondary_button(button_frame, text="Cancel",
                               command=reassign_window.destroy,
                               width=110, height=36).pack(side='right', padx=5)

    def reassign_multiple_staff(self, staff_list):
        """Reassign roles for multiple staff members."""
        ct = self._ct
        reassign_window = InGamePopup(self)
        reassign_window.title(f"Bulk Reassign ({len(staff_list)} staff)")
        reassign_window.configure(fg_color=ct['BG'])
        reassign_window.geometry("620x520")
        reassign_window.transient(self)

        main_frame = ctk.CTkFrame(reassign_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame,
                      text=f"Bulk Reassign {len(staff_list)} Staff Members",
                      size=14).pack(anchor="w", pady=(0, 12))

        # Scrollable list of staff with role dropdowns (CTkScrollableFrame)
        scroll = ctk.CTkScrollableFrame(main_frame, fg_color=ct['PANEL'],
                                        corner_radius=10)
        scroll.pack(fill="both", expand=True)

        # Role selection for each staff member
        role_combos = {}
        for staff in staff_list:
            staff_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            staff_frame.pack(fill='x', pady=5, padx=10)

            ctk.CTkLabel(staff_frame, text=f"{staff.full_name}:",
                         font=(self._ff, 10),
                         text_color=ct['TEXT']).pack(side='left')

            role_combo = ctk.CTkComboBox(
                staff_frame, values=[role.value for role in StaffRole],
                state='readonly', width=200,
                fg_color=ct['CARD'], border_color=ct['BORDER'],
                button_color=ct['PANEL'], button_hover_color=ct['BORDER'],
                dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
                dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'])
            role_combo.set(staff.role.value)
            role_combo.pack(side='right')
            role_combos[staff.id] = role_combo

        def apply_reassignments():
            # Resolve requested roles first, then validate unique roles across
            # the whole team before applying anything.
            new_roles = {}
            for staff in staff_list:
                new_role_name = role_combos[staff.id].get()
                new_role = next((role for role in StaffRole if role.value == new_role_name), None)
                new_roles[staff.id] = new_role if new_role else staff.role

            team = self._get_user_team()
            team_staff = team.staff if team else []
            for role in StaffRole:
                if Staff.is_unique_role(role):
                    holders = [s for s in team_staff
                               if new_roles.get(s.id, s.role) == role]
                    if len(holders) > 1:
                        names = ", ".join(h.full_name for h in holders)
                        messagebox.showerror(
                            "Role Conflict",
                            f"Only one {role.value} is allowed.\nConflicting: {names}.")
                        return

            changes_made = 0
            for staff in staff_list:
                if new_roles[staff.id] != staff.role:
                    staff.role = new_roles[staff.id]
                    changes_made += 1

            if changes_made > 0:
                messagebox.showinfo("Success", f"Reassigned {changes_made} staff member(s)")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showinfo("No Changes", "No role changes were made.")

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=10)

        self._primary_button(button_frame, text="Apply Changes",
                             command=apply_reassignments,
                             width=150, height=36).pack(side='left', padx=5)
        self._secondary_button(button_frame, text="Cancel",
                               command=reassign_window.destroy,
                               width=110, height=36).pack(side='right', padx=5)

    def _report_window(self, title, content):
        """Shared modern scrollable-text dialog used by the report/chart views."""
        ct = self._ct
        win = InGamePopup(self)
        win.title(title)
        win.configure(fg_color=ct['BG'])
        win.geometry("800x620")
        win.transient(self)

        main_frame = ctk.CTkFrame(win, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame, text=title, size=14).pack(anchor="w",
                                                           pady=(0, 12))

        text_widget = ctk.CTkTextbox(
            main_frame, wrap="word", font=(self._ff, 11),
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        text_widget.pack(fill="both", expand=True)

        text_widget.insert('1.0', content)
        text_widget.configure(state='disabled')

        # Close button
        self._secondary_button(main_frame, text="Close",
                               command=win.destroy,
                               width=110, height=36).pack(pady=10)

    def show_staff_report(self):
        """Show comprehensive staff report."""
        user_team = self._get_user_team()
        if not user_team:
            return

        self._report_window(f"{user_team.team_name} Staff Report",
                            self.generate_staff_report(user_team))

    def show_organizational_chart(self):
        """Show organizational chart of current staff."""
        user_team = self._get_user_team()
        if not user_team:
            return

        self._report_window(f"{user_team.team_name} Organizational Chart",
                            self.generate_organizational_chart(user_team))

    def generate_staff_report(self, team):
        """Generate comprehensive staff report."""
        staff_categories = self.categorize_staff(team.staff)

        report = f"{team.team_name} Staff Analysis Report\n"
        report += "=" * 50 + "\n\n"

        # Overall summary
        total_staff = len(team.staff)
        total_salary = sum(staff.salary for staff in team.staff)
        avg_experience = sum(staff.experience for staff in team.staff) / total_staff if total_staff > 0 else 0
        avg_overall = sum(staff.overall_rating for staff in team.staff) / total_staff if total_staff > 0 else 0

        report += f"EXECUTIVE SUMMARY\n"
        report += f"Total Staff: {total_staff}\n"
        report += f"Total Salary: ${total_salary:,}\n"
        report += f"Average Experience: {avg_experience:.1f} years\n"
        report += f"Average Overall Rating: {avg_overall:.1f}\n\n"

        # Department breakdown
        for category, staff_list in staff_categories.items():
            if staff_list:
                report += f"{category.upper()} DEPARTMENT\n"
                report += "-" * 30 + "\n"

                for staff in sorted(staff_list, key=lambda s: s.overall_rating, reverse=True):
                    morale = getattr(staff, 'morale', 10)
                    status = self.get_staff_status(staff)
                    report += f"• {staff.full_name} ({staff.role.value})\n"
                    report += f"  Overall: {staff.overall_rating} | Experience: {staff.experience}y | Morale: {morale}/100\n"
                    report += f"  Salary: ${staff.salary:,} | Contract: {staff.contract_years}y | Status: {status}\n\n"

                dept_avg = sum(s.overall_rating for s in staff_list) / len(staff_list)
                dept_salary = sum(s.salary for s in staff_list)
                report += f"Department Average: {dept_avg:.1f} | Department Salary: ${dept_salary:,}\n\n"

        # Contract expiration analysis
        expiring_staff = [staff for staff in team.staff if staff.contract_years <= 1]
        if expiring_staff:
            report += "CONTRACT EXPIRATIONS\n"
            report += "-" * 30 + "\n"
            for staff in expiring_staff:
                report += f"• {staff.full_name} ({staff.role.value}) - {staff.contract_years} year(s) remaining\n"
            report += "\n"

        return report

    def generate_organizational_chart(self, team):
        """Generate organizational chart text."""
        debug_print(f"DEBUG: Generating org chart for {team.team_name}")
        debug_print(f"DEBUG: Team has {len(team.staff)} staff members")

        staff_categories = self.categorize_staff(team.staff)
        debug_print(f"DEBUG: Staff categories: {[(k, len(v)) for k, v in staff_categories.items()]}")

        chart = f"{team.team_name} Organizational Chart\n"
        chart += "=" * 50 + "\n\n"

        # If no staff, show empty message
        if not team.staff:
            chart += "No staff members currently employed.\n"
            return chart

        # Management hierarchy
        if staff_categories['Management']:
            chart += "MANAGEMENT\n"
            chart += "├── General Manager\n"
            gm_staff = [s for s in staff_categories['Management'] if s.role == StaffRole.GENERAL_MANAGER]
            if gm_staff:
                chart += f"│   └── {gm_staff[0].full_name}\n"

            chart += "└── Assistant General Manager\n"
            agm_staff = [s for s in staff_categories['Management'] if s.role == StaffRole.ASSISTANT_GENERAL_MANAGER]
            for agm in agm_staff:
                chart += f"    └── {agm.full_name}\n"
            chart += "\n"

        # Coaching staff
        if staff_categories['Coaching']:
            chart += "COACHING STAFF\n"
            chart += "├── Head Coach\n"
            hc_staff = [s for s in staff_categories['Coaching'] if s.role == StaffRole.HEAD_COACH]
            if hc_staff:
                chart += f"│   └── {hc_staff[0].full_name}\n"

            chart += "├── Assistant Coaches\n"
            asst_coaches = [s for s in staff_categories['Coaching'] if s.role in [StaffRole.ASSISTANT_COACH, StaffRole.ASSOCIATE_COACH]]
            for coach in asst_coaches:
                chart += f"│   ├── {coach.full_name} ({coach.role.value})\n"

            chart += "└── Specialized Coaches\n"
            spec_coaches = [s for s in staff_categories['Coaching'] if s.role in [StaffRole.GOALIE_COACH, StaffRole.POWER_PLAY_COACH, StaffRole.PENALTY_KILL_COACH]]
            for coach in spec_coaches:
                chart += f"    ├── {coach.full_name} ({coach.role.value})\n"
            chart += "\n"

        # Other departments
        for dept_name in ['Development', 'Scouting', 'Medical', 'Analytics']:
            if staff_categories[dept_name]:
                chart += f"{dept_name.upper()}\n"
                for staff in staff_categories[dept_name]:
                    chart += f"├── {staff.full_name} ({staff.role.value})\n"
                chart += "\n"

        return chart
