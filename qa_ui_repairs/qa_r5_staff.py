"""QA R5: Staff Management -- reassign dropdown lists all roles; morale is /100.

(i)  The "New Role" dropdown in the reassign dialog must offer every
     StaffRole value (not just the current role); the unique-role guard
     (GM / Head Coach) still runs at confirm time. Reassigning works.
(ii) Staff morale is a 1-100 scale (game_classes.Staff.morale); the table
     must show "<n>/100", with high/low tags and status labels scaled to
     1-100.

Run headless:  DISPLAY=:99 python3 qa_ui_repairs/qa_r5_staff.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

from types import SimpleNamespace

import customtkinter as ctk

from game_classes import Staff, StaffRole
import staff_management_window as smw

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def walk(w, pred, out=None):
    out = [] if out is None else out
    try:
        if pred(w):
            out.append(w)
        children = w.winfo_children()
    except Exception:
        return out
    for c in children:
        walk(c, pred, out)
    return out


# Stub out in-game message boxes (no popup manager headless -> would block).
calls = []


class _MB:
    @staticmethod
    def showinfo(t, m, **kw):
        calls.append(("info", t, m))

    @staticmethod
    def showwarning(t, m, **kw):
        calls.append(("warning", t, m))

    @staticmethod
    def showerror(t, m, **kw):
        calls.append(("error", t, m))


smw.messagebox = _MB

root = ctk.CTk()
root.withdraw()

dan = Staff(first_name="Dan", last_name="Davis", role=StaffRole.HEAD_COACH,
            morale=82, salary=364694, contract_years=5)
paul = Staff(first_name="Paul", last_name="Wilson", role=StaffRole.GENERAL_MANAGER,
             morale=55, salary=343016, contract_years=2)
amy = Staff(first_name="Amy", last_name="Wong", role=StaffRole.ASSISTANT_COACH,
            morale=25, salary=150000, contract_years=3)

team = SimpleNamespace(staff=[dan, paul, amy])
app = SimpleNamespace(game_manager=SimpleNamespace(user_team=team, league=None),
                      open_windows={}, BG_COLOR="#1a1a1a", FONT_FAMILY="Segoe UI")

view = smw.StaffManagementView(root, app=app)
view.pack()
root.update_idletasks()

# --- (ii) morale column ------------------------------------------------------
cols = list(view.current_staff_tree["columns"])
mi, si = cols.index("morale"), cols.index("status")
cell = {}
for item in view.current_staff_tree.get_children():
    vals = view.current_staff_tree.item(item, "values")
    cell[vals[1]] = (vals[mi], vals[si], view.current_staff_tree.item(item, "tags"))

check("Dan Davis morale reads 82/100", cell["Dan Davis"][0] == "82/100",
      str(cell["Dan Davis"][0]))
check("Paul Wilson morale reads 55/100", cell["Paul Wilson"][0] == "55/100",
      str(cell["Paul Wilson"][0]))
check("Amy Wong morale reads 25/100", cell["Amy Wong"][0] == "25/100",
      str(cell["Amy Wong"][0]))
check("no /20 denominator anywhere in the table",
      all("/20" not in v for v, _, _ in cell.values()))

check("high morale tagged (>=75)", "high_morale" in cell["Dan Davis"][2],
      str(cell["Dan Davis"][2]))
check("low morale tagged (<=40)", "low_morale" in cell["Amy Wong"][2],
      str(cell["Amy Wong"][2]))
check("mid morale untagged", "high_morale" not in cell["Paul Wilson"][2]
      and "low_morale" not in cell["Paul Wilson"][2],
      str(cell["Paul Wilson"][2]))

check("status Happy at 82", view.get_staff_status(dan) == "Happy",
      view.get_staff_status(dan))
check("status Content at 55", view.get_staff_status(paul) == "Content",
      view.get_staff_status(paul))
check("status Unhappy at 25", view.get_staff_status(amy) == "Unhappy",
      view.get_staff_status(amy))
expiring = Staff(first_name="Ex", last_name="Piring", role=StaffRole.ASSISTANT_COACH,
                 morale=90, contract_years=1)
check("expiring contract still flags Expiring",
      view.get_staff_status(expiring) == "Expiring")

# --- (i) reassign dropdown ---------------------------------------------------
n_roles = len(list(StaffRole))
view.selected_staff.add(dan.id)
view.reassign_selected_staff()
root.update_idletasks()

combos = [c for c in walk(view, lambda w: type(w).__name__ == "CTkComboBox")
          if len(c.cget("values")) > 10]
check("reassign dialog opened with a role combobox", len(combos) == 1,
      f"found {len(combos)}")
combo = combos[0]
vals = list(combo.cget("values"))
check(f"dropdown lists ALL {n_roles} StaffRole values",
      len(vals) == n_roles and set(vals) == {r.value for r in StaffRole},
      f"got {len(vals)}")
check("current role present among options", StaffRole.HEAD_COACH.value in vals)
check("closed combo no longer reads as 'only the current role'",
      combo.get() != StaffRole.HEAD_COACH.value, combo.get())

# Reassign Dan: Head Coach -> Assistant Coach (non-unique, must succeed)
combo.set(StaffRole.ASSISTANT_COACH.value)
confirm = [b for b in walk(view, lambda w: type(w).__name__ == "CTkButton")
           if b.cget("text") == "Confirm"]
check("Confirm button present", len(confirm) == 1, f"found {len(confirm)}")
confirm[0].invoke()
root.update_idletasks()
check("reassign applied to the staff object",
      dan.role == StaffRole.ASSISTANT_COACH, str(dan.role))
check("success message shown",
      any(k == "info" and "reassigned" in m for k, _, m in calls), str(calls))

# Unique-role guard: Paul is GM; Amy -> General Manager must be refused
calls.clear()
view.selected_staff = {amy.id}
view.reassign_selected_staff()
root.update_idletasks()
combo2 = [c for c in walk(view, lambda w: type(w).__name__ == "CTkComboBox")
          if len(c.cget("values")) > 10][0]
combo2.set(StaffRole.GENERAL_MANAGER.value)
[b for b in walk(view, lambda w: type(w).__name__ == "CTkButton")
 if b.cget("text") == "Confirm"][0].invoke()
root.update_idletasks()
check("unique-role conflict blocked",
      any(k == "error" and "Role Conflict" in t for k, t, _ in calls),
      str(calls))
check("blocked reassign left the role unchanged",
      amy.role == StaffRole.ASSISTANT_COACH, str(amy.role))

# Bulk dialog: per-staff combos also carry the full list. Scope the search to
# the newest popup (the earlier conflict-blocked dialog is still open).
before = {id(c) for c in walk(view, lambda w: type(w).__name__ == "InGamePopup")}
view.selected_staff = {dan.id, amy.id}
view.reassign_multiple_staff([dan, amy])
root.update_idletasks()
new_popups = [c for c in walk(view, lambda w: type(w).__name__ == "InGamePopup")
              if id(c) not in before]
check("bulk reassign dialog opened", len(new_popups) == 1,
      f"found {len(new_popups)}")
bulk = ([c for c in walk(new_popups[0], lambda w: type(w).__name__ == "CTkComboBox")
         if len(c.cget("values")) > 10] if new_popups else [])
check("bulk dialog lists full roles per staff member",
      len(bulk) == 2 and all(len(c.cget("values")) == n_roles for c in bulk),
      f"found {len(bulk)} combos")

# --- (iii) staff redesign: per-team coverage, pools, backfill -----------------
import database_generator as dg

# Role design: hireable + background partition all 24 roles, no overlap.
all_roles = set(StaffRole)
check("hireable + background roles partition all 24 StaffRoles",
      set(dg.HIREABLE_STAFF_ROLES) | set(dg.BACKGROUND_STAFF_ROLES) == all_roles
      and not (set(dg.HIREABLE_STAFF_ROLES) & set(dg.BACKGROUND_STAFF_ROLES)),
      f"hireable={len(dg.HIREABLE_STAFF_ROLES)} background={len(dg.BACKGROUND_STAFF_ROLES)}")
check("physio-type roles are background (never hireable)",
      all(r in dg.BACKGROUND_STAFF_ROLES for r in
          (StaffRole.TEAM_DOCTOR, StaffRole.PHYSIOTHERAPIST,
           StaffRole.EQUIPMENT_MANAGER)))

# New-game generation: every team staffed across all roles.
gen = dg.DatabaseGenerator.__new__(dg.DatabaseGenerator)
new_team = SimpleNamespace(team_name="Buffalo Sabres", staff=[])  # small market
gen._generate_team_staff([new_team])
gen_roles = {}
for s in new_team.staff:
    gen_roles[s.role] = gen_roles.get(s.role, 0) + 1
check("new-game team covers all 24 roles", len(gen_roles) == 24,
      f"got {len(gen_roles)}")
# The AHL affiliate gets its own GM + head coach by design; the NHL club
# itself must have exactly one of each.
nhl_staff = [s for s in new_team.staff
             if getattr(s, "assignment", "nhl") == "nhl"]
nhl_gm = sum(1 for s in nhl_staff if s.role == StaffRole.GENERAL_MANAGER)
nhl_hc = sum(1 for s in nhl_staff if s.role == StaffRole.HEAD_COACH)
check("exactly one NHL GM and one NHL head coach generated",
      nhl_gm == 1 and nhl_hc == 1, f"gm={nhl_gm} hc={nhl_hc}")
check("AHL affiliate has its own GM + head coach (farm pool)",
      any(s.role == StaffRole.HEAD_COACH
          and getattr(s, "assignment", "") == "ahl" for s in new_team.staff))
payroll = sum(s.salary for s in new_team.staff)
check("full staff fits the small-market ($7M) budget with room to hire",
      payroll < 7_000_000,
      f"payroll=${payroll:,}")
check("staff budget assigned", new_team.staff_budget == 7_000_000)
# Sensible ratings distribution: Gaussian-ish, bounded 30-99.
ovrs = [s.overall_rating for s in new_team.staff]
check("generated staff ratings bounded and sane",
      all(30 <= o <= 99 for o in ovrs) and 45 <= sum(ovrs) / len(ovrs) <= 85,
      f"mean={sum(ovrs)/len(ovrs):.1f}")

# FA pool: dense, bounded, hireable-only, every role has depth.
pool = gen._generate_free_agent_staff(180)
pool_roles = {}
for s in pool:
    pool_roles[s.role] = pool_roles.get(s.role, 0) + 1
check("FA pool bounded (~180)", 150 <= len(pool) <= 220, f"got {len(pool)}")
check("every hireable role has depth (>=6 in pool)",
      all(pool_roles.get(r, 0) >= 6 for r in dg.HIREABLE_STAFF_ROLES),
      str({r.value: pool_roles.get(r, 0)
           for r in dg.HIREABLE_STAFF_ROLES if pool_roles.get(r, 0) < 6}))
check("no background roles in the FA pool",
      not any(pool_roles.get(r, 0) for r in dg.BACKGROUND_STAFF_ROLES))

# Backfill: an old-save club with only HC + GM gets topped up additively.
old_hc = Staff(first_name="Old", last_name="Coach", role=StaffRole.HEAD_COACH)
old_gm = Staff(first_name="Old", last_name="Gm", role=StaffRole.GENERAL_MANAGER)
old_team = SimpleNamespace(team_name="Old Club", staff=[old_hc, old_gm])
old_league = SimpleNamespace(teams=[old_team], free_agent_staff=[])
dg.backfill_team_staff(old_league)
bf_roles = {}
for s in old_team.staff:
    bf_roles[s.role] = bf_roles.get(s.role, 0) + 1
check("backfill covers all 24 roles on an old-save club",
      len(bf_roles) == 24, f"got {len(bf_roles)}")
check("backfill never duplicates the unique roles",
      bf_roles.get(StaffRole.GENERAL_MANAGER) == 1
      and bf_roles.get(StaffRole.HEAD_COACH) == 1)
check("backfill keeps pre-existing staff objects",
      old_hc in old_team.staff and old_gm in old_team.staff)
check("backfill sets a missing staff budget",
      getattr(old_team, "staff_budget", None) is not None)
bf_pool = {}
for s in old_league.free_agent_staff:
    bf_pool[s.role] = bf_pool.get(s.role, 0) + 1
check("backfill tops up the FA pool minimums",
      all(bf_pool.get(r, 0) >= 6 for r in dg.HIREABLE_STAFF_ROLES))
# Backfill is idempotent.
n_before = len(old_team.staff)
dg.backfill_team_staff(old_league)
check("backfill idempotent (second run adds nothing)",
      len(old_team.staff) == n_before,
      f"{n_before} -> {len(old_team.staff)}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
root.destroy()
sys.exit(1 if FAIL else 0)
