"""
Tactics screen (roadmap E1: named tactical systems, full UI).

Per-phase system pickers for the player's team. The AI uses the same
systems via ai_coach.py — this is the player's control surface.
"""

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False


# Phase -> (attribute, options, description)
TACTIC_PHASES = [
    ('Forecheck', 'tactic_forecheck',
     ['2-1-2', '1-2-2', '1-4'],
     'Pressure scheme in the offensive zone. 2-1-2 is aggressive, '
     '1-4 is a passive trap.'),
    ('Neutral Zone', 'tactic_neutral_zone',
     ['1-2-2', '1-1-3', '2-1-2'],
     'How you defend the middle of the ice. 1-1-3 clogs everything.'),
    ('Breakout', 'tactic_breakout',
     ['positional', 'board_play', 'crisscross', 'wings_cross'],
     'How defensemen move the puck out. Wings cross is high-risk.'),
    ('D-Zone Coverage', 'tactic_dz_coverage',
     ['positional', 'collapse', 'open'],
     'Collapse packs the slot (+blocks). Open is aggressive (-blocks).'),
    ('Power Play', 'tactic_pp',
     ['umbrella', '1-2-2', '2-1-2', 'diamond', 'funnel'],
     'Umbrella works the point. Funnel attacks the slot.'),
    ('Penalty Kill', 'tactic_pk',
     ['tight_box', 'wide_box', 'diamond'],
     'Tight box protects the slot. Diamond pressures the points.'),
    ('Faceoff', 'tactic_faceoff',
     ['basic', 'overload', 'drop_pass', 'point_shot'],
     'Overload wins draws. Point shot looks for the one-timer.'),
    ('O-Zone Formation', 'tactic_offense',
     ['Spread', 'Overload', 'Umbrella', 'Crash the Net'],
     'Even-strength offensive shape.'),
]


class TacticsScreen:
    """Tactics picker window for the player's team."""

    def __init__(self, parent, team):
        self.team = team
        if not HAS_CTK:
            return
        self.window = ctk.CTkToplevel(parent)
        self.window.title(f"Tactics — {team.team_name}")
        self.window.geometry("520x640")
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self.window,
            text=f"{self.team.team_name} Tactics",
            font=('Segoe UI', 16, 'bold')).pack(pady=12)

        scroll = ctk.CTkScrollableFrame(self.window)
        scroll.pack(fill='both', expand=True, padx=12, pady=6)

        self._vars = {}
        for label, attr, options, desc in TACTIC_PHASES:
            frame = ctk.CTkFrame(scroll)
            frame.pack(fill='x', padx=6, pady=6)

            ctk.CTkLabel(frame, text=label,
                         font=('Segoe UI', 12, 'bold')).pack(
                             anchor='w', padx=10, pady=(8, 0))
            ctk.CTkLabel(frame, text=desc,
                         font=('Segoe UI', 10),
                         text_color='gray').pack(
                             anchor='w', padx=10, pady=(0, 4))

            var = ctk.StringVar(value=getattr(self.team, attr, options[0]))
            self._vars[attr] = var
            menu = ctk.CTkOptionMenu(frame, variable=var, values=options,
                                     command=lambda v, a=attr: self._on_change(a, v))
            menu.pack(anchor='w', padx=10, pady=(0, 10))

        ctk.CTkButton(self.window, text="Done",
                      command=self.window.destroy).pack(pady=12)

    def _on_change(self, attr, value):
        """Apply a tactic change immediately."""
        setattr(self.team, attr, value)


def open_tactics(parent, team):
    """Open the tactics screen for a team."""
    return TacticsScreen(parent, team)
