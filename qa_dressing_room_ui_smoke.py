"""UI smoke test: Dressing Room screen (module 03). Follows the
qa_analytics_ui_smoke.py pattern. Screenshots at WxH for review."""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from types import SimpleNamespace
from datetime import date

random.seed(11)
import game_classes as g
from game_classes import PlayerPosition, StaffRole
import dressing_room as dr

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

# -- fixtures: a realistic room ------------------------------------------
NATS = ["Canada", "Canada", "USA", "Sweden", "Finland", "Russia"]
TENURES = ["4+ years", "4+ years", "3 years", "2 years", "This season"]
players = []
for i in range(23):
    p = g.Player(first_name=f"Test{i}", last_name="Player", age=24 + (i % 8),
                 primary_position=PlayerPosition.CENTER, jersey_number=i + 1)
    p.nationality = NATS[i % len(NATS)]
    p.team_tenure = TENURES[i % len(TENURES)]
    p.morale = 55 + (i * 7) % 40
    p.leadership = 40 + (i * 13) % 55
    players.append(p)
players[0].captaincy = "C"; players[0].leadership = 92
players[1].captaincy = "A"; players[2].captaincy = "A"

coach = g.Staff("Head", "Coach", StaffRole.HEAD_COACH)
coach.influence = 82
team = SimpleNamespace(team_name="Test Club", roster=players, staff=[coach],
                       streak=-2)
league = SimpleNamespace(teams=[team], free_agents=[])
app = SimpleNamespace(league=league, user_team=team, open_windows={},
                      current_date=date(2026, 11, 15))

# pre-seed some room history so the feed isn't empty
dr.cascade_on_press(team, {"player_name": "Test0 Player"}, "confident")
dr.give_talk(team, "fired-up",
             {"situation": "pregame", "score_state": "trailing",
              "rival": True, "streak": -2}, speaker="captain",
             rng=random.Random(11))

# -- the screen ------------------------------------------------------------
view = dr.DressingRoomView(root, app)
view.pack(fill="both", expand=True)
root.update(); time.sleep(0.6)

import mss
from PIL import Image
out = os.path.expanduser(
    f"~/workspace/puck-dynasty-ui-shots/dressing_room_{W}x{H}.png")
with mss.MSS() as sct:
    raw = sct.grab(sct.monitors[0])
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
x, y = view.winfo_rootx(), view.winfo_rooty()
w, h = view.winfo_width(), view.winfo_height()
print(f"view at {x},{y} {w}x{h}")
img.crop((x, y, x + w, y + h)).save(out)
print("saved", out)

# Sanity: key sections rendered.
texts = []
def walk(wid):
    try:
        texts.append(str(wid.cget("text")))
    except Exception:
        pass
    for ch in wid.winfo_children():
        walk(ch)
walk(view)
blob = "\n".join(texts)
for needle in ["Dressing Room", "Hierarchy", "Social Groups", "Team Talk",
               "Intermission Talk", "Room Feed", "Room mood",
               "Give pre-game talk"]:
    assert needle in blob, f"SMOKE FAIL: missing {needle!r}"
print("SMOKE OK")
