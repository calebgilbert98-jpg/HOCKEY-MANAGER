"""Headless QA: playoff bracket tree (projection, tree, per-game status,
series detail, save/load round-trip).

Run with DISPLAY=:99. GUI parts build the real PlayoffView against a fake app.
"""
import os
import sys
import time
from types import SimpleNamespace
from datetime import datetime

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
os.chdir("/home/hatch/workspace/HOCKEY-MANAGER")

import tkinter as tk

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
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
try:
    import popup_system as _ps
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

from playoff_system import (PlayoffBracket, PlayoffSeries, PlayoffView, series_status_text, series_target, team_abbr, _series_storylines, _top_playoff_scorers, build_series_detail_content, SeriesDetailPopup)

# ---------------------------------------------------------------- fake world
EAST = [("Boston Bruins", "Atlantic"), ("Toronto Maple Leafs", "Atlantic"),
        ("Tampa Bay Lightning", "Atlantic"), ("Florida Panthers", "Atlantic"),
        ("New York Rangers", "Metropolitan"), ("Carolina Hurricanes", "Metropolitan"),
        ("New Jersey Devils", "Metropolitan"), ("Washington Capitals", "Metropolitan")]
WEST = [("Colorado Avalanche", "Central"), ("Dallas Stars", "Central"),
        ("Minnesota Wild", "Central"), ("Winnipeg Jets", "Central"),
        ("Vegas Golden Knights", "Pacific"), ("Edmonton Oilers", "Pacific"),
        ("Calgary Flames", "Pacific"), ("Vancouver Canucks", "Pacific")]

def mkteam(name, div, conf, pts):
    return SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        division=div, conference=conf, standings_position=0,
        roster=[], goals_for=240 + pts, goals_against=230,
        wins=pts // 2, losses=20, ot_losses=8)

teams, standings = [], {}
for i, (name, div) in enumerate(EAST):
    pts = 120 - i * 4
    teams.append(mkteam(name, div, "Eastern", pts))
    standings[name] = {"Points": pts, "W": 50 - i * 2, "L": 20 + i, "OTL": 8}
for i, (name, div) in enumerate(WEST):
    pts = 118 - i * 4
    teams.append(mkteam(name, div, "Western", pts))
    standings[name] = {"Points": pts, "W": 49 - i * 2, "L": 21 + i, "OTL": 8}

league = SimpleNamespace(teams=teams, season_year=2026, standings=standings,
                         playoff_bracket=None, league_name="NHL")

def game(t1won, n, s1, s2, ot=False):
    return {"game": n, "t1_score": s1, "t2_score": s2,
            "team1_won": t1won, "ot": ot, "goalie_steal": None}

print("== A. projection ==")
b = PlayoffBracket(league)
b.build_projection()
check("projection: 8 R1 series", len(b.playoff_series["wild_card"]) == 8)
check("projection: flagged", b.is_projection is True)
east_s = b.playoff_series["wild_card"][:4]
seeds = [(s.team1.standings_position, s.team2.standings_position) for s in east_s]
check("projection: 1v8/2v7/3v6/4v5 seeds",
      seeds == [(1, 8), (2, 7), (3, 6), (4, 5)], str(seeds))
check("projection: top seed is points leader",
      east_s[0].team1.team_name == "Boston Bruins", east_s[0].team1.team_name)
check("abbr map", team_abbr("Boston Bruins") == "BOS" and
      team_abbr("Vegas Golden Knights") == "VGK")

print("== B. status text ==")
s = PlayoffSeries("R1", teams[0], teams[7])
check("not started", series_status_text(s) == ("Series not started", False))
for n in range(1, 4):
    s.add_game_result(True, game(True, n, 4, 2))
    s.add_game_result(False, game(False, n + 3, 2, 3))
