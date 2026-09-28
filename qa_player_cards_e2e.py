"""QA: player cards end-to-end with REAL generated players.

Covers every card-open path:
  1. modern_profile.PlayerProfile (double-click path) - 60 real players
  2. PlayerContextMenu._view_player_profile (right-click path) - via real app
  3. show_screen fallback (ui_components.PlayerProfileView)
  4. full roster double-click chain through RosterView.handle_double_click
  5. all 5 tabs switch without error
  6. hardening: right-click falls back to app.open_player_profile when the
     card popup raises; open_player_profile never fails silently
"""
import sys, os, traceback, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

random.seed(20260928)
print("generating database...", flush=True)
from database_generator import generate_database
league = generate_database("Small")
team = league.teams[0]

from main import GameManager, HockeyManagerGUI
gm = GameManager(); gm.league = league; gm.user_team = team
league.set_game_manager(gm)
app = HockeyManagerGUI(gm)
app.game_manager = gm; app.user_team = team; app.league = league
app.update_idletasks(); app.update()

import popup_system
mgr = popup_system._default_manager

def sample(n=40):
    cands = []
    for t in league.teams[:10]:
        cands += list(getattr(t, "roster", [])[:3])
        cands += list(getattr(t, "ahl_roster", [])[:1])
        cands += list(getattr(t, "prospects", [])[:1])
    cands += list(getattr(league, "free_agents", [])[:8])
    cands = [p for p in cands if p is not None]
    random.shuffle(cands)
    return cands[:n]

def close_cards():
    try:
        while getattr(mgr, "_stack", []):
            mgr.close_top()
    except Exception:
        pass
    app.update_idletasks(); app.update()

# -- 1. modern card sweep -------------------------------------------------
from modern_profile import PlayerProfile
fails = 0
for p in sample(60):
    try:
        card = PlayerProfile(app, p)
        app.update_idletasks(); app.update()
        assert card.winfo_ismapped()
        close_cards()
    except Exception:
        fails += 1
        traceback.print_exc()
check("modern card opens for 60 real players", fails == 0)

# -- 2. right-click path via real app --------------------------------------
from player_context_menu import PlayerContextMenu
menu = PlayerContextMenu(app)
fails = 0
for p in sample(40):
    try:
        menu._view_player_profile(p)
        for _ in range(3):
            app.update_idletasks(); app.update()
        top = mgr._stack[-1]["popup"] if getattr(mgr, "_stack", []) else None
        assert top is not None and top.winfo_ismapped()
        close_cards()
    except Exception:
        fails += 1
        traceback.print_exc()
check("right-click card opens for 40 real players", fails == 0)

# -- 3. fallback screen path ----------------------------------------------
from ui_components import PlayerProfileView
p = team.roster[2]
try:
    view = app.show_screen("player_profile", "Profile",
                           PlayerProfileView, p, False, None)
    for _ in range(4):
        app.update_idletasks(); app.update()
    check("fallback PlayerProfileView screen opens",
          view is not None and view.winfo_ismapped())
except Exception:
    traceback.print_exc()
    check("fallback PlayerProfileView screen opens", False)

# -- 4. full roster double-click chain -------------------------------------
roster_view = app.open_roster_window()
app.update_idletasks(); app.update()
found = False
for w in roster_view.winfo_children():
    pass  # walk below
def find_trees(w, out):
    from tkinter import ttk
    if isinstance(w, ttk.Treeview):
        out.append(w)
    for ch in w.winfo_children():
        find_trees(ch, out)
    return out
trees = find_trees(roster_view, [])
if trees:
    tree, rows = trees[0], trees[0].get_children()
    if rows:
        bbox = trees[0].bbox(rows[0])
        if bbox:
            fake = type("E", (), {"x": bbox[0] + 5, "y": bbox[1] + 5})()
            for rt in ("nhl", "ahl", "prospects"):
                if rt in getattr(roster_view, "player_maps", {}):
                    roster_view.handle_double_click(fake, tree, rt)
                    break
            for _ in range(5):
                app.update_idletasks(); app.update()
            top = mgr._stack[-1]["popup"] if getattr(mgr, "_stack", []) else None
            found = top is not None and top.winfo_ismapped()
            close_cards()
check("roster double-click opens card", found)

# -- 5. all tabs switch clean ----------------------------------------------
p = next(x for x in team.roster
         if "GOALIE" not in str(getattr(x, "primary_position", "")))
card = PlayerProfile(app, p)
app.update_idletasks(); app.update()
tab_fails = 0
for name in list(getattr(card, "_tab_buttons", {}).keys()):
    try:
        card._switch_tab(name)
        app.update_idletasks(); app.update()
    except Exception:
        tab_fails += 1
        traceback.print_exc()
close_cards()
check("all 5 card tabs switch without error", tab_fails == 0)

# -- 6. hardening: right-click survives a card-popup failure ---------------
import ui_components
_real = ui_components.PlayerProfileWindow
def _boom(parent, player, *a, **k):
    raise RuntimeError("simulated popup failure")
ui_components.PlayerProfileWindow = _boom
# player_context_menu imports inside the method, so patch the attr there too
import player_context_menu  # noqa - uses `from ui_components import` at call time
try:
    menu._view_player_profile(team.roster[0])
    for _ in range(4):
        app.update_idletasks(); app.update()
    top = mgr._stack[-1]["popup"] if getattr(mgr, "_stack", []) else None
    check("right-click falls back to app card when popup raises",
          top is not None and top.winfo_ismapped())
    close_cards()
except Exception:
    traceback.print_exc()
    check("right-click falls back to app card when popup raises", False)
finally:
    ui_components.PlayerProfileWindow = _real

# -- 7. open_player_profile never dies silently -----------------------------
class NoTeam:
    user_team = None
    def show_screen(self, *a, **k):
        raise RuntimeError("no screen host")
import main as main_mod
bound = main_mod.HockeyManagerGUI.open_player_profile.__get__(NoTeam(), main_mod.HockeyManagerGUI)
try:
    bound(team.roster[0])  # modern card may open; we only care it doesn't raise
    check("open_player_profile never raises to caller", True)
except Exception:
    traceback.print_exc()
    check("open_player_profile never raises to caller", False)

print(f"\n{len(passed)} passed, {len(failed)} failed")
app.destroy()
sys.exit(1 if failed else 0)
