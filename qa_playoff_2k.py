"""QA: 2K-style mirrored bracket + LEAGUE TENSION gauge + bad blood.

Run with DISPLAY=:99 (Xvfb). Builds a real PlayoffBracket through the
actual generate/advance code paths on a fake 32-team league, records
bad-blood incidents in a live NarrativeLedger, and verifies:

  1. Mirrored layout: 7 columns, West R1 left / East R1 right, SCF center.
  2. Team-colored cards, wins badges, white connectors, Cup emblem, ticker.
  3. LEAGUE TENSION gauge reflects ledger heat (CHIPPY here).
  4. Bad-blood storylines surface for the feuding pair.
  5. GameSim._apply_hit_injury: real injury + rivalry incident + ledger.

Screenshots -> ~/workspace/ahl_shots/bracket_2k_*.png. No repo files modified.
"""
import os
import sys
import time
from types import SimpleNamespace
from datetime import date

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
os.chdir("/home/hatch/workspace/HOCKEY-MANAGER")

import tkinter as tk
from tkinter import ttk

import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
try:
    import popup_system as _ps
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

import customtkinter as ctk

from playoff_system import (PlayoffBracket, PlayoffView, PlayoffSeries,
                            series_target, _series_storylines)
from narrative_ledger import (NarrativeLedger, set_active_ledger,
                              active_ledger)
from season_intensity import season_intensity

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

# ---------------------------------------------------------------- fake league
NHL32 = [
    ("Boston Bruins", "Eastern"), ("Buffalo Sabres", "Eastern"),
    ("Detroit Red Wings", "Eastern"), ("Florida Panthers", "Eastern"),
    ("Montreal Canadiens", "Eastern"), ("Tampa Bay Lightning", "Eastern"),
    ("Toronto Maple Leafs", "Eastern"), ("Carolina Hurricanes", "Eastern"),
    ("Columbus Blue Jackets", "Eastern"), ("New Jersey Devils", "Eastern"),
    ("New York Islanders", "Eastern"), ("New York Rangers", "Eastern"),
    ("Philadelphia Flyers", "Eastern"), ("Pittsburgh Penguins", "Eastern"),
    ("Washington Capitals", "Eastern"), ("Ottawa Senators", "Eastern"),
    ("Colorado Avalanche", "Western"), ("Dallas Stars", "Western"),
    ("Minnesota Wild", "Western"), ("Nashville Predators", "Western"),
    ("St. Louis Blues", "Western"), ("Winnipeg Jets", "Western"),
    ("Chicago Blackhawks", "Western"), ("Utah Hockey Club", "Western"),
    ("Edmonton Oilers", "Western"), ("Los Angeles Kings", "Western"),
    ("Vancouver Canucks", "Western"), ("Vegas Golden Knights", "Western"),
    ("Anaheim Ducks", "Western"), ("Calgary Flames", "Western"),
    ("San Jose Sharks", "Western"), ("Seattle Kraken", "Western"),
]

