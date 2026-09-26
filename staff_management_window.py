"""
Enhanced Staff Management Window for Hockey Manager
Provides comprehensive staff hiring, firing, and management with EHM-style depth.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List
from game_classes import Staff, StaffRole
from game_classes import debug_print
from modern_ui import AppColors, AppCard, AppButton

class StaffManagementWindow(tk.Toplevel):
    """Comprehensive staff management interface with EHM-style functionality."""

    # Roles whose attributes are verifiably read by the sim engine (scouting.py)
    _SCOUT_ROLES = {StaffRole.HEAD_SCOUT, StaffRole.PROFESSIONAL_SCOUT,
                    StaffRole.AMATEUR_SCOUT, StaffRole.EUROPEAN_SCOUT,
                    StaffRole.ADVANCE_SCOUT}

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Staff Management - Hockey Manager")
        self.configure(background=AppColors.BG)
        self.geometry("1200x800")

        # Staff candidates hired through the Free Agency window land here briefly
        # during negotiation; the authoritative lists live on the team/league.
        self.available_staff: List[Staff] = []

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
    
    def create_widgets(self):
        """Create the main interface widgets."""
        # Main container
        main_frame = tk.Frame(self, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title with teal accent bar
        title_label = tk.Label(main_frame, text="Staff Management", bg=AppColors.BG,
                               fg=AppColors.TEXT_PRIMARY,
                               font=(self.parent.FONT_FAMILY, 20, 'bold'))
        title_label.pack(pady=(0, 4))
        accent = tk.Frame(main_frame, bg=AppColors.ACCENT, height=3)
        accent.pack(fill=tk.X, pady=(0, 14))

        # Create notebook for different tabs
        self.notebook = ttk.Notebook(main_frame, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Current Staff tab
        self.create_current_staff_tab()

        # Hiring is handled in the Free Agency window; this tab jumps there
        self.create_available_staff_auto_redirect_tab()

        # Staff Overview tab
        self.create_staff_overview_tab()
    
    def create_current_staff_tab(self):
        """Create the current staff management tab with trade-block-style interaction."""
        current_frame = tk.Frame(self.notebook, bg=AppColors.BG)
        self.notebook.add(current_frame, text="Current Staff")

        # Initialize selection tracking like trade block
        self.selected_staff = set()
        self.staff_map = {}

        # Staff summary panel
        summary_card = AppCard(current_frame, padding=10)
        summary_card.pack(fill=tk.X, padx=18, pady=(8, 0))
        summary_inner = summary_card.get_content_frame()

        self.staff_summary_label = tk.Label(summary_inner, text="", bg=AppColors.BG_ELEVATED,
                                            fg=AppColors.TEXT_PRIMARY,
                                            font=(self.parent.FONT_FAMILY, 10, 'bold'))
        self.staff_summary_label.pack(anchor='w')

        # Filter panel
        filter_card = AppCard(current_frame, padding=10)
        filter_card.pack(fill=tk.X, padx=18, pady=(8, 0))
        filter_inner = filter_card.get_content_frame()

        self.staff_filter_vars = {
            'department': tk.StringVar(value="All"),
            'min_rating': tk.StringVar(value=""),
            'max_salary': tk.StringVar(value=""),
            'contract_status': tk.StringVar(value="All")
        }

        def _flabel(text):
            return tk.Label(filter_inner, text=text, bg=AppColors.BG_ELEVATED,
                            fg=AppColors.TEXT_SECONDARY,
                            font=(self.parent.FONT_FAMILY, 9))

        _flabel("Department:").pack(side=tk.LEFT)
        dept_options = ["All", "Management", "Coaching", "Development", "Scouting", "Medical", "Analytics"]
        ttk.Combobox(filter_inner, textvariable=self.staff_filter_vars['department'],
                    values=dept_options, width=12, state='readonly').pack(side=tk.LEFT, padx=2)

        _flabel("Min Rating:").pack(side=tk.LEFT)
        tk.Entry(filter_inner, textvariable=self.staff_filter_vars['min_rating'], width=4,
                 bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                 insertbackground=AppColors.TEXT_PRIMARY,
                 relief=tk.FLAT, highlightthickness=1,
                 highlightbackground=AppColors.BORDER).pack(side=tk.LEFT, padx=2)

        _flabel("Max Salary:").pack(side=tk.LEFT)
        tk.Entry(filter_inner, textvariable=self.staff_filter_vars['max_salary'], width=8,
                 bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                 insertbackground=AppColors.TEXT_PRIMARY,
                 relief=tk.FLAT, highlightthickness=1,
                 highlightbackground=AppColors.BORDER).pack(side=tk.LEFT, padx=2)

        _flabel("Contract:").pack(side=tk.LEFT)
        ttk.Combobox(filter_inner, textvariable=self.staff_filter_vars['contract_status'],
                    values=["All", "Expiring", "Long-term"], width=10, state='readonly').pack(side=tk.LEFT, padx=2)

        AppButton(filter_inner, text="Apply Filter", command=self.update_current_staff_view,
                  style="secondary", width=110, height=32).pack(side=tk.LEFT, padx=8)

        # Main staff list panel
        panel_card = AppCard(current_frame, padding=10)
        panel_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)
        panel = panel_card.get_content_frame()

        # Staff treeview with trade-block-style columns
        columns = {
            'sel': ('', 30),
            'name': ('Name', 160),
            'role': ('Position', 140),
            'dept': ('Department', 100),
            'overall': ('Rating', 60),
            'experience': ('Exp', 50),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'status': ('Status', 80),
            'key_skills': ('Key Skills', 180)
        }

        self.current_staff_tree = ttk.Treeview(panel, columns=list(columns.keys()), show='headings', height=15)

        # Configure columns and headings
        for col, (text, width) in columns.items():
            self.current_staff_tree.heading(col, text=text, command=lambda c=col: self._sort_staff_treeview(c))
            self.current_staff_tree.column(col, width=width, anchor='center' if col != 'key_skills' else 'w')

        # Add scrollbar
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.current_staff_tree.yview)
        self.current_staff_tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.current_staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))

        # Bind events like trade block
        self.current_staff_tree.bind("<Button-1>", self._handle_staff_checkbox_click)
        self.current_staff_tree.bind("<Double-1>", self._handle_staff_double_click)
        self.current_staff_tree.bind("<Button-3>", self.show_staff_context_menu)

        # Configure tags for visual feedback (modern palette)
        self.current_staff_tree.tag_configure('selected', background=AppColors.ACCENT_BG,
                                              foreground=AppColors.TEXT_PRIMARY)
        self.current_staff_tree.tag_configure('high_morale', foreground=AppColors.SUCCESS)
        self.current_staff_tree.tag_configure('low_morale', foreground=AppColors.DANGER)

        # Action buttons frame
        button_frame = tk.Frame(panel, bg=AppColors.BG_ELEVATED)
        button_frame.pack(fill=tk.X, pady=(8, 0))

        AppButton(button_frame, text="View Details", command=self.view_selected_staff,
                  style="secondary", width=130, height=36).pack(side=tk.LEFT, padx=5)
        AppButton(button_frame, text="Negotiate Contract", command=self.negotiate_selected_staff,
                  style="secondary", width=160, height=36).pack(side=tk.LEFT, padx=5)
        AppButton(button_frame, text="Reassign Role", command=self.reassign_selected_staff,
                  style="secondary", width=130, height=36).pack(side=tk.LEFT, padx=5)
        AppButton(button_frame, text="Release Staff", command=self.release_selected_staff,
                  style="secondary", width=130, height=36).pack(side=tk.LEFT, padx=5)

        # Report buttons on the right
        AppButton(button_frame, text="Staff Report", command=self.show_staff_report,
                  style="secondary", width=130, height=36).pack(side=tk.RIGHT, padx=5)
        AppButton(button_frame, text="Org Chart", command=self.show_organizational_chart,
                  style="secondary", width=110, height=36).pack(side=tk.RIGHT, padx=5)
    
    def create_available_staff_auto_redirect_tab(self):
        """Create a tab that jumps to the Free Agency staff page when clicked."""
        # Create empty tab that triggers redirect on selection
        redirect_frame = tk.Frame(self.notebook, bg=AppColors.BG)
        self.notebook.add(redirect_frame, text="Hire Staff")

        # Bind tab selection event to trigger redirect
        self.notebook.bind("<<NotebookTabChanged>>", self._handle_tab_change)

        # Store the tab index for this redirect tab
        self.redirect_tab_index = len(self.notebook.tabs()) - 1

    def _handle_tab_change(self, event):
        """Handle tab changes to detect the Hire Staff tab selection."""
        selected_tab = self.notebook.index(self.notebook.select())

        # If the Hire Staff tab was selected, redirect to Free Agency
        if hasattr(self, 'redirect_tab_index') and selected_tab == self.redirect_tab_index:
            # Schedule the redirect after the tab change is complete
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

        # Select the staff tab (index 1: Players=0, Staff=1, Market Overview=2)
        def select_staff_tab():
            if 'free_agency' in self.parent.open_windows:
                fa_window = self.parent.open_windows['free_agency']
                if hasattr(fa_window, 'notebook') and fa_window.winfo_exists():
                    fa_window.notebook.select(1)
                    fa_window.focus_set()

        # Schedule the tab selection for after the window is fully created
        self.parent.after_idle(select_staff_tab)

        # Close this window
        self.destroy()

    def create_staff_overview_tab(self):
        """Create staff overview and organizational chart."""
        overview_frame = tk.Frame(self.notebook, bg=AppColors.BG)
        self.notebook.add(overview_frame, text="Organization")

        # Organizational chart card
        org_card = AppCard(overview_frame, padding=10)
        org_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(12, 6))
        org_inner = org_card.get_content_frame()

        tk.Label(org_inner, text="Organizational Chart", bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(anchor='w', pady=(0, 8))

        chart_frame = tk.Frame(org_inner, bg=AppColors.BG_ELEVATED)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.org_text = tk.Text(chart_frame, bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                                font=(self.parent.FONT_FAMILY, 10), wrap=tk.WORD, height=20,
                                relief=tk.FLAT, highlightthickness=1,
                                highlightbackground=AppColors.BORDER)

        scrollbar = ttk.Scrollbar(chart_frame, orient=tk.VERTICAL, command=self.org_text.yview)
        self.org_text.configure(yscrollcommand=scrollbar.set)

        self.org_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Staff statistics card
        stats_card = AppCard(overview_frame, padding=10)
        stats_card.pack(fill=tk.X, padx=18, pady=(6, 12))
        stats_inner = stats_card.get_content_frame()

        tk.Label(stats_inner, text="Staff Statistics", bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(anchor='w', pady=(0, 8))

        self.stats_label = tk.Label(stats_inner, text="", bg=AppColors.BG_ELEVATED,
                                    fg=AppColors.TEXT_SECONDARY,
                                    font=(self.parent.FONT_FAMILY, 10), justify=tk.LEFT)
        self.stats_label.pack(anchor='w')
    
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
        self.staff_summary_label.config(text=summary_text)
        
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
        department = self.staff_filter_vars['department'].get()
        min_rating = self.staff_filter_vars['min_rating'].get()
        max_salary = self.staff_filter_vars['max_salary'].get()
        contract_status = self.staff_filter_vars['contract_status'].get()
        
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
        if not hasattr(self, 'sort_column'):
            self.sort_column = None
            self.sort_reverse = False
            
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
        self.org_text.delete(1.0, tk.END)
        
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
        
        self.org_text.insert(1.0, org_text)
    
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
        
        self.staff_summary_label.config(text=summary_text)
        
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
            
            self.stats_label.config(text=stats_text)
    
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

    def _section_card(self, parent, title):
        """Build a modern labeled card section; returns the inner content frame."""
        card = AppCard(parent, padding=10)
        card.pack(fill=tk.X, pady=(0, 10))
        inner = card.get_content_frame()
        tk.Label(inner, text=title, bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w', pady=(0, 6))
        return inner

    def _info_label(self, parent, text):
        tk.Label(parent, text=text, bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', padx=5, pady=2)

    def show_staff_details_window(self, staff: Staff, is_current: bool):
        """Show detailed staff information window."""
        details_window = tk.Toplevel(self)
        details_window.title(f"Staff Details - {staff.full_name}")
        details_window.configure(background=AppColors.BG)
        details_window.geometry("680x980")
        details_window.transient(self)

        # Main frame
        main_frame = tk.Frame(details_window, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Basic info
        info_inner = self._section_card(main_frame, "Basic Information")
        self._info_label(info_inner, f"Name: {staff.full_name}")
        self._info_label(info_inner, f"Position: {staff.role.value}")
        self._info_label(info_inner, f"Age: {staff.age}")
        self._info_label(info_inner, f"Nationality: {staff.nationality}")
        self._info_label(info_inner, f"Experience: {staff.experience} years")
        self._info_label(info_inner, f"Overall Rating: {staff.overall_rating}")
        self._info_label(info_inner, f"Reputation: {staff.reputation}")

        # Contract info
        contract_inner = self._section_card(main_frame, "Contract Information")
        self._info_label(contract_inner, f"Salary: ${staff.salary:,}")
        self._info_label(contract_inner, f"Contract Length: {staff.contract_years} years")

        # Attributes
        attr_inner = self._section_card(main_frame, "Attributes")

        # Create scrollable text for attributes
        text_frame = tk.Frame(attr_inner, bg=AppColors.BG_ELEVATED)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        attr_text = tk.Text(text_frame, bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                            font=(self.parent.FONT_FAMILY, 9), wrap=tk.WORD, height=10,
                            relief=tk.FLAT, highlightthickness=1,
                            highlightbackground=AppColors.BORDER)
        attr_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=attr_text.yview)
        attr_text.configure(yscrollcommand=attr_scrollbar.set)

        # Populate attributes
        attributes_text = self.format_staff_attributes(staff)
        attr_text.insert(1.0, attributes_text)
        attr_text.config(state=tk.DISABLED)

        attr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # On-Ice Impact - what this staffer's attributes verifiably affect
        impact_inner = self._section_card(main_frame, "On-Ice Impact")

        for line, kind in self._staff_impact_lines(staff):
            fg = {'ok': AppColors.SUCCESS, 'warn': AppColors.WARNING,
                  'info': AppColors.TEXT_TERTIARY}.get(kind, AppColors.TEXT_TERTIARY)
            tk.Label(impact_inner, text=f"\u2022  {line}", bg=AppColors.BG_ELEVATED, fg=fg,
                     font=(self.parent.FONT_FAMILY, 9), wraplength=540, justify='left',
                     anchor='w').pack(anchor='w', padx=8, pady=2)

        # Role description
        desc_inner = self._section_card(main_frame, "Role Description")

        desc_text = staff.get_role_description()
        tk.Label(desc_inner, text=desc_text, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY, font=(self.parent.FONT_FAMILY, 10),
                 wraplength=550, justify='left').pack(anchor='w', padx=5, pady=5)

        # Buttons
        button_frame = tk.Frame(main_frame, bg=AppColors.BG)
        button_frame.pack(fill=tk.X)

        if is_current:
            AppButton(button_frame, text="Negotiate Contract",
                      command=lambda: self._negotiate_current_staff(staff, details_window),
                      style="secondary", width=170, height=36).pack(side=tk.LEFT, padx=5)
            AppButton(button_frame, text="Release",
                      command=lambda: self.release_staff_action(staff, details_window),
                      style="secondary", width=110, height=36).pack(side=tk.LEFT, padx=5)
        else:
            AppButton(button_frame, text="Make Offer",
                      command=lambda: self.make_staff_offer_action(staff, details_window),
                      style="primary", width=130, height=36).pack(side=tk.LEFT, padx=5)

        AppButton(button_frame, text="Close", command=details_window.destroy,
                  style="secondary", width=110, height=36).pack(side=tk.RIGHT, padx=5)

    def _negotiate_current_staff(self, staff: Staff, details_window):
        """Negotiate with a current staffer from the details window (modal, honest result)."""
        if self.open_contract_negotiation(staff, is_hiring=False):
            messagebox.showinfo("Success", f"Contract renegotiated with {staff.full_name}!")
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
        nego_window = tk.Toplevel(self)
        nego_window.title(f"Contract Negotiation - {staff.full_name}")
        nego_window.configure(background=AppColors.BG)
        nego_window.geometry("500x430")
        nego_window.transient(self)

        # Result flag read after the modal loop exits
        nego_window._accepted = False

        # Main frame
        main_frame = tk.Frame(nego_window, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Staff info
        info_label = tk.Label(main_frame,
                              text=f"Negotiating with {staff.full_name} ({staff.role.value})",
                              bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                              font=(self.parent.FONT_FAMILY, 13, 'bold'))
        info_label.pack(pady=(0, 16))

        # Current demands
        demands_inner = self._section_card(main_frame, "Current Demands")
        self._info_label(demands_inner, f"Asking Salary: ${staff.salary:,}")
        self._info_label(demands_inner, f"Contract Length: {staff.contract_years} years")

        # Offer frame
        offer_inner = self._section_card(main_frame, "Your Offer")
        offer_grid = tk.Frame(offer_inner, bg=AppColors.BG_ELEVATED)
        offer_grid.pack(anchor='w')

        tk.Label(offer_grid, text="Salary:", bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY,
                 font=(self.parent.FONT_FAMILY, 10)).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        salary_var = tk.StringVar(value=str(staff.salary))
        salary_entry = ttk.Entry(offer_grid, textvariable=salary_var, width=15)
        salary_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(offer_grid, text="Years:", bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY,
                 font=(self.parent.FONT_FAMILY, 10)).grid(row=1, column=0, padx=5, pady=5, sticky='w')
        years_var = tk.StringVar(value=str(staff.contract_years))
        years_entry = ttk.Entry(offer_grid, textvariable=years_var, width=15)
        years_entry.grid(row=1, column=1, padx=5, pady=5)

        # Result frame
        result_frame = tk.Frame(main_frame, bg=AppColors.BG)
        result_frame.pack(fill=tk.X, pady=(0, 16))

        result_label = tk.Label(result_frame, text="", bg=AppColors.BG,
                                fg=AppColors.TEXT_SECONDARY,
                                font=(self.parent.FONT_FAMILY, 10), wraplength=450)
        result_label.pack()

        # Buttons
        button_frame = tk.Frame(main_frame, bg=AppColors.BG)
        button_frame.pack(fill=tk.X)

        def make_offer():
            try:
                offered_salary = int(salary_var.get())
                offered_years = int(years_var.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for salary and years.")
                return

            if offered_salary <= 0 or not 1 <= offered_years <= 5:
                messagebox.showerror("Invalid Input", "Salary must be positive and the term 1-5 years.")
                return

            if staff.negotiate_contract(offered_salary, offered_years):
                result_label.config(text="Offer Accepted!", fg=AppColors.SUCCESS)

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
                        if staff in self.available_staff:
                            self.available_staff.remove(staff)
                else:
                    # Update existing contract
                    staff.salary = offered_salary
                    staff.contract_years = offered_years

                nego_window._accepted = True
                nego_window.destroy()
            else:
                result_label.config(text="Offer Rejected. Try adjusting your offer.",
                                    fg=AppColors.DANGER)

        AppButton(button_frame, text="Make Offer", command=make_offer,
                  style="primary", width=130, height=36).pack(side=tk.LEFT, padx=5)
        AppButton(button_frame, text="Cancel", command=nego_window.destroy,
                  style="secondary", width=110, height=36).pack(side=tk.RIGHT, padx=5)

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
                categories['Analytics'].append(staff)
        
        return categories
    
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
        
        context_menu = tk.Menu(self, tearoff=0, bg=AppColors.BG_ELEVATED,
                               fg=AppColors.TEXT_PRIMARY,
                               activebackground=AppColors.ACCENT_BG,
                               activeforeground=AppColors.TEXT_PRIMARY)
        context_menu.add_command(label=f"View {staff.full_name} Details", command=lambda: self.show_staff_details_window(staff, True))
        context_menu.add_command(label="Negotiate Contract", command=self.negotiate_selected_staff)
        context_menu.add_command(label="Reassign Role", command=self.reassign_selected_staff)
        context_menu.add_separator()
        context_menu.add_command(label="Release Staff", command=self.release_selected_staff)
        
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
            msg = "Contract Negotiation Results:\n" + "\n".join(results)
            messagebox.showinfo("Negotiation Results", msg)

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
    
    def get_current_team_staff(self):
        """Get current team staff list."""
        user_team = self._get_user_team()
        return user_team.staff if user_team else []
    
    def show_multiple_staff_summary(self):
        """Show summary window for multiple selected staff."""
        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        summary_window = tk.Toplevel(self)
        summary_window.title(f"Selected Staff Summary ({len(selected_staff_list)} staff)")
        summary_window.configure(background=AppColors.BG)
        summary_window.geometry("600x500")
        summary_window.transient(self)

        main_frame = tk.Frame(summary_window, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        title_label = tk.Label(main_frame, text=f"Selected Staff Summary ({len(selected_staff_list)} staff)",
                               bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                               font=(self.parent.FONT_FAMILY, 14, 'bold'))
        title_label.pack(pady=(0, 16))

        # Create text widget with scrollbar
        text_frame = tk.Frame(main_frame, bg=AppColors.BG)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(text_frame, wrap='word', bg=AppColors.BG_ELEVATED,
                              fg=AppColors.TEXT_PRIMARY, font=(self.parent.FONT_FAMILY, 11),
                              relief=tk.FLAT, highlightthickness=1,
                              highlightbackground=AppColors.BORDER)
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        text_widget.pack(side='left', fill='both', expand=True)
        
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
            summary_content += f"  Rating: {staff.overall_rating} | Salary: ${staff.salary:,} | Morale: {morale}/20\n\n"
        
        text_widget.insert('1.0', summary_content)
        text_widget.config(state='disabled')

        # Close button
        AppButton(main_frame, text="Close", command=summary_window.destroy,
                  style="secondary", width=110, height=36).pack(pady=10)

    def reassign_single_staff(self, staff):
        """Reassign role for a single staff member."""
        # Create reassignment window
        reassign_window = tk.Toplevel(self)
        reassign_window.title(f"Reassign {staff.full_name}")
        reassign_window.configure(background=AppColors.BG)
        reassign_window.geometry("400x320")
        reassign_window.transient(self)

        main_frame = tk.Frame(reassign_window, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(main_frame, text=f"Reassign {staff.full_name}", bg=AppColors.BG,
                 fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 13, 'bold')).pack(pady=(0, 10))
        tk.Label(main_frame, text=f"Current Role: {staff.role.value}", bg=AppColors.BG,
                 fg=AppColors.TEXT_SECONDARY,
                 font=(self.parent.FONT_FAMILY, 10)).pack(pady=(0, 10))

        tk.Label(main_frame, text="New Role:", bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                 font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w')
        new_role_var = tk.StringVar(value=staff.role.value)
        role_combo = ttk.Combobox(main_frame, textvariable=new_role_var,
                                  values=[role.value for role in StaffRole], state='readonly')
        role_combo.pack(fill='x', pady=5)

        def confirm_reassignment():
            new_role_name = new_role_var.get()
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
        
        button_frame = tk.Frame(main_frame, bg=AppColors.BG)
        button_frame.pack(fill='x', pady=20)

        AppButton(button_frame, text="Confirm", command=confirm_reassignment,
                  style="primary", width=120, height=36).pack(side='left', padx=5)
        AppButton(button_frame, text="Cancel", command=reassign_window.destroy,
                  style="secondary", width=110, height=36).pack(side='right', padx=5)

    def reassign_multiple_staff(self, staff_list):
        """Reassign roles for multiple staff members."""
        # Create bulk reassignment window
        reassign_window = tk.Toplevel(self)
        reassign_window.title(f"Bulk Reassign ({len(staff_list)} staff)")
        reassign_window.configure(background=AppColors.BG)
        reassign_window.geometry("600x500")
        reassign_window.transient(self)

        main_frame = tk.Frame(reassign_window, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(main_frame, text=f"Bulk Reassign {len(staff_list)} Staff Members",
                 bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 13, 'bold')).pack(pady=(0, 16))

        # Create list of staff with role dropdowns
        canvas = tk.Canvas(main_frame, bg=AppColors.BG_ELEVATED,
                           highlightthickness=1, highlightbackground=AppColors.BORDER)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=AppColors.BG_ELEVATED)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Role selection for each staff member
        role_vars = {}
        for i, staff in enumerate(staff_list):
            staff_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
            staff_frame.pack(fill='x', pady=5, padx=10)

            tk.Label(staff_frame, text=f"{staff.full_name}:", bg=AppColors.BG_ELEVATED,
                     fg=AppColors.TEXT_PRIMARY,
                     font=(self.parent.FONT_FAMILY, 10)).pack(side='left')

            role_var = tk.StringVar(value=staff.role.value)
            role_vars[staff.id] = role_var

            role_combo = ttk.Combobox(staff_frame, textvariable=role_var,
                                      values=[role.value for role in StaffRole],
                                      state='readonly', width=20)
            role_combo.pack(side='right')

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def apply_reassignments():
            # Resolve requested roles first, then validate unique roles across
            # the whole team before applying anything.
            new_roles = {}
            for staff in staff_list:
                new_role_name = role_vars[staff.id].get()
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

        button_frame = tk.Frame(main_frame, bg=AppColors.BG)
        button_frame.pack(fill='x', pady=10)

        AppButton(button_frame, text="Apply Changes", command=apply_reassignments,
                  style="primary", width=150, height=36).pack(side='left', padx=5)
        AppButton(button_frame, text="Cancel", command=reassign_window.destroy,
                  style="secondary", width=110, height=36).pack(side='right', padx=5)
    
    def _report_window(self, title, content):
        """Shared modern scrollable-text dialog used by the report/chart views."""
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(background=AppColors.BG)
        win.geometry("800x600")
        win.transient(self)

        main_frame = tk.Frame(win, bg=AppColors.BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(main_frame, text=title, bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                 font=(self.parent.FONT_FAMILY, 14, 'bold')).pack(pady=(0, 16))

        # Create text widget with scrollbar
        text_frame = tk.Frame(main_frame, bg=AppColors.BG)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(text_frame, wrap='word', bg=AppColors.BG_ELEVATED,
                              fg=AppColors.TEXT_PRIMARY, font=(self.parent.FONT_FAMILY, 11),
                              relief=tk.FLAT, highlightthickness=1,
                              highlightbackground=AppColors.BORDER)
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        text_widget.pack(side='left', fill='both', expand=True)

        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')

        # Close button
        AppButton(main_frame, text="Close", command=win.destroy,
                  style="secondary", width=110, height=36).pack(pady=10)

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
                    report += f"  Overall: {staff.overall_rating} | Experience: {staff.experience}y | Morale: {morale}/20\n"
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
    