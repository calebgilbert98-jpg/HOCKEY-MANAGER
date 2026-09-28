"""Full SeriesDetailPopup demo: rich fake-but-real-path data, every insight
section rendered, stitched full-height screenshot.

Headless: DISPLAY=:99. Run: python3 /tmp/demo_series_popup.py
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
from PIL import Image, ImageGrab

from playoff_system import (PlayoffBracket, PlayoffView, _playoff_team_line,
                              _top_playoff_scorers, _playoff_goalie_line)
from narrative_ledger import NarrativeLedger, set_active_ledger
from game_classes import PlayerStats

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

FIRST = ["Nathan", "David", "Auston", "Connor", "Sidney", "Alex", "Mikko",
         "Artemi", "Jack", "Kirill"]
LAST = ["MacKinnon", "Pastrnak", "Matthews", "McDavid", "Crosby", "Ovechkin",
        "Rantanen", "Panarin", "Hughes", "Kaprizov"]
GOALIES = ["Swayman", "Shesterkin", "Hellebuyck", "Vasilevskiy", "Oettinger",
           "Saros", "Bobrovsky", "Saros", "Ullmark", "Demko"]

teams, standings = [], {}
for i, (name, conf) in enumerate(NHL32):
    pts = 118 - (i % 16) * 3
    idx = i % 16
    div = ("Atlantic" if idx < 8 else "Metropolitan") if conf == "Eastern" \
        else ("Central" if idx < 8 else "Pacific")
    roster = []
    for j in range(3):
        fn = f"{FIRST[(i + j) % 10]} {LAST[(i * 2 + j) % 10]}"
        p_pts = 20 - ((i + j) % 7)
        roster.append(SimpleNamespace(
            full_name=fn,
            playoff_stats={"points": p_pts, "goals": p_pts // 3,
                           "assists": p_pts - p_pts // 3}))
    gsaves = 300 + (i * 13) % 120
    gshots = gsaves + 28 + (i * 7) % 20
    roster.append(SimpleNamespace(
        full_name=f"{FIRST[(i + 5) % 10]} {GOALIES[i % 10]}",
        playoff_stats={"GP": 12 + (i % 5), "saves": gsaves,
                       "shots_against": gshots,
                       "shutouts": (i % 3), "goals_against": gshots - gsaves}))
    t = SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        conference=conf, division=div,
        roster=roster, wins=pts // 2, losses=20, ot_losses=5, points=pts,
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


def g(t1w, s1=3, s2=2, ot=False, num=0, steal=None):
    d = {"team1_won": t1w, "t1_score": s1, "t2_score": s2, "ot": ot,
         "game": num}
    if steal:
        d["goalie_steal"] = steal
    return d


r1 = b.playoff_series["wild_card"]
for i, s in enumerate(r1):
    w2 = i % 3
    order, a, bl = [], 0, 0
    while a < 4 or bl < w2:
        if a < 4:
            order.append(True); a += 1
        if bl < w2:
            order.append(False); bl += 1
    for n, t1w in enumerate(order, start=1):
        s.add_game_result(t1w, g(t1w, 4 if t1w else 2, 2 if t1w else 4,
                                num=n))
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
    for n, t1w in enumerate(order, start=1):
        s.add_game_result(t1w, g(t1w, 3, 2, num=n))
b.advance_to_next_round("division_semifinals")
for s in b.playoff_series["division_finals"]:
    for n in range(1, 5):
        s.add_game_result(True, g(True, 4, 1, num=n))
b.advance_to_next_round("division_finals")

# SCF live at 2-2, crafted for every big-moment type.
scf = b.playoff_series["stanley_cup_final"][0]
n1, n2 = scf.team1.team_name, scf.team2.team_name
g1w = scf.team1.roster[-1].full_name  # goalie of team1
scf.add_game_result(True, g(True, 3, 2, ot=True, num=1))
scf.add_game_result(True, g(True, 4, 0, num=2,
                            steal=f"{g1w} (38 saves)"))
scf.add_game_result(False, g(False, 1, 6, num=3))
scf.add_game_result(False, g(False, 2, 3, num=4))
check("SCF live at 2-2", not scf.is_complete and scf.team1_wins == 2
      and scf.team2_wins == 2, f"{scf.team1_wins}-{scf.team2_wins}")

# Bad blood + heat between the finalists.
led.record(kind="incident", teams=[n1, n2],
           facts={"incident_kind": "controversial_hit"}, weight=25,
           text="Game 1 boarding major on the star winger still being talked about")
led.record(kind="incident", teams=[n1, n2],
           facts={"incident_kind": "brawl"}, weight=30,
           text="Game 3 line brawl after the late hit")

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

view._open_series_detail(scf, projected=False)
root.update_idletasks(); root.update(); time.sleep(1.0); root.update()
mgr = getattr(root, "popup_manager", None)
entry = mgr._stack[-1] if mgr and getattr(mgr, "_stack", None) else None
pop = entry["popup"] if entry else None
check("popup opened", pop is not None)
if pop is None:
    raise SystemExit(1)


def all_texts(w):
    out = []
    try:
        for ch in w.winfo_children():
            try:
                t = ch.cget("text")
                if isinstance(t, str) and t.strip():
                    out.append(t)
            except Exception:
                pass
            out.extend(all_texts(ch))
    except Exception:
        pass
    return out


texts = all_texts(pop)
blob = "\n".join(texts)

# --- every insight section present ---
for sec in ["Series intensity", "Tale of the tape (playoffs to date)",
            "Game by game", "Series splits", "Storylines", "Big moments",
            "Players to watch", "Road ahead"]:
    check(f"section present: {sec}", sec in blob)

# --- tape content: real numbers ---
L1 = _playoff_team_line(b, scf.team1)
L2 = _playoff_team_line(b, scf.team2)
check("tape record row (team1)", f"{L1['w']}-{L1['l']}" in blob,
      f"{L1['w']}-{L1['l']}")
check("tape record row (team2)", f"{L2['w']}-{L2['l']}" in blob,
      f"{L2['w']}-{L2['l']}")
gl1 = scf.team1.roster[-1]
sv = gl1.playoff_stats["saves"] / gl1.playoff_stats["shots_against"]
check("tape goalie SV%", f"{sv:.3f}".replace("0.", ".") in blob,
      f"{sv:.3f}")
check("tape goalie shutouts", f"({gl1.playoff_stats['shutouts']} SO)" in blob)
top1 = max(scf.team1.roster[:3],
           key=lambda p: p.playoff_stats["points"])
check("tape top scorer",
      top1.full_name.split()[-1] in blob
      and f"{top1.playoff_stats['points']} pts" in blob,
      top1.full_name)

# --- big moments: all four kinds fire ---
for frag in ["overtime winner", "shutout", "stood on his head",
             "statement win"]:
    check(f"big moment: {frag}", frag in blob)

# --- bad blood + hype ---
check("bad-blood storyline", "Bad blood" in blob)
check("BOILING hype line", "Grudge series" in blob)

# --- players to watch rows ---
check("players to watch rows",
      sum(1 for t in texts if " pts (" in t) >= 2,
      f"{sum(1 for t in texts if ' pts (' in t)} rows")

# --- stitched full-height screenshot ---
def find_scroll(w):
    try:
        for ch in w.winfo_children():
            if "CTkScrollableFrame" in ch.__class__.__name__:
                return ch
            r = find_scroll(ch)
            if r is not None:
                return r
    except Exception:
        pass
    return None


body = find_scroll(pop)
ok = body is not None
check("scrollable body found", ok)
if ok:
    cv = body._parent_canvas
    root.update_idletasks(); root.update()
    sr = cv.bbox("all") or (0, 0, 0, 1)
    total = max(1, sr[3])
    vis = max(1, cv.winfo_height())
    bx, by, bw = body.winfo_rootx(), body.winfo_rooty(), body.winfo_width()
    tops, seen = [], set()
    n_steps = max(1, int((total - vis) / (vis * 0.85)) + 2)
    for i in range(n_steps + 1):
        frac = min(1.0, i / max(1, n_steps))
        tops.append(frac * max(0, total - vis))
    shots = []
    for top in tops:
        cv.yview_moveto(top / max(1, total))
        root.update(); time.sleep(0.2); root.update()
        actual = cv.canvasy(0)
        key = int(round(actual))
        if key in seen:
            continue
        seen.add(key)
        full = ImageGrab.grab()
        crop = full.crop((bx, by, bx + bw, by + vis))
        shots.append((actual, crop))
    stitched = Image.new("RGB", (bw, total), "#14161b")
    for actual, crop in sorted(shots):
        stitched.paste(crop, (0, int(round(actual))))
    hx, hy = pop.winfo_rootx(), pop.winfo_rooty()
    header_h = max(0, by - hy)
    hdr = ImageGrab.grab().crop((hx, hy, hx + pop.winfo_width(), by))
    W = max(bw, pop.winfo_width())
    final = Image.new("RGB", (W, header_h + total), "#14161b")
    final.paste(hdr, (0, 0))
    final.paste(stitched, (0, header_h))
    out = "/home/hatch/workspace/ahl_shots/series_popup_full.png"
    final.save(out)
    print(f"saved {out} ({W}x{header_h + total})")
    check("stitched screenshot saved", True, f"{W}x{header_h + total}")

# --- PlayerStats dataclass shape (his Playoff/RS split): the tape helpers
# must read attribute-style ledgers, not just dict fixtures ---
_dc_roster = []
for _fn, _g, _a in [("Auston Matthews", 8, 6), ("Mitch Marner", 4, 11)]:
    _ps = PlayerStats()
    _ps.goals, _ps.assists, _ps.games_played = _g, _a, 14
    _dc_roster.append(SimpleNamespace(full_name=_fn, playoff_stats=_ps))
_gps = PlayerStats()
_gps.saves, _gps.shots_against, _gps.shutouts = 412, 440, 2
_gps.games_played, _gps.wins = 14, 10
_dc_roster.append(SimpleNamespace(full_name="Joseph Woll",
                                  playoff_stats=_gps))
_dc_team = SimpleNamespace(team_name="Dataclass Club", roster=_dc_roster)
_dc_top = _top_playoff_scorers(_dc_team)
check("dataclass top scorer", len(_dc_top) == 2
      and _dc_top[0][1] == "Mitch Marner" and _dc_top[0][0] == 15,
      str([r[1] for r in _dc_top]))
_dc_goalie = _playoff_goalie_line(_dc_team)
check("dataclass goalie line", _dc_goalie is not None
      and _dc_goalie[0] == "Woll" and abs(_dc_goalie[1] - 412 / 440) < 1e-9
      and _dc_goalie[2] == 2, str(_dc_goalie))

try:
    pop.close()
except Exception:
    pass

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
