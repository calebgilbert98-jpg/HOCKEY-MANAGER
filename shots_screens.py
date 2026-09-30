"""Screenshots of representative full-screen views at a target resolution.

Mimics main.show_screen(): a slim navbar (‹ Dashboard + title) above the
embedded view, filling the window. Captures via mss, cropped to the root.
Usage: python3 shots_screens.py --res 1600x900 --out <dir>
"""
import argparse
import sys
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, ".")
import qa_screens as qs

import customtkinter as ctk
from ctk_theme import init_ctk_theme, heading, secondary_button, BG, CARD

SCREENS = [
    ("roster", "Roster", "windows", "RosterView", ()),
    ("inbox", "Inbox", "inbox_window", "InboxView", ()),
    ("stats", "Stats & Standings", "stats_standings_window",
     "StatsStandingsView", ()),
    ("morale", "Morale", "morale_window", "MoraleView", ()),
    ("finances", "Finances", "windows", "FinancesView", ()),
    ("calendar", "Calendar", "calendar_window", "CalendarView", ()),
    ("tactics", "Tactics", "tactics_window", "TacticsView", ()),
    ("draft", "Draft", "windows", "DraftView", ()),
]


def shot(widget, path):
    import mss
    from PIL import Image
    for _ in range(3):
        widget.update()
        time.sleep(0.6)
    with mss.MSS() as sct:
        raw = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    img.crop((x, y, x + w, y + h)).save(path)
    print("saved", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1600x900")
    ap.add_argument("--out", default="/tmp/shots")
    args = ap.parse_args()
    w, h = (int(v) for v in args.res.split("x"))

    import os
    os.makedirs(args.out, exist_ok=True)

    init_ctk_theme()
    root = tk.Tk()
    root.geometry(f"{w}x{h}+0+0")
    root.update()

    app = qs.build_app()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo", return_value=None), \
         patch("tkinter.messagebox.showerror", return_value=None), \
         patch("tkinter.messagebox.showwarning", return_value=None):
        import importlib
        for sid, title, mod_name, cls_name, extra in SCREENS:
            holder = ctk.CTkFrame(root, fg_color=BG)
            holder.place(x=0, y=0, relwidth=1, relheight=1)
            navbar = ctk.CTkFrame(holder, fg_color=CARD, corner_radius=0,
                                  height=44)
            navbar.pack(side="top", fill="x")
            secondary_button(navbar, text="\u2039 Dashboard",
                             width=130, height=30).pack(side="left",
                                                       padx=12, pady=7)
            heading(navbar, title, size=16).pack(side="left", padx=8)
            try:
                cls = getattr(importlib.import_module(mod_name), cls_name)
                view = cls(holder, app=app, *extra)
                view.pack(side="top", fill="both", expand=True)
                root.update()
                shot(root, f"{args.out}/screen_{sid}_{args.res}.png")
            except Exception as e:  # noqa: BLE001
                print(f"SHOT FAILED {sid}: {type(e).__name__}: {e}")
            finally:
                holder.destroy()
                root.update()

    root.destroy()


main()