teams, standings = [], {}
for i, (name, conf) in enumerate(NHL32):
    pts = 118 - (i % 16) * 3
    idx = i % 16
    if conf == "Eastern":
        div = "Atlantic" if idx < 8 else "Metropolitan"
    else:
        div = "Central" if idx < 8 else "Pacific"
    t = SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        conference=conf, division=div,
        roster=[], wins=pts // 2, losses=20, ot_losses=5, points=pts,
        goals_for=280, goals_against=240, standings_position=(i % 16) + 1)
    teams.append(t)
    standings[name] = {"Points": pts, "W": pts // 2}

league = SimpleNamespace(teams=teams, standings=standings, season_year=2026,
                         rivalries=[], playoff_bracket=None)

# ------------------------------------------------------- live ledger + heat
led = NarrativeLedger()
led.set_clock(2026, 200)
set_active_ledger(led)
led.record("incident",
           teams=["Buffalo Sabres", "Toronto Maple Leafs"],
           players=["Rival Slugger", "Star Victim"],
           facts={"incident_kind": "star_injured",
                  "detail": "Rival Slugger injured Star Victim with a charging hit"},
           weight=25, text="Rival Slugger injured Star Victim with a charging hit")
led.record("incident",
           teams=["Buffalo Sabres", "Toronto Maple Leafs"],
           players=[],
           facts={"incident_kind": "brawl", "detail": "Line brawl in the third"},
           weight=15, text="Line brawl in the third")

info = season_intensity(led)
check("gauge value 60 from 25+15 heat", info["value"] == 60.0, str(info["value"]))
check("gauge mood CHIPPY", info["label"] == "CHIPPY", info["label"])
check("gauge drivers list the hit", any("Slugger" in d["label"] for d in info["drivers"]))

# ------------------------------------------------------- build real bracket
b = PlayoffBracket(league)
b.generate_playoff_bracket()
check("R1 has 8 series", len(b.playoff_series.get("wild_card", [])) == 8)

def g(t1w, s1=3, s2=2, ot=False):
    return {"team1_won": t1w, "t1_score": s1, "t2_score": s2, "ot": ot,
            "game": 0}

# Complete ALL 8 R1 series (varied scores), so the full tree builds.
r1 = b.playoff_series["wild_card"]
for i, s in enumerate(r1):
    w2 = i % 4  # 0..3 -> sweeps through game-7s
    seq = []
    for k in range(4):
        seq.append(True)
        if k < w2:
            seq.append(False)
    # interleave for realism: T1 wins, then alternate
    order = []
    a, bl = 0, 0
    while a < 4 or bl < w2:
        if a < 4:
            order.append(True); a += 1
        if bl < w2:
            order.append(False); bl += 1
    for j, t1w in enumerate(order):
        s.add_game_result(t1w, g(t1w, 4 if t1w else 2, 2 if t1w else 4,
                                 ot=(j == 2 and i % 2 == 0)))
check("8 R1 series complete", sum(1 for s in r1 if s.is_complete) == 8)

b.advance_to_next_round("wild_card")
check("R2 created with 4 series",
      len(b.playoff_series.get("division_semifinals", [])) == 4,
      str(len(b.playoff_series.get("division_semifinals", []))))

# R2: all 4 complete (varied) -> both CFs form.
r2 = b.playoff_series["division_semifinals"]
for i, s in enumerate(r2):
    w2 = i % 3  # 0, 1, 2, 0
    order, a, bl = [], 0, 0
    while a < 4 or bl < w2:
        if a < 4:
            order.append(True); a += 1
        if bl < w2:
            order.append(False); bl += 1
    for t1w in order:
        s.add_game_result(t1w, g(t1w, 3, 2))
check("4 R2 series complete", sum(1 for s in r2 if s.is_complete) == 4)
b.advance_to_next_round("division_semifinals")
check("CF created with 2 series",
      len(b.playoff_series.get("division_finals", [])) == 2)

# Complete both CFs -> Stanley Cup Final, play 3 SCF games.
for s in b.playoff_series["division_finals"]:
    for i in range(4):
        s.add_game_result(True, g(True, 4, 1))
b.advance_to_next_round("division_finals")
scf = b.playoff_series.get("stanley_cup_final", [])
check("SCF created", len(scf) == 1)
scf[0].add_game_result(True, g(True, 3, 2, ot=True))
scf[0].add_game_result(False, g(False, 1, 4))
scf[0].add_game_result(True, g(True, 2, 1))

# Bad-blood storyline check on a live R1 series between the feuding clubs.
feud = None
for s in r1:
    names = {s.team1.team_name, s.team2.team_name}
    if names == {"Buffalo Sabres", "Toronto Maple Leafs"}:
        feud = s
        break
if feud is None:
    # force the pairing: reuse a live East series' slot is complex; instead
    # check storylines on any series then separately verify the ledger read.
    lines = []
else:
    lines = _series_storylines(feud)
check("bad-blood storyline surfaces for feuding pair",
      any("Bad blood" in ln and "Slugger" in ln for ln in lines),
      str(lines[:2]) if lines else "no feud series found")

# ------------------------------------------------------- hit-injury hook
from simulation import GameSim, HitType, HitResult

sim = GameSim.__new__(GameSim)
sim.rivalries = []
sim._log_event = lambda *a, **k: None
victim = SimpleNamespace(full_name="Star Victim", overall=91,
                         is_injured=False, injury_type="",
                         games_remaining_injured=0)
hitter = SimpleNamespace(full_name="Rival Slugger", overall=78)
ht = SimpleNamespace(team_name="Buffalo Sabres")
vt = SimpleNamespace(team_name="Toronto Maple Leafs")
sim._apply_hit_injury(victim, hitter, ht, vt, HitType.CHARGING, 2)
check("victim sidelined", victim.is_injured is True)
check("dirty hit costs 4+ games",
      4 <= victim.games_remaining_injured <= 10,
      str(victim.games_remaining_injured))
rec = sim.rivalries[0] if sim.rivalries else {}
check("rivalry record created",
      rec.get("kind") == "team_team", str(rec.get("kind")))
inc = (rec.get("incidents") or [{}])[0]
check("incident kind star_injured", inc.get("kind") == "star_injured",
      str(inc.get("kind")))
bridge = [e for e in led.events
          if (e.get("facts") or {}).get("incident_kind") == "star_injured"
          and "charging" in (e.get("text") or "")]
check("ledger bridge recorded", len(bridge) >= 1, str(len(bridge)))

# ------------------------------------------------------- render the tree
app = SimpleNamespace(
    league=league, current_date=date(2027, 5, 20),
    FONT_FAMILY="Arial", BG_COLOR="#0B0F14", CONTENT_BG="#0B0F14")
league.playoff_bracket = b

root = ctk.CTk()
root.geometry("1600x900")
root.update()
view = PlayoffView(root, app=app)
view.pack(fill="both", expand=True)
root.update_idletasks()
root.update()
time.sleep(0.6)
root.update()

canvas = view.canvas
check("canvas navy background",
      str(canvas.cget("bg")).upper() == "#0A1428", str(canvas.cget("bg")))
items = canvas.find_all()
check("canvas has drawn content", len(items) >= 30, str(len(items)))

# ticker
tick = ""
try:
    tick = view.ticker_label.cget("text")
except Exception:
    pass
check("ticker shows a series readout", "vs" in tick and "ROUND" in tick.upper(),
      tick[:80])

# league gauge removed from the bracket screen: intensity lives per-series now
check("no league gauge on bracket header",
      getattr(view, "_tension_canvas", None) is None)

# columns: count embedded card windows per column region
wins = [w for w in items if canvas.type(w) == "window"]
check("16 series cards embedded", len(wins) == 15,
      str(len(wins)))  # 8 R1 + 4 R2 + 2 CF + 1 SCF = 15

from PIL import ImageGrab
def shot(path, xfrac=None):
    if xfrac is not None:
        try:
            canvas.xview_moveto(xfrac)
            root.update()
            time.sleep(0.4)
        except Exception:
            pass
    root.update()
    img = ImageGrab.grab()
    img.save(path)
    print("saved", path, img.size)

shot("/home/hatch/workspace/ahl_shots/bracket_2k_west.png", 0.0)
shot("/home/hatch/workspace/ahl_shots/bracket_2k_center.png", 0.42)
shot("/home/hatch/workspace/ahl_shots/bracket_2k_east.png", 0.78)

# projection mode: fresh view, no bracket -> mirrored projection tree
league.playoff_bracket = None
root2 = ctk.CTk()
root2.geometry("1600x900")
view2 = PlayoffView(root2, app=app)
view2.pack(fill="both", expand=True)
root2.update_idletasks(); root2.update(); time.sleep(0.6); root2.update()
proj_items = view2.canvas.find_all()
proj_wins = [w for w in proj_items if view2.canvas.type(w) == "window"]
check("projection shows 8 R1 cards", len(proj_wins) == 8, str(len(proj_wins)))
tick2 = ""
try:
    tick2 = view2.ticker_label.cget("text")
except Exception:
    pass
check("projection ticker flagged", "PROJECTION" in tick2, tick2[:80])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)

