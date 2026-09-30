"""UI smoke test: modern player profile Analytics tab (department lens +
scout insights). Follows the qa_ui_accessibility.py pattern (InGamePopup
cards, mss full-monitor crop). Screenshots at 1600x900 for review."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from types import SimpleNamespace
from datetime import date

import game_classes as g
from game_classes import PlayerPosition, StaffRole
import analytics_scouting as an
import reputation_system as rs

W, H = 1600, 900
if len(sys.argv) >= 3:
    try:
        W, H = int(sys.argv[1]), int(sys.argv[2])
    except ValueError:
        pass
root = tk.Tk()
root.geometry(f"{W}x{H}+0+0")
root.update()
from popup_system import register
register(root)

# -- fixtures -----------------------------------------------------------
player = g.Player(first_name="Test", last_name="Player", age=24,
                  primary_position=PlayerPosition.CENTER, jersey_number=9)
rs.ensure_reputation_fields(player)
player.games_played = 50; player.goals = 22; player.assists = 30
player.shots = 210
scout = g.Staff("Ace", "Scout", StaffRole.HEAD_SCOUT)
scout.judging_player_ability = 80
an.ensure_analytics_fields(scout)
scout.tip_record = {"calls": 12, "hits": 9}  # record_tip_call below increments to 13
scout.tip_history = [
    {"player_name": "Breakout Kid", "kind": "buy", "result": "hit",
     "date": "2026-11-01"},
    {"player_name": "Washed Vet", "kind": "sell", "result": "miss",
     "date": "2026-10-01"},
]
team = SimpleNamespace(team_name="Test Club", roster=[player], staff=[scout],
                       inbox=[], analytics_quality=30)
an.seed_analytics_identities([team])
an.record_tip_call(scout, team, "buy", player, "2026-11-01",
                   reason="ixG 14.2 vs 6 goals -- finishing luck")
league = SimpleNamespace(teams=[team], free_agents=[])
app = SimpleNamespace(league=league, user_team=team, open_windows={},
                      current_date=date(2026, 11, 15),
                      BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
                      TEXT_COLOR="#ffffff", FONT_FAMILY="Helvetica")

# -- player card, Analytics tab ------------------------------------------
from modern_profile import PlayerProfile
pw = PlayerProfile(app, player)
root.update()
pw._switch_tab("Analytics")
root.update(); time.sleep(0.5)

import mss
from PIL import Image
out = os.path.expanduser(
    f"~/workspace/puck-dynasty-ui-shots/analytics_tab_{W}x{H}.png")
with mss.MSS() as sct:
    raw = sct.grab(sct.monitors[0])
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
try:
    shell = pw._popup_entry["shell"]
except Exception:
    shell = pw
x, y = shell.winfo_rootx(), shell.winfo_rooty()
w, h = shell.winfo_width(), shell.winfo_height()
print(f"shell at {x},{y} {w}x{h}")
img.crop((x, y, x + w, y + h)).save(out)
print("saved", out)

# Sanity: the insights card rendered the filed read.
texts = []
def walk(wid):
    try:
        texts.append(str(wid.cget("text")))
    except Exception:
        pass
    for ch in wid.winfo_children():
        walk(ch)
walk(pw)
blob = "\n".join(texts)
for needle in ["Scout Insights", "9 hits in 13 graded calls",
               "ixG 14.2 vs 6 goals", "models as of"]:
    assert needle in blob, f"SMOKE FAIL: missing {needle!r}"
print("SMOKE OK")