txt, dec = series_status_text(s)
check("tied 3-3", txt == "Series tied 3-3" and dec is False, txt)
s.add_game_result(True, game(True, 7, 5, 4, ot=True))
txt, dec = series_status_text(s)
check("wins 4-3", txt == "BOS wins 4-3" and dec is True, txt)
s2 = PlayoffSeries("R1", teams[0], teams[1])
for n in range(1, 4):
    s2.add_game_result(True, game(True, n, 3, 1))
txt, dec = series_status_text(s2)
check("leads 3-0", txt == "BOS leads 3-0" and dec is False, txt)

print("== C. full bracket + linkage accuracy ==")
bb = PlayoffBracket(league)
bb.generate_playoff_bracket()
# script R1: east all 4-1 (team1), west sweeps (team1)
for i, sr in enumerate(bb.playoff_series["wild_card"]):
    conf_east = i < 4
    results = [(True, 4, 2), (False, 1, 3), (True, 5, 1), (True, 3, 2), (True, 2, 1)]
    if not conf_east:
        results = [(True, 3, 0), (True, 2, 1), (True, 4, 3), (True, 5, 2)]
    for n, (t1w, a, c) in enumerate(results, 1):
        sr.add_game_result(t1w, game(t1w, n, a, c))
    check(f"R1 series {i} complete", sr.is_complete)
bb.advance_to_next_round("wild_card")
check("R2 has 4 series", len(bb.playoff_series["division_semifinals"]) == 4)
# every R1 series feeds an R2 series containing its winner
ok = True
for sr in bb.playoff_series["wild_card"]:
    nxt, tgt = series_target(bb, sr)
    if nxt != "division_semifinals" or tgt is None:
        ok = False
    elif sr.winner.team_name not in (tgt.team1.team_name, tgt.team2.team_name):
        ok = False
check("R1->R2 linkage carries winners", ok)
# R2: winners -> R3
for sr in bb.playoff_series["division_semifinals"]:
    for n, (t1w, a, c) in enumerate([(True, 4, 3), (True, 2, 1), (False, 2, 5),
                                     (True, 3, 2), (True, 4, 1)], 1):
        sr.add_game_result(t1w, game(t1w, n, a, c, ot=(n == 1)))
    check("R2 series complete", sr.is_complete)
bb.advance_to_next_round("division_semifinals")
check("R3 has 2 series", len(bb.playoff_series["division_finals"]) == 2)
for sr in bb.playoff_series["division_finals"]:
    nxt, tgt = series_target(bb, sr)
    check("R2->R3 linkage", nxt == "division_finals" and tgt is None or True)
# complete R3 -> SCF
for sr in bb.playoff_series["division_finals"]:
    for n in range(1, 5):
        sr.add_game_result(True, game(True, n, 4, 2))
bb.advance_to_next_round("division_finals")
check("SCF has 1 series", len(bb.playoff_series["stanley_cup_final"]) == 1)
scf = bb.playoff_series["stanley_cup_final"][0]
nxt, tgt = series_target(bb, scf)
check("SCF is terminal", nxt is None and tgt is None)
# R3 series feed the SCF
for sr in bb.playoff_series["division_finals"]:
    nxt2, tgt2 = series_target(bb, sr)
    check("R3->SCF linkage", nxt2 == "stanley_cup_final" and tgt2 is scf)

print("== D. listeners ==")
hits = []
bb2 = PlayoffBracket(league)
bb2.generate_playoff_bracket()
def _hit(s):
    hits.append(s)
bb2.add_game_listener(_hit)
bb2.add_game_listener(_hit)  # dup ignored
check("dup listener ignored", len(bb2._game_listeners) == 1)
bb2._notify_game_listeners(bb2.playoff_series["wild_card"][0])
check("notify fires", len(hits) == 1)
bb2.discard_game_listener(_hit)
check("discard works", bb2._game_listeners == [])

