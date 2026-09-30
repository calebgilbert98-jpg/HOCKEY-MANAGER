# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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

def profile_screen_open():
    """The card is a screen in the main instance, not a popup."""
    cur = getattr(app, "_current_screen", None) or {}
    view = cur.get("view")
    return (cur.get("id") == "player_profile" and view is not None
            and view.winfo_exists() and bool(view.winfo_ismapped()))

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
        assert profile_screen_open(), "profile screen did not open"
        app.show_dashboard()
        for _ in range(2):
            app.update_idletasks(); app.update()
        close_cards()
    except Exception:
        fails += 1
        traceback.print_exc()
check("right-click opens profile as a main-instance screen (40 players)", fails == 0)

# -- 2b. opening a second player's profile replaces the first --------------
p1, p2 = team.roster[0], team.roster[1]
app.open_player_profile(p1)
for _ in range(3):
    app.update_idletasks(); app.update()
app.open_player_profile(p2)
for _ in range(3):
    app.update_idletasks(); app.update()
cur = getattr(app, "_current_screen", None) or {}
check("second profile replaces the first (no stale player)",
      profile_screen_open() and getattr(cur.get("view"), "player", None) is p2)
try:
    app.show_dashboard()
except Exception:
    pass
for _ in range(2):
    app.update_idletasks(); app.update()

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
            found = profile_screen_open()
            try:
                app.show_dashboard()
            except Exception:
                pass
            close_cards()
check("roster double-click opens card as a screen", found)

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

# -- 6. hardening: right-click survives a screen failure ---------------------
# Screen-first now: if show_screen raises, the modern popup card is the
# fallback and the click still produces a visible card.
_real_show_screen = app.show_screen
def _boom_screen(*a, **k):
    raise RuntimeError("simulated screen failure")
app.show_screen = _boom_screen
try:
    menu._view_player_profile(team.roster[0])
    for _ in range(4):
        app.update_idletasks(); app.update()
    top = mgr._stack[-1]["popup"] if getattr(mgr, "_stack", []) else None
    check("right-click falls back to popup card when screen raises",
          top is not None and top.winfo_ismapped())
    close_cards()
except Exception:
    traceback.print_exc()
    check("right-click falls back to popup card when screen raises", False)
finally:
    app.show_screen = _real_show_screen

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

# -- 8. personality screen tab ---------------------------------------------
# Talent traits stay on Attributes; personality traits, personal details,
# reputation and the social circle live on the new Personality tab.
p2 = next(x for x in team.roster
          if "GOALIE" not in str(getattr(x, "primary_position", "")))
p2.traits = ["sniper", "clutch"]  # offense talent + mental personality
view = app.open_player_profile(p2)
for _ in range(6):
    app.update_idletasks(); app.update()
tabs = [view.notebook.tab(i, "text")
        for i in range(view.notebook.index("end"))]
check("personality tab exists right after attributes",
      "Personality" in tabs
      and tabs.index("Personality") == tabs.index("Attributes") + 1)

def _tab_texts(idx):
    view.notebook.select(idx)
    for _ in range(4):
        app.update_idletasks(); app.update()
    tab = view.notebook.nametowidget(view.notebook.select())
    out, stack = [], [tab]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass
        try:
            t = str(w.cget("text") or "").strip()
        except Exception:
            t = ""
        if t:
            out.append(t)
    return out

attr_texts = _tab_texts(tabs.index("Attributes"))
pers_texts = _tab_texts(tabs.index("Personality"))
ov_texts = _tab_texts(tabs.index("Overview"))
check("talent traits stay on attributes tab",
      "Talent Traits" in attr_texts and "Sniper" in attr_texts
      and "Clutch" not in attr_texts)
check("personality traits move to personality tab",
      "Personality Traits" in pers_texts and "Clutch" in pers_texts
      and "Sniper" not in pers_texts)
check("personal details live on personality tab, not overview",
      "Personal Details" in pers_texts
      and "Personal Details" not in ov_texts
      and "Personal Information" not in ov_texts)
check("reputation section moved to personality tab",
      "Reputation & Personality" in pers_texts
      and "Reputation & Personality" not in attr_texts)
check("close allies sections render",
      all(s in pers_texts for s in ("Close Allies", "Family",
                                    "Best Friends in the League",
                                    "Favourite Teammate",
                                    "Favourite Staff", "Rivals")))

