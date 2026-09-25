"""
Advanced contract negotiation components for Hockey Manager.
Contains enhanced contract negotiation features including performance bonuses.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
from typing import Dict, List, Optional, Tuple, Union

class AdvancedContractNegotiationWindow(tk.Toplevel):
    """Enhanced window for negotiating contract extensions with NHL-style features."""
    
    def __init__(self, parent, player, market_value=None, max_years=8):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.market_value = market_value or self._calculate_market_value()
        self.max_years = max_years
        
        # Contract parameters
        self.performance_bonuses = []
        self.bonus_types = self._get_available_bonus_types()
        
        # Setup window
        self.title(f"Advanced Contract Negotiation - {player.full_name}")
        self.geometry("800x650")
        self.configure(background=parent.BG_COLOR)
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the user interface for the contract negotiation window."""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header with player info
        self._create_player_info_header(main_frame)
        
        # Create notebook with tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Basic terms tab
        basic_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(basic_frame, text="Basic Terms")
        self._create_basic_terms_tab(basic_frame)
        
        # Performance bonuses tab
        bonus_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(bonus_frame, text="Performance Bonuses")
        self._create_performance_bonuses_tab(bonus_frame)
        
        # Contract summary tab
        summary_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(summary_frame, text="Contract Summary")
        self._create_contract_summary_tab(summary_frame)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(button_frame, text="Submit Offer", 
                  command=self.submit_offer, style='Accent.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy).pack(side='right', padx=5)
        
        # Initial calculations
        self.update_total()
    
    def _create_player_info_header(self, parent_frame):
        """Create the player info header section."""
        info_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        info_frame.pack(fill='x', padx=5, pady=5)
        
        # Player name and position
        ttk.Label(info_frame, text=f"{self.player.full_name} - {self.player.primary_position.value}", 
                 font=(self.parent.FONT_FAMILY, 16, 'bold'), style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Player details in columns
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(fill='x', padx=10, pady=5)
        
        # Left column - Player attributes
        left_col = ttk.Frame(details_frame)
        left_col.pack(side='left', fill='x', expand=True)
        
        ttk.Label(left_col, text=f"Age: {self.player.age}", style='Info.TLabel').pack(anchor='w', pady=2)
        from game_classes import to_100_scale
        ttk.Label(left_col, text=f"Overall Rating: {to_100_scale(self.player.overall_rating())}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Potential: {self.player.potential_grade}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Right column - Contract info
        right_col = ttk.Frame(details_frame)
        right_col.pack(side='right', fill='x', expand=True)
        
        ttk.Label(right_col, text=f"Current Salary: ${self.player.contract.salary:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Years Remaining: {self.player.contract.years_remaining}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Market Value: ${self.market_value:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Season stats
        stats_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Season Statistics", 
                 font=(self.parent.FONT_FAMILY, 12, 'bold'), style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        stats_text = f"Goals: {self.player.stats.goals}   Assists: {self.player.stats.assists}   Points: {self.player.stats.points}"
        ttk.Label(stats_frame, text=stats_text, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
    
    def _create_basic_terms_tab(self, parent_frame):
        """Create the basic contract terms tab."""
        # Salary section
        salary_frame = ttk.LabelFrame(parent_frame, text="Salary Details", style='Panel.TLabelframe')
        salary_frame.pack(fill='x', padx=10, pady=10)
        
        # Base salary
        base_salary_frame = ttk.Frame(salary_frame)
        base_salary_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(base_salary_frame, text="Annual Salary:", style='Info.TLabel').pack(side='left')
        
        self.salary_var = tk.StringVar(master=self, value=f"{self.market_value:,}")
        salary_entry = ttk.Entry(base_salary_frame, textvariable=self.salary_var, width=15)
        salary_entry.pack(side='left', padx=10)
        
        # Salary presets
        salary_presets = ttk.Frame(salary_frame)
        salary_presets.pack(fill='x', padx=10, pady=5)
        
        min_salary = max(750000, int(self.market_value * 0.8))
        recommended_salary = self.market_value
        max_salary = int(self.market_value * 1.2)
        
        ttk.Button(salary_presets, text=f"Min (${min_salary:,})", 
                  command=lambda: self.salary_var.set(f"{min_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Recommended (${recommended_salary:,})", 
                  command=lambda: self.salary_var.set(f"{recommended_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Max (${max_salary:,})", 
                  command=lambda: self.salary_var.set(f"{max_salary:,}")).pack(side='left', padx=5)
        
        # Contract length
        contract_frame = ttk.LabelFrame(parent_frame, text="Contract Length", style='Panel.TLabelframe')
        contract_frame.pack(fill='x', padx=10, pady=10)
        
        years_frame = ttk.Frame(contract_frame)
        years_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(years_frame, text="Term (years):", style='Info.TLabel').pack(side='left')
        
        self.years_var = tk.IntVar(master=self, value=min(5, self.max_years))
        years_scale = ttk.Scale(years_frame, from_=1, to=self.max_years, variable=self.years_var, 
                               orient='horizontal', length=200)
        years_scale.pack(side='left', padx=10)
        
        years_label = ttk.Label(years_frame, textvariable=self.years_var, style='Info.TLabel')
        years_label.pack(side='left')
        
        # Term recommendation info
        ideal_years = 8 if self.player.age <= 25 else 5 if self.player.age <= 30 else 2
        term_info = ttk.Label(contract_frame, 
                              text=f"Recommendation: For a {self.player.age}-year-old player, consider a {ideal_years}-year term.",
                              style='Info.TLabel')
        term_info.pack(anchor='w', padx=10, pady=5)
        
        # Additional clauses
        clauses_frame = ttk.LabelFrame(parent_frame, text="Contract Clauses", style='Panel.TLabelframe')
        clauses_frame.pack(fill='x', padx=10, pady=10)
        
        # No-trade clause
        ntc_frame = ttk.Frame(clauses_frame)
        ntc_frame.pack(fill='x', padx=10, pady=10)
        
        self.ntc_var = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(ntc_frame, text="Include No-Trade Clause", variable=self.ntc_var,
                       style='TCheckbutton').pack(side='left')
        
        # Signing bonus
        bonus_frame = ttk.Frame(clauses_frame)
        bonus_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(bonus_frame, text="Signing Bonus ($):", style='Info.TLabel').pack(side='left')
        
        self.bonus_var = tk.StringVar(master=self, value="0")
        bonus_entry = ttk.Entry(bonus_frame, textvariable=self.bonus_var, width=15)
        bonus_entry.pack(side='left', padx=10)
        
        # Front-loaded contract option
        self.front_loaded_var = tk.BooleanVar(master=self, value=False)
        front_loaded_frame = ttk.Frame(clauses_frame)
        front_loaded_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Checkbutton(front_loaded_frame, text="Front-Load Contract (Higher salary in earlier years)", 
                       variable=self.front_loaded_var, style='TCheckbutton').pack(side='left')
        
        # Update when values change
        self.years_var.trace_add('write', self.update_total)
        self.salary_var.trace_add('write', self.update_total)
        self.bonus_var.trace_add('write', self.update_total)
        self.front_loaded_var.trace_add('write', self.update_total)
    
    def _create_performance_bonuses_tab(self, parent_frame):
        """Create the performance bonuses tab."""
        # Instructions
        instructions = ttk.Label(parent_frame, 
                               text="Add performance bonuses to incentivize specific achievements. These bonuses can make your offer more attractive while limiting salary cap impact.",
                               style='Info.TLabel', wraplength=700)
        instructions.pack(fill='x', padx=10, pady=10)
        
        # Bonus controls frame
        controls_frame = ttk.Frame(parent_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)
        
        # Bonus type selection
        ttk.Label(controls_frame, text="Bonus Type:", style='Info.TLabel').pack(side='left', padx=5)
        
        self.bonus_type_var = tk.StringVar(master=self)
        bonus_type_combo = ttk.Combobox(controls_frame, textvariable=self.bonus_type_var, 
                                       values=list(self.bonus_types.keys()), state='readonly', width=30)
        bonus_type_combo.pack(side='left', padx=5)
        bonus_type_combo.bind("<<ComboboxSelected>>", self.update_bonus_target)
        
        # Bonus amount
        ttk.Label(controls_frame, text="Amount ($):", style='Info.TLabel').pack(side='left', padx=5)
        
        self.bonus_amount_var = tk.StringVar(master=self, value="100000")
        bonus_amount_entry = ttk.Entry(controls_frame, textvariable=self.bonus_amount_var, width=10)
        bonus_amount_entry.pack(side='left', padx=5)
        
        # Target threshold
        self.target_frame = ttk.Frame(parent_frame)
        self.target_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(self.target_frame, text="Target:", style='Info.TLabel').pack(side='left', padx=5)
        
        self.bonus_target_var = tk.StringVar(master=self)
        self.target_entry = ttk.Entry(self.target_frame, textvariable=self.bonus_target_var, width=10)
        self.target_entry.pack(side='left', padx=5)
        
        self.target_description = ttk.Label(self.target_frame, text="", style='Info.TLabel')
        self.target_description.pack(side='left', padx=5)
        
        # Add bonus button
        ttk.Button(parent_frame, text="Add Bonus", command=self.add_performance_bonus).pack(padx=10, pady=10)
        
        # Bonuses list
        list_frame = ttk.LabelFrame(parent_frame, text="Current Performance Bonuses", style='Panel.TLabelframe')
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for bonuses
        columns = {'type': ('Bonus Type', 200), 'target': ('Target', 100), 'amount': ('Amount', 100)}
        self.bonus_tree = ttk.Treeview(list_frame, columns=list(columns.keys()), show='headings')
        
        for col, (text, width) in columns.items():
            self.bonus_tree.heading(col, text=text)
            self.bonus_tree.column(col, width=width)
        
        self.bonus_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Remove button
        ttk.Button(list_frame, text="Remove Selected", command=self.remove_performance_bonus).pack(pady=5)
    
    def _create_contract_summary_tab(self, parent_frame):
        """Create the contract summary tab."""
        # Summary frame
        summary_frame = ttk.Frame(parent_frame)
        summary_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Basic terms summary
        basics_frame = ttk.LabelFrame(summary_frame, text="Basic Terms", style='Panel.TLabelframe')
        basics_frame.pack(fill='x', padx=5, pady=5)
        
        self.summary_text = tk.Text(basics_frame, height=7, width=70, bg=self.parent.CONTENT_BG, 
                                   fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 10))
        self.summary_text.pack(padx=10, pady=10, fill='both', expand=True)
        self.summary_text.config(state='disabled')
        
        # Yearly breakdown
        yearly_frame = ttk.LabelFrame(summary_frame, text="Yearly Breakdown", style='Panel.TLabelframe')
        yearly_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Treeview for yearly breakdown
        columns = {
            'year': ('Year', 100), 
            'age': ('Player Age', 100), 
            'base': ('Base Salary', 150), 
            'bonus': ('Signing Bonus', 150),
            'total': ('Total', 150)
        }
        
        self.yearly_tree = ttk.Treeview(yearly_frame, columns=list(columns.keys()), show='headings')
        
        for col, (text, width) in columns.items():
            self.yearly_tree.heading(col, text=text)
            self.yearly_tree.column(col, width=width)
        
        self.yearly_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Total contract value
        total_frame = ttk.Frame(summary_frame)
        total_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Label(total_frame, text="Total Contract Value:", 
                 font=(self.parent.FONT_FAMILY, 12, 'bold'), style='Header.TLabel').pack(side='left')
        
        self.total_value_var = tk.StringVar(master=self, value="$0")
        ttk.Label(total_frame, textvariable=self.total_value_var,
                 font=(self.parent.FONT_FAMILY, 12, 'bold'), style='Header.TLabel').pack(side='left', padx=10)
        
        # Player decision probability
        prob_frame = ttk.Frame(summary_frame)
        prob_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(prob_frame, text="Estimated Likelihood of Acceptance:", style='Info.TLabel').pack(side='left')
        
        self.accept_prob_var = tk.StringVar(master=self, value="N/A")
        ttk.Label(prob_frame, textvariable=self.accept_prob_var, style='Info.TLabel').pack(side='left', padx=10)
    
    def update_total(self, *args):
        """Update the total contract value and yearly breakdown."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            base_salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            signing_bonus = int(bonus_str) if bonus_str else 0
            
            # Calculate total contract value
            total_salary = 0
            yearly_breakdown = []
            
            # Front-loaded contract logic
            if self.front_loaded_var.get() and years > 1:
                # Create a declining salary structure (10% decrease per year)
                first_year_salary = base_salary * 1.2  # Start 20% higher
                for year in range(years):
                    year_salary = max(750000, int(first_year_salary * (0.9 ** year)))
                    year_bonus = signing_bonus if year == 0 else 0  # Signing bonus only in first year
                    yearly_breakdown.append({
                        'year': f"{self.parent.current_date.year + 1 + year}-{self.parent.current_date.year + 2 + year}",
                        'age': self.player.age + 1 + year,
                        'base': year_salary,
                        'bonus': year_bonus,
                        'total': year_salary + year_bonus
                    })
                    total_salary += year_salary + year_bonus
            else:
                # Standard evenly distributed contract
                for year in range(years):
                    year_bonus = signing_bonus if year == 0 else 0  # Signing bonus only in first year
                    yearly_breakdown.append({
                        'year': f"{self.parent.current_date.year + 1 + year}-{self.parent.current_date.year + 2 + year}",
                        'age': self.player.age + 1 + year,
                        'base': base_salary,
                        'bonus': year_bonus,
                        'total': base_salary + year_bonus
                    })
                    total_salary += base_salary + year_bonus
            
            # Add potential performance bonuses
            performance_bonus_total = sum(int(bonus['amount'].replace(',', '')) for bonus in self.performance_bonuses)
            if performance_bonus_total > 0:
                # This is a maximum potential value
                total_with_bonuses = total_salary + performance_bonus_total
                self.total_value_var.set(f"${total_salary:,} (Up to ${total_with_bonuses:,} with bonuses)")
            else:
                self.total_value_var.set(f"${total_salary:,}")
            
            # Update yearly breakdown treeview
            self.yearly_tree.delete(*self.yearly_tree.get_children())
            for year_data in yearly_breakdown:
                values = (
                    year_data['year'],
                    year_data['age'],
                    f"${year_data['base']:,}",
                    f"${year_data['bonus']:,}",
                    f"${year_data['total']:,}"
                )
                self.yearly_tree.insert('', 'end', values=values)
            
            # Update summary text
            self._update_summary_text(base_salary, years, signing_bonus)
            
            # Update acceptance probability
            acceptance_chance = self.calculate_acceptance_chance(base_salary, years, signing_bonus)
            probability_text = self._get_probability_text(acceptance_chance)
            self.accept_prob_var.set(probability_text)
            
        except ValueError:
            self.total_value_var.set("Invalid input")
            self.accept_prob_var.set("N/A")
    
    def _update_summary_text(self, salary, years, signing_bonus):
        """Update the contract summary text."""
        front_loaded = "Yes" if self.front_loaded_var.get() else "No"
        ntc = "Yes" if self.ntc_var.get() else "No"
        
        performance_text = ""
        if self.performance_bonuses:
            performance_text = "\n\nPerformance Bonuses:\n"
            for idx, bonus in enumerate(self.performance_bonuses, 1):
                performance_text += f"{idx}. {bonus['type']}: {bonus['target']} - {bonus['amount']}\n"
        
        summary = (
            f"Contract Length: {years} years\n"
            f"Base Salary: ${salary:,} per year\n"
            f"Signing Bonus: ${signing_bonus:,}\n"
            f"Front-Loaded: {front_loaded}\n"
            f"No-Trade Clause: {ntc}"
            f"{performance_text}"
        )
        
        self.summary_text.config(state='normal')
        self.summary_text.delete('1.0', tk.END)
        self.summary_text.insert('1.0', summary)
        self.summary_text.config(state='disabled')
    
    def _get_probability_text(self, chance):
        """Convert numerical probability to descriptive text."""
        if chance >= 0.8:
            return "Very Likely (>80%)"
        elif chance >= 0.6:
            return "Likely (60-80%)"
        elif chance >= 0.4:
            return "Moderate (40-60%)"
        elif chance >= 0.2:
            return "Unlikely (20-40%)"
        else:
            return "Very Unlikely (<20%)"
    
    def update_bonus_target(self, event=None):
        """Update the target input field based on selected bonus type."""
        bonus_type = self.bonus_type_var.get()
        if not bonus_type:
            return
            
        target_info = self.bonus_types[bonus_type]
        
        # Clear previous value
        self.bonus_target_var.set("")
        
        # Set default value based on bonus type
        if bonus_type in ["Goals", "Assists", "Points"]:
            # For offensive stats, set a reasonable target based on player's previous season
            if bonus_type == "Goals":
                baseline = self.player.stats.goals
                suggested = max(baseline + 5, 20)
                self.bonus_target_var.set(str(suggested))
            elif bonus_type == "Assists":
                baseline = self.player.stats.assists
                suggested = max(baseline + 5, 25)
                self.bonus_target_var.set(str(suggested))
            elif bonus_type == "Points":
                baseline = self.player.stats.points
                suggested = max(baseline + 10, 40)
                self.bonus_target_var.set(str(suggested))
        elif bonus_type == "All-Star Selection":
            self.bonus_target_var.set("Yes")
        elif bonus_type == "Award Nomination":
            self.bonus_target_var.set("Any")
        elif bonus_type == "Games Played":
            self.bonus_target_var.set("70")
        
        # Update description
        self.target_description.config(text=target_info['description'])
    
    def add_performance_bonus(self):
        """Add a performance bonus to the contract."""
        bonus_type = self.bonus_type_var.get()
        if not bonus_type:
            messagebox.showwarning("Missing Information", "Please select a bonus type.")
            return
            
        target = self.bonus_target_var.get()
        if not target:
            messagebox.showwarning("Missing Information", "Please specify a target for the bonus.")
            return
            
        try:
            amount_str = self.bonus_amount_var.get().replace(',', '')
            amount = int(amount_str)
            if amount <= 0:
                messagebox.showerror("Invalid Amount", "Bonus amount must be greater than zero.")
                return
                
            # Format for display
            formatted_amount = f"${amount:,}"
            
            # Add to performance bonuses list
            self.performance_bonuses.append({
                'type': bonus_type,
                'target': target,
                'amount': formatted_amount
            })
            
            # Add to treeview
            self.bonus_tree.insert('', 'end', values=(bonus_type, target, formatted_amount))
            
            # Update total
            self.update_total()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the bonus amount.")
    
    def remove_performance_bonus(self):
        """Remove the selected performance bonus."""
        selected_item = self.bonus_tree.selection()
        if not selected_item:
            return
            
        item_idx = self.bonus_tree.index(selected_item[0])
        
        # Remove from internal list
        if 0 <= item_idx < len(self.performance_bonuses):
            self.performance_bonuses.pop(item_idx)
            
        # Remove from treeview
        self.bonus_tree.delete(selected_item[0])
        
        # Update total
        self.update_total()
    
    def _get_available_bonus_types(self):
        """Get the available performance bonus types based on player position."""
        # Common bonuses for all positions
        bonuses = {
            "Games Played": {
                "description": "Number of regular season games played",
                "cap_hit_percentage": 0.5
            },
            "All-Star Selection": {
                "description": "Selected to the All-Star team",
                "cap_hit_percentage": 0.0
            },
            "Award Nomination": {
                "description": "Nominated for a major NHL award",
                "cap_hit_percentage": 0.0
            }
        }
        
        # Position-specific bonuses
        if self.player.primary_position.name != "G":  # For skaters
            bonuses.update({
                "Goals": {
                    "description": "Number of goals scored in regular season",
                    "cap_hit_percentage": 0.5
                },
                "Assists": {
                    "description": "Number of assists in regular season",
                    "cap_hit_percentage": 0.5
                },
                "Points": {
                    "description": "Total points (goals + assists) in regular season",
                    "cap_hit_percentage": 0.5
                },
                "Plus/Minus": {
                    "description": "Plus/minus rating for the season",
                    "cap_hit_percentage": 0.5
                }
            })
            
            # Forward-specific bonuses
            if self.player.primary_position.name in ["LW", "RW", "C"]:
                bonuses.update({
                    "Power Play Goals": {
                        "description": "Goals scored on the power play",
                        "cap_hit_percentage": 0.5
                    }
                })
            
            # Defense-specific bonuses
            if self.player.primary_position.name in ["LD", "RD", "D"]:
                bonuses.update({
                    "Blocked Shots": {
                        "description": "Number of shots blocked",
                        "cap_hit_percentage": 0.5
                    }
                })
        else:  # Goalie-specific bonuses
            bonuses.update({
                "Wins": {
                    "description": "Number of wins",
                    "cap_hit_percentage": 0.5
                },
                "Save Percentage": {
                    "description": "Save percentage (e.g., 0.920)",
                    "cap_hit_percentage": 0.5
                },
                "Shutouts": {
                    "description": "Number of shutouts",
                    "cap_hit_percentage": 0.5
                }
            })
            
        return bonuses
    
    def _calculate_market_value(self):
        """Calculate player's market value if not provided."""
        # Base value determined by overall rating
        base_value = self.player.overall_rating() * 100000
        
        # Age modifier
        age_modifier = 1.0
        if 23 <= self.player.age <= 29:
            age_modifier = 1.2
        elif self.player.age >= 30:
            age_modifier = max(0.5, 1.0 - ((self.player.age - 30) * 0.05))
        
        # Position modifier
        position_modifier = 1.0
        if self.player.primary_position.name == "C":
            position_modifier = 1.15
        elif self.player.primary_position.name in ["LD", "RD", "D"]:
            position_modifier = 1.1
        elif self.player.primary_position.name == "G":
            position_modifier = 1.0 if self.player.overall_rating() >= 85 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if self.player.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(self.player.potential_grade, 1.0)
        
        # Stats performance bonus
        performance_bonus = self.player.stats.goals * 50000 + self.player.stats.assists * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def calculate_acceptance_chance(self, salary, years, bonus):
        """Calculate the likelihood of the player accepting the contract offer."""
        # Base acceptance chance
        chance = 0.5
        
        # Adjust based on salary vs market value
        salary_ratio = salary / self.market_value
        
        if salary_ratio >= 1.1:
            chance += 0.3  # Great offer
        elif salary_ratio >= 1.0:
            chance += 0.15  # Good offer
        elif salary_ratio >= 0.9:
            chance += 0.05  # Fair offer
        else:
            chance -= 0.3  # Poor offer
        
        # Adjust based on player age and contract length
        ideal_years = 8 if self.player.age <= 25 else 5 if self.player.age <= 30 else 2
        years_diff = abs(years - ideal_years)
        
        if years_diff == 0:
            chance += 0.15  # Perfect term
        elif years_diff <= 1:
            chance += 0.05  # Close to ideal term
        elif years_diff >= 4:
            chance -= 0.15  # Far from ideal term
        
        # Bonus adds slight bonus to acceptance
        if bonus > 0:
            chance += min(0.1, bonus / (salary * years) * 0.5)
        
        # No-trade clause adds value for veterans
        if self.ntc_var.get() and self.player.age >= 28:
            chance += 0.1
        
        # Performance bonuses add value for appropriate players
        if self.performance_bonuses:
            if self.player.age <= 22 or self.player.age >= 35:
                # Young players and veterans value performance bonuses more
                chance += min(0.15, len(self.performance_bonuses) * 0.05)
            else:
                chance += min(0.05, len(self.performance_bonuses) * 0.02)
        
        # Front-loaded contracts are appealing
        if self.front_loaded_var.get():
            chance += 0.05
        
        # Cap the chance between 5% and 95%
        return max(0.05, min(0.95, chance))
    
    def submit_offer(self):
        """Submit contract offer to the player."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0
            
            # Validate inputs
            if salary < 750000:
                messagebox.showerror("Invalid Salary", "Salary must be at least $750,000 (NHL minimum).")
                return
                
            if years < 1 or years > self.max_years:
                messagebox.showerror("Invalid Contract Length", 
                                   f"Contract length must be between 1 and {self.max_years} years.")
                return
                
            if bonus < 0:
                messagebox.showerror("Invalid Bonus", "Signing bonus cannot be negative.")
                return
            
            # Calculate likelihood of acceptance
            acceptance_chance = self.calculate_acceptance_chance(salary, years, bonus)
            
            # Simulate player decision
            accepted = random.random() < acceptance_chance
            
            # Format performance bonuses for display
            bonus_text = ""
            if self.performance_bonuses:
                bonus_text = "\nPerformance Bonuses:\n"
                for bonus in self.performance_bonuses:
                    bonus_text += f"- {bonus['type']}: {bonus['target']} - {bonus['amount']}\n"
            
            if accepted:
                # Update player contract
                self.player.contract.salary = salary
                self.player.contract.years_remaining = years
                self.player.contract.signing_bonus = bonus
                self.player.contract.no_trade_clause = self.ntc_var.get()
                
                # Add performance bonuses (in a real implementation, would store these details)
                performance_bonus_total = 0
                for perf_bonus in self.performance_bonuses:
                    amount = int(perf_bonus['amount'].replace('$', '').replace(',', ''))
                    performance_bonus_total += amount
                
                self.player.contract.performance_bonus = performance_bonus_total
                
                messagebox.showinfo("Offer Accepted", 
                                  f"{self.player.full_name} has accepted your contract extension offer.\n\n"
                                  f"{years} years at ${salary:,}/year\n"
                                  f"{'Front-loaded' if self.front_loaded_var.get() else 'Evenly distributed'} contract\n"
                                  f"{'With' if self.ntc_var.get() else 'Without'} No-Trade Clause\n"
                                  f"Signing Bonus: ${bonus:,}{bonus_text}")
                self.destroy()
            else:
                # Generate counter offer
                counter_years = min(years + random.randint(-1, 1), self.max_years)
                counter_salary = int(salary * random.uniform(1.05, 1.2))
                
                response = messagebox.askyesno("Offer Rejected", 
                                             f"{self.player.full_name} has rejected your contract extension offer.\n\n"
                                             f"Counter offer: {counter_years} years at ${counter_salary:,}/year\n\n"
                                             f"Would you like to accept this counter offer?")
                
                if response:
                    # Update player contract with counter offer
                    self.player.contract.salary = counter_salary
                    self.player.contract.years_remaining = counter_years
                    self.player.contract.signing_bonus = bonus
                    self.player.contract.no_trade_clause = self.ntc_var.get()
                    
                    # We'll keep performance bonuses as they were
                    performance_bonus_total = 0
                    for perf_bonus in self.performance_bonuses:
                        amount = int(perf_bonus['amount'].replace('$', '').replace(',', ''))
                        performance_bonus_total += amount
                    
                    self.player.contract.performance_bonus = performance_bonus_total
                    
                    messagebox.showinfo("Counter Offer Accepted", 
                                      f"You have accepted {self.player.full_name}'s counter offer.\n\n"
                                      f"{counter_years} years at ${counter_salary:,}/year")
                    self.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for salary, years, and bonus.")
