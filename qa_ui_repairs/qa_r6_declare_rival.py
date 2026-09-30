"""QA R6: "Declare Rival" context actions register through the rivalry system.

Right-click a player card (player_context_menu) or a staff row
(staff_management_window) as the user GM -> "Declare Rival" must:
  - register via reputation_system.declare_rivalry (heat 70, user_declared,
    declared floor 40 -- the same entry point the Morale window's
    DeclareRivalPopup uses),
  - post to the news feed AND the user team's inbox (headlines),
  - refuse own-club targets with an explanation, and be idempotent on
    repeat declarations.

Run headless:  DISPLAY=:99 python3 qa_ui_repairs/qa_r6_declare_rival.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

import tkinter as tk
from types import SimpleNamespace
from datetime import date

import customtkinter as ctk

from game_classes import Player, PlayerPosition, Staff, StaffRole
import player_context_menu as pcm
from player_context_menu import PlayerContextMenu
import staff_management_window as smw

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


# Stub blocking messageboxes: record instead of showing.
dialogs = []


class _MB:
    @staticmethod
    def showinfo(t, m, **kw):
        dialogs.append(("info", t, m))

    @staticmethod
    def showwarning(t, m, **kw):
        dialogs.append(("warning", t, m))

    @staticmethod
    def showerror(t, m, **kw):
        dialogs.append(("error", t, m))


pcm.messagebox = _MB
smw.messagebox = _MB

# Record context-menu labels + commands.
recorded = []
_real_menu = tk.Menu


class RecMenu(_real_menu):
    def add_command(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        recorded.append((kw.get("label"), kw.get("command")))
        return super().add_command(cnf, **kw)


tk.Menu = RecMenu

root = ctk.CTk()
root.withdraw()


def mkp(pid, fn, ln):
    p = Player(first_name=fn, last_name=ln, age=24,
               primary_position=PlayerPosition.CENTER)
    p.id = pid
    return p


def mks(sid, fn, ln, role):
    s = Staff(first_name=fn, last_name=ln, role=role)
    s.id = sid
    return s


class FakeInbox:
    def __init__(self):
        self.messages = []

    def add_message(self, m):
        self.messages.append(m)


user_players = [mkp("u1", "Liam", "Lavoie"), mkp("u2", "Aatu", "Raty")]
opp_players = [mkp("o1", "Auston", "Matthews"), mkp("o2", "Connor", "McDavid")]
user_coach = mks("c1", "Dan", "Davis", StaffRole.HEAD_COACH)
opp_coach = mks("c2", "Paul", "Wilson", StaffRole.HEAD_COACH)
user_inbox = FakeInbox()
user_team = SimpleNamespace(
    team_name="User Club", roster=user_players, ahl_roster=[], prospects=[],
    staff=[user_coach], is_user_team=True, inbox=user_inbox,
    gm_name="Test GM")
opp_team = SimpleNamespace(
    team_name="Opp Club", roster=opp_players, ahl_roster=[], prospects=[],
    staff=[opp_coach], is_user_team=False, inbox=FakeInbox())
news = []
league = SimpleNamespace(teams=[user_team, opp_team], rivalries=[])
gm = SimpleNamespace(user_team=user_team, league=league,
                     current_date=date(2026, 9, 29))


class FakeApp:
    user_team = user_team
    game_manager = gm

    def add_news(self, story):
        news.append(story)


app = FakeApp()

# --- 1. player context menu carries the action --------------------------------
host = tk.Frame(root)
host.parent = SimpleNamespace(parent=app)
pmenu = PlayerContextMenu(host)
recorded.clear()
fake_event = SimpleNamespace(x_root=0, y_root=0, widget=host)
try:
    pmenu.show_context_menu(fake_event, opp_players[0])
except Exception as e:
    print(f"(menu popup raised {e!r} -- continuing)")
labels = [lb for lb, _ in recorded]
check("'Declare Rival' on the player context menu", "Declare Rival" in labels,
      str(labels))
rival_cmd = next((cmd for lb, cmd in recorded if lb == "Declare Rival"), None)
check("Declare Rival menu entry is wired to a command", callable(rival_cmd))

# --- 2. declaring on an opposing player registers -----------------------------
dialogs.clear()
rival_cmd()
import reputation_system as rs
recs = [r for r in league.rivalries if r.get("user_declared")]
check("rivalry record registered", len(recs) == 1, f"got {len(recs)}")
rec = recs[0]
check("heat set to 70", rec.get("intensity") == 70, str(rec.get("intensity")))
check("declared floor 40 (never cools below)", rec.get("declared_floor") == 40)
check("origin marked declared", rec.get("origin") == "declared")
check("targets the right player",
      rec.get("b_name") == "Auston Matthews" or rec.get("a_name") == "Auston Matthews",
      f"{rec.get('a_name')} vs {rec.get('b_name')}")
check("news feed reflects the declaration", len(news) == 1, str(news))
check("user inbox reflects the declaration",
      len(user_inbox.messages) == 1, f"got {len(user_inbox.messages)}")
if user_inbox.messages:
    m = user_inbox.messages[0]
    check("inbox copy is a milestone",
          bool(getattr(m, "is_milestone", False)),
          f"milestone={getattr(m, 'is_milestone', None)}")
check("confirmation dialog shown",
      any(k == "info" and t == "Rival Declared" for k, t, _ in dialogs),
      str([(k, t) for k, t, _ in dialogs]))

# --- 3. repeat declaration is idempotent ---------------------------------------
dialogs.clear()
rival_cmd()
check("no duplicate record on repeat declaration",
      len([r for r in league.rivalries if r.get("user_declared")]) == 1)
check("repeat reports already-declared",
      any("already declared" in m for _, _, m in dialogs), str(dialogs))

# --- 4. own-club player refused --------------------------------------------------
dialogs.clear()
recorded.clear()
try:
    pmenu.show_context_menu(fake_event, user_players[0])
except Exception:
    pass
own_cmd = next((cmd for lb, cmd in recorded if lb == "Declare Rival"), None)
before = len(league.rivalries)
own_cmd()
check("no rivalry registered for own-club player",
      len(league.rivalries) == before)
check("refusal explains the action is for opponents",
      any("opposing" in m for _, _, m in dialogs), str(dialogs))

# --- 5. staff table context menu carries the action ------------------------------
class FakeStaffApp:
    game_manager = gm
    user_team = user_team
    open_windows = {}
    BG_COLOR = "#1a1a1a"
    FONT_FAMILY = "Segoe UI"

    def add_news(self, story):
        news.append(story)


sapp = FakeStaffApp()
sview = smw.StaffManagementView(root, app=sapp)
sview.pack()
root.update_idletasks()
items = sview.current_staff_tree.get_children()
check("staff table populated", len(items) >= 1, f"got {len(items)}")
bbox = sview.current_staff_tree.bbox(items[0])
fake_staff_event = SimpleNamespace(x_root=0, y_root=100,
                                   y=(bbox[1] + 2) if bbox else 5,
                                   widget=sview.current_staff_tree)
recorded.clear()
try:
    sview.show_staff_context_menu(fake_staff_event)
except Exception as e:
    print(f"(staff menu popup raised {e!r} -- continuing)")
slabels = [lb for lb, _ in recorded]
check("'Declare Rival' on the staff table menu", "Declare Rival" in slabels,
      str(slabels))

# --- 6. declaring on opposing staff registers ------------------------------------
dialogs.clear()
sview._declare_rival_staff(opp_coach)
staff_recs = [r for r in league.rivalries
              if r.get("user_declared") and r.get("kind") == "gm_coach"]
names = {(r.get("a_name"), r.get("b_name")) for r in staff_recs}
check("staff rivalry registered through the rivalry system",
      any("Paul Wilson" in n for pair in names for n in pair),
      str(names))
prec = next(r for r in staff_recs
            if "Paul Wilson" in (r.get("a_name"), r.get("b_name")))
check("staff beef heat set to 70", prec.get("intensity") == 70)
check("staff declaration hits the news feed", len(news) == 2, str(news))
check("staff declaration hits the inbox", len(user_inbox.messages) == 2)
check("staff confirmation dialog shown",
      any(k == "info" and t == "Rival Declared" for k, t, _ in dialogs))

# --- 7. own staff refused ----------------------------------------------------------
dialogs.clear()
before = len(league.rivalries)
sview._declare_rival_staff(user_coach)
check("no rivalry registered for own staff", len(league.rivalries) == before)
check("own-staff refusal explains the action is for opponents",
      any("opposing" in m for _, _, m in dialogs), str(dialogs))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
tk.Menu = _real_menu
root.destroy()
sys.exit(1 if FAIL else 0)
