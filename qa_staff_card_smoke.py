"""UI smoke test: hired-staff card Track Record (scout) and Analytics
(director) tabs. Screenshots both at W x H for review.
Usage: python3 qa_staff_card_smoke.py [W H]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from types import SimpleNamespace
from datetime import date

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

import game_classes as g
from game_classes import StaffRole
import analytics_scouting as an

# -- fixtures -----------------------------------------------------------
team = SimpleNamespace(team_name="Test Club", roster=[], staff=[],
                       inbox=[], analytics_quality=25,
                       analytics_philosophy=70.0)

scout = g.Staff("Ace", "Scout", StaffRole.PROFESSIONAL_SCOUT)
scout.judging_player_ability = 88
an.ensure_analytics_fields(scout)
scout.tip_record = {"calls": 12, "hits": 9}
scout.tip_history = [
    {"player_name": "Breakout Kid", "kind": "buy", "result": "hit",
     "date": "2026-11-01"},
    {"player_name": "Washed Vet", "kind": "sell", "result": "miss",
     "date": "2026-10-01"},
]
director = g.Staff("Data", "Nerd", StaffRole.ANALYTICS_DIRECTOR)
director.judging_player_ability = 85
director.tactical_knowledge = 82
director.adaptability = 78
an.ensure_analytics_fields(director)
team.staff = [scout, director]
an.refresh_analytics_quality(team)

app = SimpleNamespace(league=SimpleNamespace(teams=[team]),
                      user_team=team, open_windows={},
                      current_date=date(2026, 11, 15),
                      BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
                      TEXT_COLOR="#ffffff", FONT_FAMILY="Segoe UI")

from staff_management_window import StaffManagementView
view = StaffManagementView(root, app=app)
view.pack(fill="both", expand=True)
root.update()

import mss
from PIL import Image
outdir = os.path.expanduser("~/workspace/puck-dynasty-ui-shots")

def _find_popup_card():
    """Find the InGamePopup card for the staff details overlay."""
    found = []
    def rec(wid):
        try:
            entry = getattr(wid, "_popup_entry", None)
            if entry and "Staff Details" in str(
                    getattr(wid, "_popup_title", "")):
                found.append(wid)
        except Exception:
            pass
        for ch in wid.winfo_children():
            rec(ch)
    rec(root)
    return found[0] if found else None

def grab_card(staff, tab, outfile):
    view.show_staff_details_window(staff, is_current=True)
    root.update(); time.sleep(0.5)
    popup = _find_popup_card()
    assert popup is not None, "details popup card not found"
    # click the tab button
    clicked = []
    def rec(wid):
        try:
            if wid.cget("text") == tab:
                wid.invoke(); clicked.append(True); return
        except Exception:
            pass
        for ch in wid.winfo_children():
            if not clicked:
                rec(ch)
    rec(popup)
    assert clicked, f"tab {tab!r} not found"
    root.update(); time.sleep(0.5)
    shell = popup._popup_entry["shell"]
    with mss.MSS() as sct:
        raw = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    x, y = shell.winfo_rootx(), shell.winfo_rooty()
    w, h = shell.winfo_width(), shell.winfo_height()
    img.crop((x, y, x + w, y + h)).save(outfile)
    print("saved", outfile)
    texts = []
    def walk(wid):
        try:
            texts.append(str(wid.cget("text")))
        except Exception:
            pass
        for ch in wid.winfo_children():
            walk(ch)
    walk(popup)
    try:
        popup.destroy()
    except Exception:
        pass
    root.update(); time.sleep(0.2)
    return "\n".join(texts)

blob1 = grab_card(scout, "Track Record",
                 f"{outdir}/staff_track_record_{W}x{H}.png")
for needle in ["9 hits in 12 graded calls", "Breakout Kid",
               "clubs fire scouts under 40%"]:
    assert needle in blob1, f"SMOKE FAIL: missing {needle!r}"
print("track record needles OK")

blob2 = grab_card(director, "Analytics",
                 f"{outdir}/staff_analytics_{W}x{H}.png")
for needle in ["Club department quality", "Models rebuild every"]:
    assert needle in blob2, f"SMOKE FAIL: missing {needle!r}"
print("analytics needles OK")
print("SMOKE OK")
