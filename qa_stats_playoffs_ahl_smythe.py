"""Headless QA: playoff/RS split, AHL no-bleed, AHL screen, Conn Smythe.

Run with DISPLAY=:99. GUI parts build the real views against a fake app.
"""
import os
import sys
from types import SimpleNamespace
from datetime import datetime

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
os.chdir("/home/hatch/workspace/HOCKEY-MANAGER")

import tkinter as tk
from unittest.mock import patch

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

# Silence messageboxes headless
import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = lambda *a, **k: None
try:
    import popup_system as _ps
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = lambda *a, **k: None
except Exception:
    pass

from game_classes import PlayerStats
import ahl_system
from playoff_system import PlayoffBracket

# ---------------------------------------------------------------- fake world
def pos(v):
    return SimpleNamespace(value=v)

def mkplayer(name, position, age=24, overall=70):
    p = SimpleNamespace(
        full_name=name, name=name, primary_position=pos(position),
        age=age, overall=overall, team_name="",
        stats=PlayerStats(), playoff_stats=PlayerStats(),
        ahl_stats=None,
        # direct attrs (legacy RS path reads these)
        goals=0, assists=0, games_played=0, plus_minus=0,
        penalty_minutes=0, shots=0,
    )
    return p

def mkteam(name, div="Atlantic", conf="Eastern"):
    return SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        division=div, conference=conf,
        roster=[], ahl_roster=[],
        wins=0, losses=0, ot_losses=0, points=0, games_played=0,
        goals_for=0, goals_against=0, avg_attendance=17000,
    )

teams = [mkteam("Boston Bruins"), mkteam("Florida Panthers"),
         mkteam("Edmonton Oilers"), mkteam("Toronto Maple Leafs")]

# NHL skaters: RS leader vs playoff leader are DIFFERENT players
rs_star = mkplayer("RS Star", "C"); rs_star.goals, rs_star.assists = 50, 60
rs_star.stats.goals, rs_star.stats.assists, rs_star.stats.games_played = 50, 60, 82
po_star = mkplayer("Playoff Star", "LW"); po_star.goals, po_star.assists = 20, 25
po_star.stats.goals, po_star.stats.assists, po_star.stats.games_played = 20, 25, 82
po_star.playoff_stats.goals, po_star.playoff_stats.assists = 12, 14
po_star.playoff_stats.games_played = 20
po_star.playoff_stats.shots, po_star.playoff_stats.penalties_in_minutes = 70, 18
rs_star.playoff_stats.goals, rs_star.playoff_stats.assists = 3, 4
rs_star.playoff_stats.games_played = 7
for p in (rs_star, po_star):
    p.team_name = "Boston Bruins"
teams[0].roster = [rs_star, po_star]

champ_goalie = mkplayer("Champ Goalie", "G", overall=88)
champ_goalie.playoff_stats.games_played = 18
champ_goalie.playoff_stats.wins = 16
champ_goalie.playoff_stats.shots_against = 500
champ_goalie.playoff_stats.saves = 465  # .930 -- below the .935 exception
champ_goalie.team_name = "Boston Bruins"
teams[0].roster.append(champ_goalie)

# Farm players (ahl_roster) -- cooking prospect + farm goalie
cooker = mkplayer("Cooking Prospect", "C", age=20, overall=68)
farm_goalie = mkplayer("Farm Goalie", "G", age=23, overall=66)
for p in (cooker, farm_goalie):
    p.team_name = "Boston Bruins"
teams[0].ahl_roster = [cooker, farm_goalie]
# A second farm for the All-Farms table
cooker2 = mkplayer("Other Farm Star", "RW", age=21, overall=70)
cooker2.team_name = "Florida Panthers"
teams[1].ahl_roster = [cooker2]

# Fake bracket: Boston beats Florida in a 5-game final
def g(t1, t2, ot=False):
    return {"t1_score": t1, "t2_score": t2, "ot": ot}