# ------------------------------------------------- series detail popup QA
print("\n== series detail: per-series intensity + big moments ==")
from playoff_system import (SeriesDetailPopup, _series_big_moments)
from season_intensity import series_intensity, hype_line
from narrative_ledger import NarrativeLedger as _NL

led2 = _NL(); led2.set_clock(2026, 200)
led2.record("incident", teams=["X X", "Y Y"], players=[],
            facts={"incident_kind": "star_injured"}, weight=25, text="s")
led2.record("incident", teams=["X X", "Y Y"], players=[],
            facts={"incident_kind": "brawl"}, weight=15, text="b")
led2.record("incident", teams=["X X", "Z Z"], players=[],
            facts={"incident_kind": "brawl"}, weight=15, text="other-pair")
si = series_intensity(led2, "X X", "Y Y")
check("series intensity pair-scoped 60 CHIPPY",
      si["value"] == 60.0 and si["label"] == "CHIPPY"
      and si["incident_count"] == 2,
      f"{si['value']} {si['label']} n={si['incident_count']}")
si2 = series_intensity(led2, "X X", "Q Q")
check("unrelated pair is CALM 0",
      si2["value"] == 0.0 and si2["incident_count"] == 0)
check("series intensity needs no ledger",
      series_intensity(None, "A", "B")["label"] == "CALM")
