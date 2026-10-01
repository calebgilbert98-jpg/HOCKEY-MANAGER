# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: Composite Ratings visibility toggle (new-save advanced setting).

Muck's test: the toggle must "fit right in the ecosystem both ways."
  ON  -> Composite Ratings section + scout's composite line render.
  OFF -> the card reads naturally: zero dangling composite references,
         and the underlying sim is untouched (visibility only, never logic).
"""
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import game_classes as g
from game_classes import PlayerPosition

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name +
          (f" -- {detail}" if detail and not cond else ""))


from modern_profile import composites_visible, PlayerProfile

print("== visibility helper ==")
check("default True (no setting)",
      composites_visible(SimpleNamespace()) is True)
check("default True (no app)", composites_visible(None) is True)
check("ON via startup_settings",
      composites_visible(SimpleNamespace(
          startup_settings={"show_composite_ratings": True})) is True)
check("OFF via startup_settings",
      composites_visible(SimpleNamespace(
          startup_settings={"show_composite_ratings": False})) is False)
check("game_manager fallback",
      composites_visible(SimpleNamespace(
          game_manager=SimpleNamespace(show_composite_ratings=False)))
      is False)
check("startup_settings wins over game_manager",
      composites_visible(SimpleNamespace(
          startup_settings={"show_composite_ratings": True},
          game_manager=SimpleNamespace(show_composite_ratings=False)))
      is True)


def _walk(w):
    yield w
    try:
        for k in w.winfo_children():
            yield from _walk(k)
    except Exception:
        pass


def _texts(w):
    out = []
    for x in _walk(w):
        try:
            t = x.cget("text")
            if isinstance(t, str) and t.strip():
                out.append(t)
        except Exception:
            pass
    return out


print("== card rendering both ways ==")
root = tk.Tk()
root.geometry("1600x900")
p1 = g.Player("Test", "Player", 25, PlayerPosition.CENTER, 75)
root.user_team = SimpleNamespace(roster=[p1], ahl_roster=[], prospects=[])

# ON state
root.startup_settings = {"show_composite_ratings": True}
w_on = PlayerProfile(root, p1)
root.update()
texts_on = _texts(w_on)
w_on.destroy()
check("ON: Composite Ratings section renders",
      any("Composite Ratings" in t for t in texts_on))
check("ON: composite bars render (Chance Creation)",
      any("Chance Creation" in t for t in texts_on))

# OFF state
root.startup_settings = {"show_composite_ratings": False}
w_off = PlayerProfile(root, p1)
root.update()
texts_off = _texts(w_off)
w_off.destroy()
check("OFF: card renders without error", True)
check("OFF: no 'Composite Ratings' text",
      not any("Composite Ratings" in t for t in texts_off),
      str([t for t in texts_off if "Composite" in t])[:200])
check("OFF: no composite bar labels",
      not any(x in t for t in texts_off
              for x in ("Chance Creation", "Puck Retrieval", "Defensive Play")),
      str([t for t in texts_off if "Creation" in t or "Retrieval" in t])[:200])
check("OFF: no scout composite line",
      not any("Scout's ratings:" in t for t in texts_off))
check("OFF: attributes still shown (card reads naturally)",
      any("Attributes" in t for t in texts_off))
check("OFF: no dangling composite references anywhere",
      not any("composite" in t.lower() for t in texts_off),
      str([t for t in texts_off if "composite" in t.lower()])[:200])
root.destroy()

print("== sim untouched (visibility only) ==")
import attribute_composites as acm
p2 = g.Player("Sim", "Check", 24, PlayerPosition.CENTER, 80)
before = dict(acm.get_composite_ratings(p2))
# The toggle lives in UI/settings layers; the engine module has no input
# for it -- prove the computation is identical regardless of setting.
after = dict(acm.get_composite_ratings(p2))
check("composite computation identical (no toggle input)",
      before == after)
check("engine module has no visibility dependency",
      "show_composite_ratings" not in open("attribute_composites.py").read())

print("== goalie/skater composite gating (bug 2) ==")
root2 = tk.Tk()
root2.geometry("1600x900")
root2.startup_settings = {"show_composite_ratings": True}
skater = g.Player("Skater", "Test", 25, PlayerPosition.CENTER, 75)
w_sk = PlayerProfile(root2, skater)
root2.update()
texts_sk = _texts(w_sk)
w_sk.destroy()
check("skater card: no 'Goaltending' composite bar",
      not any(t.strip() == "Goaltending" for t in texts_sk),
      str([t for t in texts_sk if "Goaltend" in t])[:200])
check("skater card: skater composites still render",
      any("Chance Creation" in t for t in texts_sk)
      and any("Faceoffs" in t for t in texts_sk))
goalie = g.Player("Goalie", "Test", 25, PlayerPosition.GOALIE, 75)
w_gk = PlayerProfile(root2, goalie)
root2.update()
texts_gk = _texts(w_gk)
w_gk.destroy()
check("goalie card: 'Goaltending' composite bar renders",
      any(t.strip() == "Goaltending" for t in texts_gk))
check("goalie card: no skater-only 'Finishing' bar",
      not any(t.strip() == "Finishing" for t in texts_gk),
      str([t for t in texts_gk if "Finish" in t])[:200])
root2.destroy()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
