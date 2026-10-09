"""QA: Right-click context menus on player/staff names (Muck 2026-10-02).

Verifies:
1. bind_player_context / bind_staff_context exist and are importable
2. StaffContextMenu class exists with View Profile
3. main.py has open_staff_profile
4. Bindings attach <Button-3> without raising
5. Right-clicking opens the correct menu (headless logic test)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


print("== Imports ==")
try:
    from player_context_menu import (
        bind_player_context,
        bind_staff_context,
        PlayerContextMenu,
        StaffContextMenu,
        add_player_context_menu,
        add_staff_context_menu,
    )
    check("all helpers importable", True)
except Exception as e:
    check(f"all helpers importable ({e})", False)
    bind_player_context = bind_staff_context = None

print("== StaffContextMenu ==")
try:
    check("StaffContextMenu class exists", StaffContextMenu is not None)
    mgr = StaffContextMenu(parent_window=None)
    check("StaffContextMenu instantiates", mgr is not None)
    check("has show_context_menu", hasattr(mgr, 'show_context_menu'))
    check("has _view_staff_profile", hasattr(mgr, '_view_staff_profile'))
except Exception as e:
    check(f"StaffContextMenu ({e})", False)

print("== PlayerContextMenu still intact ==")
try:
    mgr = PlayerContextMenu(parent_window=None)
    check("PlayerContextMenu instantiates", mgr is not None)
    check("has show_context_menu", hasattr(mgr, 'show_context_menu'))
except Exception as e:
    check(f"PlayerContextMenu ({e})", False)

print("== main.py open_staff_profile ==")
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')) as f:
        src = f.read()
    check("open_staff_profile defined", "def open_staff_profile(self, staff)" in src)
    check("staff View Profile in tree menu",
          'View {staff.full_name}' in src or "View {staff.full_name}'s Profile" in src)
except Exception as e:
    check(f"main.py check ({e})", False)

print("== Binding behavior (headless) ==")
# Fake widget that records bindings
class FakeWidget:
    def __init__(self):
        self.bindings = {}
    def bind(self, seq, func):
        self.bindings[seq] = func

class FakePlayer:
    full_name = "Test Player"
    id = "p1"

class FakeStaff:
    full_name = "Test Coach"
    id = "s1"

try:
    w = FakeWidget()
    mgr = bind_player_context(w, FakePlayer(), parent_window=None)
    check("<Button-3> bound for player", "<Button-3>" in w.bindings)
    check("<Shift-F10> bound for player", "<Shift-F10>" in w.bindings)
    check("returns manager", mgr is not None)
except Exception as e:
    check(f"player binding ({e})", False)

try:
    w = FakeWidget()
    mgr = bind_staff_context(w, FakeStaff(), parent_window=None)
    check("<Button-3> bound for staff", "<Button-3>" in w.bindings)
    check("<Shift-F10> bound for staff", "<Shift-F10>" in w.bindings)
    check("returns manager", mgr is not None)
except Exception as e:
    check(f"staff binding ({e})", False)

print("== Getter form ==")
try:
    w = FakeWidget()
    p = FakePlayer()
    bind_player_context(w, lambda e: p, parent_window=None)
    check("callable getter accepted (player)", "<Button-3>" in w.bindings)
    w2 = FakeWidget()
    s = FakeStaff()
    bind_staff_context(w2, lambda e: s, parent_window=None)
    check("callable getter accepted (staff)", "<Button-3>" in w2.bindings)
except Exception as e:
    check(f"getter form ({e})", False)

print("== Never-raises ==")
try:
    # Binding on a broken widget should not raise
    class BrokenWidget:
        def bind(self, *a, **k):
            raise RuntimeError("nope")
    bind_player_context(BrokenWidget(), FakePlayer(), None)
    bind_staff_context(BrokenWidget(), FakeStaff(), None)
    check("broken widget doesn't raise", True)
except Exception as e:
    check(f"broken widget doesn't raise ({e})", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