# Family links dealt at generation are mutual and resolvable.
by_id = {}
for t in league.teams:
    for pl in t.roster:
        by_id[pl.id] = pl
for pl in league.free_agents:
    by_id[pl.id] = pl
for pl in getattr(league, "draft_prospects", []) or []:
    by_id[pl.id] = pl
fam_ok = True
for t in league.teams:
    for pl in t.roster:
        for fid in getattr(pl, "family_ids", []) or []:
            fp = by_id.get(fid)
            if fp is None or pl.id not in (getattr(fp, "family_ids", []) or []):
                fam_ok = False
check("generated family links are mutual", fam_ok)
d = view._allies_data()
check("allies data resolves without error",
      isinstance(d, dict)
      and all(k in d for k in ("family", "friends", "teammate",
                               "staff", "rivals")))

# -- 9. statistics tab shows real per-player advanced analytics -----------
# (department lens, honest ±CI on modeled metrics; no placeholders)
_stats_texts = _tab_texts(tabs.index("Statistics"))
check("stats tab has advanced analytics header",
      "Advanced Analytics" in _stats_texts)
check("stats tab shows department as-of line",
      any("models as of" in t for t in _stats_texts))
check("skater advanced metrics are real, not placeholders",
      "Offense — Finishing & Creation" in _stats_texts
      and "Possession — Driving Play" in _stats_texts
      and "Defense & Luck" in _stats_texts
      and "Corsi %" in _stats_texts
      and "50.0%" not in _stats_texts
      and "Individual xG" in _stats_texts
      and "Game Score" in _stats_texts)
check("modeled metrics carry the department confidence interval",
      any("±" in t for t in _stats_texts))
check("estimates-not-tracking disclaimer present",
      any("Estimates, not tracking data" in t for t in _stats_texts))

# Goalie card: GSAx / GSAA / HDSV% / QS% through the same lens.
pg = next(x for x in team.roster
          if "GOALIE" in str(getattr(x, "primary_position", "")))
view_g = app.open_player_profile(pg)
for _ in range(6):
    app.update_idletasks(); app.update()
tabs_g = [view_g.notebook.tab(i, "text")
          for i in range(view_g.notebook.index("end"))]
view_g.notebook.select(tabs_g.index("Statistics"))
for _ in range(4):
    app.update_idletasks(); app.update()
gtab = view_g.notebook.nametowidget(view_g.notebook.select())
g_texts, stack = [], [gtab]
while stack:
    w = stack.pop()
    try:
        stack.extend(w.winfo_children())
    except Exception:
        pass
    try:
        t = str(w.cget("text") or "").strip()
    except Exception:
        t = ""
    if t:
        g_texts.append(t)
check("goalie advanced metrics are real, not placeholders",
      "Goaltending — Above Expected" in g_texts
      and "GSAx" in g_texts and "GSAA" in g_texts
      and "High-danger SV%" in g_texts
      and "Quality-start %" in g_texts
      and "Medium Danger SV%" not in g_texts
      and "Even Strength SV%" not in g_texts)

# -- 10. family links resolve for free agents and draft prospects -------
import game_classes as _gc
from game_classes import PlayerPosition as _PP
fa1 = _gc.Player("Free", "AgentBro", 25, _PP.CENTER, 70)
fa1.team_name = "Free Agent"
fa1.id = 990001
p2fam = list(getattr(p2, "family_ids", []) or [])
p2.family_ids = p2fam + [fa1.id]
fa1.family_ids = [p2.id]
league.free_agents.append(fa1)
pr1 = _gc.Player("Young", "ProspectBro", 18, _PP.LEFT_WING, 62)
pr1.team_name = "Draft Prospect"
pr1.id = 990002
p2.family_ids = list(getattr(p2, "family_ids", []) or []) + [pr1.id]
pr1.family_ids = [p2.id]
league.draft_prospects.append(pr1)
view2 = app.open_player_profile(p2)
for _ in range(6):
    app.update_idletasks(); app.update()
d2 = view2._allies_data()
fam_names = [f.full_name for f in d2["family"]]
check("family member on free agents resolves on the card",
      "Free AgentBro" in fam_names)
check("family member in draft prospects resolves on the card",
      "Young ProspectBro" in fam_names)

print(f"\n{len(passed)} passed, {len(failed)} failed")
app.destroy()
sys.exit(1 if failed else 0)
