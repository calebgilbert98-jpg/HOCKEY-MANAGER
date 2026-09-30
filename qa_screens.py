# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Headless smoke: every full-screen view builds without error.

Instantiates each converted XxxView with a stub app under Xvfb, runs one
update cycle, verifies the close_view contract, and tears down. This proves
the popup -> screen conversion didn't break view construction.
"""
import sys
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, ".")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL") + f" {name}" +
          (f" -- {detail}" if detail and not cond else ""))


class AutoStub:
    """Permissive stub: any attr/method returns another stub; iterates empty."""
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        v = AutoStub()
        self.__dict__[name] = v
        return v

    def __call__(self, *a, **k):
        return AutoStub()

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0

    def __bool__(self):
        return True


class StubTraining:
    """Minimal stand-in for the career training model."""
    def __init__(self):
        self.preset_name = "Balanced"
        self.schedule = {u: ("Medium", "General")
                         for u in ("Forwards", "Defense", "Goalies")}

    def set_preset(self, name):
        self.preset_name = name

    def set_unit(self, unit, intensity, focus):
        self.schedule[unit] = (intensity, focus)

    def weekly_effects(self):
        return {"development_mult": 1.0, "injury_risk_mult": 1.0,
                "morale_delta": 0, "notes": []}


def _stub_create_panel(parent, title, row, col, rowspan=1, colspan=1):
    from tkinter import ttk
    outer = ttk.Frame(parent, padding=1)
    outer.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan,
               sticky="nsew", padx=0, pady=8)
    frame = ttk.Frame(outer)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text=title, padding=(10, 5)).grid(row=0, column=0,
                                                      sticky="ew")
    return frame


def _stub_create_treeview(parent, columns, height=15):
    from tkinter import ttk
    cols = list(columns.keys()) if isinstance(columns, dict) else list(columns)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c in cols:
        text = columns[c][0] if isinstance(columns, dict) else c
        tree.heading(c, text=text)
    return tree


def build_app():
    import game_classes as g
    import reputation_system as rs
    from game_classes import EmailInbox
    from datetime import date

    player = g.Player(first_name="Test", last_name="Player", age=24,
                      primary_position=g.PlayerPosition.CENTER, jersey_number=9)
    rs.ensure_reputation_fields(player)
    player.salary = 5_250_000
    player.contract_years = 2
    goalie = g.Player(first_name="Test", last_name="Goalie", age=28,
                      primary_position=g.PlayerPosition.GOALIE, jersey_number=30)
    rs.ensure_reputation_fields(goalie)

    team = SimpleNamespace(
        team_name="Test Club", city="Testville", abbreviation="TST",
        roster=[player, goalie], ahl_roster=[], prospects=[], staff=[],
        inbox=EmailInbox(), tactics_control="coach", scouting_reports=[],
        schedule=[], payroll=85_000_000, salary_cap=95_500_000,
        cap_space=10_500_000,
        games_played=38, wins=20, losses=15, otl=3, is_user_team=True,
    )
    league = SimpleNamespace(teams=[team], free_agents=[], free_agent_staff=[],
                             season_year=2026, schedule=[], draft_prospects=[],
                             current_date=date(2026, 10, 1),
                             standings={"Test Club": {"W": 20, "L": 15, "OTL": 3}})
    gm = SimpleNamespace(league=league, user_team=team, free_agents=[],
                        current_date=date(2026, 10, 1))
    board = SimpleNamespace(expectation="playoffs", confidence=70,
                            job_status="Secure", season_wins=20,
                            season_losses=15, season_otl=3,
                            last_review="Solid start to the season.")
    profile = SimpleNamespace(reputation=65, level="Established",
                              career_wins=120, career_losses=90, career_otl=22,
                              titles_won=0, playoff_appearances=3,
                              seasons_managed=4)
    career = SimpleNamespace(board=board, training=StubTraining(),
                            youth_history=[], press_history=[],
                            profile=profile, prompts_enabled=True)
    app = AutoStub(league=league, user_team=team, open_windows={},
                   tree_maps={}, news_log=[], current_date=date(2026, 10, 1),
                   game_manager=gm, career=career,
                   media_system=SimpleNamespace(auto_handle_minor_events=True),
                   _create_panel=_stub_create_panel,
                   _create_treeview=_stub_create_treeview,
                   BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
                   TEXT_COLOR="#ffffff", ACCENT_COLOR="#4a9eff",
                   HEADER_COLOR="#ffffff",
                   TITLE_BAR_COLOR="#101018", FONT_FAMILY="Helvetica",
                   GAME_MODE_LABELS=(("Quick Sim", "quick"),
                                     ("Ask Each Game", "ask"),
                                     ("Watch Live", "watch")))
    # show_screen collaborators used by views that teleport further
    app.show_screen = lambda sid, title, cls, *a, **k: None
    app.show_dashboard = lambda: None
    app.refresh_screen_navbar = lambda: None
    app.negotiation_sessions = {}
    app.get_live_cap = lambda: 95_500_000
    staffer = g.Staff(first_name="Test", last_name="Coach", age=50,
                      role=g.StaffRole.HEAD_COACH, nationality="CAN")
    staffer.salary = 2_500_000
    staffer.contract_years = 3
    app._qa_player = player
    app._qa_staff = staffer
    return app


VIEWS = [
    ("windows", "RosterView", ()),
    ("windows", "FreeAgencyView", ()),
    ("windows", "ScoutingView", ()),
    ("windows", "DraftView", ()),
    ("windows", "ScheduleView", ()),
    ("windows", "FinancesView", ()),
    ("windows", "NewsView", ()),
    ("windows", "GMOptionsView", ()),
    ("windows", "WaiversView", ()),
    ("windows", "GMDashboardView", ()),
    ("windows", "TeamAnalyticsView", ()),
    ("windows", "SalaryAnalyticsView", ()),
    ("calendar_window", "CalendarView", ()),
    ("staff_management_window", "StaffManagementView", ()),
    ("professional_scouting_window", "ProfessionalScoutingView", ()),
    ("modern_scouting_window", "ModernScoutingView", ()),
    ("stats_standings_window", "StatsStandingsView", ()),
    ("playoff_system", "PlayoffView", ()),
    ("media_center_window", "MediaCenterView", ()),
    ("morale_window", "MoraleView", ()),
    ("manager_hub_window", "ManagerHubView", ()),
    ("game_results_window", "GameResultsView", ()),
    ("enhanced_practice_system", "DevelopmentOverviewView", ()),
    ("enhanced_practice_system", "PracticeCenterView", ()),
    ("player_development_window_professional",
     "PlayerDevelopmentViewProfessional", ()),
    ("tactics_window", "TacticsView", ()),
    ("inbox_window", "InboxView", ()),
    ("windows", "ContractNegotiationView", ()),
    ("windows", "ContractExtensionsView", ()),
    ("windows", "ExtensionNegotiationView", ()),
    ("windows", "StaffContractView", ()),
    ("windows", "BuyoutCalculatorView", ()),
]

RESULTS_DATA = {
    'date': 'October 10, 2026', 'user_game_result': None, 'all_games': [],
    'league_results': [], 'news_events': [], 'game_highlights': [],
    'games_played': 0, 'new_messages_count': 0,
}


def main():
    import importlib
    root = tk.Tk()
    root.withdraw()
    app = build_app()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo", return_value=None), \
         patch("tkinter.messagebox.showerror", return_value=None), \
         patch("tkinter.messagebox.showwarning", return_value=None):
        for mod_name, cls_name, _ in VIEWS:
            holder = tk.Frame(root, width=1600, height=900)
            holder.pack(fill="both", expand=True)
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
                extra = (RESULTS_DATA,) if cls_name == "GameResultsView" else ()
                if cls_name == "ContractNegotiationView":
                    extra = (app._qa_player, False)
                elif cls_name == "ExtensionNegotiationView":
                    extra = (app._qa_player, 6_000_000, 8)
                elif cls_name == "StaffContractView":
                    extra = (app._qa_staff,)
                view = cls(holder, app=app, *extra)
                root.update()
                check(f"{cls_name} builds",
                      view.winfo_exists() and view.winfo_children(),
                      "no child widgets")
                check(f"{cls_name} close_view contract",
                      callable(getattr(view, "close_view", None))
                      and hasattr(view, "_close_screen"))
                # close_view with no _close_screen set must fall back safely
                try:
                    view._close_screen = None
                    view.close_view()
                    root.update()
                    closed_ok = not view.winfo_exists()
                except Exception as e:  # noqa: BLE001
                    closed_ok = False
                    print(f"        close fallback raised: {e}")
                check(f"{cls_name} close fallback destroys", closed_ok)
            except Exception as e:  # noqa: BLE001
                import traceback
                check(f"{cls_name} builds", False, f"{type(e).__name__}: {e}")
                traceback.print_exc(limit=3)
            finally:
                try:
                    holder.destroy()
                except Exception:  # noqa: BLE001
                    pass
                root.update()

    # main.py's own views (imported live, not via module import)
    import main as m
    for cls_name in ("TacticsView", "GMOptionsView", "ContractExtensionsView"):
        holder = tk.Frame(root, width=1600, height=900)
        holder.pack(fill="both", expand=True)
        try:
            cls = getattr(m, cls_name)
            view = cls(holder, app=app)
            root.update()
            check(f"main.{cls_name} builds",
                  view.winfo_exists() and view.winfo_children(),
                  "no child widgets")
            check(f"main.{cls_name} close_view contract",
                  callable(getattr(view, "close_view", None)))
        except Exception as e:  # noqa: BLE001
            check(f"main.{cls_name} builds", False, f"{type(e).__name__}: {e}")
        finally:
            try:
                holder.destroy()
            except Exception:  # noqa: BLE001
                pass
            root.update()

    root.destroy()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
