"""QA: staff contract negotiation is a full-screen jump (not a popup).

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_staff_contract.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

import windows
from game_classes import Staff, StaffRole

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def make_staff():
    s = Staff(first_name="Test", last_name="Coach", age=50,
              role=StaffRole.HEAD_COACH, nationality="CAN")
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


# --- 1. entry point jumps via show_screen, no popup -------------------------
jump = {}
staff = make_staff()
fake_self = SimpleNamespace(
    app=SimpleNamespace(
        show_screen=lambda sid, title, cls, *a, **k: jump.update(
            sid=sid, title=title, cls=cls, args=a, kwargs=k)))
windows.FreeAgencyView._open_staff_contract_dialog(fake_self, staff)
check("entry point uses show_screen", bool(jump))
check("screen id is staff_contract", jump.get("sid") == "staff_contract")
check("view class is StaffContractView",
      jump.get("cls") is windows.StaffContractView)
check("staffer passed through", jump.get("args") == (staff,))

# --- 2. view builds with no Toplevel ----------------------------------------
msgs = MsgBox()
windows.messagebox = msgs  # patch the popup_system binding in windows
signed = []
closed = []


def fake_sign(st, salary, years):
    signed.append((st, salary, years))
    return True


gm = SimpleNamespace(user_team=SimpleNamespace(prestige=60),
                     sign_free_agent_staff=fake_sign)
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


t = texts(view)
check("asking banner names the ask",
      any("$2,500,000" in x for x in t))
check("acceptance chance readout present",
      any("Estimated acceptance chance" in x for x in t))
check("make-offer + back buttons present",
      any("Make Offer" in x for x in t) and any("Back" in x for x in t))

# --- 3. accept path: roll-first, signs, refreshes, closes -------------------
import random
real_random = random.random
random.random = lambda: 0.0  # force accept
try:
    view._resolve_staff_offer(staff, 2, 2_500_000)
finally:
    random.random = real_random
root.update()
check("accept signs the staffer", len(signed) == 1)
check("accept uses offered terms",
      signed and signed[0][1] == 2_500_000 and signed[0][2] == 2)
check("accept shows confirmation",
      any(c[0] == "info" and "Accepted" in c[1] for c in msgs.calls))
check("accept refreshes views", "refreshed" in closed)
check("accept closes the screen", "closed" in closed)

# --- 4. decline path: no signing, screen stays ------------------------------
msgs.calls.clear()
signed.clear()
closed.clear()
view2 = windows.StaffContractView(root, staff, app=app)
view2._close_screen = lambda: closed.append("closed")
root.update()
random.random = lambda: 0.999  # force decline
try:
    view2._resolve_staff_offer(staff, 2, 2_000_000)
finally:
    random.random = real_random
root.update()
check("decline does not sign", not signed)
check("decline shows declined notice",
      any(c[0] == "info" and "Declined" in c[1] for c in msgs.calls))
check("decline keeps the screen open", "closed" not in closed)

# --- 5. sign failure: error shown, screen stays ------------------------------
msgs.calls.clear()
gm_fail = SimpleNamespace(user_team=SimpleNamespace(prestige=60),
                          sign_free_agent_staff=lambda *a: False)
app_fail = SimpleNamespace(game_manager=gm_fail,
                           update_all_views=lambda: None)
view3 = windows.StaffContractView(root, staff, app=app_fail)
closed3 = []
view3._close_screen = lambda: closed3.append("closed")
root.update()
random.random = lambda: 0.0
try:
    view3._resolve_staff_offer(staff, 2, 2_500_000)
finally:
    random.random = real_random
check("sign failure shows error",
      any(c[0] == "error" for c in msgs.calls))
check("sign failure keeps the screen open", not closed3)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
