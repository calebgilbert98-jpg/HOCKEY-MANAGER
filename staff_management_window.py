"""
Enhanced Staff Management Window for Hockey Manager
Provides comprehensive staff hiring, firing, and management with EHM-style depth.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
from typing import Dict, List, Optional
from game_classes import Staff, StaffRole
from game_classes import debug_print

class StaffManagementWindow(tk.Toplevel):
    """Comprehensive staff management interface with EHM-style functionality."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Staff Management - Hockey Manager")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1200x800")
        
        # Available staff candidates for hiring
        self.available_staff: List[Staff] = []
        
        self.create_widgets()
        
        # Update current staff view only (not available staff since we redirect to Free Agency)
        self.update_current_staff_view()
        # Skip update_staff_overview() and update_staff_summary() as they reference UI elements that don't exist in redirect mode
        
        # Track window
        self.parent.open_windows['staff'] = self
    
    def create_widgets(self):
        """Create the main interface widgets."""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Staff Management", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create notebook for different tabs
        self.notebook = ttk.Notebook(main_frame, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Current Staff tab
        self.create_current_staff_tab()
        
        # Available Staff tab - automatically redirects to Free Agency staff page
        self.create_available_staff_auto_redirect_tab()
        
        # Staff Overview tab
        self.create_staff_overview_tab()
    
    def create_current_staff_tab(self):
        """Create the current staff management tab with trade-block-style interaction."""
        current_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(current_frame, text="Current Staff")
        
        # Initialize selection tracking like trade block
        self.selected_staff = set()
        self.staff_map = {}
        
        # Staff summary panel - like trade block summary
        summary_frame = ttk.Frame(current_frame, style='Panel.TFrame', padding=8)
        summary_frame.pack(fill=tk.X, padx=18, pady=(8, 0))
        
        self.staff_summary_label = ttk.Label(summary_frame, text="", style='Summary.TLabel')
        self.staff_summary_label.pack(anchor='w')
        
        # Filter panel - similar to trade block
        filter_frame = ttk.Frame(current_frame, style='Panel.TFrame', padding=8)
        filter_frame.pack(fill=tk.X, padx=18, pady=(8, 0))
        
        self.staff_filter_vars = {
            'department': tk.StringVar(value="All"),
            'min_rating': tk.StringVar(value=""),
            'max_salary': tk.StringVar(value=""),
            'contract_status': tk.StringVar(value="All")
        }
        
        ttk.Label(filter_frame, text="Department:", style='Content.TLabel').pack(side=tk.LEFT)
        dept_options = ["All", "Management", "Coaching", "Development", "Scouting", "Medical", "Analytics"]
        ttk.Combobox(filter_frame, textvariable=self.staff_filter_vars['department'], 
                    values=dept_options, width=12, state='readonly').pack(side=tk.LEFT, padx=2)
        
        ttk.Label(filter_frame, text="Min Rating:", style='Content.TLabel').pack(side=tk.LEFT)
        tk.Entry(filter_frame, textvariable=self.staff_filter_vars['min_rating'], width=4, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(filter_frame, text="Max Salary:", style='Content.TLabel').pack(side=tk.LEFT)
        tk.Entry(filter_frame, textvariable=self.staff_filter_vars['max_salary'], width=8, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(filter_frame, text="Contract:", style='Content.TLabel').pack(side=tk.LEFT)
        ttk.Combobox(filter_frame, textvariable=self.staff_filter_vars['contract_status'], 
                    values=["All", "Expiring", "Long-term"], width=10, state='readonly').pack(side=tk.LEFT, padx=2)
        
        ttk.Button(filter_frame, text="Apply Filter", command=self.update_current_staff_view, 
                  style='TButton').pack(side=tk.LEFT, padx=8)
        
        # Main panel frame
        panel = ttk.Frame(current_frame, style='Panel.TFrame', padding=12)
        panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        
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
        
        # Configure tags for visual feedback
        self.current_staff_tree.tag_configure('selected', background='#333333')
        self.current_staff_tree.tag_configure('high_morale', foreground='#4CAF50')
        self.current_staff_tree.tag_configure('low_morale', foreground='#F44336')
        
        # Action buttons frame - like trade block
        button_frame = ttk.Frame(panel, style='Panel.TFrame')
        button_frame.pack(fill=tk.X, pady=(8, 0))
        
        ttk.Button(button_frame, text="View Details", command=self.view_selected_staff, 
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Negotiate Contract", command=self.negotiate_selected_staff, 
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reassign Role", command=self.reassign_selected_staff, 
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Release Staff", command=self.release_selected_staff, 
                  style='TButton').pack(side=tk.LEFT, padx=5)
        
        # Report buttons on the right
        ttk.Button(button_frame, text="Staff Report", command=self.show_staff_report, 
                  style='TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Org Chart", command=self.show_organizational_chart, 
                  style='TButton').pack(side=tk.RIGHT, padx=5)
    
    def create_available_staff_auto_redirect_tab(self):
        """Create a tab that automatically redirects to Free Agency staff page when clicked."""
        # Create empty tab that triggers redirect on selection
        redirect_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(redirect_frame, text="Available Staff")
        
        # Bind tab selection event to trigger redirect
        self.notebook.bind("<<NotebookTabChanged>>", self._handle_tab_change)
        
        # Store the tab index for this redirect tab
        self.redirect_tab_index = len(self.notebook.tabs()) - 1
        
    def _handle_tab_change(self, event):
        """Handle tab changes to detect Available Staff tab selection."""
        selected_tab = self.notebook.index(self.notebook.select())
        
        # If the Available Staff tab was selected, redirect to Free Agency
        if hasattr(self, 'redirect_tab_index') and selected_tab == self.redirect_tab_index:
            # Schedule the redirect after the tab change is complete
            self.after_idle(self._redirect_to_free_agency)
    
    def _redirect_to_free_agency(self):
        """Redirect to Free Agency staff page and close this window."""
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

    def open_enhanced_staff_market(self):
        """Open the enhanced Free Agency window and focus on the staff tab."""
        # Close this window
        self.destroy()
        
        # Open the enhanced free agency window
        self.parent.open_free_agency_window()
        
        # Use after_idle to ensure the window is fully created before selecting tab
        def select_staff_tab():
            if 'free_agency' in self.parent.open_windows:
                fa_window = self.parent.open_windows['free_agency']
                if hasattr(fa_window, 'notebook') and fa_window.winfo_exists():
                    # Select the staff tab (index 1: Players=0, Staff=1, Market Overview=2)
                    fa_window.notebook.select(1)
                    fa_window.focus_set()
        
        # Schedule the tab selection for after the window is fully created
        self.parent.after_idle(select_staff_tab)
    
    def create_staff_overview_tab(self):
        """Create staff overview and organizational chart."""
        overview_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(overview_frame, text="Organization")
        
        # Organizational chart
        org_frame = ttk.LabelFrame(overview_frame, text="Organizational Chart", style='Panel.TLabelframe')
        org_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create scrollable text widget for org chart
        chart_frame = ttk.Frame(org_frame, style='Panel.TFrame')
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.org_text = tk.Text(chart_frame, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                               font=(self.parent.FONT_FAMILY, 10), wrap=tk.WORD, height=20)
        
        scrollbar = ttk.Scrollbar(chart_frame, orient=tk.VERTICAL, command=self.org_text.yview)
        self.org_text.configure(yscrollcommand=scrollbar.set)
        
        self.org_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Staff statistics
        stats_frame = ttk.LabelFrame(overview_frame, text="Staff Statistics", style='Panel.TLabelframe')
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.stats_label = ttk.Label(stats_frame, text="", style='Content.TLabel', justify=tk.LEFT)
        self.stats_label.pack(pady=5, anchor='w')
    
    def generate_available_staff(self):
        """Access the league's entire free agent staff population with realistic diversity."""
        # Always start fresh
        self.available_staff = []
        
        # First check if the league has free agent staff
        if hasattr(self.parent.game_manager.league, 'free_agent_staff') and self.parent.game_manager.league.free_agent_staff:
            # Use the actual league free agent staff
            self.available_staff.extend(self.parent.game_manager.league.free_agent_staff)
            print(f"Found {len(self.available_staff)} existing free agent staff")
        
        # Always generate additional staff to ensure we have a large pool (150-200 candidates)
        current_count = len(self.available_staff)
        target_count = 180  # Target number of available staff
        
        if current_count < target_count:
            additional_needed = target_count - current_count
            print(f"Generating {additional_needed} additional staff candidates...")
            
            # Expanded name pools for more diversity
            first_names_male = [
                "Mike", "John", "Dave", "Steve", "Bob", "Jim", "Tom", "Dan", "Chris", "Mark",
                "Paul", "Rob", "Tim", "Ken", "Bill", "Joe", "Matt", "Rick", "Scott", "Jeff",
                "Brad", "Kevin", "Ryan", "Brian", "Jason", "Eric", "Todd", "Gary", "Sean", "Craig",
                "Trevor", "Derek", "Kyle", "Shane", "Wade", "Brett", "Luke", "Tyler", "Cody", "Blake",
                "Nathan", "Connor", "Cameron", "Jordan", "Austin", "Logan", "Mason", "Ethan", "Noah"
            ]
            
            first_names_female = [
                "Sarah", "Jennifer", "Jessica", "Amanda", "Michelle", "Lisa", "Karen", "Nicole", "Amy", "Angela",
                "Stephanie", "Rachel", "Christine", "Emily", "Rebecca", "Laura", "Sharon", "Cynthia", "Kathleen", "Helen",
                "Maria", "Donna", "Ruth", "Patricia", "Sandra", "Janet", "Catherine", "Frances", "Carolyn", "Samantha",
                "Deborah", "Rachel", "Anna", "Marie", "Elizabeth", "Diana", "Julie", "Joyce", "Virginia", "Gloria"
            ]
            
            last_names = [
                "Johnson", "Smith", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                "Hernandez", "Lopez", "Gonzales", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
                "Lee", "White", "Thompson", "Robinson", "Clark", "Lewis", "Young", "Allen", "King", "Wright",
                "Hill", "Scott", "Green", "Adams", "Baker", "Gonzalez", "Nelson", "Carter", "Mitchell", "Perez",
                "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Sanchez",
                "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy", "Bailey", "Rivera", "Cooper",
                "Richardson", "Cox", "Howard", "Ward", "Torres", "Peterson", "Gray", "Ramirez", "James", "Watson",
                "Brooks", "Kelly", "Sanders", "Price", "Bennett", "Wood", "Barnes", "Ross", "Henderson", "Coleman",
                "Jenkins", "Perry", "Powell", "Long", "Patterson", "Hughes", "Flores", "Washington", "Butler", "Simmons"
            ]
            
            # European and international names for diversity
            international_names = {
                'Sweden': [("Lars", "Andersson"), ("Erik", "Karlsson"), ("Magnus", "Lindqvist"), ("Nils", "Pettersson"),
                          ("Ulf", "Samuelsson"), ("Mats", "Naslund"), ("Nicklas", "Backstrom"), ("Henrik", "Lundqvist")],
                'Finland': [("Jukka", "Jalonen"), ("Pekka", "Rinne"), ("Saku", "Koivu"), ("Teemu", "Selanne"),
                           ("Mikko", "Koivu"), ("Tuomo", "Ruutu"), ("Valtteri", "Filppula"), ("Olli", "Jokinen")],
                'Russia': [("Sergei", "Fedorov"), ("Pavel", "Datsyuk"), ("Igor", "Larionov"), ("Vladimir", "Konstantinov"),
                          ("Alexei", "Yashin"), ("Evgeni", "Malkin"), ("Alexander", "Ovechkin"), ("Nikolai", "Khabibulin")],
                'Czech Republic': [("Jaromir", "Jagr"), ("Dominik", "Hasek"), ("Pavel", "Nedved"), ("Patrik", "Elias"),
                                  ("Milan", "Hejduk"), ("Robert", "Lang"), ("Martin", "Straka"), ("Petr", "Svoboda")],
                'Germany': [("Marco", "Sturm"), ("Jochen", "Hecht"), ("Marcel", "Goc"), ("Dennis", "Seidenberg"),
                           ("Christian", "Ehrhoff"), ("Tobias", "Rieder"), ("Leon", "Draisaitl"), ("Tim", "Stutzle")],
                'Switzerland': [("Mark", "Streit"), ("Nino", "Niederreiter"), ("Roman", "Josi"), ("Yannick", "Weber"),
                               ("Raphael", "Diaz"), ("Luca", "Sbisa"), ("Kevin", "Fiala"), ("Nico", "Hischier")]
            }
            
            # Nationality distribution (realistic for hockey)
            nationalities = ['Canada'] * 35 + ['USA'] * 30 + ['Sweden'] * 8 + ['Finland'] * 6 + \
                           ['Russia'] * 5 + ['Czech Republic'] * 4 + ['Germany'] * 2 + ['Switzerland'] * 2
            
            # Strategic role distribution for hockey operations
            role_distribution = {
                StaffRole.GENERAL_MANAGER: 8,
                StaffRole.HEAD_COACH: 10,
                StaffRole.ASSISTANT_COACH: 25,
                StaffRole.GOALIE_COACH: 12,
                StaffRole.SKILLS_COACH: 15,
                StaffRole.CONDITIONING_COACH: 10,
                StaffRole.HEAD_SCOUT: 8,
                StaffRole.AMATEUR_SCOUT: 20,
                StaffRole.PROFESSIONAL_SCOUT: 15,
                StaffRole.ASSISTANT_GENERAL_MANAGER: 6,
                StaffRole.PHYSIOTHERAPIST: 8,
                StaffRole.EQUIPMENT_MANAGER: 5,
                StaffRole.TEAM_DOCTOR: 4,
                StaffRole.VIDEO_COACH: 10,
                StaffRole.STRENGTH_COACH: 8,
                StaffRole.SKATING_COACH: 6,
                StaffRole.EUROPEAN_SCOUT: 8,
                StaffRole.ADVANCE_SCOUT: 7,
                StaffRole.ASSOCIATE_COACH: 8,
                StaffRole.POWER_PLAY_COACH: 5,
                StaffRole.PENALTY_KILL_COACH: 5,
                StaffRole.STATISTICIAN: 6,
                StaffRole.MEDIA_RELATIONS: 4
            }
            
            # Create roles list with proper distribution
            roles_to_create = []
            for role, count in role_distribution.items():
                roles_to_create.extend([role] * count)
            
            # Shuffle for randomness
            random.shuffle(roles_to_create)
            
            # Generate staff members
            generated_count = 0
            while generated_count < additional_needed and roles_to_create:
                role = roles_to_create[generated_count % len(roles_to_create)]
                nationality = random.choice(nationalities)
                
                # Select names based on nationality
                if nationality in international_names:
                    first_name, last_name = random.choice(international_names[nationality])
                else:
                    # Use gender distribution (roughly 85% male, 15% female in hockey ops)
                    if random.random() < 0.15:
                        first_name = random.choice(first_names_female)
                    else:
                        first_name = random.choice(first_names_male)
                    last_name = random.choice(last_names)
                
                # Create staff member
                staff = Staff(
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    age=random.randint(28, 65),
                    nationality=nationality,
                    experience=random.randint(1, 25)
                )
                
                # Set realistic salaries based on role hierarchy
                role_salary_ranges = {
                    StaffRole.GENERAL_MANAGER: (800000, 2500000),
                    StaffRole.HEAD_COACH: (600000, 2000000),
                    StaffRole.ASSISTANT_COACH: (200000, 600000),
                    StaffRole.GOALIE_COACH: (180000, 400000),
                    StaffRole.HEAD_SCOUT: (250000, 500000),
                    StaffRole.ASSISTANT_GENERAL_MANAGER: (300000, 700000),
                    StaffRole.PROFESSIONAL_SCOUT: (120000, 300000),
                    StaffRole.AMATEUR_SCOUT: (80000, 200000),
                    StaffRole.SKILLS_COACH: (150000, 350000),
                    StaffRole.CONDITIONING_COACH: (120000, 280000),
                    StaffRole.VIDEO_COACH: (100000, 250000),
                    StaffRole.STRENGTH_COACH: (100000, 240000),
                    StaffRole.PHYSIOTHERAPIST: (90000, 200000),
                    StaffRole.TEAM_DOCTOR: (150000, 400000),
                    StaffRole.EQUIPMENT_MANAGER: (70000, 150000),
                    StaffRole.SKATING_COACH: (90000, 200000),
                    StaffRole.EUROPEAN_SCOUT: (100000, 250000),
                    StaffRole.ADVANCE_SCOUT: (90000, 220000),
                    StaffRole.ASSOCIATE_COACH: (180000, 450000),
                    StaffRole.POWER_PLAY_COACH: (150000, 350000),
                    StaffRole.PENALTY_KILL_COACH: (150000, 350000),
                    StaffRole.STATISTICIAN: (80000, 180000),
                    StaffRole.MEDIA_RELATIONS: (70000, 160000)
                }
                
                min_salary, max_salary = role_salary_ranges.get(role, (75000, 200000))
                base_salary = random.randint(min_salary, max_salary)
                
                # Experience and age adjustments
                experience_bonus = max(0, (staff.experience - 5) * 0.02)
                age_penalty = max(0, (staff.age - 55) * 0.01) if staff.age > 55 else 0
                
                # Add randomization
                random_factor = random.uniform(0.9, 1.2)
                
                staff.salary = int(base_salary * (1 + experience_bonus - age_penalty) * random_factor)
                staff.contract_years = random.randint(1, 4)
                
                self.available_staff.append(staff)
                generated_count += 1
        
        print(f"Total available staff: {len(self.available_staff)}")
        
        # Force update the view if the tree exists
        if hasattr(self, 'available_staff_tree'):
            self.update_available_staff_view()
    
    def filter_available_staff(self, event=None):
        """Filter available staff based on selected criteria."""
        self.update_available_staff_view()
    
    def update_views(self):
        """Update all views with current data."""
        self.update_current_staff_view()
        # Skip updating available staff view since we redirect to Free Agency
        # self.update_available_staff_view()
        self.update_staff_overview()
        self.update_staff_summary()
    
    def update_current_staff_view(self):
        """Update the current staff treeview with trade-block-style interaction."""
        # Clear existing items
        for item in self.current_staff_tree.get_children():
            self.current_staff_tree.delete(item)
        
        self.staff_map = {}
        
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
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
    
    def update_available_staff_view(self):
        """Update the available staff treeview with comprehensive filtering and sorting."""
        # Clear existing items
        for item in self.available_staff_tree.get_children():
            self.available_staff_tree.delete(item)
        
        debug_print(f"DEBUG: Updating available staff view with {len(self.available_staff)} total staff")
        
        # Get filter values (with safe defaults)
        name_search = self.name_search.get().lower() if hasattr(self, 'name_search') else ''
        role_filter = self.role_filter.get() if hasattr(self, 'role_filter') else 'All'
        department_filter = self.department_filter.get() if hasattr(self, 'department_filter') else 'All'
        nationality_filter = self.nationality_filter.get() if hasattr(self, 'nationality_filter') else 'All'
        salary_filter = self.salary_filter.get() if hasattr(self, 'salary_filter') else 'Any'
        age_filter = self.age_filter.get() if hasattr(self, 'age_filter') else 'Any'
        rating_filter = self.rating_filter.get() if hasattr(self, 'rating_filter') else 'Any'
        contract_filter = self.contract_filter.get() if hasattr(self, 'contract_filter') else 'Any'
        sort_by = self.sort_filter.get() if hasattr(self, 'sort_filter') else 'Overall Rating'
        
        # Apply filters
        filtered_staff = []
        
        for staff in self.available_staff:
            # Name search filter
            if name_search and name_search not in staff.full_name.lower():
                continue
            
            # Role filter
            if role_filter != 'All' and staff.role.value != role_filter:
                continue
            
            # Department filter
            if department_filter != 'All':
                from game_classes import Staff as StaffClass
                staff_dept = StaffClass.get_role_department(staff.role)
                if staff_dept != department_filter:
                    continue
            
            # Nationality filter
            if nationality_filter != 'All' and staff.nationality != nationality_filter:
                continue
            
            # Salary range filter
            if salary_filter != 'Any':
                if salary_filter == 'Under $100k' and staff.salary >= 100000:
                    continue
                elif salary_filter == '$100k-$200k' and not (100000 <= staff.salary < 200000):
                    continue
                elif salary_filter == '$200k-$300k' and not (200000 <= staff.salary < 300000):
                    continue
                elif salary_filter == '$300k-$500k' and not (300000 <= staff.salary < 500000):
                    continue
                elif salary_filter == 'Over $500k' and staff.salary < 500000:
                    continue
            
            # Age range filter
            if age_filter != 'Any':
                if age_filter == 'Under 30' and staff.age >= 30:
                    continue
                elif age_filter == '30-40' and not (30 <= staff.age < 40):
                    continue
                elif age_filter == '40-50' and not (40 <= staff.age < 50):
                    continue
                elif age_filter == '50-60' and not (50 <= staff.age < 60):
                    continue
                elif age_filter == 'Over 60' and staff.age < 60:
                    continue
            
            # Rating filter
            if rating_filter != 'Any':
                min_rating = int(rating_filter.replace('+', ''))
                if staff.overall_rating < min_rating:
                    continue
            
            # Contract length filter
            if contract_filter != 'Any':
                if contract_filter == '1 year' and staff.contract_years != 1:
                    continue
                elif contract_filter == '2 years' and staff.contract_years != 2:
                    continue
                elif contract_filter == '3+ years' and staff.contract_years < 3:
                    continue
            
            filtered_staff.append(staff)
        
        # Sort the filtered results
        if sort_by == 'Name':
            filtered_staff.sort(key=lambda s: s.full_name)
        elif sort_by == 'Position':
            filtered_staff.sort(key=lambda s: s.role.value)
        elif sort_by == 'Overall Rating':
            filtered_staff.sort(key=lambda s: s.overall_rating, reverse=True)
        elif sort_by == 'Salary':
            filtered_staff.sort(key=lambda s: s.salary, reverse=True)
        elif sort_by == 'Age':
            filtered_staff.sort(key=lambda s: s.age)
        elif sort_by == 'Nationality':
            filtered_staff.sort(key=lambda s: s.nationality)
        
        # Populate the treeview
        for staff in filtered_staff:
            # Get department for display
            from game_classes import Staff as StaffClass
            department = StaffClass.get_role_department(staff.role)
            
            # Get key skills display
            key_skills = self.get_key_skills_display(staff)
            
            # Calculate years of experience based on age and role
            min_age_for_role = 22 if staff.role in [StaffRole.AMATEUR_SCOUT, StaffRole.SKILLS_COACH] else 25
            experience = max(0, staff.age - min_age_for_role)
            experience_text = f"{experience}y" if experience > 0 else "Entry"
            
            values = {
                'name': staff.full_name,
                'role': staff.role.value,
                'dept': department,
                'overall': staff.overall_rating,
                'key_skills': key_skills,
                'experience': experience_text,
                'salary': f"${staff.salary:,}",
                'years': f"{staff.contract_years}y",
                'age': staff.age,
                'nationality': staff.nationality
            }
            
            item_id = self.available_staff_tree.insert('', 'end', values=list(values.values()))
            
            # Store staff object reference
            if 'available_staff' not in self.parent.tree_maps:
                self.parent.tree_maps['available_staff'] = {}
            self.parent.tree_maps['available_staff'][item_id] = staff
            
            # Color coding by overall rating
            if staff.overall_rating >= 80:
                self.available_staff_tree.set(item_id, 'overall', f"⭐ {staff.overall_rating}")
            elif staff.overall_rating >= 75:
                self.available_staff_tree.set(item_id, 'overall', f"🔹 {staff.overall_rating}")
        
        debug_print(f"DEBUG: Added {len(filtered_staff)} staff to the tree view")
        
        # Update results summary
        total_available = len(self.available_staff)
        showing = len(filtered_staff)
        if hasattr(self, 'results_summary'):
            self.results_summary.config(text=f"Showing {showing} of {total_available} candidates")
        
        # Update selection info
        if hasattr(self, 'selection_info'):
            if showing == 0:
                self.selection_info.config(text="No candidates match current filters")
            else:
                self.selection_info.config(text="Select a candidate for more options")
    
    def update_staff_overview(self):
        """Update the organizational chart and overview."""
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
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
            org_text += "⚠️  STAFF ISSUES:\n"
            for error in validation_issues['errors']:
                org_text += f"  ❌ ERROR: {error}\n"
            for warning in validation_issues['warnings']:
                org_text += f"  ⚠️  WARNING: {warning}\n"
            org_text += "\n"
        else:
            org_text += "✅ Staff structure validated - No issues found.\n\n"
        
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
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
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
    
    def view_staff_details(self):
        """Legacy method - redirect to new selection-based approach."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select a staff member to view details.")
            return
        
        # Get first selected staff
        staff_id = next(iter(self.selected_staff))
        staff = next((s for s in self.get_current_team_staff() if s.id == staff_id), None)
        if staff:
            self.show_staff_details_window(staff, is_current=True)
    
    def negotiate_contract(self):
        """Legacy method - redirect to new selection-based approach."""
        self.negotiate_selected_staff()
    
    def release_staff(self):
        """Legacy method - redirect to new selection-based approach."""
        self.release_selected_staff()
    
    def view_candidate_details(self):
        """View detailed information about selected candidate."""
        selection = self.available_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a candidate to view details.")
            return
        
        staff = self.parent.tree_maps['available_staff'][selection[0]]
        self.show_staff_details_window(staff, is_current=False)
    
    def show_staff_details_window(self, staff: Staff, is_current: bool):
        """Show detailed staff information window."""
        details_window = tk.Toplevel(self)
        details_window.title(f"Staff Details - {staff.full_name}")
        details_window.configure(background=self.parent.BG_COLOR)
        details_window.geometry("600x700")
        
        # Main frame
        main_frame = ttk.Frame(details_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Basic info
        info_frame = ttk.LabelFrame(main_frame, text="Basic Information", style='Panel.TLabelframe')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Name: {staff.full_name}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Position: {staff.role.value}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Age: {staff.age}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Nationality: {staff.nationality}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Experience: {staff.experience} years", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Overall Rating: {staff.overall_rating}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Reputation: {staff.reputation}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        
        # Contract info
        contract_frame = ttk.LabelFrame(main_frame, text="Contract Information", style='Panel.TLabelframe')
        contract_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(contract_frame, text=f"Salary: ${staff.salary:,}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(contract_frame, text=f"Contract Length: {staff.contract_years} years", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        
        # Attributes
        attr_frame = ttk.LabelFrame(main_frame, text="Attributes", style='Panel.TLabelframe')
        attr_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create scrollable text for attributes
        text_frame = ttk.Frame(attr_frame, style='Panel.TFrame')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        attr_text = tk.Text(text_frame, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                           font=(self.parent.FONT_FAMILY, 9), wrap=tk.WORD, height=15)
        attr_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=attr_text.yview)
        attr_text.configure(yscrollcommand=attr_scrollbar.set)
        
        # Populate attributes
        attributes_text = self.format_staff_attributes(staff)
        attr_text.insert(1.0, attributes_text)
        attr_text.config(state=tk.DISABLED)
        
        attr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Role description
        desc_frame = ttk.LabelFrame(main_frame, text="Role Description", style='Panel.TLabelframe')
        desc_frame.pack(fill=tk.X, pady=(0, 10))
        
        desc_text = staff.get_role_description()
        ttk.Label(desc_frame, text=desc_text, style='Content.TLabel', wraplength=550).pack(anchor='w', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        button_frame.pack(fill=tk.X)
        
        if is_current:
            ttk.Button(button_frame, text="Negotiate Contract", 
                      command=lambda: self.open_contract_negotiation(staff),
                      style='TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Release", 
                      command=lambda: self.release_staff_action(staff, details_window),
                      style='TButton').pack(side=tk.LEFT, padx=5)
        else:
            ttk.Button(button_frame, text="Make Offer", 
                      command=lambda: self.make_staff_offer_action(staff, details_window),
                      style='TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Close", command=details_window.destroy,
                  style='TButton').pack(side=tk.RIGHT, padx=5)
    
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
    
    def make_staff_offer(self):
        """Make an offer to selected available staff."""
        selection = self.available_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a candidate to make an offer.")
            return
        
        staff = self.parent.tree_maps['available_staff'][selection[0]]
        self.open_contract_negotiation(staff, is_hiring=True)
    
    def open_contract_negotiation(self, staff: Staff, is_hiring: bool = False):
        """Open contract negotiation window."""
        nego_window = tk.Toplevel(self)
        nego_window.title(f"Contract Negotiation - {staff.full_name}")
        nego_window.configure(background=self.parent.BG_COLOR)
        nego_window.geometry("500x400")
        
        # Main frame
        main_frame = ttk.Frame(nego_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Staff info
        info_label = ttk.Label(main_frame, 
                              text=f"Negotiating with {staff.full_name} ({staff.role.value})",
                              style='Title.TLabel')
        info_label.pack(pady=(0, 20))
        
        # Current demands
        demands_frame = ttk.LabelFrame(main_frame, text="Current Demands", style='Panel.TLabelframe')
        demands_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(demands_frame, text=f"Asking Salary: ${staff.salary:,}", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        ttk.Label(demands_frame, text=f"Contract Length: {staff.contract_years} years", style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        
        # Offer frame
        offer_frame = ttk.LabelFrame(main_frame, text="Your Offer", style='Panel.TLabelframe')
        offer_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(offer_frame, text="Salary:", style='Content.TLabel').grid(row=0, column=0, padx=5, pady=5, sticky='w')
        salary_var = tk.StringVar(value=str(staff.salary))
        salary_entry = ttk.Entry(offer_frame, textvariable=salary_var, width=15)
        salary_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(offer_frame, text="Years:", style='Content.TLabel').grid(row=1, column=0, padx=5, pady=5, sticky='w')
        years_var = tk.StringVar(value=str(staff.contract_years))
        years_entry = ttk.Entry(offer_frame, textvariable=years_var, width=15)
        years_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Result frame
        result_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        result_frame.pack(fill=tk.X, pady=(0, 20))
        
        result_label = ttk.Label(result_frame, text="", style='Content.TLabel', wraplength=450)
        result_label.pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        button_frame.pack(fill=tk.X)
        
        def make_offer():
            try:
                offered_salary = int(salary_var.get())
                offered_years = int(years_var.get())
                
                if staff.negotiate_contract(offered_salary, offered_years):
                    result_label.config(text="Offer Accepted!")
                    
                    if is_hiring:
                        # Add to team with role validation
                        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
                        if user_team:
                            # Check for unique role violations before hiring
                            from game_classes import Staff as StaffClass
                            if StaffClass.is_unique_role(staff.role):
                                existing_with_role = [s for s in user_team.staff if s.role == staff.role]
                                if existing_with_role:
                                    messagebox.showerror("Role Conflict", 
                                                       f"Team already has a {staff.role.value}: {existing_with_role[0].full_name}.\n"
                                                       f"You must reassign or fire the existing {staff.role.value} first.")
                                    return
                            
                            staff.salary = offered_salary
                            staff.contract_years = offered_years
                            user_team.staff.append(staff)
                            self.available_staff.remove(staff)
                            messagebox.showinfo("Success", f"{staff.full_name} has been hired!")
                            nego_window.destroy()
                            self.update_views()
                    else:
                        # Update existing contract
                        staff.salary = offered_salary
                        staff.contract_years = offered_years
                        messagebox.showinfo("Success", f"Contract renegotiated with {staff.full_name}!")
                        nego_window.destroy()
                        self.update_views()
                else:
                    result_label.config(text="Offer Rejected. Try adjusting your offer.")
                    
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for salary and years.")
        
        ttk.Button(button_frame, text="Make Offer", command=make_offer, style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=nego_window.destroy, style='TButton').pack(side=tk.RIGHT, padx=5)
    
    def interview_candidate(self):
        """Interview selected candidate for additional information."""
        selection = self.available_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a candidate to interview.")
            return
        
        staff = self.parent.tree_maps['available_staff'][selection[0]]
        
        # Generate interview responses
        responses = [
            f"'{staff.full_name}' discusses their {staff.experience} years of experience in hockey.",
            f"They emphasize their strength in {random.choice(['player development', 'tactical analysis', 'team building'])}.",
            f"When asked about their coaching philosophy: 'I believe in {random.choice(['hard work and dedication', 'player-first approach', 'tactical flexibility'])}'",
            f"Their reputation in the league is {'well-regarded' if staff.reputation > 12 else 'developing'}.",
            f"They express {random.choice(['strong enthusiasm', 'cautious optimism', 'professional interest'])} about joining the organization."
        ]
        
        interview_text = "\n\n".join(responses)
        
        messagebox.showinfo(f"Interview with {staff.full_name}", interview_text)
    
    def negotiate_contract(self):
        """Negotiate contract with selected current staff member."""
        selection = self.current_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to negotiate with.")
            return
        
        staff = self.parent.tree_maps['current_staff'][selection[0]]
        self.open_contract_negotiation(staff, is_hiring=False)
    
    def release_staff(self):
        """Release selected current staff member."""
        selection = self.current_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to release.")
            return
        
        staff = self.parent.tree_maps['current_staff'][selection[0]]
        self.release_staff_action(staff)
    
    def release_staff_action(self, staff: Staff, details_window=None):
        """Perform staff release action."""
        result = messagebox.askyesno("Confirm Release", 
                                    f"Are you sure you want to release {staff.full_name}?\n"
                                    f"This will end their contract immediately.")
        
        if result:
            user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
            if user_team and staff in user_team.staff:
                user_team.staff.remove(staff)
                messagebox.showinfo("Staff Released", f"{staff.full_name} has been released.")
                
                if details_window:
                    details_window.destroy()
                    
                self.update_views()
    
    def make_staff_offer_action(self, staff: Staff, details_window=None):
        """Make offer to candidate from details window."""
        if details_window:
            details_window.destroy()
        self.open_contract_negotiation(staff, is_hiring=True)
    
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
        
        context_menu = tk.Menu(self, tearoff=0, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
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
        """Negotiate contracts with selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to negotiate contracts.")
            return
        
        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]
        results = []
        
        for staff in selected_staff_list:
            # Use existing negotiation logic
            result = self.open_contract_negotiation(staff, is_hiring=False)
            if result:
                results.append(f"{staff.full_name}: Negotiated successfully")
            else:
                results.append(f"{staff.full_name}: Negotiation failed")
        
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
        
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
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
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
        return user_team.staff if user_team else []
    
    def show_multiple_staff_summary(self):
        """Show summary window for multiple selected staff."""
        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]
        
        summary_window = tk.Toplevel(self)
        summary_window.title(f"Selected Staff Summary ({len(selected_staff_list)} staff)")
        summary_window.configure(background=self.parent.BG_COLOR)
        summary_window.geometry("600x500")
        
        main_frame = ttk.Frame(summary_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        title_label = ttk.Label(main_frame, text=f"Selected Staff Summary ({len(selected_staff_list)} staff)", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap='word', bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 11))
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
        ttk.Button(main_frame, text="Close", command=summary_window.destroy, style='TButton').pack(pady=10)
    
    def reassign_single_staff(self, staff):
        """Reassign role for a single staff member."""
        # Create reassignment window
        reassign_window = tk.Toplevel(self)
        reassign_window.title(f"Reassign {staff.full_name}")
        reassign_window.configure(background=self.parent.BG_COLOR)
        reassign_window.geometry("400x300")
        
        main_frame = ttk.Frame(reassign_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text=f"Reassign {staff.full_name}", style='Title.TLabel').pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Current Role: {staff.role.value}", style='Content.TLabel').pack(pady=(0, 10))
        
        ttk.Label(main_frame, text="New Role:", style='Content.TLabel').pack(anchor='w')
        new_role_var = tk.StringVar(value=staff.role.value)
        role_combo = ttk.Combobox(main_frame, textvariable=new_role_var, 
                                 values=[role.value for role in StaffRole], state='readonly')
        role_combo.pack(fill='x', pady=5)
        
        def confirm_reassignment():
            new_role_name = new_role_var.get()
            new_role = next((role for role in StaffRole if role.value == new_role_name), None)
            
            if new_role and new_role != staff.role:
                staff.role = new_role
                messagebox.showinfo("Success", f"{staff.full_name} has been reassigned to {new_role.value}")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showwarning("No Change", "Please select a different role.")
        
        button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        button_frame.pack(fill='x', pady=20)
        
        ttk.Button(button_frame, text="Confirm", command=confirm_reassignment, style='TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=reassign_window.destroy, style='TButton').pack(side='right', padx=5)
    
    def reassign_multiple_staff(self, staff_list):
        """Reassign roles for multiple staff members."""
        # Create bulk reassignment window
        reassign_window = tk.Toplevel(self)
        reassign_window.title(f"Bulk Reassign ({len(staff_list)} staff)")
        reassign_window.configure(background=self.parent.BG_COLOR)
        reassign_window.geometry("600x500")
        
        main_frame = ttk.Frame(reassign_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text=f"Bulk Reassign {len(staff_list)} Staff Members", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Create list of staff with role dropdowns
        canvas = tk.Canvas(main_frame, bg=self.parent.CONTENT_BG)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Role selection for each staff member
        role_vars = {}
        for i, staff in enumerate(staff_list):
            staff_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame')
            staff_frame.pack(fill='x', pady=5, padx=10)
            
            ttk.Label(staff_frame, text=f"{staff.full_name}:", style='Content.TLabel').pack(side='left')
            
            role_var = tk.StringVar(value=staff.role.value)
            role_vars[staff.id] = role_var
            
            role_combo = ttk.Combobox(staff_frame, textvariable=role_var, 
                                     values=[role.value for role in StaffRole], 
                                     state='readonly', width=20)
            role_combo.pack(side='right')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def apply_reassignments():
            changes_made = 0
            for staff in staff_list:
                new_role_name = role_vars[staff.id].get()
                new_role = next((role for role in StaffRole if role.value == new_role_name), None)
                
                if new_role and new_role != staff.role:
                    staff.role = new_role
                    changes_made += 1
            
            if changes_made > 0:
                messagebox.showinfo("Success", f"Reassigned {changes_made} staff member(s)")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showinfo("No Changes", "No role changes were made.")
        
        button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        button_frame.pack(fill='x', pady=10)
        
        ttk.Button(button_frame, text="Apply Changes", command=apply_reassignments, 
                  style='TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=reassign_window.destroy, 
                  style='TButton').pack(side='right', padx=5)
    
    def show_staff_report(self):
        """Show comprehensive staff report."""
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
        if not user_team:
            return
        
        report_window = tk.Toplevel(self)
        report_window.title(f"{user_team.team_name} Staff Report")
        report_window.configure(background=self.parent.BG_COLOR)
        report_window.geometry("800x600")
        
        main_frame = ttk.Frame(report_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        title_label = ttk.Label(main_frame, text=f"{user_team.team_name} Staff Report", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap='word', bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 11))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        text_widget.pack(side='left', fill='both', expand=True)
        
        # Generate report content
        report_content = self.generate_staff_report(user_team)
        text_widget.insert('1.0', report_content)
        text_widget.config(state='disabled')
        
        # Close button
        ttk.Button(main_frame, text="Close", command=report_window.destroy, style='TButton').pack(pady=10)
    
    def show_organizational_chart(self):
        """Show organizational chart of current staff."""
        user_team = next((team for team in self.parent.game_manager.league.teams if team.is_user_team), None)
        if not user_team:
            return
        
        chart_window = tk.Toplevel(self)
        chart_window.title(f"{user_team.team_name} Organizational Chart")
        chart_window.configure(background=self.parent.BG_COLOR)
        chart_window.geometry("900x700")
        
        main_frame = ttk.Frame(chart_window, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        title_label = ttk.Label(main_frame, text=f"{user_team.team_name} Organizational Chart", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap='word', bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 11))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        text_widget.pack(side='left', fill='both', expand=True)
        
        # Generate organizational chart
        chart_content = self.generate_organizational_chart(user_team)
        text_widget.insert('1.0', chart_content)
        text_widget.config(state='disabled')
        
        # Close button
        ttk.Button(main_frame, text="Close", command=chart_window.destroy, style='TButton').pack(pady=10)
    
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
    
    def clear_all_filters(self):
        """Reset all filters to their default values."""
        if hasattr(self, 'name_search'):
            self.name_search.delete(0, tk.END)
        if hasattr(self, 'role_filter'):
            self.role_filter.set('All')
        if hasattr(self, 'department_filter'):
            self.department_filter.set('All')
        if hasattr(self, 'nationality_filter'):
            self.nationality_filter.set('All')
        if hasattr(self, 'salary_filter'):
            self.salary_filter.set('Any')
        if hasattr(self, 'age_filter'):
            self.age_filter.set('Any')
        if hasattr(self, 'rating_filter'):
            self.rating_filter.set('Any')
        if hasattr(self, 'contract_filter'):
            self.contract_filter.set('Any')
        if hasattr(self, 'sort_filter'):
            self.sort_filter.set('Overall Rating')
        
        # Update the view
        self.update_available_staff_view()
    
    def show_available_staff_context_menu(self, event):
        """Show context menu for available staff with hire and compare options."""
        item = self.available_staff_tree.selection()[0] if self.available_staff_tree.selection() else None
        if not item:
            return
        
        # Get the staff member
        staff = self.parent.tree_maps.get('available_staff', {}).get(item)
        if not staff:
            return
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.configure(bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        
        context_menu.add_command(
            label=f"Hire {staff.full_name}",
            command=lambda: self.hire_staff_member(staff)
        )
        context_menu.add_separator()
        context_menu.add_command(
            label="View Profile",
            command=lambda: self.show_staff_profile(staff)
        )
        context_menu.add_command(
            label="Compare to Current Staff",
            command=lambda: self.compare_to_current_staff(staff)
        )
        context_menu.add_separator()
        context_menu.add_command(
            label="Add to Shortlist",
            command=lambda: self.add_to_shortlist(staff)
        )
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def hire_staff_member(self, staff):
        """Attempt to hire a staff member."""
        user_team = self.parent.game_manager.user_team
        
        # Check if team already has this role and it's unique
        from game_classes import Staff as StaffClass
        if StaffClass.is_unique_role(staff.role):
            existing_staff = [s for s in user_team.staff if s.role == staff.role]
            if existing_staff:
                messagebox.showwarning(
                    "Cannot Hire",
                    f"Your team already has a {staff.role.value}. You must fire {existing_staff[0].full_name} first."
                )
                return
        
        # Check budget (simplified - you might want more complex budget logic)
        if user_team.cap_space < staff.salary:
            messagebox.showwarning(
                "Insufficient Funds",
                f"Cannot afford ${staff.salary:,} salary. Available cap space: ${user_team.cap_space:,}"
            )
            return
        
        # Confirm hiring
        confirm = messagebox.askyesno(
            "Confirm Hire",
            f"Hire {staff.full_name} as {staff.role.value} for ${staff.salary:,}/year ({staff.contract_years} years)?\n\n"
            f"Overall Rating: {staff.overall_rating}\n"
            f"Key Skills: {self.get_key_skills_display(staff)}"
        )
        
        if confirm:
            # Add to team
            user_team.staff.append(staff)
            user_team.cap_space -= staff.salary
            
            # Remove from available staff
            if staff in self.available_staff:
                self.available_staff.remove(staff)
            
            # Update views
            self.update_available_staff_view()
            self.update_current_staff_view()
            
            messagebox.showinfo(
                "Staff Hired",
                f"Successfully hired {staff.full_name} as {staff.role.value}!"
            )
    
    def show_staff_profile(self, staff):
        """Show detailed profile for a staff member."""
        profile_window = tk.Toplevel(self)
        profile_window.title(f"Staff Profile - {staff.full_name}")
        profile_window.configure(bg=self.parent.BG_COLOR)
        profile_window.geometry("500x600")
        profile_window.transient(self)
        
        # Header with name and role
        header_frame = ttk.Frame(profile_window, style='Panel.TFrame')
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(header_frame, text=staff.full_name, style='Title.TLabel').pack()
        ttk.Label(header_frame, text=f"{staff.role.value} | Age {staff.age} | {staff.nationality}", 
                 style='Subtitle.TLabel').pack()
        
        # Key info
        info_frame = ttk.Frame(profile_window, style='Panel.TFrame')
        info_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Overall Rating: {staff.overall_rating}", 
                 style='Header.TLabel').pack(anchor='w')
        ttk.Label(info_frame, text=f"Salary: ${staff.salary:,} per year", 
                 style='Content.TLabel').pack(anchor='w')
        ttk.Label(info_frame, text=f"Contract Length: {staff.contract_years} years", 
                 style='Content.TLabel').pack(anchor='w')
        
        # Department
        from game_classes import Staff as StaffClass
        department = StaffClass.get_role_department(staff.role)
        ttk.Label(info_frame, text=f"Department: {department}", 
                 style='Content.TLabel').pack(anchor='w')
        
        # Skills section
        skills_frame = ttk.LabelFrame(profile_window, text="Skills", style='Panel.TLabelframe')
        skills_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Display relevant skills based on role
        skills_to_show = self.get_relevant_skills_for_role(staff.role)
        for skill_name in skills_to_show:
            if hasattr(staff, skill_name.lower().replace(' ', '_')):
                skill_value = getattr(staff, skill_name.lower().replace(' ', '_'))
                ttk.Label(skills_frame, text=f"{skill_name}: {skill_value}", 
                         style='Content.TLabel').pack(anchor='w', padx=5, pady=2)
        
        # Close button
        ttk.Button(profile_window, text="Close", 
                  command=profile_window.destroy, style='TButton').pack(pady=10)
    
    def compare_to_current_staff(self, candidate_staff):
        """Compare candidate staff to current staff in same role."""
        user_team = self.parent.game_manager.user_team
        current_staff = [s for s in user_team.staff if s.role == candidate_staff.role]
        
        if not current_staff:
            messagebox.showinfo(
                "No Comparison Available",
                f"Your team doesn't currently have a {candidate_staff.role.value} to compare with."
            )
            return
        
        current = current_staff[0]  # Assume only one per role for comparison
        
        # Create comparison window
        comp_window = tk.Toplevel(self)
        comp_window.title(f"Staff Comparison - {candidate_staff.role.value}")
        comp_window.configure(bg=self.parent.BG_COLOR)
        comp_window.geometry("700x500")
        comp_window.transient(self)
        
        # Headers
        header_frame = ttk.Frame(comp_window, style='Panel.TFrame')
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(header_frame, text="Current Staff vs. Candidate", 
                 style='Title.TLabel').pack()
        
        # Comparison table
        comp_frame = ttk.Frame(comp_window, style='Panel.TFrame')
        comp_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create comparison treeview
        columns = ['Attribute', 'Current', 'Candidate', 'Difference']
        comp_tree = ttk.Treeview(comp_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            comp_tree.heading(col, text=col)
            comp_tree.column(col, width=150)
        
        # Add comparison data
        comparisons = [
            ('Name', current.full_name, candidate_staff.full_name, ''),
            ('Overall Rating', current.overall_rating, candidate_staff.overall_rating, 
             candidate_staff.overall_rating - current.overall_rating),
            ('Age', current.age, candidate_staff.age, candidate_staff.age - current.age),
            ('Salary', f"${current.salary:,}", f"${candidate_staff.salary:,}", 
             f"${candidate_staff.salary - current.salary:+,}"),
            ('Contract', f"{current.contract_years}y", f"{candidate_staff.contract_years}y", 
             f"{candidate_staff.contract_years - current.contract_years:+}y"),
            ('Nationality', current.nationality, candidate_staff.nationality, '')
        ]
        
        for attr, curr_val, cand_val, diff in comparisons:
            if isinstance(diff, (int, float)) and diff != 0:
                diff_text = f"{diff:+}" if diff != '' else ''
                # Color code the difference
                if diff > 0:
                    diff_text = f"{diff_text}"
                elif diff < 0:
                    diff_text = f"{diff_text}"
            else:
                diff_text = str(diff) if diff != '' else ''
            
            comp_tree.insert('', 'end', values=[attr, curr_val, cand_val, diff_text])
        
        comp_tree.pack(fill='both', expand=True)
        
        # Close button
        ttk.Button(comp_window, text="Close", 
                  command=comp_window.destroy, style='TButton').pack(pady=10)
    
    def add_to_shortlist(self, staff):
        """Add staff member to shortlist (placeholder for future feature)."""
        messagebox.showinfo(
            "Added to Shortlist",
            f"{staff.full_name} has been added to your shortlist.\n(Feature coming soon!)"
        )
    
    def get_relevant_skills_for_role(self, role):
        """Get list of relevant skills to display for a specific role."""
        skill_mapping = {
            StaffRole.GENERAL_MANAGER: ['Leadership', 'Negotiating', 'Player Knowledge', 'Staff Management'],
            StaffRole.HEAD_COACH: ['Tactics', 'Motivation', 'Player Development', 'Game Management'],
            StaffRole.ASSISTANT_COACH: ['Tactics', 'Player Development', 'Motivation'],
            StaffRole.GOALIE_COACH: ['Goalie Knowledge', 'Player Development', 'Tactics'],
            StaffRole.SKILLS_COACH: ['Player Development', 'Motivation', 'Technical Knowledge'],
            StaffRole.CONDITIONING_COACH: ['Fitness Training', 'Injury Prevention', 'Motivation'],
            StaffRole.HEAD_SCOUT: ['Player Knowledge', 'Scouting Network', 'Analysis'],
            StaffRole.AMATEUR_SCOUT: ['Player Knowledge', 'Regional Knowledge', 'Analysis'],
            StaffRole.PRO_SCOUT: ['Player Knowledge', 'Analysis', 'Report Writing'],
            StaffRole.DIRECTOR_PLAYER_PERSONNEL: ['Player Knowledge', 'Analysis', 'Negotiating'],
            StaffRole.TRAINER: ['Medical Knowledge', 'Injury Treatment', 'Player Care'],
            StaffRole.EQUIPMENT_MANAGER: ['Equipment Knowledge', 'Organization', 'Technical Skills'],
            StaffRole.TEAM_DOCTOR: ['Medical Knowledge', 'Diagnosis', 'Treatment'],
            StaffRole.TEAM_PSYCHOLOGIST: ['Psychology', 'Player Support', 'Mental Training'],
            StaffRole.VIDEO_COACH: ['Video Analysis', 'Technical Knowledge', 'Presentation'],
            StaffRole.STRENGTH_COACH: ['Strength Training', 'Fitness', 'Program Design'],
            StaffRole.NUTRITIONIST: ['Nutrition Knowledge', 'Meal Planning', 'Health Assessment'],
            StaffRole.MASSAGE_THERAPIST: ['Massage Therapy', 'Recovery', 'Injury Prevention'],
            StaffRole.SKATING_COACH: ['Skating Technique', 'Player Development', 'Technical Knowledge'],
            StaffRole.TEAM_SERVICES_COORDINATOR: ['Organization', 'Communication', 'Logistics'],
            StaffRole.MEDIA_RELATIONS: ['Communication', 'Public Relations', 'Media Management'],
            StaffRole.COMMUNITY_RELATIONS: ['Community Outreach', 'Event Planning', 'Public Relations'],
            StaffRole.ANALYTICS_SPECIALIST: ['Data Analysis', 'Statistics', 'Technology']
        }
        
        return skill_mapping.get(role, ['Leadership', 'Experience', 'Knowledge'])
    
    def get_key_skills_display_new(self, staff):
        """Get a formatted string of key skills for display in the treeview."""
        relevant_skills = self.get_relevant_skills_for_role(staff.role)
        
        # Get top 3 skills (simplified - you might want actual skill values)
        # For now, we'll use a placeholder format
        skill_ratings = []
        for skill in relevant_skills[:3]:
            # Generate a realistic skill rating (60-95 range)
            import random
            base_rating = staff.overall_rating
            skill_rating = max(60, min(95, base_rating + random.randint(-10, 10)))
            skill_ratings.append(str(skill_rating))
        
        return ' | '.join(skill_ratings) if skill_ratings else 'N/A'
    
    def compare_candidates(self):
        """Compare selected candidates with each other or current staff."""
        selected_items = self.available_staff_tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select candidates to compare.")
            return
        
        if len(selected_items) == 1:
            # Single selection - compare to current staff in same role
            staff = self.parent.tree_maps.get('available_staff', {}).get(selected_items[0])
            if staff:
                self.compare_to_current_staff(staff)
        else:
            # Multiple selections - compare candidates to each other
            self.compare_multiple_candidates(selected_items)
    
    def compare_multiple_candidates(self, selected_items):
        """Compare multiple selected candidates side by side."""
        candidates = []
        for item_id in selected_items:
            staff = self.parent.tree_maps.get('available_staff', {}).get(item_id)
            if staff:
                candidates.append(staff)
        
        if len(candidates) < 2:
            messagebox.showwarning("Insufficient Selection", "Please select at least 2 candidates to compare.")
            return
        
        # Create comparison window
        comp_window = tk.Toplevel(self)
        comp_window.title(f"Candidate Comparison ({len(candidates)} candidates)")
        comp_window.configure(bg=self.parent.BG_COLOR)
        comp_window.geometry("900x600")
        comp_window.transient(self)
        
        # Main frame
        main_frame = ttk.Frame(comp_window, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        ttk.Label(main_frame, text=f"Candidate Comparison - {candidates[0].role.value}", 
                 style='Title.TLabel').pack(pady=(0, 10))
        
        # Create comparison treeview
        columns = ['Attribute'] + [f"Candidate {i+1}" for i in range(len(candidates))]
        comp_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        comp_tree.column('Attribute', width=150)
        comp_tree.heading('Attribute', text='Attribute')
        
        for i, candidate in enumerate(candidates):
            col = f"Candidate {i+1}"
            comp_tree.column(col, width=150)
            comp_tree.heading(col, text=f"{candidate.full_name}")
        
        # Add scrollbar
        comp_scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=comp_tree.yview)
        comp_tree.configure(yscrollcommand=comp_scrollbar.set)
        
        comp_scrollbar.pack(side='right', fill='y')
        comp_tree.pack(side='left', fill='both', expand=True)
        
        # Comparison data
        comparisons = [
            ('Overall Rating', [c.overall_rating for c in candidates]),
            ('Age', [c.age for c in candidates]),
            ('Nationality', [c.nationality for c in candidates]),
            ('Salary', [f"${c.salary:,}" for c in candidates]),
            ('Contract Length', [f"{c.contract_years}y" for c in candidates]),
            ('Experience', [f"{c.experience}y" for c in candidates]),
        ]
        
        # Add relevant skills
        relevant_skills = self.get_relevant_skills_for_role(candidates[0].role)
        for skill in relevant_skills[:5]:  # Top 5 relevant skills
            skill_values = []
            for candidate in candidates:
                # Generate skill value based on overall rating with some variance
                import random
                base_rating = candidate.overall_rating
                skill_rating = max(60, min(95, base_rating + random.randint(-8, 8)))
                skill_values.append(skill_rating)
            comparisons.append((skill, skill_values))
        
        # Populate comparison tree
        for attr, values in comparisons:
            row_values = [attr] + [str(v) for v in values]
            item_id = comp_tree.insert('', 'end', values=row_values)
            
            # Highlight best values for numeric comparisons
            if attr in ['Overall Rating', 'Experience'] or any(isinstance(v, (int, float)) for v in values):
                try:
                    numeric_values = []
                    for v in values:
                        if isinstance(v, str) and v.startswith('$'):
                            # Handle salary format
                            numeric_values.append(int(v.replace('$', '').replace(',', '')))
                        elif isinstance(v, str) and v.endswith('y'):
                            # Handle year format
                            numeric_values.append(int(v.replace('y', '')))
                        elif isinstance(v, (int, float)):
                            numeric_values.append(v)
                        else:
                            numeric_values.append(0)
                    
                    if numeric_values:
                        max_val = max(numeric_values)
                        best_indices = [i for i, v in enumerate(numeric_values) if v == max_val]
                        
                        # Color the best values
                        for idx in best_indices:
                            comp_tree.set(item_id, f"Candidate {idx+1}", f"🏆 {values[idx]}")
                
                except (ValueError, AttributeError):
                    pass  # Skip highlighting for non-numeric values
        
        # Summary at bottom
        summary_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        summary_frame.pack(fill='x', pady=10)
        
        avg_rating = sum(c.overall_rating for c in candidates) / len(candidates)
        avg_salary = sum(c.salary for c in candidates) / len(candidates)
        
        summary_text = f"Average Rating: {avg_rating:.1f} | Average Salary: ${avg_salary:,.0f}"
        ttk.Label(summary_frame, text=summary_text, style='Content.TLabel').pack()
        
        # Close button
        ttk.Button(main_frame, text="Close", 
                  command=comp_window.destroy, style='TButton').pack(pady=10)
