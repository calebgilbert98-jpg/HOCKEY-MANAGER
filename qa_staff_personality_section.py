# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Bug 4: the staff hiring card must show coaching style + attitude insights.

Builds FreeAgencyView._staff_personality_section headlessly for a
drill-sergeant head coach and a scout, then walks the widget tree
asserting the section heading, style label/description, and attitude
lines are present.
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from ctk_theme import (heading, body, TEAL, TEAL_HOVER, BG, PANEL, CARD,
                       BORDER, TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED,
                       BLUE)
from game_classes import Staff, StaffRole
from windows import FreeAgencyView

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


def texts(widget):
    out = []
    try:
        t = widget.cget("text")
        if t:
            out.append(str(t))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(texts(child))
    return out


root = ctk.CTk()
root.withdraw()
# Build the view without __init__ (full init needs a live app); attach
# only what _staff_personality_section uses.
view = FreeAgencyView.__new__(FreeAgencyView)
view._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                BLUE=BLUE)
view._heading = heading
view._body = body
root.update()

# A drill-sergeant head coach: high discipline, low man_management
coach = Staff(first_name="Mike", last_name="Sergeant",
              role=StaffRole.HEAD_COACH)
coach.discipline = 95
coach.motivating = 60
coach.man_management = 30
coach.tactical_knowledge = 50
coach.game_preparation = 50
coach.working_with_youngsters = 50
coach.player_development = 50
coach.leadership = 60
coach.control_need = 95
coach.ambition = "stanley_cup"
coach.base_controversy = 70  # locked hothead identity (not re-dealt)
coach.controversy = 70
coach.favorite_team = "Test Club"

holder = ctk.CTkFrame(root)
holder.pack()
view._staff_personality_section(holder, coach)
root.update()
got = " ".join(texts(holder))

check("section heading present", "Coaching Style & Personality" in got, got[:200])
check("style label present", "Drill Sergeant" in got, got[:200])
check("style description present", "Bag skates" in got)
check("ambition line present", "Stanley Cup" in got)
check("control-need line present", "full control" in got)
check("controversy line present", "headlines" in got)

# A scout (non-coach): no style header, but attitude lines still show
scout = Staff(first_name="Sam", last_name="Eyes", role=StaffRole.HEAD_SCOUT)
scout.ambition = "lifer"
scout.controversy = 10
holder2 = ctk.CTkFrame(root)
holder2.pack()
view._staff_personality_section(holder2, scout)
root.update()
got2 = " ".join(texts(holder2))
check("scout: section present", "Coaching Style & Personality" in got2)
check("scout: no coaching-style label", "Drill Sergeant" not in got2
      and "Tactician" not in got2)
check("scout: ambition line present", "lifer" in got2)

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
