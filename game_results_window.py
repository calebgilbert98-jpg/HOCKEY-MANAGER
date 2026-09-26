import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta

class GameResultsWindow(tk.Toplevel):
    """Simple, clean game results window"""
    
    def __init__(self, parent, results_data):
        super().__init__(parent)
        self.parent = parent
        self.results_data = results_data
        
        # Extract date from results_data
        if isinstance(results_data, dict) and 'date' in results_data:
            self.date_str = results_data['date']
        else:
            self.date_str = date.today().strftime("%B %d, %Y")
        
        self.title(f"Daily Results - {self.date_str}")
        self.geometry("1000x700")
        self.configure(bg=self.parent.BG_COLOR)
        
        # Center the window
        self._center_window()
        
        # Create the interface
        self._create_interface()
        
        # Load and display data
        self._load_data()
    
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def _create_interface(self):
        """Create clean, simple interface"""
        # Main frame
        main_frame = tk.Frame(self, bg=self.parent.BG_COLOR)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.parent.BG_COLOR)
        header_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(header_frame, 
                              text=f"Daily Results - {self.date_str}",
                              font=('Segoe UI', 18, 'bold'),
                              fg='#FFFFFF',
                              bg=self.parent.BG_COLOR)
        title_label.pack()
        
        # Content notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Games tab
        self._create_games_tab()
        
        # Standings tab  
        self._create_standings_tab()
        
        # News tab
        self._create_news_tab()
        
        # Close button
        close_frame = tk.Frame(main_frame, bg=self.parent.BG_COLOR)
        close_frame.pack(fill='x', pady=(20, 0))
        
        close_btn = tk.Button(close_frame,
                             text="Close",
                             command=self.destroy,
                             font=('Segoe UI', 10),
                             bg='#00ceb8',
                             fg='white',
                             padx=30,
                             pady=8,
                             border=0,
                             activebackground='#00a894')
        close_btn.pack(side='right')
    
    def _create_games_tab(self):
        """Create games results tab"""
        games_frame = tk.Frame(self.notebook, bg='#1F1F1F')
        self.notebook.add(games_frame, text="Games")
        
        # Games list
        columns = ('Home Team', 'Score', 'Away Team', 'Status')
        self.games_tree = ttk.Treeview(games_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.games_tree.heading('Home Team', text='Home Team')
        self.games_tree.heading('Score', text='Score') 
        self.games_tree.heading('Away Team', text='Away Team')
        self.games_tree.heading('Status', text='Status')
        
        self.games_tree.column('Home Team', width=200, anchor='e')
        self.games_tree.column('Score', width=100, anchor='center')
        self.games_tree.column('Away Team', width=200, anchor='w')
        self.games_tree.column('Status', width=100, anchor='center')
        
        # Scrollbar for games
        games_scrollbar = ttk.Scrollbar(games_frame, orient='vertical', command=self.games_tree.yview)
        self.games_tree.configure(yscrollcommand=games_scrollbar.set)
        
        # Pack games components
        self.games_tree.pack(side='left', fill='both', expand=True, padx=20, pady=20)
        games_scrollbar.pack(side='right', fill='y', pady=20)
    
    def _create_standings_tab(self):
        """Create standings tab"""
        standings_frame = tk.Frame(self.notebook, bg='#1F1F1F')
        self.notebook.add(standings_frame, text="Standings")
        
        # Standings list
        columns = ('Team', 'GP', 'W', 'L', 'OTL', 'PTS', 'GF', 'GA', 'DIFF')
        self.standings_tree = ttk.Treeview(standings_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.standings_tree.heading(col, text=col)
            if col == 'Team':
                self.standings_tree.column(col, width=150, anchor='w')
            else:
                self.standings_tree.column(col, width=60, anchor='center')
        
        # Scrollbar for standings
        standings_scrollbar = ttk.Scrollbar(standings_frame, orient='vertical', command=self.standings_tree.yview)
        self.standings_tree.configure(yscrollcommand=standings_scrollbar.set)
        
        # Pack standings components
        self.standings_tree.pack(side='left', fill='both', expand=True, padx=20, pady=20)
        standings_scrollbar.pack(side='right', fill='y', pady=20)
    
    def _create_news_tab(self):
        """Create news tab"""
        news_frame = tk.Frame(self.notebook, bg='#1F1F1F')
        self.notebook.add(news_frame, text="News")
        
        # News text area
        self.news_text = tk.Text(news_frame,
                                font=('Segoe UI', 10),
                                bg='#2A2A2A',
                                fg='#E0E0E0',
                                insertbackground='#E0E0E0',
                                selectbackground='#00ceb8',
                                wrap='word')
        
        # Scrollbar for news
        news_scrollbar = ttk.Scrollbar(news_frame, orient='vertical', command=self.news_text.yview)
        self.news_text.configure(yscrollcommand=news_scrollbar.set)
        
        # Pack news components
        self.news_text.pack(side='left', fill='both', expand=True, padx=20, pady=20)
        news_scrollbar.pack(side='right', fill='y', pady=20)
    
    def _load_data(self):
        """Load and display the results data"""
        if not self.results_data or not isinstance(self.results_data, dict):
            return
        
        # Load games from 'all_games' (the key used by main.py)
        games = self.results_data.get('all_games', [])
        for game in games:
            if isinstance(game, dict):
                home_team = game.get('home_team', 'Unknown')
                away_team = game.get('away_team', 'Unknown')
                home_score = game.get('home_score', 0)
                away_score = game.get('away_score', 0)
                status = game.get('status', 'Final')
                
                # Handle team objects vs strings
                if hasattr(home_team, 'team_name'):
                    home_team = home_team.team_name
                if hasattr(away_team, 'team_name'):
                    away_team = away_team.team_name
                
                score_text = f"{home_score} - {away_score}"
                self.games_tree.insert('', 'end', values=(home_team, score_text, away_team, status))
        
        # Load standings from 'league_results'
        league_results = self.results_data.get('league_results', {})
        
        # Try to extract standings from league results
        standings = []
        if isinstance(league_results, dict):
            # Look for standings in the league results structure
            for league_name, league_data in league_results.items():
                if isinstance(league_data, dict) and 'standings' in league_data:
                    standings.extend(league_data['standings'])
        
        for team_data in standings:
            if isinstance(team_data, dict):
                values = (
                    team_data.get('name', 'Unknown'),
                    team_data.get('games_played', 0),
                    team_data.get('wins', 0),
                    team_data.get('losses', 0),
                    team_data.get('ot_losses', 0),
                    team_data.get('points', 0),
                    team_data.get('goals_for', 0),
                    team_data.get('goals_against', 0),
                    team_data.get('goal_diff', 0)
                )
                self.standings_tree.insert('', 'end', values=values)
        
        # Load news from 'news_events' (the key used by main.py)
        news_items = self.results_data.get('news_events', [])
        if news_items:
            for item in news_items:
                if isinstance(item, str):
                    self.news_text.insert('end', f"• {item}\n\n")
                elif isinstance(item, dict):
                    headline = item.get('headline', item.get('text', 'No headline'))
                    content = item.get('content', item.get('description', ''))
                    if content:
                        self.news_text.insert('end', f"• {headline}\n{content}\n\n")
                    else:
                        self.news_text.insert('end', f"• {headline}\n\n")
        else:
            self.news_text.insert('end', "No news available for today.")

# Legacy alias for compatibility
AdvancedGameResultsWindow = GameResultsWindow