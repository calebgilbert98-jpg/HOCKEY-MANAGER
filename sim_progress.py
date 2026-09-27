# sim_progress.py
# Shared progress dialog + fallback-save helper for long sim operations
# (playoff Sim All, round sims, ...). The dialog is modal and pumps the
# UI between sim steps so the app shows live progress instead of a freeze.

import os
import tkinter as tk
from popup_system import InGamePopup
from tkinter import ttk
from datetime import datetime


class SimProgressDialog:
    """Modal progress dialog for a long sim operation.

    Usage:
        dlg = SimProgressDialog(parent, title="Simulating Playoffs",
                                warning="...")
        try:
            for i, step in enumerate(steps):
                ... do work ...
                dlg.update((i + 1) / len(steps), f"Working on {step}...")
        finally:
            dlg.close()
    """

    def __init__(self, parent, title="Simulating...",
                 status="Starting...",
                 warning=("This can take a minute or two. The app may appear "
                          "frozen while it works -- this is normal.")):
        self._closed = False
        self.root = InGamePopup(parent)
        self.root.title(title)
        self.root.configure(bg="#0e0e11")
        self.root.resizable(False, False)
        try:
            self.root.transient(parent)
            self.root.grab_set()
        except Exception:
            pass
        w, h = 460, 210
        try:
            x = parent.winfo_x() + (parent.winfo_width() - w) // 2
            y = parent.winfo_y() + (parent.winfo_height() - h) // 2
            self.root.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            self.root.geometry(f"{w}x{h}")
        try:
            self.root.lift()
            self.root.attributes('-topmost', True)
        except Exception:
            pass

        tk.Label(self.root, text=title, bg="#0e0e11", fg="#00ceb8",
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 6))

        self.status_var = tk.StringVar(value=status)
        tk.Label(self.root, textvariable=self.status_var, bg="#0e0e11",
                 fg="#E8ECF1", font=("Segoe UI", 10),
                 wraplength=420, justify="center").pack(pady=(0, 10))

        self.bar = ttk.Progressbar(self.root, mode='determinate',
                                   length=400, maximum=100)
        self.bar.pack(pady=(0, 12))

        tk.Label(self.root, text=warning, bg="#0e0e11", fg="#8B93A5",
                 font=("Segoe UI", 9), wraplength=420,
                 justify="center").pack(pady=(0, 12))
        self.root.update_idletasks()

    def update(self, fraction, status=None):
        """Advance the bar (0.0-1.0) and pump the UI. Safe to call often."""
        if self._closed:
            return
        try:
            pct = max(0.0, min(1.0, float(fraction))) * 100.0
            self.bar['value'] = pct
            if status is not None:
                self.status_var.set(status)
            self.root.update_idletasks()
            # Also let the parent repaint behind the modal.
            self.root.update()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.root.grab_release()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def create_fallback_save(app, context: str):
    """Save a fallback snapshot before a heavy sim. Returns the filename
    or None. Never raises -- a failed fallback save must not block the sim.
    """
    try:
        mgr = getattr(app, 'save_manager', None)
        if mgr is None:
            return None
        fallback_dir = os.path.join(getattr(mgr, 'save_directory', 'saves'),
                                    'fallback')
        os.makedirs(fallback_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join('fallback', f'fallback_{context}_{stamp}.hm')
        ok = mgr.save_game(filename, compress=True)
        if ok:
            print(f"Fallback save created: {filename}")
            return filename
    except Exception as e:
        print(f"Fallback save failed (non-fatal): {e}")
    return None


def confirm_heavy_sim(parent, title, detail):
    """Yes/No gate with the unresponsiveness warning. Returns True to proceed."""
    from popup_system import messagebox
    return messagebox.askyesno(
        title,
        f"{detail}\n\n"
        "This can take a minute or two, during which the app may appear "
        "frozen -- this is normal. A fallback save will be created first "
        "so you can restore if anything goes wrong.\n\n"
        "Proceed?",
        parent=parent)