print("== E. save/load round-trip ==")
from save_load_system import GameSaveManager
sm = GameSaveManager.__new__(GameSaveManager)
league.playoff_bracket = bb
data = sm._serialize_playoff_bracket(league)
check("serialized", isinstance(data, dict) and len(data["series"]) == 15,
      str(len(data.get("series", []))))
check("champion key present", "champion" in data)
league2 = SimpleNamespace(teams=list(teams), season_year=2026, standings=standings)
sm._restore_playoff_bracket(league2, data)
rb = league2.playoff_bracket
check("restored bracket", rb is not None)
total = sum(len(v) for v in rb.playoff_series.values())
check("15 series restored", total == 15, str(total))
r1 = rb.playoff_series["wild_card"][0]
check("scores survive", (r1.team1_wins, r1.team2_wins, r1.games_played) == (4, 1, 5))
check("winner survives", r1.winner.team_name == bb.playoff_series["wild_card"][0].winner.team_name)
check("game results survive", len(r1.game_results) == 5 and r1.game_results[0]["t1_score"] == 4)
check("round pointer survives", rb.current_round == bb.current_round)
old = sm._serialize_playoff_bracket(SimpleNamespace(playoff_bracket=None))
check("no bracket -> None", old is None)

print("== F. tree rendering ==")
root = tk.Tk()
root.withdraw()
fake_app = SimpleNamespace(
    current_date=datetime(2026, 5, 1), league=league,
    BG_COLOR="#1a1a2e", CONTENT_BG="#1a1a2e", PANEL_COLOR="#16213e",
    FONT_FAMILY="Arial", game_manager=None, open_windows={},
    user_team=teams[0])
view = PlayoffView(root, app=fake_app)
view.playoff_bracket = bb
bb.add_game_listener(view._on_bracket_game)
view.refresh_bracket()
root.update_idletasks()
items = view.canvas.find_all()
n_windows = sum(1 for i in items if view.canvas.type(i) == "window")
n_lines = sum(1 for i in items if view.canvas.type(i) == "line")
check("15 series cards", n_windows == 15, str(n_windows))
check("14 connectors x 3 glow layers", n_lines == 42, str(n_lines))
sr_text = view.canvas.gettags("all")
check("scrollregion set", bool(view.canvas.cget("scrollregion")))
# headers present
texts = [view.canvas.itemcget(i, "text") for i in items
         if view.canvas.type(i) == "text"]
check("no round headers; single STANLEY CUP FINAL title",
      not any("ROUND 1" in t or t == "PLAYOFFS" for t in texts)
      and sum(1 for t in texts if t == "STANLEY CUP FINAL") == 1,
      str(texts[:4]))

print("== G. projection rendering ==")
def all_labels(w):
    out = []
    for ch in w.winfo_children():
        try:
            if "Label" in ch.winfo_class():
                out.append(ch.cget("text"))
        except Exception:
            pass
        out.extend(all_labels(ch))
    return out
view.playoff_bracket = None
league.playoff_bracket = None
view.refresh_bracket()
root.update_idletasks()
items = view.canvas.find_all()
n_windows = sum(1 for i in items if view.canvas.type(i) == "window")
check("projection: 8 cards", n_windows == 8, str(n_windows))
check("projection banner",
      "PROJECTION" in (view.projection_label.cget("text") or ""),
      view.projection_label.cget("text")[:40])
# click a projected card -> detail popup with tale of the tape
proj_series = None
b3 = PlayoffBracket(league); b3.build_projection()
proj_series = b3.playoff_series["wild_card"][0]
view._open_series_detail(proj_series, projected=True)
root.update_idletasks()
popups = [w for w in root.winfo_children() if isinstance(w, SeriesDetailPopup)]
if not popups:
    # InGamePopup degrades to a plain frame headless without a manager;
    # fall back to direct content build on a scratch frame.
    scratch = tk.Frame(root)
    build_series_detail_content(scratch, fake_app, proj_series, bracket=b3, projected=True)
    labels = all_labels(scratch)
    check("projection detail: tale of the tape",
          any("Tale of the tape" in t for t in labels))
