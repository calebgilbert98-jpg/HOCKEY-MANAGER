"""QA: staff contract negotiation is a full-screen jump (not a popup),
with a free dollar offer entry and a league-wide staff budget gate.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_staff_contract.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

import windows
from game_classes import Staff, StaffRole, staff_market_ask

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def make_staff():
    s = Staff(first_name="Test", last_name="Coach", age=50,
              role=StaffRole.HEAD_COACH, nationality="CAN")
    s.reputation = 70
    s.salary = 2_500_000
    s.contract_years = 3
    return s


class MsgBox:
    def __init__(self):
        self.calls = []

    def showinfo(self, title, msg):
        self.calls.append(("info", title, msg))

    def showerror(self, title, msg):
        self.calls.append(("error", title, msg))


ASK = staff_market_ask(make_staff())

# --- 1. entry point jumps via show_screen, no popup -------------------------
jump = {}
staff = make_staff()
fake_self = SimpleNamespace(
    app=SimpleNamespace(
        game_manager=SimpleNamespace(user_team=SimpleNamespace(),
                                      current_date=None),
        show_screen=lambda sid, title, cls, *a, **k: jump.update(
            sid=sid, title=title, cls=cls, args=a, kwargs=k)))
windows.FreeAgencyView._open_staff_contract_dialog(fake_self, staff)
check("entry point uses show_screen", bool(jump))
check("screen id is staff_contract", jump.get("sid") == "staff_contract")
check("view class is StaffContractView",
      jump.get("cls") is windows.StaffContractView)
check("staffer passed through", jump.get("args") == (staff,))
check("hire_source defaults to free_agent",
      jump.get("kwargs", {}).get("hire_source") == "free_agent")

# --- 2. view builds with no Toplevel ----------------------------------------
msgs = MsgBox()
windows.messagebox = msgs  # patch the popup_system binding in windows
signed = []
closed = []


def fake_sign(st, salary, years):
    signed.append((st, salary, years))
    return True


team_ns = SimpleNamespace(prestige=60, staff_budget=10_000_000,
                          staff_payroll=lambda: 3_000_000,
                          staff_budget_remaining=lambda: 7_000_000)
gm = SimpleNamespace(user_team=team_ns, sign_free_agent_staff=fake_sign)
app = SimpleNamespace(game_manager=gm,
                      update_all_views=lambda: closed.append("refreshed"))

root = ctk.CTk()
root.withdraw()
view = windows.StaffContractView(root, staff, app=app)
view._close_screen = lambda: closed.append("closed")
root.update()
root.update_idletasks()
check("view builds", view.winfo_exists() and bool(view.winfo_children()))
check("no Toplevel popup opened",
      not [w for w in root.winfo_children()
           if w.winfo_class() == "Toplevel"])


def texts(w):
    out = []
    try:
        out.append(str(w.cget("text")))
    except Exception:
        pass
    for ch in w.winfo_children():
        out.extend(texts(ch))
    return out


def entries(w):
    out = []
    if "entry" in w.winfo_class().lower():
        out.append(w)
    for ch in w.winfo_children():
        out.extend(entries(ch))
    return out


t = texts(view)
check("asking banner names the market ask",
      any(f"${ASK:,}" in x for x in t), f"ask=${ASK:,}")
check("budget line shown",
      any("Club staff budget" in x for x in t))
check("budget line shows availability",
      any("$7,000,000" in x for x in t))
check("salary entry prefilled with the ask",
      any(e.get().replace(",", "") == str(ASK) for e in entries(view)))
check("acceptance chance readout present",
      any("Estimated acceptance chance" in x for x in t))
check("make-offer + back buttons present",
      any("Make Offer" in x for x in t) and any("Back" in x for x in t))


def set_offer(v, offer):
    v._salary_entry.delete(0, "end")
    v._salary_entry.insert(0, f"{offer:,}")
    root.update()


# --- 3. accept path: roll-first, signs, refreshes, closes -------------------
import random
real_random = random.random
set_offer(view, ASK)
random.random = lambda: 0.0  # force accept
try:
    view._resolve_staff_offer(staff, 2)
finally:
    random.random = real_random
root.update()
check("accept signs the staffer", len(signed) == 1)
check("accept uses the typed offer",
      signed and signed[0][1] == ASK and signed[0][2] == 2,
      f"signed={signed}")
check("accept shows confirmation",
      any(c[0] == "info" and "Accepted" in c[1] for c in msgs.calls))
check("accept refreshes views", "refreshed" in closed)
check("accept closes the screen", "closed" in closed)

# --- 4. tailored offer: below-ask exact dollars ------------------------------
msgs.calls.clear()
signed.clear()
closed.clear()
view_t = windows.StaffContractView(root, staff, app=app)
view_t._close_screen = lambda: closed.append("closed")
root.update()
set_offer(view_t, 3_123_456)
check("tailored offer parses exact dollars",
      view_t._parse_offer() == 3_123_456)
random.random = lambda: 0.0
try:
    view_t._resolve_staff_offer(staff, 3)
finally:
    random.random = real_random
check("tailored offer signs at typed dollars",
      signed and signed[0][1] == 3_123_456 and signed[0][2] == 3)

# --- 5. over-budget offer is blocked ------------------------------------------
msgs.calls.clear()
signed.clear()
view_b = windows.StaffContractView(root, staff, app=app)
view_b._close_screen = lambda: None
root.update()
set_offer(view_b, 7_000_001)  # $1 over the $7M remaining
random.random = lambda: 0.0
try:
    view_b._resolve_staff_offer(staff, 2)
finally:
    random.random = real_random
check("over-budget offer blocked", not signed)
check("over-budget shows budget error",
      any(c[0] == "error" and "Budget" in c[1] for c in msgs.calls))

# --- 6. decline path: no signing, screen stays -------------------------------
msgs.calls.clear()
signed.clear()
closed.clear()
view2 = windows.StaffContractView(root, staff, app=app)
view2._close_screen = lambda: closed.append("closed")
root.update()
set_offer(view2, ASK)
random.random = lambda: 0.999  # force decline
try:
    view2._resolve_staff_offer(staff, 2)
finally:
    random.random = real_random
root.update()
check("decline does not sign", not signed)
check("decline shows declined notice",
      any(c[0] == "info" and "Declined" in c[1] for c in msgs.calls))
check("decline keeps the screen open", "closed" not in closed)

# --- 7. sign failure: error shown, screen stays ------------------------------
msgs.calls.clear()
team_ns2 = SimpleNamespace(prestige=60, staff_budget=10_000_000,
                           staff_payroll=lambda: 0,
                           staff_budget_remaining=lambda: 10_000_000)
gm_fail = SimpleNamespace(user_team=team_ns2,
                          sign_free_agent_staff=lambda *a: False)
app_fail = SimpleNamespace(game_manager=gm_fail,
                           update_all_views=lambda: None)
view3 = windows.StaffContractView(root, staff, app=app_fail)
closed3 = []
view3._close_screen = lambda: closed3.append("closed")
root.update()
set_offer(view3, ASK)
random.random = lambda: 0.0
try:
    view3._resolve_staff_offer(staff, 2)
finally:
    random.random = real_random
check("sign failure shows error",
      any(c[0] == "error" for c in msgs.calls))
check("sign failure keeps the screen open", not closed3)

# --- 8. AHL poach: source mutates only after a successful signing --------------
import random as _rand
msgs.calls.clear()
signed.clear()
poached = make_staff()
poached.assignment = "ahl"
from_team = SimpleNamespace(staff=[poached])
team_ns3 = SimpleNamespace(prestige=60, staff_budget=10_000_000,
                           staff_payroll=lambda: 0,
                           staff_budget_remaining=lambda: 10_000_000)
gm3 = SimpleNamespace(user_team=team_ns3, sign_free_agent_staff=fake_sign)
app3 = SimpleNamespace(game_manager=gm3,
                       league=SimpleNamespace(),
                       update_all_views=lambda: None)
view4 = windows.StaffContractView(root, poached, app=app3,
                                  hire_source="ahl_poach",
                                  from_team=from_team)
view4._close_screen = lambda: None
root.update()
set_offer(view4, ASK)
real_random = _rand.random
_rand.random = lambda: 0.0  # force accept
try:
    view4._resolve_staff_offer(poached, 2)
finally:
    _rand.random = real_random
check("poach accept signs the staffer", len(signed) == 1)
check("poached coach leaves the old club", poached not in from_team.staff)

# Failure AFTER acceptance must not strand the staffer anywhere.
msgs.calls.clear()
poached2 = make_staff()
poached2.assignment = "ahl"
from_team2 = SimpleNamespace(staff=[poached2])
gm_fail2 = SimpleNamespace(user_team=team_ns3,
                           sign_free_agent_staff=lambda *a: False)
app_fail2 = SimpleNamespace(game_manager=gm_fail2,
                            league=SimpleNamespace(),
                            update_all_views=lambda: None)
view5 = windows.StaffContractView(root, poached2, app=app_fail2,
                                  hire_source="ahl_poach",
                                  from_team=from_team2)
view5._close_screen = lambda: None
root.update()
set_offer(view5, ASK)
_rand.random = lambda: 0.0
try:
    view5._resolve_staff_offer(poached2, 2)
finally:
    _rand.random = real_random
check("failed sign keeps the staffer at the old club",
      poached2 in from_team2.staff)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
