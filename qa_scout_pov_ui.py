#!/usr/bin/env python3
"""QA (UI-level): the Scout Report tab shows the scout's perceived read,
the Overview tab keeps true values, and no-scout shows unavailable state.
Headless: run under xvfb-run."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(42)

import tkinter as tk
from types import SimpleNamespace
from game_classes import Player, Staff, StaffRole, ScoutingReport, PlayerPosition

passed, failed = [], []


def check(name, cond, detail=""):
    if cond:
        passed.append(name); print(f"  PASS {name}")
    else:
        failed.append(name); print(f"  FAIL {name} {detail}")


def page_texts(page):
    out = []
    def walk(w):
        try:
            if w.winfo_class() == "Label":
                out.append(w.cget("text"))
        except Exception:
            pass
        for c in w.winfo_children():
            walk(c)
    walk(page)
    return " \n ".join(out)


random.seed(99)
p = Player(first_name="Ui", last_name="Probe", age=24,
           primary_position=PlayerPosition.LEFT_WING)
p.shooting = 85
for a, v in {"passing": 70, "skating": 70, "vision": 50}.items():
    setattr(p, a, v)

scout = Staff(first_name="Seedy", last_name="McScout",
              role=StaffRole.PROFESSIONAL_SCOUT,
              judging_player_ability=10, judging_player_potential=10)
rep = ScoutingReport(player=p, scout=scout)
rep.update_report(p, scout)  # 1 viewing -> F grade
assert rep.accuracy == 'F', rep.accuracy

import scout_perception as sp
perc = sp.perceived_attributes(p, scout, rep)
comps = sp.perceived_composites(p, scout, rep)

root = tk.Tk()
root.withdraw()
root.user_team = SimpleNamespace(staff=[scout],
                                 scouting_reports={p.id: rep},
                                 roster=[p], ahl_roster=[])
root.league = SimpleNamespace(teams=[])

from modern_profile import PlayerProfile
w = PlayerProfile(root, p)
root.update()

scout_txt = page_texts(w._tab_pages["Scout Report"])
ov_txt = page_texts(w._tab_pages["Overview"])

check("UI scout name on tab", "Seedy McScout" in scout_txt)
check("UI record line on tab",
      "graded calls" in scout_txt or "no graded calls yet" in scout_txt)
check("UI F-grade accuracy shown", "Report accuracy F" in scout_txt)

flo, fhi = comps["finishing"]
exp = f"Finishing {flo:.0f}-{fhi:.0f}"
check("UI perceived composite range shown", exp in scout_txt,
      f"looked for {exp!r}")

strengths, _weak = sp.perceived_strengths_weaknesses(p, scout, rep)
check("UI perceived strengths shown w/ ranges",
      strengths and strengths[0] in scout_txt,
      f"looked for {strengths[0] if strengths else None!r}")
check("UI true point value NOT on scout tab", "(85)" not in scout_txt)
check("UI Overview keeps TRUE shooting 85",
      "\n85" in ov_txt or " 85" in ov_txt or ov_txt.strip().endswith("85")
      or "85\n" in ov_txt,
      "true value missing from Overview")
w.destroy()

# no-scout state: never fall back to truth
root2 = tk.Tk(); root2.withdraw()
root2.user_team = SimpleNamespace(staff=[], scouting_reports={},
                                  roster=[p], ahl_roster=[])
root2.league = SimpleNamespace(teams=[])
w2 = PlayerProfile(root2, p)
root2.update()
scout_txt2 = page_texts(w2._tab_pages["Scout Report"])
check("UI no-scout unavailable state",
      "No scout on staff" in scout_txt2, scout_txt2[:200])
w2.destroy()

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
