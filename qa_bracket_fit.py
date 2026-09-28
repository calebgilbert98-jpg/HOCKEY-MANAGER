"""QA: bracket zoom-to-fit + popup card bg + winner contrast.

Builds a real 32-team league, plays the full tree to a live SCF, and
verifies:
  1. _bracket_scale() < 1 at 1600px wide (tree shrinks to fit).
  2. No horizontal overflow: canvas bbox fits the canvas width.
  3. All 15 series cards drawn (8 R1 + 4 R2 + 2 CF + 1 SCF).
  4. Winner text readable on light accents (BOS gold -> black text).
  5. SeriesDetailPopup frame bg matches the dark card (#14161b).
  6. Click journey: card click -> ticker updates + popup card opens.
  7. Resize to 1920: debounced refit grows the scale, still no overflow.

Screenshots -> ~/workspace/ahl_shots/bracket_fit_*.png
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
import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
import popup_system as _ps
try:
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

import customtkinter as ctk
import ctk_theme as _ct
_ct.init_ctk_theme()
from PIL import ImageGrab

from playoff_system import PlayoffBracket, PlayoffView
from narrative_ledger import NarrativeLedger, set_active_ledger

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name +
          (f" [{extra}]" if extra else ""))

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
    div = ("Atlantic" if idx < 8 else "Metropolitan") if conf == "Eastern" \
        else ("Central" if idx < 8 else "Pacific")
    t = SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        conference=conf, division=div,
        roster=[], wins=pts // 2, losses=20, ot_losses=5, points=pts,
        goals_for=280, goals_against=240, standings_position=(i % 16) + 1)
    teams.append(t)
    standings[name] = {"Points": pts, "W": pts // 2}

league = SimpleNamespace(teams=teams, standings=standings, season_year=2026,
                         rivalries=[], playoff_bracket=None)
led = NarrativeLedger()
led.set_clock(2026, 200)
set_active_ledger(led)

b = PlayoffBracket(league)
b.generate_playoff_bracket()

def g(t1w, s1=3, s2=2, ot=False):
    return {"team1_won": t1w, "t1_score": s1, "t2_score": s2, "ot": ot, "game": 0}

r1 = b.playoff_series["wild_card"]
for i, s in enumerate(r1):
    w2 = i % 3
    order, a, bl = [], 0, 0
    while a < 4 or bl < w2:
        if a < 4:
            order.append(True); a += 1
        if bl < w2:
            order.append(False); bl += 1
    for t1w in order:
        s.add_game_result(t1w, g(t1w, 4 if t1w else 2, 2 if t1w else 4))
b.advance_to_next_round("wild_card")
r2 = b.playoff_series["division_semifinals"]
for i, s in enumerate(r2):
    w2 = i % 2
    order, a, bl = [], 0, 0
    while a < 4 or bl < w2:
        if a < 4:
            order.append(True); a += 1
        if bl < w2:
            order.append(False); bl += 1
    for t1w in order:
        s.add_game_result(t1w, g(t1w, 3, 2))
b.advance_to_next_round("division_semifinals")
for s in b.playoff_series["division_finals"]:
    for _ in range(4):
        s.add_game_result(True, g(True, 4, 1))
b.advance_to_next_round("division_finals")
scf = b.playoff_series["stanley_cup_final"][0]
scf.add_game_result(True, g(True, 3, 2, ot=True))
scf.add_game_result(False, g(False, 1, 4))
check("full tree built, SCF live at 1-1",
      len(r1) == 8 and len(r2) == 4 and not scf.is_complete)

league.playoff_bracket = b
app = SimpleNamespace(league=league, current_date=date(2027, 6, 4),
                      FONT_FAMILY="Arial", BG_COLOR="#0B0F14",
                      CONTENT_BG="#0A1428")

root = ctk.CTk()
root.geometry("1600x900")
_ps.register(root)
view = PlayoffView(root, app=app)
view.pack(fill="both", expand=True)
root.update_idletasks(); root.update(); time.sleep(0.8); root.update()

# --- 1: scale shrinks at 1600 ---
s1600 = view._bracket_scale()
check("scale < 1.0 at 1600px (tree shrinks to fit)",
      0.45 <= s1600 < 1.0, f"{s1600:.3f}")

# --- 2: no horizontal overflow ---
canvas = view.canvas
root.update_idletasks(); root.update()
bbox = canvas.bbox("all")
cw = canvas.winfo_width()
check("bracket bbox fits canvas width (no h-scroll)",
      bbox is not None and bbox[2] <= cw + 2, f"bbox_w={bbox[2] if bbox else None} canvas_w={cw}")

# --- 3: all 15 series cards drawn ---
nwins = sum(1 for it in canvas.find_all() if canvas.type(it) == "window")
check("15 series cards on canvas", nwins == 15, str(nwins))

# --- 3b: no dead space: cards hug their two rows ---
_sc = view._bracket_scale()
_row_h = max(26, int(40 * _sc))
_tight, _worst = True, 0
for _it in canvas.find_all():
    if canvas.type(_it) == "window":
        try:
            _w = canvas.nametowidget(canvas.itemcget(_it, "window"))
            _rh = int(_w.winfo_reqheight())
        except Exception:
            continue
        _worst = max(_worst, _rh)
        if _rh > 2 * _row_h + 30:
            _tight = False
check("cards hug content (no dead space)", _tight,
      f"worst_h={_worst} budget={2 * _row_h + 30}")

# --- 4: winner contrast on light accents ---
check("BOS gold accent -> black winner text",
      PlayoffView._winner_text_color("#FFB81C", "#000000") == "#000000")
check("PIT gold accent -> black winner text",
      PlayoffView._winner_text_color("#FCB514", "#000000") == "#000000")
check("LA silver accent -> black winner text",
      PlayoffView._winner_text_color("#A2AAAD", "#000000") == "#000000")
check("TOR navy accent -> gold winner text",
      PlayoffView._winner_text_color("#003E7E", "#FFFFFF") == "#C9A227")

ImageGrab.grab().save("/home/hatch/workspace/ahl_shots/bracket_fit_1600.png")
print("saved bracket_fit_1600.png")

# --- 5+6: click journey + dark popup card ---
view._open_series_detail(scf, projected=False)
root.update_idletasks(); root.update(); time.sleep(1.0); root.update()
pop = None
for w in root.winfo_children():
    pass
# find the popup via the manager stack
mgr = getattr(root, "popup_manager", None)
entry = mgr._stack[-1] if mgr and getattr(mgr, "_stack", None) else None
pop = entry["popup"] if entry else None
check("click opens a real popup card", pop is not None)
if pop is not None:
    bg = str(pop.cget("bg")).lower()
    check("popup frame bg matches dark card", bg == "#14161b", bg)
ticker = view.ticker_label.cget("text") if view.ticker_label else ""
check("ticker follows clicked series", "Stanley Cup Final" in ticker or "FINAL" in ticker.upper(), ticker[:60])
ImageGrab.grab().save("/home/hatch/workspace/ahl_shots/bracket_fit_popup.png")
print("saved bracket_fit_popup.png")
try:
    if pop is not None:
        pop.close()
except Exception:
    pass
root.update(); time.sleep(0.3)

# --- 7: resize to 1920 -> debounced refit, scale grows, still fits ---
root.geometry("1920x1080")
root.update_idletasks(); root.update(); time.sleep(1.2); root.update()
s1920 = view._bracket_scale()
check("scale grows at 1920px", s1920 > s1600, f"{s1600:.3f} -> {s1920:.3f}")
bbox2 = canvas.bbox("all")
cw2 = canvas.winfo_width()
check("still no h-overflow at 1920",
      bbox2 is not None and bbox2[2] <= cw2 + 2, f"bbox_w={bbox2[2] if bbox2 else None} canvas_w={cw2}")
ImageGrab.grab().save("/home/hatch/workspace/ahl_shots/bracket_fit_1920.png")
print("saved bracket_fit_1920.png")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