final = SimpleNamespace(
    team1=teams[0], team2=teams[1],
    team1_wins=4, team2_wins=1,
    game_results=[g(4, 2), g(2, 3, True), g(5, 1), g(3, 2), g(4, 0)],
)
bracket = SimpleNamespace(
    playoff_series={"stanley_cup_final": [final]},
    stanley_cup_champion=teams[0],
    conn_smythe_winner=None, conn_smythe_name=None,
    league=SimpleNamespace(teams=teams, season_year=2026),
)

fake_app = SimpleNamespace(
    current_date=datetime(2026, 4, 20),
    league=SimpleNamespace(teams=teams, season_year=2026,
                           playoff_bracket=bracket, standings={}),
    game_manager=None, open_windows={},
    user_team=teams[0],
    BG_COLOR="#1a1a2e", PANEL_COLOR="#16213e",
)
fake_app.game_manager = SimpleNamespace(league=fake_app.league,
                                        user_team=teams[0])
# _create_treeview shim (real HockeyApp builds a sortable ttk.Treeview)
import tkinter.ttk as _ttk
def _fake_create_treeview(parent, columns, height=15, **kw):
    tree = _ttk.Treeview(parent, columns=list(columns.keys()),
                         show="headings", height=height)
    for col, spec in columns.items():
        text, width = spec[0], spec[1]
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="center")
    return tree
fake_app._create_treeview = _fake_create_treeview
fake_app.atmospheric_dashboard = None
# hasattr(app,'atmospheric_dashboard') is True but None -> falls to fallback
del fake_app.atmospheric_dashboard

print("== A. ahl_system ==")
led = ahl_system.ensure_ahl_stats(cooker)
check("ensure_ahl_stats returns PlayerStats", isinstance(led, PlayerStats))
check("ensure_ahl_stats idempotent", ahl_system.ensure_ahl_stats(cooker) is led)
check("no-bleed: NHL stats untouched pre-sim",
      cooker.stats.games_played == 0 and cooker.stats.goals == 0)

import random
random.seed(7)
for _ in range(60):
    ahl_system.simulate_ahl_day(fake_app.league)
check("farm games accumulate", cooker.ahl_stats.games_played > 5,
      f"gp={cooker.ahl_stats.games_played}")
check("no-bleed: NHL stats still zero after 60 farm days",
      cooker.stats.games_played == 0 and cooker.stats.goals == 0
      and rs_star.stats.goals == 50)
check("no-bleed: NHL roster never gains ahl games",
      rs_star.ahl_stats is None or rs_star.ahl_stats.games_played == 0)
check("farm goalie got starts", farm_goalie.ahl_stats.games_played > 0)

sk = ahl_system.top_skaters(fake_app.league, limit=25)
check("top_skaters sorted desc",
      all((a[2].goals + a[2].assists) >= (b[2].goals + b[2].assists)
          for a, b in zip(sk, sk[1:])))
check("top_skaters NHL-free", all(
    p.ahl_stats is not None and p not in teams[0].roster for p, _, _ in sk))
ck = ahl_system.cooking(fake_app.league, limit=15, min_gp=10)
check("cooking respects min GP", all(l.games_played >= 10 for _, _, l, _ in ck))
check("cooking sorted by P/GP",
      all(a[3] >= b[3] for a, b in zip(ck, ck[1:])))
gl = ahl_system.top_goalies(fake_app.league, limit=15)
check("top_goalies are goalies w/ min GP",
      all("G" in str(p.primary_position.value) and l.games_played >= 5
          for p, _, l in gl))

print("== B. Conn Smythe ==")
def smythe_stub(**kw):
    stub = SimpleNamespace(
        stanley_cup_champion=teams[0],
        league=SimpleNamespace(teams=teams, season_year=2026),
        _smythe_is_goalie=PlayoffBracket._smythe_is_goalie,
        _SMYTHE_GOALIE_WINS=12, _SMYTHE_GOALIE_SV=0.935,
        conn_smythe_winner=None, conn_smythe_name=None,
        **kw)
    stub._historic_loser_run = lambda k: PlayoffBracket._historic_loser_run(
        stub, k)
    return stub

