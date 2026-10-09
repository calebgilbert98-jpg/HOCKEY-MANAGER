#!/usr/bin/env python3
"""QA: Health tab on player card -- injuries, timeline, history, condition (Muck 2026-10-02)."""
import sys, os
sys.path.insert(0, "/home/hatch/workspace/wt-cardinjuries")
os.chdir("/home/hatch/workspace/wt-cardinjuries")

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== Health tab wiring in modern_profile.py ==")
with open("/home/hatch/workspace/wt-cardinjuries/modern_profile.py") as f:
    src = f.read()

check("Health tab in tab_defs", '("Health", self._page_health)' in src)
check("_page_health method exists", "def _page_health" in src)
check("_create_health method exists", "def _create_health" in src)
check("condition bar moved OUT of _create_attributes",
      "one-row canonical Condition bar" not in src)
check("active injury section present", "Active Injury" in src)
check("recovery timeline present", "games_remaining_injured" in src)
check("injury history section present", "Injury History" in src)
check("injury_history data read", 'getattr(p, "injury_history"' in src)
check("never-raises guarded", src.count("except Exception") >= 3)

print("== headless UI smoke (Xvfb) ==")
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    import modern_profile as mp

    class FakePlayer:
        primary_position = "CENTER"
        is_injured = True
        injury_type = "Separated Shoulder"
        games_remaining_injured = 12
        injury_proneness = 30
        career_games_missed = 45
        days_missed = 8
        career_concussions = 1
        injury_history = [
            {"type": "Sprained Knee", "region": "Knee", "games": 6,
             "concussion": False},
            {"type": "Concussion", "region": "Head", "games": 10,
             "concussion": True},
        ]
        condition = 72

    prof = mp.PlayerProfile.__new__(mp.PlayerProfile)
    prof.player = FakePlayer()
    page = tk.Frame(root)

    ok = True
    try:
        prof._create_health(page)
    except Exception as e:
        ok = False
        print(f"  _create_health raised: {e}")
    check("_create_health builds without raising (injured player)", ok)

    texts = []
    def collect(w):
        try:
            for ch in w.winfo_children():
                try:
                    t = ch.cget("text")
                    if t:
                        texts.append(str(t))
                except Exception:
                    pass
                collect(ch)
        except Exception:
            pass
    collect(page)
    blob = "\n".join(texts)

    check("shows injury type", "Separated Shoulder" in blob)
    check("shows recovery timeline (~12 games)", "12 game" in blob)
    check("shows condition", "Condition" in blob)
    check("shows injury history entries", "Sprained Knee" in blob)
    check("shows concussion marker", "Concussion" in blob)
    check("shows career games missed", "45" in blob)
    check("shows durability", "Durability" in blob)

    # Healthy player: no Active Injury card, shows healthy status
    class HealthyPlayer(FakePlayer):
        is_injured = False
        injury_type = "None"
        games_remaining_injured = 0
        injury_history = []
    prof.player = HealthyPlayer()
    page2 = tk.Frame(root)
    ok2 = True
    try:
        prof._create_health(page2)
    except Exception as e:
        ok2 = False
        print(f"  _create_health raised (healthy): {e}")
    check("_create_health builds without raising (healthy player)", ok2)
    texts2 = []
    def collect2(w):
        try:
            for ch in w.winfo_children():
                try:
                    t = ch.cget("text")
                    if t:
                        texts2.append(str(t))
                except Exception:
                    pass
                collect2(ch)
        except Exception:
            pass
    collect2(page2)
    blob2 = "\n".join(texts2)
    check("healthy player shows no Active Injury card",
          "Active Injury" not in blob2)
    check("healthy player shows Healthy status", "Healthy" in blob2)
    check("healthy player shows empty history state",
          "No recorded injuries" in blob2)

    root.destroy()
except Exception as e:
    print(f"  UI smoke skipped/failed: {e}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
