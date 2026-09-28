"""Headless render + a11y probe of the ELC negotiation view.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_elc_view_shot.py
Writes /tmp/elc_view.png and runs layout/a11y assertions.
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from game_classes import Player, PlayerPosition
import windows

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {extra}" if extra and not cond else ""))


random.seed(7)
p = Player("Connor", "Bedard", 19, PlayerPosition.CENTER)
p.contract = None
# The Player dataclass defaults birth_date to a random 1995-2006 date,
# independent of the age argument -- pin one consistent with age 19 so
# the Sept-15 signing-age math (which the view uses) agrees with p.age.
p.birth_date = "2008-04-22"
p.overall_pick = 1
p.draft_round = 1
p.selfishness = 60
p.rights_team = "Test Team"

ASK = {"salary": 1_050_000, "years": 3, "signing_bonus": 105_000,
       "performance_bonus": 1_000_000}


def fake_handle_elc_offer(player, salary, sb=0, pb=0):
    if salary >= ASK["salary"]:
        return {"verdict": "accepted", "counter": None, "note": "Deal."}
    return {"verdict": "counter", "counter": ASK,
            "note": "Agent counters at his ask."}


app = SimpleNamespace(
    BG_COLOR="#1a1d29", FONT_FAMILY="Helvetica",
    CONTENT_BG="#222636", TEXT_COLOR="#e8eaf0",
    league=SimpleNamespace(season_year=2027),
    user_team=SimpleNamespace(team_name="Test Team", payroll=80_000_000),
    get_live_cap=lambda: 95_500_000,
    handle_elc_offer=fake_handle_elc_offer,
)

root = ctk.CTk()
root.geometry("1400x900")
root.update()

view = windows.ContractNegotiationView(root, p, False, app=app, is_elc=True)
view.pack(fill="both", expand=True)
root.update()
root.update_idletasks()

# --- a11y / layout probes ---
def _all_texts(widget):
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for ch in widget.winfo_children():
        out.extend(_all_texts(ch))
    return out


_texts = _all_texts(view)
check("title reads Entry-Level Contract",
      any("Entry-Level Contract" in t for t in _texts))
check("banner mentions ELC band",
      "Entry-Level Contract" in view.banner_var.get())
check("term locked label mentions not negotiable",
      any("not negotiable" in t for t in _texts))
check("ELC band hint shown",
      any("ELC band" in t for t in _texts))


def _all_widgets(widget):
    out = [widget]
    for ch in widget.winfo_children():
        out.extend(_all_widgets(ch))
    return out


_widgets = _all_widgets(view)
check("no term slider in ELC mode",
      not any(w.winfo_class() == "CTkSlider" for w in _widgets))
check("years_var locked to 3", int(view.years_var.get()) == 3)
check("clause widgets hidden in ELC mode", not hasattr(view, "clause_menu"))
check("signing + perf bonus entries exist",
      hasattr(view, "signing_var") and hasattr(view, "perf_var"))
check("context shows agent ask",
      "Agent's ask" in view.context_box.get("1.0", "end"))
check("counter button hidden initially",
      not bool(view.counter_btn.winfo_ismapped()))

# --- counter path: submit a low offer, agent counters, button appears ---
view.salary_var.set("900000")
view.signing_var.set("0")
view.perf_var.set("0")
view._close_session = lambda: None
view.close_view = lambda: None
view._submit_elc_offer()
root.update(); root.update_idletasks()
check("counter verdict shows agent number",
      "counters" in view.banner_var.get(), view.banner_var.get()[:80])
check("counter accept button appears",
      bool(view.counter_btn.winfo_ismapped()))
check("counter button names the number",
      "1,050,000" in view.counter_btn.cget("text"),
      view.counter_btn.cget("text"))

# --- accept-counter path fills the fields ---
view._accept_elc_counter()
root.update(); root.update_idletasks()
check("accept-counter fills salary",
      view.salary_var.get().replace(",", "") == str(ASK["salary"]),
      view.salary_var.get())

# --- screenshot ---
from PIL import ImageGrab
img = ImageGrab.grab()
img.save("/tmp/elc_view.png")
w, h = img.size
check("screenshot non-trivial size", w >= 1400 and h >= 900, f"{w}x{h}")
# crude clipping check: the window's own right edge must not be a black
# void (would indicate the layout overran the virtual screen)
wx, wy, ww, wh = (root.winfo_x(), root.winfo_y(),
                  root.winfo_width(), root.winfo_height())
crop = img.crop((wx, wy, wx + ww, wy + wh))
px = crop.load()
cw, ch = crop.size
right_col = [px[cw - 5, y] for y in range(0, ch, 40)]
check("no black void on window right edge",
      not all(sum(c[:3]) < 30 for c in right_col))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
print("shot: /tmp/elc_view.png")
sys.exit(1 if FAIL else 0)
