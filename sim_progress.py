# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# sim_progress.py
# Shared progress dialog + fallback-save helper for long sim operations
# (playoff Sim All, round sims, ...). Two modes:
#   * synchronous: the dialog is modal and pumps the UI between sim steps
#     so the app shows live progress instead of a freeze;
#   * threaded (run_threaded): the sim runs in a worker thread while the
#     dialog stays fully responsive, with Cancel support.

import os
import queue
import threading
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
                          "frozen while it works -- this is normal."),
                 cancelable=False):
        self._closed = False
        self._cancel_event = threading.Event()
        self._cancelable = bool(cancelable)
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
        if self._cancelable:
            ttk.Button(self.root, text="Cancel",
                       command=self._on_cancel).pack(pady=(0, 12))
        self.root.update_idletasks()

    def _on_cancel(self):
        """User hit Cancel: the worker finishes the current game, then stops."""
        self._cancel_event.set()
        try:
            self.status_var.set("Cancelling... finishing the current game.")
        except Exception:
            pass

    @property
    def cancel_event(self):
        """threading.Event the worker checks between sim steps."""
        return self._cancel_event

    def was_cancelled(self):
        return self._cancel_event.is_set()

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


def run_threaded(parent, title, worker, on_done=None,
                status="Starting..."):
    """Run a heavy sim in a worker thread with a cancelable progress dialog.

    worker(cancel_event, progress) runs OFF the UI thread and must not touch
    widgets -- only sim objects. progress(fraction, status) is thread-safe
    (it queues to the UI thread). The worker should check
    cancel_event.is_set() between steps and return early when set.

    on_done(cancelled, error) runs ON the UI thread after the worker
    finishes, so it can safely refresh widgets. Returns the dialog.
    """
    dlg = SimProgressDialog(
        parent, title=title, status=status, cancelable=True,
        warning=("Running in the background -- the app stays responsive. "
                 "You can cancel anytime; the current game finishes first, "
                 "and the bracket keeps every game already played."))
    q = queue.Queue()

    def progress(fraction, status_text=None):
        try:
            q.put(("progress", float(fraction), status_text))
        except Exception:
            pass

    def _worker():
        try:
            worker(dlg.cancel_event, progress)
            q.put(("done", None, None))
        except Exception as e:  # noqa: BLE001 -- reported on UI thread
            q.put(("error", e, None))

    def _poll():
        if dlg._closed:
            return
        try:
            while True:
                kind, a, b = q.get_nowait()
                if kind == "progress":
                    dlg.update(a, b)
                elif kind in ("done", "error"):
                    err = a if kind == "error" else None
                    cancelled = dlg.was_cancelled()
                    dlg.close()
                    if on_done is not None:
                        try:
                            on_done(cancelled, err)
                        except Exception:
                            pass
                    return
        except queue.Empty:
            pass
        try:
            dlg.root.after(100, _poll)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
    try:
        dlg.root.after(100, _poll)
    except Exception:
        pass
    return dlg


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
