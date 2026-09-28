"""
Analytics window (roadmap F6: visible surface for the sim's depth).

Shows xG, shot maps, and the analyst's report for the last game.
"""

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False


class AnalyticsWindow:
    """Post-game analytics display."""

    def __init__(self, parent, game_data):
        self.game_data = game_data
        if not HAS_CTK:
            return
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Analytics Hub")
        self.window.geometry("600x500")
        self._build()

    def _build(self):
        from analytics import game_xg, analyst_report, shot_map
        data = self.game_data
        home = data.get('home_team', 'Home')
        away = data.get('away_team', 'Away')

        ctk.CTkLabel(self.window, text="Analytics Hub",
                     font=('Segoe UI', 16, 'bold')).pack(pady=12)

        scroll = ctk.CTkScrollableFrame(self.window)
        scroll.pack(fill='both', expand=True, padx=12, pady=6)

        # xG
        xg = game_xg(data.get('pbp_events', []))
        hx = xg.get(home, {}).get('xg', 0)
        ax = xg.get(away, {}).get('xg', 0)
        xg_frame = ctk.CTkFrame(scroll)
        xg_frame.pack(fill='x', padx=6, pady=6)
        ctk.CTkLabel(xg_frame, text="Expected Goals (xG)",
                     font=('Segoe UI', 13, 'bold')).pack(pady=6)
        ctk.CTkLabel(xg_frame,
                     text=f"{home}: {hx:.2f}    {away}: {ax:.2f}",
                     font=('Segoe UI', 14)).pack(pady=6)

        # Analyst report
        rep_frame = ctk.CTkFrame(scroll)
        rep_frame.pack(fill='x', padx=6, pady=6)
        ctk.CTkLabel(rep_frame, text="Analyst's Report",
                     font=('Segoe UI', 13, 'bold')).pack(pady=6)
        report = analyst_report(data)
        ctk.CTkLabel(rep_frame, text=report,
                     font=('Segoe UI', 11),
                     wraplength=520, justify='left').pack(
                         padx=10, pady=6)

        ctk.CTkButton(self.window, text="Close",
                      command=self.window.destroy).pack(pady=12)


def open_analytics(parent, game_data):
    return AnalyticsWindow(parent, game_data)
