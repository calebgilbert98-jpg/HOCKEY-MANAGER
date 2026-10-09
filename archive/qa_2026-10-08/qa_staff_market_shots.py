# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Headless screenshots for the staff-market work.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_staff_market_shots.py
Writes:
  /tmp/staff_contract_offer_v2.png  (editable dollar offer + budget line)
  /tmp/staff_market_sources.png     (staff tab with source pills)
Copies both to ~/workspace/puck-dynasty-ui-shots/.
"""
import os
import random
import shutil
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(11)

import customtkinter as ctk
import time
from PIL import ImageGrab

import windows
from game_classes import Staff, StaffRole, Team, default_staff_budget

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def mkstaff(fn, ln, role, rep, assignment="free_agent"):
    s = Staff(first_name=fn, last_name=ln, age=48, role=role,
              nationality="CAN")
    s.reputation = rep
    s.salary = 1_500_000
    s.assignment = assignment
    return s


def grab(path):
    img = ImageGrab.grab()
    img.save(path)
    return img.size


SHOT_DIR = os.path.expanduser("~/workspace/puck-dynasty-ui-shots")

# --- shot 1: negotiation view -----------------------------------------------
user = Team("Seattle Kraken", "Seattle", "Pacific", "West", "NHL", "GM", None)
user.staff_budget = default_staff_budget("Seattle Kraken")
user.roster = []
user.salary_cap = 104_000_000
gm = SimpleNamespace(user_team=user,
                     sign_free_agent_staff=lambda *a: True,
                     current_date=date(2026, 7, 15))
app = SimpleNamespace(game_manager=gm,
                      update_all_views=lambda: None)

coach = mkstaff("Erik", "Lindqvist", StaffRole.HEAD_COACH, 82,
                assignment="overseas")
coach.current_club = "Frolunda HC (SHL)"

root = ctk.CTk()
root.geometry("1600x900")
root.update()

view = windows.StaffContractView(root, coach, app=app,
                                 hire_source="overseas")
view.pack(fill="both", expand=True)
root.update()
root.update_idletasks()

w, h = grab("/tmp/staff_contract_offer_v2.png")
check("contract view screenshot size", w >= 1500 and h >= 850, f"{w}x{h}")


def texts(widget):
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for ch in widget.winfo_children():
        out.extend(texts(ch))
    return out


t = texts(view)
check("view shows overseas source", any("Currently coaching" in x for x in t))
check("view shows budget line", any("Club staff budget" in x for x in t))
check("view shows editable offer", any("Salary offer" in x for x in t))
view.destroy()

# --- shot 2: market tab with source pills ------------------------------------
t1 = Team("Seattle Kraken", "Seattle", "Pacific", "West", "NHL", "GM", None)
t1.staff_budget = default_staff_budget("Seattle Kraken")
t1.roster = []
t1.salary_cap = 104_000_000
ahl_hc = mkstaff("Dan", "Bylsma", StaffRole.HEAD_COACH, 74, assignment="ahl")
t1.staff = [ahl_hc]

t2 = Team("Boston Bruins", "Boston", "Atlantic", "East", "NHL", "GM", None)
t2.staff_budget = default_staff_budget("Boston Bruins")
t2.roster = []
t2.salary_cap = 104_000_000
ahl_ac = mkstaff("Marco", "Sturm", StaffRole.ASSISTANT_COACH, 66,
                 assignment="ahl")
t2.staff = [ahl_ac]

league = SimpleNamespace(
    free_agent_staff=[mkstaff("Alain", "Vigneault", StaffRole.HEAD_COACH, 78)],
    overseas_staff=[mkstaff("Jukka", "Jalonen", StaffRole.HEAD_COACH, 80,
                            assignment="overseas")],
    teams=[t1, t2],
)
league.overseas_staff[0].current_club = "Team Finland"
gm2 = SimpleNamespace(user_team=t1, league=league, free_agents=[],
                      current_date=date(2026, 7, 15))
app2 = SimpleNamespace(game_manager=gm2, league=league,
                       open_windows={},
                       show_screen=lambda *a, **k: None,
                       update_all_views=lambda: None,
                       tree_maps={},
                       _sort_treeview_generic=lambda *a, **k: None)

fa = windows.FreeAgencyView(root, app=app2)
fa.pack(fill="both", expand=True)
fa._build_fa_tab('staff')
# customtkinter 6.0 defers each tab-frame swap via after(100, ...), and the
# tabview's own construction schedules one too -- flush it first so a rapid
# programmatic .set() doesn't get its frame forgotten by the stale callback.
root.update()
time.sleep(0.2)
root.update()
fa.tabview.set("Free Agent Staff")
time.sleep(0.2)
root.update()
root.update_idletasks()

w, h = grab("/tmp/staff_market_sources.png")
check("market tab screenshot size", w >= 1500 and h >= 850, f"{w}x{h}")
t = texts(fa)
pill_options = set()
for _var, btns in getattr(fa, "_staff_pill_groups", []):
    pill_options.update(btns.keys())
check("tab shows source pills",
      {"All", "Free Agents", "Overseas", "Rival AHL"} <= pill_options,
      f"{sorted(pill_options)}")
check("tab shows budget header", any("Club staff budget" in x for x in t))
rows = [fa.fa_staff_tree.item(i, "values")
        for i in fa.fa_staff_tree.get_children()]
flat = " ".join(" ".join(map(str, r)) for r in rows)
check("tab lists the FA staffer", "Vigneault" in flat)
check("tab lists the overseas coach", "Jalonen" in flat)
check("tab lists the rival AHL coach", "Sturm" in flat)
check("own AHL coach excluded", "Bylsma" not in flat)
check("club column shows sources",
      "Team Finland" in flat and "(AHL)" in flat and "Free agent" in flat)

for f in ("staff_contract_offer_v2.png", "staff_market_sources.png"):
    shutil.copy(f"/tmp/{f}", os.path.join(SHOT_DIR, f))
print(f"copied to {SHOT_DIR}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
