# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""R8 QA: top-nav Continue pill + loading indicator.

R8(i): the top-nav "Continue (1)" pill painted its label ONCE at startup
(main.py:3446) and never again in single-player -- after the blocker was
resolved it kept reading "Continue (1)" (stale), and a blocker appearing
mid-session left it reading "Next Day". The fix refreshes the pill from
update_all_views, simulate_day's finally, and the blocker dialog's jump
action. Proves:
  - refresh_next_day_button() paints live state when invoked
    ("Continue (1)" / "Continue (2)" / "Next Day");
  - the three refresh hooks are wired.

R8(ii): TradeWindow busy/loading indicator for heavy ops (mirrors the
existing dashboard_home.set_continue_busy pattern). Behavior is covered
in qa_r3_trade_center.py; here we pin the pattern lineage.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_r8_continue_loading.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/wt-ui-repairs")
os.chdir("/home/hatch/workspace/wt-ui-repairs")

import tkinter as tk
from popup_system import register

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


root = tk.Tk()
root.geometry("1200x800")
register(root)
root.update()

import main as main_mod

# --- R8(i): the real method paints live state when invoked ---------------
state = {"label": "Next Day", "blockers": []}
btn = tk.Button(root, text="Next Day")
btn.pack()
root.update_idletasks()

gui = SimpleNamespace(
    _next_day_btn=btn,
    _mp_host_mode=lambda: False,
    _mp_client_mode=lambda: False,
    get_continue_state=lambda: (state["label"], state["blockers"]),
)
_refresh = main_mod.HockeyManagerGUI.refresh_next_day_button

state["label"], state["blockers"] = "Continue", [{"id": "x"}]
_refresh(gui)
root.update_idletasks()
check("R8(i) one blocker -> 'Continue (1)'",
      btn.cget("text") == "Continue (1)", repr(btn.cget("text")))

state["blockers"] = [{"id": "x"}, {"id": "y"}]
_refresh(gui)
root.update_idletasks()
check("R8(i) two blockers -> 'Continue (2)'",
      btn.cget("text") == "Continue (2)", repr(btn.cget("text")))

state["label"], state["blockers"] = "Next Day", []
_refresh(gui)
root.update_idletasks()
check("R8(i) blocker resolved -> 'Next Day' (no staleness)",
      btn.cget("text") == "Next Day", repr(btn.cget("text")))

# --- R8(i): the refresh hooks are wired -----------------------------------
_src = open("main.py").read()


def _has_hook(snippet, where):
    return snippet in _src


check("R8(i) update_all_views refreshes the pill",
      "def update_all_views" in _src
      and _src.index("def update_all_views")
      < _src.index("self.refresh_next_day_button()",
                   _src.index("def update_all_views")))
# simulate_day finally: the refresh sits after _set_continue_feedback(False)
_fin = _src.index("Restore the Continue button")
check("R8(i) simulate_day finally refreshes the pill",
      "self.refresh_next_day_button()" in _src[_fin:_fin + 800])
# blocker dialog jump action
_go = _src.index("def _go():")
check("R8(i) blocker dialog jump action refreshes the pill",
      "self.refresh_next_day_button()" in _src[_go:_go + 600])

# --- R8(ii): pattern lineage ------------------------------------------------
import dashboard_home
check("R8(ii) reuses existing busy pattern (set_continue_busy)",
      hasattr(dashboard_home, "HomeDashboard")
      and hasattr(dashboard_home.HomeDashboard, "set_continue_busy"))
from windows import TradeWindow
check("R8(ii) TradeWindow has _set_busy helper",
      hasattr(TradeWindow, "_set_busy"))
_wsrc = open("windows.py").read()
check("R8(ii) partner switch is wrapped in busy",
      '"Loading trade partner..."' in _wsrc
      and "badge_fn=_badge_fn" in _wsrc)
check("R8(ii) user list refresh is wrapped in busy",
      '"Loading roster..."' in _wsrc)

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
