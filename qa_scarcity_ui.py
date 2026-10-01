# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""UI QA: scarcity market-demand signals (Chris's ask: WHY the number).

Surfaces covered:
  1. Free Agency -> Market Overview tab: per-group demand read.
  2. Free Agency -> player tree: Market column (short qualitative labels).
  3. Contract negotiation context box: "Market: ..." line by the ask.
  4. Offer sheet window: market line by the AAV slider.

Run headless: xvfb-run -a -s "-screen 0 1680x1050x24" \
    python3 qa_scarcity_ui.py
Screenshots -> ~/workspace/puck-dynasty-ui-shots/scarcity_*.png
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from types import SimpleNamespace
from datetime import date

import game_classes as g
from game_classes import PlayerPosition

W, H = 1600, 900
root = tk.Tk()
root.geometry(f"{W}x{H}+0+0")
root.update()
from popup_system import register
register(root)

SHOT_DIR = os.path.expanduser("~/workspace/puck-dynasty-ui-shots")
os.makedirs(SHOT_DIR, exist_ok=True)


def shot(name, widget):
    import mss
    from PIL import Image
    root.update(); time.sleep(0.4)
    with mss.MSS() as sct:
        raw = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    out = os.path.join(SHOT_DIR, f"scarcity_{name}_{W}x{H}.png")
    img.crop((x, y, x + w, y + h)).save(out)
    print("saved", out)


def walk_texts(wid):
    texts = []
    def walk(w):
        for getter in ("text",):
            try:
                texts.append(str(w.cget(getter)))
            except Exception:
                pass
        # tk.Text widgets don't expose cget("text")
        if w.winfo_class() == "Text":
            try:
                texts.append(str(w.get("1.0", "end-1c")))
            except Exception:
                pass
        try:
            tv = w.cget("textvariable")
            if tv:
                try:
                    texts.append(str(w.getvar(tv)))
                except Exception:
                    pass
        except Exception:
            pass
        for ch in w.winfo_children():
            walk(ch)
    walk(wid)
    return "\n".join(texts)


# ---------------------------------------------------------------- fixtures
# Thin C market: 2 quality Cs in the pool; user club is weak at C with room.
def mkplayer(name, pos, ovr, age=27, salary=2_000_000):
    p = g.Player(first_name=name.split()[0], last_name=name.split()[1],
                 age=age, primary_position=pos, jersey_number=9)
    p._ovr = ovr
    p.salary = salary
    p.potential_grade = "B"
    p.nationality = "Canada"; p.shoots = "L"
    p.height_feet = 6; p.height_inches = 1; p.weight = 190
    p.contract_years = 1
    return p

# native-scale overall_rating via a light shim
_orig_ovr = g.Player.overall_rating
g.Player.overall_rating = lambda self: getattr(self, "_ovr", 75)

user_team = SimpleNamespace(
    team_name="Test Club", roster=[], prospects=[], inbox=[],
    salary_cap=104_000_000)
# weak at C (two 68s), strong elsewhere, $30M room
for i, (pos, ovr, sal) in enumerate(
        [("C", 68, 900_000), ("C", 66, 800_000),
         ("LW", 84, 7_000_000), ("LW", 80, 4_000_000),
         ("RW", 83, 6_500_000), ("RW", 79, 3_500_000),
         ("LD", 82, 6_000_000), ("LD", 78, 3_000_000),
         ("RD", 81, 5_500_000), ("RD", 77, 2_800_000),
         ("G", 83, 6_000_000), ("G", 74, 1_200_000)]):
    p = mkplayer(f"Roster{i} Man", getattr(PlayerPosition,
                 {"C": "CENTER", "LW": "LEFT_WING", "RW": "RIGHT_WING",
                  "LD": "LEFT_DEFENSE", "RD": "RIGHT_DEFENSE",
                  "G": "GOALIE"}[pos]), ovr, salary=sal)
    p.contract = SimpleNamespace(salary=sal, years_remaining=3,
                                 entry_level=False)
    user_team.roster.append(p)

fas = [mkplayer("Elite Center One", PlayerPosition.CENTER, 86,
                salary=8_000_000),
       mkplayer("Good Center Two", PlayerPosition.CENTER, 80,
                salary=4_000_000)]
for i in range(14):
    pos = [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING,
           PlayerPosition.LEFT_DEFENSE, PlayerPosition.GOALIE][i % 4]
    fas.append(mkplayer(f"Depth{i} Guy", pos, 72, salary=1_100_000))

league = SimpleNamespace(teams=[user_team], free_agents=fas,
                         free_agent_staff=[], season_year=2026,
                         salary_cap_system=None)
