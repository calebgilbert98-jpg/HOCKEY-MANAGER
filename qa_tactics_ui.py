"""Headless UI smoke: TacticsWindow (menu) + visualizer tactics tab."""
import sys
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, ".")

import tkinter as tk
import tactics as tx
import reputation_system as rs

PASS, FAIL = [], []
def check(n, c, d=""):
    (PASS if c else FAIL).append(n)
    print(("  ok  " if c else "  FAIL") + f" {n}" + (f" -- {d}" if d and not c else ""))

def coach(**kw):
    base = dict(full_name="Test Coach", control_need=40, gm_trust=70,
                adaptability=60, first_nhl_chair=False, years_with_team=3,
                controversy=30, reputation=60, leadership=60, happiness=70,
                morale=70, discipline=65, motivating=65, man_management=65,
                tactical_knowledge=65, game_preparation=65,
                working_with_youngsters=50, player_development=50)
    base.update(kw); c = SimpleNamespace(**base)
    c.role = SimpleNamespace(value="Head Coach"); c.id = 1
    return c

# --- menu window ---
root = tk.Tk(); root.withdraw()
team = SimpleNamespace(team_name="Test Club", roster=[], staff=[coach()],
                       tactics_control="coach")
tx.ensure_team_tactics(team)
app = tk.Toplevel(root); app.withdraw()
app.user_team = team; app.open_windows = {}
app.league = SimpleNamespace(standings={"Test Club": {"W": 20, "L": 15, "OTL": 3}})
app.mp_client = None
app.add_news = lambda line: None
from tactics_window import TacticsWindow
w = TacticsWindow(app)
root.update()
check("menu window builds 7 module cards", len(w._cards.winfo_children()) == 7,
      str(len(w._cards.winfo_children())))
w._on_pick("ozone", tx.OZONE_SYSTEMS["oz_rush"]["name"])
check("pick stages pending under coach control", w._pending == {"ozone": "oz_rush"})
with patch.object(rs.random, "random", return_value=0.0):
    w._on_suggest()
root.update()
check("suggest applies + clears pending",
      not w._pending and team.tactics["ozone"] == "oz_rush")
# identity preset stages every differing module as pending
w._on_identity_preset("stranglehold")
_expected = {c: k for c, k in tx.IDENTITY_PRESETS["stranglehold"]["modules"].items()
             if team.tactics.get(c) != k}
check("preset stages all differing modules",
      w._pending == _expected and len(w._pending) >= 5, str(w._pending))
w._pending.clear()
w._response_text = ""
tx.set_tactics_control(team, "gm")
w._on_pick("pp", tx.POWERPLAY_SYSTEMS["umbrella"]["name"])
check("gm control applies immediately",
      team.tactics["pp"] == "umbrella" and not w._pending)
tx.save_preferred_tactics(team)
team.tactics["pp"] = "spread"
w._on_load_pref()
check("load preferred installs under gm", team.tactics["pp"] == "umbrella")
w.destroy()

# --- visualizer tab (harness: real methods, no sim thread) ---
from pbp_visual_sim import PBPVisualSim
home = SimpleNamespace(team_name="Home Club", roster=[], staff=[coach()],
                       tactics_control="coach")
away = SimpleNamespace(team_name="Away Club", roster=[], staff=[coach()],
                       tactics_control="coach")
tx.ensure_team_tactics(home); tx.ensure_team_tactics(away)
win = PBPVisualSim.__new__(PBPVisualSim)
win.home_team, win.away_team, win.user_team = home, away, home
win._tac_tab, win._tac_pending, win._tac_response_text = "pbp", {}, ""
win._ui_accent = "#2EB5A5"; win._cur_score = (1, 3)
win._pill = PBPVisualSim._pill.__get__(win, PBPVisualSim)
win._refresh_toggle_btn = PBPVisualSim._refresh_toggle_btn
shell = tk.Toplevel(root); shell.withdraw()
win._tactics_frame = tk.Frame(shell, bg="#16161a")
win._pbp_frame = tk.Frame(shell, bg="#16161a")
win._tab_pbp_btn = tk.Button(shell); win._tab_tac_btn = tk.Button(shell)
win._refresh_tactics_tab()
root.update()
kids = win._tactics_frame.winfo_children()
check("tab builds (header+rows+opp section)", len(kids) > 12, str(len(kids)))
labels = []
def walk(wd):
    for ch in wd.winfo_children():
        if isinstance(ch, tk.Label): labels.append(ch.cget("text"))
        walk(ch)
walk(win._tactics_frame)
check("tab shows control badge", any("COACH IN CONTROL" in t for t in labels))
check("tab shows opponent systems", any("OPPONENT (AI)" in t for t in labels))
# simulate a pick -> pending -> suggest
first = win._tactics_frame
with patch.object(rs.random, "random", return_value=0.0):
    win._on_tac_pick("ozone", tx.OZONE_SYSTEMS["oz_rush"]["name"],
                     {v.get("name", k): k for k, v in tx.OZONE_SYSTEMS.items()})
    check("tab pick stages pending", win._tac_pending == {"ozone": "oz_rush"})
    win._on_tac_suggest()
check("tab suggest applies live", home.tactics["ozone"] == "oz_rush" and not win._tac_pending)
check("mid-game familiarity hit is soft",
      35 <= float(home.tactics_familiarity) < 85, str(home.tactics_familiarity))
# takeover path
win._on_tac_pick("neutral_zone", tx.NEUTRAL_ZONE_SYSTEMS["nz_trap_131"]["name"],
                 {v.get("name", k): k for k, v in tx.NEUTRAL_ZONE_SYSTEMS.items()})
with patch("tkinter.messagebox.askyesno", return_value=True):
    win._on_tac_takeover()
check("tab takeover: gm control + pending applied",
      tx.get_tactics_control(home) == "gm" and home.tactics["neutral_zone"] == "nz_trap_131")
shell.destroy(); root.destroy()

print(); print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