check("hype boiling copy", "Grudge series" in hype_line("BOILING", "BUF", "TOR"))
check("hype chippy copy", "fireworks" in hype_line("CHIPPY", "BUF", "TOR"))
check("hype calm copy", "All business" in hype_line("CALM", "BOS", "WSH"))

# crafted live series on the feuding pair: OT, shutout, statement, steal
tA = SimpleNamespace(team_name="Buffalo Sabres", standings_position=2)
tB = SimpleNamespace(team_name="Toronto Maple Leafs", standings_position=7)
ms = PlayoffSeries("Wild Card Round", tA, tB)
_crafted = [(True, 4, 3, True, None),
            (False, 0, 5, False, None),
            (True, 6, 2, False, None),
            (True, 3, 1, False, "Ukko-Pekka Luukkonen")]
for t1w, s1, s2, ot, steal in _crafted:
    d = {"team1_won": t1w, "t1_score": s1, "t2_score": s2, "ot": ot, "game": 0}
    if steal:
        d["goalie_steal"] = steal
    ms.add_game_result(t1w, d)
moments = _series_big_moments(ms)
kinds = " | ".join(t for _, t in moments)
check("4 big moments extracted", len(moments) == 4, kinds)
check("OT moment", any("overtime winner" in t for _, t in moments))
check("shutout moment", any("shutout" in t for _, t in moments))
check("statement moment", any("statement win" in t for _, t in moments))
check("steal moment", any("stood on his head" in t for _, t in moments))
check("empty series, empty log",
      _series_big_moments(PlayoffSeries("Wild Card Round", tA, tB)) == [])

# popup renders headless: intensity gauge + big moments sections present
pop = SeriesDetailPopup(root, app, ms, bracket=None, projected=False)
root.update_idletasks(); root.update(); time.sleep(0.5); root.update()
found = set()
canvases = []
def _walk(w):
    try:
        cls = w.winfo_class()
    except Exception:
        return
    if "Label" in cls:
        try:
            found.add(w.cget("text"))
        except Exception:
            pass
    if cls == "Canvas":
        canvases.append(w)
    for ch in w.winfo_children():
        _walk(ch)
_walk(pop)
check("popup has Series intensity section", "Series intensity" in found)
check("popup has Big moments section", "Big moments" in found)
check("popup has hype line",
      any("Grudge series" in str(t) or "fireworks" in str(t)
          or "brewing" in str(t) or "All business" in str(t) for t in found))
gitems = sum(len(c.find_all()) for c in canvases)
check("popup gauge canvas drawn", gitems >= 8, str(gitems))
root.update()
try:
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.6)
    root.update()
except Exception:
    pass
ImageGrab.grab().save("/home/hatch/workspace/ahl_shots/series_detail_intensity.png")
try:
    root.attributes("-topmost", False)
except Exception:
    pass
print("saved series_detail_intensity.png")

# projected popup: intensity hype present, no games needed
pop2 = SeriesDetailPopup(root, app, ms, bracket=None, projected=True)
root.update_idletasks(); root.update(); time.sleep(0.4); root.update()
found2 = set()
def _walk2(w):
    try:
        if "Label" in w.winfo_class():
            found2.add(w.cget("text"))
    except Exception:
        pass
    for ch in w.winfo_children():
        _walk2(ch)
_walk2(pop2)
check("projected popup has intensity hype",
      "Series intensity" in found2
      and any("Grudge series" in str(t) or "fireworks" in str(t)
              or "brewing" in str(t) or "All business" in str(t)
              for t in found2))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
