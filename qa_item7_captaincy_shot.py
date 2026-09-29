"""Item 7 xvfb shot: MandatoryCaptainsWindow render + a11y probes.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_item7_captaincy_shot.py
Writes ~/workspace/puck-dynasty-ui-shots/captaincy_blocker{,_error}.png
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

random.seed(20260929)

import tkinter as tk
from popup_system import register
from game_classes import PlayerPosition
import windows
from main import GameManager

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


class StubPlayer:
    _id = 0

    def __init__(self, name, pos, leadership=50):
        StubPlayer._id += 1
        self.id = StubPlayer._id
        self.full_name = name
        self.primary_position = pos
        self.leadership = leadership
        self.captaincy = None


class StubTeam:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.roster = []


team = StubTeam("Test Club")
for i in range(14):
    team.roster.append(StubPlayer(f"Skater {i:02d}", PlayerPosition.CENTER,
                                 leadership=50 + i))
for i in range(2):
    team.roster.append(StubPlayer(f"Goalie {i:02d}", PlayerPosition.GOALIE,
                                 leadership=90))

gm = GameManager.__new__(GameManager)
gm._captaincy_choice_pending = False
gm.user_team = team
gm.add_news = lambda s: None

app = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team, game_manager=gm,
    update_all_views=lambda: None,
)

root = tk.Tk()
root.geometry("1400x900")
register(root)
# Production theme so the shot reflects the real app, not default ttk.
try:
    from ui_theme_system import ModernUITheme
    ModernUITheme().apply_to_style(tk.ttk.Style())
except Exception as e:
    print("theme skipped:", e)
root.update()
root.update_idletasks()

win = windows.MandatoryCaptainsWindow(app, team=team)
root.update()
root.update_idletasks()
root.after(50, root.update)  # let after_idle adoption run
root.update()
root.update_idletasks()

view = win._view

# --- non-dismissible probes ---
check("blocker is non-dismissible", win._dismissible is False)
check("WM_DELETE_WINDOW refused",
      callable(getattr(win, "_wm_delete_cb", None)))
win._wm_delete_cb()  # simulate X click
root.update(); root.update_idletasks()
check("X click does not close the card", bool(win.winfo_exists()))
check("X click nudges back to the form",
      "to continue" in view.error_var.get())
view.error_var.set("")
root.update(); root.update_idletasks()

# --- a11y probes ---
def _all_widgets(w):
    out = [w]
    for ch in w.winfo_children():
        out.extend(_all_widgets(ch))
    return out


widgets = _all_widgets(view)
combos = [w for w in widgets if w.winfo_class() == "TCombobox"]
check("three comboboxes", len(combos) == 3, f"found {len(combos)}")


def _fontsize(w):
    try:
        return w.cget("font")
    except Exception:
        return ""


texts = []
for w in widgets:
    try:
        t = str(w.cget("text"))
        if t:
            texts.append(t)
    except Exception:
        pass
check("header names the rule", any("Rule 6.1" in t for t in texts))
check("explains 1C+2A requirement",
      any("exactly one captain" in t for t in texts))
check("no scrollbar (single-level scrolling)",
      not any(w.winfo_class() in ("Scrollbar", "CTkScrollbar")
              for w in widgets))
check("error label is high-contrast red",
      str(view.error_label.cget("foreground")).lower() == "#e5484d")
check("confirm button present",
      any(w.winfo_class() == "TButton" and "Confirm" in str(w.cget("text"))
          for w in widgets))
check("comboboxes keyboard-reachable (enabled, mapped)",
      all(str(c.cget("state")) == "readonly" and bool(c.winfo_ismapped())
          for c in combos))

# --- screenshot: initial state ---
from PIL import ImageGrab
shot_dir = os.path.expanduser("~/workspace/puck-dynasty-ui-shots")
os.makedirs(shot_dir, exist_ok=True)
img = ImageGrab.grab()
p1 = os.path.join(shot_dir, "captaincy_blocker.png")
img.save(p1)
check("initial screenshot saved", os.path.exists(p1), p1)
print("saved", p1, img.size)

# --- invalid pick: goalie as C -> inline error, card stays open ---
view.captain_var.set("Goalie 00")
view.alternate1_var.set("Skater 00")
view.alternate2_var.set("Skater 01")
view.save_captains()
root.update(); root.update_idletasks()
check("goalie-C confirm rejected with inline error",
      "goaltender cannot be captain" in view.error_var.get(),
      view.error_var.get())
check("card still open after rejection", bool(win.winfo_exists()))
check("no letters persisted on rejection",
      all(getattr(p, "captaincy", None) is None for p in team.roster))

img2 = ImageGrab.grab()
p2 = os.path.join(shot_dir, "captaincy_blocker_error.png")
img2.save(p2)
check("error screenshot saved", os.path.exists(p2), p2)
print("saved", p2, img2.size)

# --- valid pick: confirms and closes ---
view.captain_var.set("Skater 13")
view.alternate1_var.set("Skater 11")
view.alternate2_var.set("Skater 12")
view.save_captains()
root.update(); root.update_idletasks()
check("card closed after valid confirm", not bool(win.winfo_exists()))
c = [p.full_name for p in team.roster if p.captaincy == "C"]
a = sorted(p.full_name for p in team.roster if p.captaincy == "A")
check("persisted exactly 1C", c == ["Skater 13"], str(c))
check("persisted exactly 2A", a == ["Skater 11", "Skater 12"], str(a))

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
print("shots:", p1, "|", p2)
sys.exit(1 if FAIL else 0)
