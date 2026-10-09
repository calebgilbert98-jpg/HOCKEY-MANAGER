# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Headless UI smoke: Tactics screen League Intel section."""
import sys
from types import SimpleNamespace
sys.path.insert(0, ".")

import tkinter as tk
import tactics as tx

PASS, FAIL = [], []
def check(n, c, d=""):
    (PASS if c else FAIL).append(n)
    print(("  ok  " if c else "  FAIL") + f" {n}" + (f" -- {d}" if d and not c else ""))

def coach(**kw):
    base = dict(full_name="Test Coach", control_need=40, gm_trust=70,
                adaptability=60, first_nhl_chair=False, years_with_team=3,
                controversy=30, reputation=60, leadership=60, happiness=70,
                morale=70, discipline=65, motivating=65, man_management=65,
                tactical_knowledge=65, game_preparation=65,
                working_with_youngsters=50, player_development=50)
    base.update(kw); c = SimpleNamespace(**base)
    c.role = SimpleNamespace(value="Head Coach"); c.id = 1
    return c

root = tk.Tk(); root.withdraw()
team = SimpleNamespace(team_name="Test Club", roster=[], staff=[coach()],
                       tactics_control="coach")
opp = SimpleNamespace(team_name="Rival Club", roster=[], staff=[coach()],
                      tactics_control="coach")
tx.ensure_team_tactics(team); tx.ensure_team_tactics(opp)
app = tk.Toplevel(root); app.withdraw()
app.user_team = team; app.open_windows = {}
app.league = SimpleNamespace(
    standings={"Test Club": {"W": 20, "L": 15, "OTL": 3}},
    teams=[team, opp])
app.mp_client = None
app.add_news = lambda line: None

from tactics_window import TacticsWindow
w = TacticsWindow(app)
root.update()

check("default section is Whiteboard, 7 cards",
      w._section == "whiteboard" and len(w._cards.winfo_children()) == 7,
      str(len(w._cards.winfo_children())))
check("footer visible in whiteboard", not w._footer_hidden)

# Switch to intel with no intel recorded: empty states, footer hidden.
w._on_section("League Intel")
root.update()
texts = []
def collect(widget):
    for ch in widget.winfo_children():
        if isinstance(ch, tk.Label) or ch.__class__.__name__.startswith("CTkLabel"):
            try: texts.append(ch.cget("text"))
            except Exception: pass
        collect(ch)
collect(w._cards)
check("intel headers present",
      any("THE BOOK ON YOU" in t for t in texts)
      and any("THE CHESSBOARD" in t for t in texts))
check("no-book empty state shows",
      any("No team has a real book" in t for t in texts))
check("footer hidden in intel", w._footer_hidden)
check("chessboard maps every current system",
      sum(1 for ch in w._cards.winfo_children()
          if ch.__class__.__name__ == "CTkFrame") == 7,
      str(len(w._cards.winfo_children())))

# Record hot intel for the opponent, then refresh.
for _ in range(3):
    tx.record_tactical_intel(opp, team, 5, ai_goals=1, user_shots=35,
                             user_pp_pct=0.35)
w.refresh(); root.update()
texts2 = []
def collect2(widget):
    for ch in widget.winfo_children():
        if ch.__class__.__name__.startswith("CTkLabel"):
            try: texts2.append(ch.cget("text"))
            except Exception: pass
        collect2(ch)
collect2(w._cards)
check("book card names the hot opponent",
      any("Rival Club" in t for t in texts2))
check("book card shows the expected answer",
      any(t.startswith("Expect:") for t in texts2),
      str([t for t in texts2 if "Expect" in t])[:200])

# Back to whiteboard: footer returns, cards rebuild.
w._on_section("Whiteboard")
root.update()
check("back to whiteboard restores 7 cards + footer",
      w._section == "whiteboard" and not w._footer_hidden
      and len(w._cards.winfo_children()) == 7,
      str(len(w._cards.winfo_children())))
w.destroy()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