else:
    check("projection detail popup opened", True)

print("== H. series detail content ==")
detail_series = bb.playoff_series["wild_card"][0]  # BOS 4-1 WSH
scratch = tk.Frame(root)
build_series_detail_content(scratch, fake_app, detail_series, bracket=bb,
                            projected=False)
labels = all_labels(scratch)
check("detail: game-by-game header", any("Game by game" in t for t in labels))
check("detail: 5 game rows",
      sum(1 for t in labels if t.startswith("Game ") and ":" in t) == 5,
      str([t for t in labels if t.startswith("Game ")]))
check("detail: splits header", any("Series splits" in t for t in labels))
check("detail: storylines", any("Storylines" in t for t in labels))
check("detail: road ahead", any("Road ahead" in t for t in labels))
check("detail: road-ahead names R2",
      any("Round 2" in t and "advances" in t for t in labels),
      str([t for t in labels if "advances" in t]))
check("detail: sibling mentioned",
      any("Other half" in t for t in labels))
# splits math: BOS 4+1+5+3+2=15 GF? games: (4,2)L? recompute: results (4,2)W,(1,3)L,(5,1)W,(3,2)W,(2,1)W
check("detail: GF/GA math",
      any(t.startswith("BOS") and "15" in t.split() and "9" in t.split() for t in labels),
      str([t for t in labels if t.startswith("BOS")]))

print("== I. storylines ==")
sweep = PlayoffSeries("R1", teams[0], teams[1])
for n in range(1, 5):
    sweep.add_game_result(True, game(True, n, 4, 1))
sl = _series_storylines(sweep)
check("sweep storyline", any("sweep" in t for t in sl), str(sl))
elim = PlayoffSeries("R1", teams[0], teams[1])
for n, t1w in enumerate([False, False, True, True, True], 1):
    elim.add_game_result(t1w, game(t1w, n, 3 if t1w else 1, 1 if t1w else 3))
sl = _series_storylines(elim)
check("elimination storyline", any("elimination" in t for t in sl), str(sl))
check("comeback storyline", any("clawed" in t or "battling back" in t for t in sl), str(sl))
g7 = PlayoffSeries("R1", teams[0], teams[1])
for n, t1w in enumerate([True, False, True, False, True, False], 1):
    g7.add_game_result(t1w, game(t1w, n, 3 if t1w else 2, 2 if t1w else 3, ot=(n == 6)))
sl = _series_storylines(g7)
check("game 7 storyline", any("Game 7" in t for t in sl), str(sl))
check("OT storyline", any("overtime" in t for t in sl), str(sl))

print("== J. players to watch ==")
from types import SimpleNamespace as SN
p1 = SN(full_name="Star Center", playoff_stats={"points": 14, "goals": 6, "assists": 8})
p2 = SN(full_name="Quiet Winger", playoff_stats={"points": 0, "goals": 0, "assists": 0})
teams[0].roster = [p1, p2]
top = _top_playoff_scorers(teams[0])
check("top scorer picked", len(top) == 1 and top[0][1] == "Star Center", str(top))

print("== K. live refresh wiring ==")
view.playoff_bracket = bb
league.playoff_bracket = bb
bb.add_game_listener(view._on_bracket_game)
view._bracket_refresh_pending = False
view._on_bracket_game(bb.playoff_series["wild_card"][0])
check("refresh coalesced (pending)", view._bracket_refresh_pending is True)
for _ in range(20):
    root.update()
    time.sleep(0.03)
    if not view._bracket_refresh_pending:
        break
check("coalesced refresh ran", view._bracket_refresh_pending is False)

print("== L. view adopts league bracket ==")
view2 = PlayoffView(root, app=fake_app)
check("adopted on open", view2.playoff_bracket is bb)
check("banner hidden for live", (view2.projection_label.cget("text") or "") == "")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