w = PlayoffBracket._decide_conn_smythe(smythe_stub())
check("default: champion scoring leader wins", w is po_star,
      f"got {getattr(w, 'full_name', w)}")

# Goalie exception: .940 with 16 wins
champ_goalie.playoff_stats.saves = 470  # .940
w = PlayoffBracket._decide_conn_smythe(smythe_stub())
check("goalie exception .940/16W wins", w is champ_goalie,
      f"got {getattr(w, 'full_name', w)}")
champ_goalie.playoff_stats.saves = 465  # back to .930

# McDavid exception: Oiler puts up 42, champ best is 26
mcd = mkplayer("Loser Star", "C"); mcd.team_name = "Edmonton Oilers"
mcd.playoff_stats.goals, mcd.playoff_stats.assists = 15, 27
mcd.playoff_stats.games_played = 24
teams[2].roster = [mcd]
w = PlayoffBracket._decide_conn_smythe(smythe_stub())
check("McDavid exception: 42-pt loser beats 26-pt champ", w is mcd,
      f"got {getattr(w, 'full_name', w)}")
# Near-miss 1: 34 pts (below 35 floor)
mcd.playoff_stats.goals, mcd.playoff_stats.assists = 12, 22
w = PlayoffBracket._decide_conn_smythe(smythe_stub())
check("34-pt loser does NOT trigger exception", w is po_star,
      f"got {getattr(w, 'full_name', w)}")
# Near-miss 2: 40 pts but champ best 30 (ratio 1.33 < 1.5)
mcd.playoff_stats.goals, mcd.playoff_stats.assists = 14, 26
po_star.playoff_stats.goals, po_star.playoff_stats.assists = 14, 16  # 30
w = PlayoffBracket._decide_conn_smythe(smythe_stub())
check("40 pts at 1.33x champ does NOT trigger", w is po_star,
      f"got {getattr(w, 'full_name', w)}")
po_star.playoff_stats.goals, po_star.playoff_stats.assists = 12, 14  # restore
teams[2].roster = []

print("== C. stats-screen helpers ==")
from stats_standings_window import StatsStandingsView
stub = SimpleNamespace(app=fake_app)
pg = StatsStandingsView.get_team_playoff_stats(stub)
check("playoff team table: champ 5GP/4W", pg["Boston Bruins"]["GP"] == 5
      and pg["Boston Bruins"]["W"] == 4, str(pg.get("Boston Bruins")))
check("playoff team table: champ GF=18 GA=8",
      pg["Boston Bruins"]["GF"] == 18 and pg["Boston Bruins"]["GA"] == 8)
check("playoff team table: champ result", pg["Boston Bruins"]["result"]
      == "Won Stanley Cup")
check("playoff team table: runner-up Lost Cup Final",
      pg["Florida Panthers"]["result"] == "Lost Cup Final")
check("non-playoff teams excluded", "Edmonton Oilers" not in pg)

class FakeVar:
    def __init__(self, v): self._v = v
    def get(self): return self._v
    def set(self, v): self._v = v
led_stub = SimpleNamespace(season_type=FakeVar("Regular Season"))
led_stub._in_playoff_mode = lambda: StatsStandingsView._in_playoff_mode(led_stub)
led_stub._stat_ledger = lambda p: StatsStandingsView._stat_ledger(led_stub, p)
check("RS mode ledger is stats",
      StatsStandingsView._stat_ledger(led_stub, po_star) is po_star.stats)
led_stub.season_type.set("Playoffs")
check("playoff mode ledger is playoff_stats",
      StatsStandingsView._stat_ledger(led_stub, po_star)
      is po_star.playoff_stats)