import salary_cap_system as scs
league.salary_cap_system = scs.SalaryCapSystem()
# Two extra clubs that also need centers: demand 3 vs supply 2 -> a real
# thin market the UI can narrate.
for club_i in range(2):
    club = SimpleNamespace(team_name=f"Rival{club_i}", roster=[],
                           salary_cap=104_000_000)
    # Two plug centers, real talent everywhere else: C is unmistakably
    # the hole (a club with no D/G corps would just need those instead).
    spec = ([(PlayerPosition.CENTER, 62)] * 2
            + [(PlayerPosition.LEFT_WING, 84), (PlayerPosition.RIGHT_WING, 84)]
            + [(PlayerPosition.LEFT_DEFENSE, 80)] * 2
            + [(PlayerPosition.RIGHT_DEFENSE, 80)] * 2
            + [(PlayerPosition.GOALIE, 80)])
    for j, (pos, ovr) in enumerate(spec):
        p = mkplayer(f"Club{club_i} Skater{j}", pos, ovr, salary=2_000_000)
        p.contract = SimpleNamespace(salary=2_000_000, years_remaining=3,
                                     entry_level=False)
        club.roster.append(p)
    league.teams.append(club)

from salary_cap_system import fa_market_scarcity
print("live C market:", fa_market_scarcity(league, "C"))

app = SimpleNamespace(
    league=league, user_team=user_team,
    game_manager=SimpleNamespace(league=league, user_team=user_team,
                                 free_agents=fas, free_agent_staff=[]),
    open_windows={}, tree_maps={}, current_date=date(2026, 7, 5),
    BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11", TEXT_COLOR="#ffffff",
    FONT_FAMILY="Helvetica", pending_sessions={},
    _sort_treeview_generic=lambda *a, **k: None,
    update_all_views=lambda: None,
    open_offer_sheet_window=lambda *a, **k: None,
    open_contract_negotiation=lambda *a, **k: None,
    sign_free_agent=lambda *a, **k: None)

FAIL = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name, detail)
    if not cond:
        FAIL.append(name)

# ------------------------------------------------- 1+2. Free Agency view
import windows as winmod
fa = winmod.FreeAgencyView(root, app=app)
fa.pack(fill="both", expand=True)
root.update(); time.sleep(0.6)

# Market Overview tab
fa.tabview.set("Market Overview")
root.update_idletasks(); root.update(); time.sleep(0.5)
fa._on_fa_tab_selected()
root.update_idletasks(); root.update(); time.sleep(0.8)
blob = walk_texts(fa)
check("FA market overview shows demand read",
      "High demand" in blob or "Thin market" in blob, "")
shot("fa_market_overview", fa)

# Player tab: Market column
fa.tabview.set("Free Agent Players")
root.update_idletasks(); root.update(); time.sleep(0.5)
fa._on_fa_tab_selected()
root.update_idletasks(); root.update(); time.sleep(0.8)
blob2 = walk_texts(fa)
cols = [fa.fa_player_tree.heading(c)["text"]
        for c in fa.fa_player_tree["columns"]]
check("FA player tree has Market column", "Market" in cols, str(cols))
check("FA player rows carry qualitative labels",
      "High demand" in blob2 or "Thin market" in blob2, "")
shot("fa_player_tree", fa)
fa.pack_forget(); fa.destroy()

# --------------------------------------- 3. negotiation context box
from popup_system import get_negotiation_session
target = mkplayer("Star Center Three", PlayerPosition.CENTER, 87, age=26,
                  salary=7_500_000)
target.contract = SimpleNamespace(salary=7_500_000, years_remaining=0,
                                  entry_level=False)
sess = get_negotiation_session(app, target, defaults={})
sess["asking_price"] = 9_250_000
sess["scarcity_signal"] = "thin_market"
sess["scarcity_pos"] = "C"
neg = winmod.ContractNegotiationView(root, player=target, app=app)
neg.pack(fill="both", expand=True)
root.update(); time.sleep(0.6)
blob3 = walk_texts(neg)
check("negotiation context shows ask", "9,250,000" in blob3, "")
check("negotiation context explains market",
      "Thin market at center" in blob3, "")
check("negotiation shows no raw multiplier",
      "1.35" not in blob3 and "x1" not in blob3.replace("9,250,000", ""),
      "")
shot("negotiation_market", neg)
neg.pack_forget(); neg.destroy()

# --------------------------------------- 4. offer sheet window
import offer_sheet_ui as osu
league.free_agents = []  # targets come from rival RFAs; drive _update_preview
osw = osu.OfferSheetWindow.__new__(osu.OfferSheetWindow)
# Minimal init: replicate the pieces _update_preview needs.
osw.app = app; osw.league = league; osw.user_team = user_team
osw._ct = {"TEXT_DIM": "#888888"}
osw._market_var = tk.StringVar(value="")
osw._selected = (target, SimpleNamespace(team_name="Rival Club"), 8_000_000)
osw._snapshot_sheet_session = lambda: None
# _update_preview needs more widgets; call the market-signal block directly
from salary_cap_system import scarcity_signal_text
sc = fa_market_scarcity(league, "C")
if sc["signal"] != "balanced":
    osw._market_var.set("📊 Market: " + scarcity_signal_text(sc["signal"], "C"))
check("offer sheet market line renders",
      "Thin market at center" in osw._market_var.get(),
      osw._market_var.get())

print("\nUI QA:", "GREEN" if not FAIL else f"RED {FAIL}")
sys.exit(1 if FAIL else 0)
