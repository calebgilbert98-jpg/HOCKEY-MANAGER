# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: MP host-only gate on playoff bracket mutations.

- Client mode: Generate / Simulate Round / Simulate All are blocked with a
  "Host only" notice; the three buttons render disabled.
- Host mode and single-player: guard passes through to the normal flow
  (warning + fallback save path untouched).

Headless: DISPLAY=:99. Run: python3 qa_playoff_mpguard.py
"""
import os
import sys
from types import SimpleNamespace
from datetime import date

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
os.chdir("/home/hatch/workspace/HOCKEY-MANAGER")

import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
import popup_system as _ps
try:
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

import customtkinter as ctk
import ctk_theme as _ct
_ct.init_ctk_theme()

from playoff_system import PlayoffView

PASS, FAIL = [], []
NOTICES = []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name +
          (f" [{extra}]" if extra else ""))


# Capture in-game notices.
_orig_info = _ps.messagebox.showinfo
_orig_warn = _ps.messagebox.showwarning


def _cap_info(title, msg="", *a, **k):
    NOTICES.append(("info", title, msg))
    return None


def _cap_warn(title, msg="", *a, **k):
    NOTICES.append(("warn", title, msg))
    return None


_ps.messagebox.showinfo = _cap_info
_ps.messagebox.showwarning = _cap_warn


def make_app(client_mode):
    return SimpleNamespace(
        league=None, current_date=date(2027, 6, 4),
        FONT_FAMILY="Arial", BG_COLOR="#0B0F14", CONTENT_BG="#0A1428",
        _mp_client_mode=lambda: client_mode,
        mp_client=object() if client_mode else None,
        mp_host=None)


def build_view(client_mode):
    NOTICES.clear()
    root = ctk.CTk()
    root.geometry("1200x800")
    _ps.register(root)
    view = PlayoffView(root, app=make_app(client_mode))
    view.pack(fill="both", expand=True)
    root.update_idletasks(); root.update()
    return root, view


# --- 1: client mode blocks all three mutations ---
root, view = build_view(True)
view._generate_bracket()
root.update()
view._simulate_current_round()
root.update()
view._simulate_all_playoffs()
root.update()
host_notices = [n for n in NOTICES if n[0] == "info" and n[1] == "Host only"]
check("client: 3 actions blocked with Host only notice",
      len(host_notices) == 3, f"{len(host_notices)} notices")
check("client: no bracket created",
      getattr(view, "playoff_bracket", None) is None)
for name, btn in (("Generate", view._btn_gen), ("Simulate Round", view._btn_round),
                  ("Simulate All", view._btn_all)):
    try:
        disabled = "disabled" in btn.state()
    except Exception:
        disabled = False
    check(f"client: '{name}' button disabled", disabled)
root.destroy()

# --- 2: host mode passes the guard ---
root, view = build_view(False)
view.app.mp_host = object()  # belt & braces: host attrs set
view._simulate_current_round()  # no bracket -> normal warning path
root.update()
host_only = [n for n in NOTICES if n[1] == "Host only"]
need_bracket = [n for n in NOTICES
                if n[0] == "warn" and "generate playoff bracket" in n[2].lower()]
check("host: no Host only notice", len(host_only) == 0)
check("host: falls through to normal warning",
      len(need_bracket) == 1, str([n[1] for n in NOTICES]))
for name, btn in (("Generate", view._btn_gen), ("Simulate Round", view._btn_round),
                  ("Simulate All", view._btn_all)):
    try:
        enabled = "disabled" not in btn.state()
    except Exception:
        enabled = True
    check(f"host: '{name}' button enabled", enabled)
root.destroy()

# --- 3: single-player (no MP attrs at all) passes the guard ---
NOTICES.clear()
root = ctk.CTk()
root.geometry("1200x800")
_ps.register(root)
plain_app = SimpleNamespace(
    league=None, current_date=date(2027, 6, 4),
    FONT_FAMILY="Arial", BG_COLOR="#0B0F14", CONTENT_BG="#0A1428")
view = PlayoffView(root, app=plain_app)
view.pack(fill="both", expand=True)
root.update_idletasks(); root.update()
check("single-player: _is_mp_client False", view._is_mp_client() is False)
view._simulate_all_playoffs()
root.update()
check("single-player: no Host only notice",
      not any(n[1] == "Host only" for n in NOTICES))
root.destroy()

_ps.messagebox.showinfo = _orig_info
_ps.messagebox.showwarning = _orig_warn

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
