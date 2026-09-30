"""QA R6 (redirected): Declare-Rival modal has NO coach dropdown.

- Team-rival dropdown still works; declaring a team rival works.
- Personal-rival section is guidance text pointing at the right-click flow.
- The rivalry system exposes a clean, importable entry point for personal
  beefs: reputation_system.declare_rivalry_for_gm(..., target_kind="coach")
  plus the lower-level declare_rivalry(league, gm_persona(team), person,
  kind="gm_coach") the right-click worker will call per card.

Run: DISPLAY=:99 python3 qa_r6_rival_redirect.py   (headless; Xvfb on :99)
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

random.seed(20260929)

import reputation_system as rs
from game_classes import League, Staff, StaffRole
from database_generator import DatabaseGenerator

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def build_league():
    league = League("National Hockey League", "NHL")
    gen = DatabaseGenerator.__new__(DatabaseGenerator)
    gen._generate_team_staff(list(league.teams))
    league.rivalries = []
    return league


import tkinter as tk
import customtkinter as ctk
from morale_window import DeclareRivalPopup

league = build_league()
user_team = league.teams[0]

# --- 1. widget: no coach dropdown, guidance text present --------------------
root = ctk.CTk()
root.withdraw()
parent = tk.Frame(root)
parent.app = SimpleNamespace(
    user_team=user_team, league=league, mp_client=None)
popup = DeclareRivalPopup(parent, user_team, league)
check("no coach dropdown on the modal",
      not hasattr(popup, "_coach_pick"))
check("no coach map on the modal",
      not hasattr(popup, "_coach_map"))
texts = []

def walk(w):
    try:
        texts.append(str(w.cget("text")))
    except Exception:
        pass
    for c in w.winfo_children():
        walk(c)

walk(popup)
check("no '(no coaches)' anywhere in the modal",
      not any("(no coaches)" in t for t in texts))
check("guidance points at the right-click flow",
      any("Right-click" in t and "Declare rival" in t for t in texts))

# --- 2. team-rival dropdown still works --------------------------------------
check("team dropdown lists 31 opposing clubs",
      len(popup._team_names) == 31)
check("team OptionMenu populated",
      len(popup._team_pick.cget("values")) == 31)

# --- 3. declaring a team rival works ------------------------------------------
target = league.teams[5]
rec, label = rs.declare_rivalry_for_gm(league, user_team, target, "team")
check("declare team rival returns record", rec is not None
      and rec.get("kind") == "team_team")
check("team declaration heat is 70", rec.get("intensity") == 70)
check("team label is the club name", label == target.team_name)
live = rs.declared_rivalries_for(league.rivalries, user_team)
check("team declaration is live", len(live) == 1)
check("renounce team rival works",
      rs.renounce_rivalry_for_gm(league, user_team, target, "team") is True
      and not rs.declared_rivalries_for(league.rivalries, user_team))

# --- 4. entry point: declare_rivalry_for_gm(kind="coach") --------------------
check("entry point importable",
      callable(rs.declare_rivalry_for_gm))
import inspect
sig = inspect.signature(rs.declare_rivalry_for_gm)
check("entry point signature (league, team, target_team, target_kind='team')",
      list(sig.parameters) == ["league", "team", "target_team",
                               "target_kind"])
rec, label = rs.declare_rivalry_for_gm(league, user_team, target, "coach")
coach = rs._head_coach_of(target)
check("coach declaration records gm_coach kind",
      rec is not None and rec.get("kind") == "gm_coach")
check("coach declaration heat is 70", rec.get("intensity") == 70)
check("coach label names the opposing head coach",
      label == coach.full_name)
live = rs.declared_rivalries_for(league.rivalries, user_team)
check("coach declaration shows as live", len(live) == 1)

# --- 5. lower-level entry point for the right-click worker --------------------
check("declare_rivalry importable", callable(rs.declare_rivalry))
check("gm_persona importable", callable(rs.gm_persona))
rec2 = rs.declare_rivalry(league, rs.gm_persona(user_team), coach,
                          kind="gm_coach")
check("declare_rivalry(league, gm_persona, coach, kind='gm_coach') works",
      rec2 is not None and rec2.get("user_declared") is True)
check("renounce coach beef works",
      rs.renounce_rivalry_for_gm(league, user_team, target, "coach") is True
      and not rs.declared_rivalries_for(league.rivalries, user_team))

# --- 6. modal renounce list still handles coach-kind declarations ------------
rs.declare_rivalry_for_gm(league, user_team, target, "coach")
popup._rebuild_renounce_list()
btns = [w for w in popup._renounce_frame.winfo_children()
        if "Renounce" in str(getattr(w, "cget", lambda *a: "")("text")
                             if hasattr(w, "cget") else "")]
renounce_labels = []
for w in popup._renounce_frame.winfo_children():
    try:
        renounce_labels.append(str(w.cget("text")))
    except Exception:
        pass
check("renounce list offers the coach beef",
      any(l.startswith("Renounce vs") and coach.full_name in l
          for l in renounce_labels))
# invoke the renounce button
invoked = False
for w in popup._renounce_frame.winfo_children():
    try:
        if str(w.cget("text")).startswith("Renounce vs"):
            w.invoke()
            invoked = True
    except Exception:
        pass
check("renounce button clears the coach beef",
      invoked and not rs.declared_rivalries_for(league.rivalries, user_team))

popup.destroy()
root.destroy()

print(f"\nR6: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
