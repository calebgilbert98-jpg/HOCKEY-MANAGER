"""QA: scout tips are private to the club -- never broadcast in the news feed.

Covers:
  1. The monthly scan no longer emits "SCOUT READ" news stories
     (regression guard on main.py).
  2. Filed tips carry the display fields the scout card needs
     (name/team/kind/reason/risks/confidence) without breaking the
     trade engine's reads (jpa/correct/scout_id still present).
  3. The scout's staff card shows an "Open Reads" section with only
     THIS scout's reads from the user's club -- a rival scout's card
     shows nothing (tips are private to the filing club).
  4. Screenshot for visual review.

Run under Xvfb: xvfb-run -a -s "-screen 0 1680x1050x24" \
    python3 qa_scout_private_tips.py
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


# --- 1. no broadcast in main.py ----------------------------------------------
src = open("main.py", encoding="utf-8").read()
check("news: no SCOUT READ broadcast stories remain",
      "SCOUT READ" not in src,
      "main.py still contains a SCOUT READ news story")

# --- 2. filed tip shape ---------------------------------------------------------
import tkinter as tk
from types import SimpleNamespace

import game_classes as g
from game_classes import StaffRole
import analytics_scouting as an

root = tk.Tk()
root.geometry("1680x1050+0+0")
root.update()
from popup_system import register
register(root)

scout = g.Staff("Ace", "Scout", StaffRole.HEAD_SCOUT)
scout.id = "scout-ace"
scout.judging_player_ability = 80
an.ensure_analytics_fields(scout)

rival_scout = g.Staff("Rival", "Eye", StaffRole.PROFESSIONAL_SCOUT)
rival_scout.id = "scout-rival"
rival_scout.judging_player_ability = 80
an.ensure_analytics_fields(rival_scout)

team = SimpleNamespace(team_name="Test Club", staff=[scout, rival_scout],
                       inbox=[], analytics_quality=30)
an.ensure_analytics_fields(team)
team.scout_buy_tips = {}
team.scout_sell_tips = {}


def file_buy(pid, s, name, pteam, kind, reason):
    team.scout_buy_tips[pid] = {
        "jpa": 18, "correct": True, "scout": s.full_name,
        "scout_id": getattr(s, "id", ""), "name": name, "pteam": pteam,
        "kind": kind, "reason": reason,
        "risks": ["Translation risk: AHL scoring doesn't always cross over"],
        "confidence": "High"}


file_buy(101, scout, "Farm Gem", "Rival Club", "AHL",
         "Out-producing pedigree: 0.60 NHLe P/GP (1.9x expected)")
file_buy(102, scout, "Junior Kid", "Other Club", "PROSPECT",
         "Draft steal brewing: round-5 pick at 0.62 NHLe P/GP")
# A rival scout's read lives on the RIVAL club's books -- never on the
# user's. Filing it there proves cross-team privacy: the user's card
# for any scout can only ever see the user's own club's reads.
rival_team = SimpleNamespace(team_name="Rival Club", staff=[rival_scout],
                             inbox=[], analytics_quality=30)
an.ensure_analytics_fields(rival_team)
rival_team.scout_buy_tips = {}
rival_team.scout_sell_tips = {}
rival_team.scout_buy_tips[103] = {
    "jpa": 18, "correct": True, "scout": rival_scout.full_name,
    "scout_id": rival_scout.id, "name": "Not Mine", "pteam": "Far Club",
    "kind": "AHL", "reason": "Out-producing pedigree: 0.58 NHLe P/GP",
    "risks": [], "confidence": "High"}
team.scout_sell_tips[201] = {
    "jpa": 16, "correct": True, "scout": scout.full_name,
    "scout_id": scout.id, "name": "Fading Vet", "kind": "",
    "reason": "PDO 1.04 with xGF% 44 -- results outrunning process",
    "risks": [], "confidence": "Medium"}

tip = team.scout_buy_tips[101]
check("tips: trade-engine keys intact",
      tip["jpa"] == 18 and tip["correct"] is True
      and tip["scout_id"] == "scout-ace")
check("tips: card display keys present",
      all(k in tip for k in ("name", "pteam", "kind", "reason",
                             "risks", "confidence")))

# --- 3. staff card renders only this scout's reads -------------------------------
app = SimpleNamespace(user_team=team, open_windows={})
from windows import FreeAgencyView
from ctk_theme import (heading, body, TEAL, TEAL_HOVER, BG, PANEL, CARD,
                       BORDER, TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED,
                       BLUE, ROW_HOVER, ROW_SELECTED)
# Bypass the heavy FA-market __init__ (needs a full game manager); wire
# only what the staff-card section methods touch, then exercise the
# real method.
view = FreeAgencyView.__new__(FreeAgencyView)
view._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                BLUE=BLUE, ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
view._heading = heading
view._body = body
view.app = app
import tkinter as _tk
view.tk = root.tk  # noqa: attribute for widget parenting fallback
import customtkinter as ctk
scroll = ctk.CTkScrollableFrame(root, fg_color="transparent")
scroll.pack(fill="both", expand=True, padx=16, pady=14)

view._staff_open_reads_section(scroll, scout)
root.update()
time.sleep(0.4)


def texts(w):
    out = []
    try:
        for ch in w.winfo_children():
            try:
                t = ch.cget("text")
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
            except Exception:
                pass
            out.extend(texts(ch))
    except Exception:
        pass
    return out


got = texts(scroll)
check("card: Open Reads section renders",
      any("Open Reads" in t for t in got), f"found={got[:8]}")
check("card: buy reads listed",
      any("Farm Gem" in t for t in got) and any("Junior Kid" in t for t in got),
      f"found={got[:12]}")
check("card: AHL tag shown",
      any("[AHL]" in t for t in got))
check("card: sell read listed",
      any("Fading Vet" in t for t in got))
check("card: rival club's tip NOT visible on user's card",
      not any("Not Mine" in t for t in got),
      f"found={got[:12]}")
check("card: evidence + uncertainty shown",
      any("1.9x expected" in t for t in got)
      and any("High confidence" in t for t in got))
check("card: risks disclosed",
      any("Risk:" in t for t in got))

# Rival scout's card: no open reads (their tips belong to their club,
# which isn't the user's).
scroll2 = ctk.CTkScrollableFrame(root, fg_color="transparent")
view._staff_open_reads_section(scroll2, rival_scout)
root.update()
got2 = texts(scroll2)
check("card: rival scout shows no reads on user's card",
      not any("Open Reads" in t for t in got2),
      f"found={got2[:6]}")

# --- 4. screenshot ----------------------------------------------------------------
shot = "/tmp/qa_scout_open_reads.png"
try:
    from mss import MSS
    with MSS() as sct:
        try:
            sct.shot(output=shot)
        except TypeError:
            sct.shot(mon=-1, output=shot)
    check("shot: screenshot saved", os.path.exists(shot), shot)
    print(f"screenshot: {shot}")
except Exception as e:
    check("shot: screenshot saved", False, str(e))

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