check("_pstat playoff goals=12",
      StatsStandingsView._pstat(led_stub, po_star, "goals") == 12)
old = mkplayer("Old Save Guy", "C")  # no playoff_stats attr
del old.playoff_stats
check("old-save fallback to stats",
      StatsStandingsView._stat_ledger(led_stub, old) is old.stats)

print("== D. GUI smoke (headless) ==")
root = tk.Tk(); root.withdraw()
try:
    from stats_standings_window import StatsStandingsView as SSV
    view = SSV(root, app=fake_app)
    check("StatsStandingsView builds", True)
    view.season_type.set("Regular Season")
    view.load_all_players_data("scoring")
    _rs = view.pagination_data["scoring"]["all_players"]
    top_rs = _rs[0][0].full_name if _rs else None
    check("RS scoring leader correct", top_rs == "RS Star", str(top_rs))
    view.season_type.set("Playoffs")
    view.on_season_type_change()  # full refresh_all_data path
    check("toggle to Playoffs: refresh survives", True)
    view.load_all_players_data("scoring")
    _po = view.pagination_data["scoring"]["all_players"]
    top_po = _po[0][0].full_name if _po else None
    check("playoff scoring leader correct", top_po == "Playoff Star", str(top_po))
    # min-games filter: Playoff Star has 20 GP; RS Star only 7 playoff GP --
    # with default min_games=10 the RS Star must be filtered out entirely
    names_po = {p.full_name for p, _ in _po}
    check("playoff min-games filter works", "RS Star" not in names_po,
          str(sorted(names_po)))
    cols = view.get_enhanced_player_columns("advanced")
    check("playoff advanced -> rate columns", "ppg" in cols and "xgf" not in cols,
          str(sorted(cols)))
    view.season_type.set("Regular Season")
    cols = view.get_enhanced_player_columns("advanced")
    check("RS advanced -> xG columns restored", "xgf_pct" in cols)
    # dashboard metric cards: NHL goals only, no AHL bleed
    mf = __import__("customtkinter").CTkFrame(root)
    view._fill_metric_cards(mf)
    labels = [str(w.cget("text")) for w in mf.winfo_children()
              for w in [w] if "CTkLabel" in type(w).__name__]
    check("metric cards built", len(mf.winfo_children()) == 4,
          str(len(mf.winfo_children())))
    view.destroy()
except Exception as e:
    import traceback; traceback.print_exc()
    check("stats view GUI smoke", False, repr(e))

try:
    from ahl_stats_window import AHLStatsView
    av = AHLStatsView(root, app=fake_app)
    check("AHLStatsView builds", True)
    av.refresh_view()
    rows = av.scorers_tree.get_children()
    check("scorers table populated", len(rows) > 0, f"rows={len(rows)}")
    vals = av.scorers_tree.item(rows[0])["values"]
    top_pts = vals[8]
    exp = cooker.ahl_stats.goals + cooker.ahl_stats.assists
    exp2 = cooker2.ahl_stats.goals + cooker2.ahl_stats.assists
    check("scorers PTS == ahl_stats ledger",
          top_pts == max(exp, exp2), f"row={top_pts} exp={max(exp, exp2)}")
    names = {av.scorers_tree.item(r)["values"][1] for r in rows}
    check("no NHL skaters in AHL table",
          "RS Star" not in names and "Playoff Star" not in names, str(names))
    grows = av.goalies_tree.get_children()
    check("goalies table populated", len(grows) > 0)
    av.team_choice.set("My Farm Team")
    av.refresh_view()
    rows2 = av.scorers_tree.get_children()
    teams_shown = {av.scorers_tree.item(r)["values"][2] for r in rows2}
    check("My Farm Team filter", teams_shown == {"Boston Bruins"},
          str(teams_shown))
    av.destroy()
except Exception:
    import traceback; traceback.print_exc()
    check("AHL view GUI smoke", False, "exception")

root.destroy()
print(f"\nQA RESULT: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
